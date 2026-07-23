"""Dependency-free CFBF/OLE2 inspector - independently verifies a .msg file.

Parses the compound-file container by hand (no olefile, no MsgKit) so the
verification does not rely on the same library that wrote the file. Reads stream
contents, and decompresses PR_RTF_COMPRESSED per [MS-OXRTFCP] so the RTF body
can be checked rather than merely counted.

Usage:  python3 inspect_msg.py <file.msg> [--rtf]
"""
import struct
import sys

SIG = bytes.fromhex("D0CF11E0A1B11AE1")
ENDOFCHAIN = 0xFFFFFFFE

# MAPI property tags relevant to EML->MSG fidelity.
TAGS = {
    "0037": "PR_SUBJECT",
    "0C1A": "PR_SENDER_NAME",
    "0C1F": "PR_SENDER_EMAIL_ADDRESS",
    "5D01": "PR_SENDER_SMTP_ADDRESS",
    "0E1D": "PR_NORMALIZED_SUBJECT",
    "1000": "PR_BODY",
    "1013": "PR_HTML",
    "1009": "PR_RTF_COMPRESSED",
    "1035": "PR_INTERNET_MESSAGE_ID",
    "001A": "PR_MESSAGE_CLASS",
    "0E04": "PR_DISPLAY_TO",
    "0E03": "PR_DISPLAY_CC",
    "0E02": "PR_DISPLAY_BCC",
    "0039": "PR_CLIENT_SUBMIT_TIME",
    "0E06": "PR_MESSAGE_DELIVERY_TIME",
    "3007": "PR_CREATION_TIME",
    "007D": "PR_TRANSPORT_MESSAGE_HEADERS",
    "3001": "PR_DISPLAY_NAME",
    "3003": "PR_EMAIL_ADDRESS",
    "39FE": "PR_SMTP_ADDRESS",
    "3701": "PR_ATTACH_DATA_BIN",
    "3704": "PR_ATTACH_FILENAME",
    "3707": "PR_ATTACH_LONG_FILENAME",
}

TYPES = {
    "001E": "PT_STRING8", "001F": "PT_UNICODE", "0102": "PT_BINARY",
    "0040": "PT_SYSTIME", "0003": "PT_LONG", "000B": "PT_BOOLEAN",
}

# The fixed 207-byte dictionary every LZFu stream starts from ([MS-OXRTFCP]).
# Byte-exact: back-references point into this preamble, so a single wrong
# character here decodes the start of every RTF body into garbage.
LZFU_INIT = (
    b"{\\rtf1\\ansi\\mac\\deff0\\deftab720{\\fonttbl;}"
    b"{\\f0\\fnil \\froman \\fswiss \\fmodern \\fscript \\fdecor MS Sans Serif"
    b"SymbolArialTimes New RomanCourier{\\colortbl\\red0\\green0\\blue0\r\n"
    b"\\par \\pard\\plain\\f0\\fs20\\b\\i\\u\\tab\\tx"
)
assert len(LZFU_INIT) == 207, f"init dictionary must be 207 bytes, got {len(LZFU_INIT)}"


class Cfbf:
    """Minimal compound-file reader: directory walk plus stream extraction."""

    def __init__(self, data):
        if data[:8] != SIG:
            raise ValueError("not a compound file - wrong magic bytes")
        self.data = data
        h = data[:512]
        self.sector_size = 1 << struct.unpack_from("<H", h, 0x1E)[0]
        self.mini_size = 1 << struct.unpack_from("<H", h, 0x20)[0]
        self.mini_cutoff = struct.unpack_from("<I", h, 0x38)[0]
        self.fat = self._read_fat(h)
        self.minifat = self._read_minifat(h)
        self.entries = self._read_directory(struct.unpack_from("<I", h, 0x30)[0])
        # The root entry owns the mini stream that all small streams live inside.
        root = next(e for e in self.entries if e["type"] == 5)
        self.mini_stream = self._read_chain(root["start"], root["size"])

    def _sector(self, n):
        off = (n + 1) * self.sector_size
        return self.data[off:off + self.sector_size]

    def _read_fat(self, h):
        n_fat = struct.unpack_from("<I", h, 0x2C)[0]
        difat = list(struct.unpack_from("<109I", h, 0x4C))
        nxt = struct.unpack_from("<I", h, 0x44)[0]
        for _ in range(struct.unpack_from("<I", h, 0x48)[0]):
            if nxt >= 0xFFFFFFFA:
                break
            vals = struct.unpack_from(f"<{self.sector_size // 4}I", self._sector(nxt))
            difat.extend(vals[:-1])
            nxt = vals[-1]

        fat = []
        for s in difat[:n_fat]:
            if s < 0xFFFFFFFA:
                fat.extend(struct.unpack_from(f"<{self.sector_size // 4}I", self._sector(s)))
        return fat

    def _read_minifat(self, h):
        start = struct.unpack_from("<I", h, 0x3C)[0]
        mini = []
        for s in self._chain(self.fat, start):
            mini.extend(struct.unpack_from(f"<{self.sector_size // 4}I", self._sector(s)))
        return mini

    @staticmethod
    def _chain(fat, start):
        out, cur, guard = [], start, 0
        while cur < 0xFFFFFFFA and guard < 200000:
            out.append(cur)
            cur = fat[cur] if cur < len(fat) else ENDOFCHAIN
            guard += 1
        return out

    def _read_directory(self, first):
        entries = []
        for s in self._chain(self.fat, first):
            sec = self._sector(s)
            for i in range(self.sector_size // 128):
                e = sec[i * 128:(i + 1) * 128]
                if len(e) < 128:
                    continue
                nlen = struct.unpack_from("<H", e, 64)[0]
                if nlen == 0:
                    continue
                entries.append({
                    "name": e[:max(0, nlen - 2)].decode("utf-16-le", "replace"),
                    "type": e[66],
                    "start": struct.unpack_from("<I", e, 116)[0],
                    "size": struct.unpack_from("<Q", e, 120)[0],
                })
        return entries

    def _read_chain(self, start, size):
        out = bytearray()
        for s in self._chain(self.fat, start):
            out += self._sector(s)
        return bytes(out[:size])

    def read(self, entry):
        """Return a stream's bytes, from the mini stream when it is small."""
        if entry["size"] < self.mini_cutoff and entry["type"] == 2:
            out = bytearray()
            for s in self._chain(self.minifat, entry["start"]):
                off = s * self.mini_size
                out += self.mini_stream[off:off + self.mini_size]
            return bytes(out[:entry["size"]])
        return self._read_chain(entry["start"], entry["size"])


def lzfu_decompress(blob):
    """Decompress a PR_RTF_COMPRESSED payload. Returns (rtf_bytes, note)."""
    if len(blob) < 16:
        return b"", "too short to hold a header"

    comp_size, raw_size, comp_type, _crc = struct.unpack_from("<IIII", blob, 0)

    if comp_type == 0x414C454D:                      # "MELA" - stored uncompressed
        return blob[16:16 + raw_size], "uncompressed (MELA)"
    if comp_type != 0x75465A4C:                      # "LZFu"
        return b"", f"unknown compression type 0x{comp_type:08X}"

    dictionary = bytearray(4096)
    dictionary[:len(LZFU_INIT)] = LZFU_INIT
    write = len(LZFU_INIT)

    out = bytearray()
    pos = 16
    end = min(len(blob), comp_size + 4)

    while pos < end and len(out) < raw_size:
        control = blob[pos]
        pos += 1
        for bit in range(8):
            if pos >= end or len(out) >= raw_size:
                break
            if not (control >> bit) & 1:
                # Literal byte.
                b = blob[pos]
                pos += 1
                out.append(b)
                dictionary[write % 4096] = b
                write += 1
            else:
                if pos + 1 >= end:
                    break
                ref = (blob[pos] << 8) | blob[pos + 1]
                pos += 2
                offset = ref >> 4
                length = (ref & 0x0F) + 2
                if offset == write % 4096:
                    return bytes(out), "ok"
                for _ in range(length):
                    b = dictionary[offset % 4096]
                    offset += 1
                    out.append(b)
                    dictionary[write % 4096] = b
                    write += 1

    return bytes(out), "ok"


def main(argv):
    path = argv[1]
    show_rtf = "--rtf" in argv
    data = open(path, "rb").read()

    print(f"file      : {path}")
    print(f"size      : {len(data):,} bytes")

    try:
        cf = Cfbf(data)
    except ValueError as exc:
        print(f"!! {exc}")
        return 1

    print("magic     : OK (valid OLE2/CFBF container)")
    print(f"sector    : {cf.sector_size} bytes")

    streams = [e for e in cf.entries if e["type"] == 2]
    storages = [e for e in cf.entries if e["type"] == 1]
    print(f"entries   : {len(cf.entries)} ({len(storages)} storages, {len(streams)} streams)")
    print()
    print(f"recipients: {len([s for s in storages if s['name'].startswith('__recip')])}")
    print(f"attachments: {len([s for s in storages if s['name'].startswith('__attach')])}")
    print()

    print("--- top-level MAPI properties found ---")
    found = []
    for e in sorted(streams, key=lambda x: x["name"]):
        if not e["name"].startswith("__substg1.0_"):
            continue
        code = e["name"][len("__substg1.0_"):]
        label = TAGS.get(code[:4])
        if label:
            found.append((label, TYPES.get(code[4:8], code[4:8]), e["size"]))

    for label, typ, size in sorted(set(found)):
        print(f"  {label:<28} {typ:<11} {size:>8,} bytes")

    have = {f[0] for f in found}
    print()
    print("--- fidelity check ---")
    for req in ("PR_SUBJECT", "PR_BODY", "PR_HTML", "PR_RTF_COMPRESSED",
                "PR_DISPLAY_TO", "PR_INTERNET_MESSAGE_ID", "PR_MESSAGE_CLASS"):
        print(f"  {'OK ' if req in have else '-- '} {req}")

    # Prove the RTF is real by decompressing it, not merely counting its bytes.
    rtf_entry = next((e for e in streams if e["name"].startswith("__substg1.0_1009")), None)
    if rtf_entry:
        blob = cf.read(rtf_entry)
        comp_size, raw_size, comp_type, _ = struct.unpack_from("<IIII", blob, 0)
        rtf, note = lzfu_decompress(blob)
        print()
        print("--- PR_RTF_COMPRESSED ---")
        tag = struct.pack("<I", comp_type).decode("ascii", "replace")
        print(f"  stored      : {len(blob):,} bytes  (header says {comp_size + 4:,})")
        print(f"  type        : {tag!r}")
        print(f"  decompressed: {len(rtf):,} bytes  (header says {raw_size:,})  [{note}]")
        if rtf:
            checks = [
                ("size matches header", len(rtf) == raw_size),
                (r"starts with {\rtf1", rtf.lstrip()[:6] == b"{\\rtf1"),
                (r"declares \fromhtml1", b"\\fromhtml1" in rtf),
                ("braces balanced",
                 rtf.count(b"{") - rtf.count(b"\\{") == rtf.count(b"}") - rtf.count(b"\\}")),
            ]
            for label, ok in checks:
                print(f"  {'OK ' if ok else '!! '}{label}")
            if show_rtf:
                print("\n--- decompressed RTF ---")
                print(rtf.decode("latin-1"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
