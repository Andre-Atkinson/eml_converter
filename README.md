# eml2msg

[![CI](https://github.com/Andre-Atkinson/eml_converter/actions/workflows/ci.yml/badge.svg)](https://github.com/Andre-Atkinson/eml_converter/actions/workflows/ci.yml)

Convert Outlook-for-Mac `.eml` files into Windows Outlook `.msg` files, so
colleagues on Windows can open them natively — from the command line or a Finder
right-click.

> **Disclaimer — please read.** This project was written with substantial help
> from AI (Anthropic's Claude). It has an automated test suite and verifies its
> output against an independent parser, but it is a personal utility provided
> **as is, without warranty. Use at your own risk** — keep your original `.eml`
> files and spot-check important conversions.

Outlook for Mac saves messages as `.eml` (plain MIME text); Windows Outlook
expects `.msg`, a binary OLE2 compound file full of MAPI properties. `eml2msg`
re-encodes every header, body, and attachment into that format.

> **Note:** Outlook for Mac cannot *open* `.msg` files. This tool produces files
> for other people to open on Windows; it is not a `.msg` reader.

## What it converts

- Subject, plain-text and HTML bodies
- A synthesised **RTF body** (`PR_RTF_COMPRESSED`) matching how Outlook stores
  HTML mail — see [RTF bodies](#rtf-bodies)
- To / Cc / Bcc recipients, as MAPI recipient storages
- Attachments, byte-for-byte, including long Unicode filenames
- `Message-ID` and the full original headers (`PR_TRANSPORT_MESSAGE_HEADERS`)
- Non-ASCII text throughout, written as `PT_UNICODE` (no mojibake)
- Whole folders in one go

Not handled: S/MIME signed or encrypted mail.

## Installation

### Homebrew (recommended)

```bash
brew install andre-atkinson/tap/eml2msg
```

This builds the self-contained binary from source (the .NET SDK is pulled in
only as a build dependency) and puts `eml2msg` on your `PATH`.

To add the optional Finder **Convert to MSG** Quick Action — Homebrew can't
create the per-user action itself, so this is one extra command:

```bash
eml2msg-quickaction --from "Your Name <you@example.com>"
```

### From source

Requires the .NET SDK (`brew install dotnet`); everything else restores locally
into `~/.nuget`, and nothing is installed system-wide.

```bash
git clone https://github.com/Andre-Atkinson/eml_converter.git
cd eml_converter
make install FROM="Your Name <you@example.com>"
```

`make install` builds the binary into `bin/` (choosing `osx-arm64`/`osx-x64`
from your CPU) and installs the Quick Action. Other `make` targets are listed
under [Development](#development).

## Usage

### Finder Quick Action

Select one or more `.eml` files, right-click → **Quick Actions → Convert to
MSG**. Each `.msg` is written next to its original and a notification reports the
result.

If it doesn't appear in the menu, enable it under System Settings → General →
Login Items & Extensions → Services → Files & Folders.

### Command line

```bash
eml2msg mail.eml                          # writes mail.msg alongside the original
eml2msg -o ~/Desktop/out ~/Desktop/mail   # convert every .eml in a folder
```

(A source build produces the binary at `./bin/eml2msg`.)

| Option | Meaning |
| --- | --- |
| `-o, --outdir DIR` | write `.msg` files to `DIR` (default: beside the `.eml`) |
| `-f, --from ADDR` | sender to use when the `.eml` has no `From:` header |
| `--no-rtf` | skip the synthesised RTF body |
| `--overwrite` | replace an existing `.msg` instead of appending `" (1)"` |
| `-h, --help` | show help |

Folders are expanded to their `.eml` children. `$EML2MSG_FROM` provides a default
for `--from`.

#### Messages you sent yourself

Outlook for Mac omits the `From:` header on messages **you** sent, which would
otherwise arrive in Windows Outlook with a blank sender. `eml2msg` warns when it
sees this and fills the sender in from `--from` if you provide one; the Quick
Action passes it automatically. Re-run the installer to change the address.

## How it works

```
.eml ──[MimeKit parse]──> MimeMessage ──[MsgKit: MAPI mapping]──> .msg (OLE2/CFBF)
```

[MimeKit](https://www.mimekit.net/) parses the MIME and
[MsgKit](https://github.com/Sicos1977/MsgKit) writes the MAPI properties and
compound file. (.NET is used because Python has no usable `.msg` *writer* —
`extract-msg`, `olefile` and friends are all read-only.)

### RTF bodies

Windows Outlook stores an RTF body in `PR_RTF_COMPRESSED` alongside the HTML, and
some document-management systems require it — but Outlook-for-Mac `.eml` never
contains one. `eml2msg` synthesises it as **encapsulated HTML** (`\fromhtml1`,
per [MS-OXRTFEX]), the same form Outlook uses: the original HTML is carried
verbatim inside `\*\htmltag` destinations, so nothing is re-rendered or lost,
then compressed with LZFu.

- On by default; `--no-rtf` disables it.
- A message that already carries a real `text/rtf` part is left untouched.
- Plain-text-only mail gets no RTF — Outlook renders it correctly without one.

The subtle part is astral characters (emoji and the like): RTF's `\uN` takes a
**signed** 16-bit value, so anything above U+7FFF is written as its negative
equivalent. Getting that wrong garbles emoji in Outlook, so it's covered by the
tests.

## Development

Prerequisite: the .NET SDK. Third-party dependencies restore into `~/.nuget`,
pinned in `src/Eml2Msg/packages.lock.json`.

| `make` target | Does |
| --- | --- |
| `make build` | build the self-contained binary into `bin/` |
| `make install FROM=…` | build, then install the Quick Action |
| `make uninstall` | remove the Quick Action |
| `make verify` | restore in locked mode; fails if the dependency graph drifts |
| `make lock` | regenerate `packages.lock.json` after changing a dependency |
| `make clean` | remove build output |

The build is self-contained (~80 MB) on purpose: Automator runs Quick Actions in
a near-empty environment that can't find a Homebrew .NET.

### Tests

The suite synthesises `.eml` fixtures at runtime (no sample mail is committed),
converts them, and verifies the resulting `.msg` with `tools/inspect_msg.py` — an
independent parser that walks the OLE2 container by hand, so a bug in MsgKit
can't vouch for itself. It covers the fiddly paths: encapsulated-HTML RTF,
signed-`\uN` emoji escaping, byte-for-byte attachments, the missing-sender case,
Unicode subjects, and recipients.

```bash
make build
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

Set `EML2MSG_BIN` to test a specific binary. CI runs the suite on every push
(macOS), together with `make verify` and a dependency vulnerability audit.

### Inspecting output

```bash
python3 tools/inspect_msg.py somefile.msg          # list the MAPI properties present
python3 tools/inspect_msg.py somefile.msg --rtf    # also decompress and print the RTF
```

## Security

`eml2msg` runs entirely locally — no network, no credentials — and parses
untrusted `.eml` input with the well-tested MimeKit library. Dependencies are
pinned and hash-verified (`make verify`) and audited for known vulnerabilities in
CI. To report a vulnerability, see [SECURITY.md](SECURITY.md).

`.eml` and `.msg` files are gitignored: real messages carry other people's
addresses and attachment payloads that don't belong in a repository.

## License

Released under the [MIT License](LICENSE). The self-contained binary bundles
third-party components under their own licenses (MIT and MPL-2.0) — see
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
