"""Read MAPI properties out of a .msg using inspect_msg as an independent oracle.

The compound file is parsed by hand (via tools/inspect_msg.py), never by the
MsgKit library that wrote it, so a bug in MsgKit cannot hide behind itself when
the tests check the output. This module wraps that parser in an assertion-
friendly view:

    view = read_properties("some.msg")
    text(view, "PR_SUBJECT")            -> decoded unicode value (or None)
    raw(view, "PR_ATTACH_DATA_BIN")     -> raw bytes (or None)
    all_text(view, "PR_EMAIL_ADDRESS")  -> every value for a repeated tag
    has(view, "PR_RTF_COMPRESSED")      -> bool
    decompress_rtf(view)                -> decompressed RTF bytes (or None)
    view["recipients"] / view["attachments"]  -> storage entry lists
"""
import pathlib
import sys

_TOOLS = pathlib.Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
import inspect_msg as im  # noqa: E402

# label -> 4-char tag hex, inverted from inspect_msg's own tag table so the
# oracle and the CLI inspector always agree on what a tag means.
_LABEL_TO_TAG = {label: code for code, label in im.TAGS.items()}


def read_properties(path):
    """Parse a .msg into a flat view of its __substg1.0_ property streams plus
    recipient/attachment storages. Raises ValueError on a non-compound file.

    The reader is intentionally flat: nested recipient and attachment property
    streams land in the same `props` map as top-level ones (keyed by tag), which
    is why repeated tags like PR_EMAIL_ADDRESS are read with all_text()."""
    data = pathlib.Path(path).read_bytes()
    cf = im.Cfbf(data)

    props = {}
    for e in cf.entries:
        if e["type"] != 2 or not e["name"].startswith("__substg1.0_"):
            continue
        code = e["name"][len("__substg1.0_"):]
        tag, typ = code[:4].upper(), code[4:8].upper()
        raw_bytes = cf.read(e)
        props.setdefault(tag, []).append({
            "tag": tag, "type": typ, "size": e["size"],
            "raw": raw_bytes, "text": _decode(typ, raw_bytes),
        })

    storages = [e for e in cf.entries if e["type"] == 1]
    return {
        "cf": cf,
        "props": props,
        "recipients": [s for s in storages if s["name"].startswith("__recip")],
        "attachments": [s for s in storages if s["name"].startswith("__attach")],
    }


def _decode(typ, raw_bytes):
    if typ == "001F":            # PT_UNICODE
        return raw_bytes.decode("utf-16-le", "replace")
    if typ == "001E":            # PT_STRING8
        return raw_bytes.decode("latin-1", "replace")
    return None                  # binary / numeric - callers use raw


def _entries(view, label):
    return view["props"].get(_LABEL_TO_TAG[label], [])


def prop(view, label):
    """First property entry for a named tag, or None."""
    entries = _entries(view, label)
    return entries[0] if entries else None


def text(view, label):
    entry = prop(view, label)
    return entry["text"] if entry else None


def raw(view, label):
    entry = prop(view, label)
    return entry["raw"] if entry else None


def all_text(view, label):
    return [e["text"] for e in _entries(view, label)]


def has(view, label):
    return bool(_entries(view, label))


def decompress_rtf(view):
    """Decompressed PR_RTF_COMPRESSED bytes, or None if the property is absent."""
    entry = prop(view, "PR_RTF_COMPRESSED")
    if not entry:
        return None
    out, _note = im.lzfu_decompress(entry["raw"])
    return out
