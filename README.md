# eml2msg

[![CI](https://github.com/Andre-Atkinson/eml_converter/actions/workflows/ci.yml/badge.svg)](https://github.com/Andre-Atkinson/eml_converter/actions/workflows/ci.yml)

Converts Outlook-for-Mac `.eml` files into Windows Outlook `.msg` files, so
colleagues on Windows can open them natively.

## Why this exists

Outlook for Mac saves messages as `.eml` (plain MIME text). Windows Outlook
expects `.msg`, which is a completely different thing: a binary OLE2 compound
file holding MAPI properties. Converting means re-encoding every header, body
and attachment as MAPI properties inside that container.

> **Worth knowing:** Outlook for Mac cannot *open* `.msg` files. This tool is for
> producing files other people can open on Windows — not for reading them here.

## Usage

### Finder (installed)

Select one or more `.eml` files in Finder, right-click → **Quick Actions → Convert to MSG**.
The `.msg` lands next to the original and a notification reports the result.

If it isn't in the menu, enable it under
System Settings → General → Login Items & Extensions → Services → Files & Folders.

### Command line

Build once with `make build`, then:

```bash
./bin/eml2msg mail.eml
```

| Option | Meaning |
| --- | --- |
| `-o, --outdir DIR` | write `.msg` files to `DIR` (default: beside the `.eml`) |
| `-f, --from ADDR` | sender to use when the `.eml` has no `From:` header |
| `--no-rtf` | skip the RTF body (RTF is added by default) |
| `--overwrite` | replace an existing `.msg` instead of appending `" (1)"` |
| `-h, --help` | show help |

Folders are accepted and expanded to their `.eml` children:

```bash
./bin/eml2msg -o ~/Desktop/converted ~/Desktop/exported-mail
```

`$EML2MSG_FROM` works as a default for `--from`.

## The missing-sender gotcha

Outlook for Mac omits the `From:` header on messages **you** sent. Converted
straight across, those arrive in Windows Outlook with a **blank sender**
(`PR_SENDER_NAME` and `PR_SENDER_EMAIL_ADDRESS` are written as zero-length).

`eml2msg` detects this and either warns, or fills in `--from` if you supply one.
The Quick Action sets it automatically — edit `FROM` at the top of the script if
your address changes:

```
~/Library/Services/Convert to MSG.workflow/Contents/document.wflow
```

## What survives conversion

Verified against real output by parsing the generated container independently
(see *Verifying* below):

- Subject, plain-text body, HTML body
- **RTF body** (`PR_RTF_COMPRESSED`) — see below
- To / Cc / Bcc recipients, as MAPI recipient storages
- Attachments, byte-for-byte, with long filenames
- `Message-ID`, and the full original headers in `PR_TRANSPORT_MESSAGE_HEADERS`
- Non-ASCII text — everything is written as `PT_UNICODE`, so no mojibake

Not currently handled: S/MIME signed and encrypted mail.

## RTF

Windows Outlook composes mail with an RTF body in `PR_RTF_COMPRESSED` alongside
the HTML, and some document-management systems require it. Outlook-for-Mac `.eml`
files never contain RTF, so `eml2msg` synthesises one.

It uses **encapsulated HTML** (`\fromhtml1`, per [MS-OXRTFEX]) — the same form
Outlook itself uses for HTML mail. The original HTML is carried verbatim inside
`\*\htmltag` destinations, so nothing is re-rendered, reflowed or lost: a reader
recovers the exact HTML back out. MsgKit then compresses it with LZFu.

Behaviour:

- On by default; `--no-rtf` disables it.
- A message that already contains a genuine `text/rtf` part keeps it untouched.
- **Plain-text-only mail gets no RTF** — `\fromhtml1` would be a lie, and Outlook
  renders plain bodies correctly without it.

Escaping follows the RTF rules: `{`, `}` and `\` are backslash-escaped, tabs
become `\tab`, newlines become `\par`, Latin-1 characters become `\'XX`, and
anything higher becomes `\uN?`. Note `\uN` is a **signed 16-bit** value, so
characters above U+7FFF — which includes every surrogate, and therefore all
emoji and other astral characters — are written as their negative equivalent.
Getting that wrong garbles them in Outlook.

## Setting up on a Mac

The only prerequisite is the .NET SDK. Everything else (MsgKit and its
dependencies) is restored per-project into `~/.nuget`, pinned in
`src/Eml2Msg/packages.lock.json`; nothing is installed system-wide.

```bash
brew install dotnet
```

Then clone and install the Quick Action. `make install` builds the binary —
picking `osx-arm64` or `osx-x64` from your CPU automatically — and installs the
Finder action:

```bash
git clone https://github.com/Andre-Atkinson/eml_converter.git
cd eml_converter
make install FROM="Your Name <you@example.com>"
```

| Target | Does |
| --- | --- |
| `make build` | build the self-contained binary into `bin/` |
| `make install FROM=…` | build, then install the Quick Action |
| `make uninstall` | remove the Quick Action |
| `make lock` | regenerate `packages.lock.json` after a dependency change |
| `make clean` | remove build output |

Notes:

- The RID is chosen from your CPU; override it with `make install RID=osx-x64`
  if you need to cross-target.
- Builds run with `RestoreLockedMode`, so a dependency that doesn't match the
  committed lock file fails the build instead of resolving silently. The .NET
  SDK is pinned in `global.json` (its ILLink tooling is captured in the lock);
  after intentionally bumping a package or the SDK, run `make lock` and commit
  the diff.
- The build is **self-contained** (~79 MB) on purpose. Automator runs Quick
  Actions with a near-empty environment and will not find a Homebrew .NET, so a
  framework-dependent binary fails there with "You must install .NET".
- `bin/` is gitignored — the binary is always built locally, never committed.
- The Quick Action stores the binary's absolute path, so rebuilding in place is
  picked up automatically. Move the repo and re-run `make install`.
- `FROM` is baked into the installed Quick Action. Re-run `make install` to
  change it, or edit `COMMAND_STRING` in
  `~/Library/Services/Convert to MSG.workflow/Contents/document.wflow`.

To remove it:

```bash
make uninstall
```

## Verifying

Conversion succeeding is not proof the file is valid. `tools/inspect_msg.py`
parses the OLE2 container by hand — no MsgKit, no `olefile` — and lists the MAPI
properties actually present, so the check doesn't rely on the library that wrote
the file:

```bash
python3 tools/inspect_msg.py somefile.msg
```

It also **decompresses `PR_RTF_COMPRESSED`** (LZFu, per [MS-OXRTFCP]) and checks
the result is well-formed, rather than just counting its bytes. Add `--rtf` to
print the decompressed RTF and confirm the HTML round-trips out intact:

```bash
python3 tools/inspect_msg.py somefile.msg --rtf
```

## Testing

The tests synthesise `.eml` fixtures, convert them, and verify the resulting
`.msg` with `tools/inspect_msg.py` as an independent oracle — the container is
parsed by hand, never by the MsgKit library that wrote it, so a bug in MsgKit
cannot hide behind itself. They cover the fiddly paths: encapsulated-HTML RTF,
the signed-`\uN` escaping of astral characters (emoji), byte-for-byte
attachments, the missing-`From:` blank sender, Unicode subjects, and recipients.

Fixtures are built at runtime with Python's `email` package, so no sample mail
is ever committed. The suite runs against `bin/eml2msg` when it is built, and
otherwise builds a framework-dependent binary on the fly. Run it in a virtual
environment:

```bash
make build
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

Point `EML2MSG_BIN` at a specific binary to test that one instead.

## Notes on handling mail

`.eml` and `.msg` are both gitignored, deliberately. Real messages carry other
people's addresses, internal Exchange server names and attachment payloads, and
none of that belongs in a repository — including a private one.

The Quick Action passes converter output to `osascript` as an **argument**, never
spliced into the AppleScript source. Output contains filenames, filenames may
legally contain quotes and backslashes, and interpolating those into script
source lets them escape the string literal and be parsed as code.

## How it works

```
.eml ──[MimeKit parse]──> MimeMessage ──[MsgKit: MAPI mapping]──> .msg (OLE2/CFBF)
```

[MsgKit](https://github.com/Sicos1977/MsgKit) (MIT) does the MAPI and compound-file
work; MimeKit parses the MIME. Note that Python has no usable `.msg` *writer* —
`extract-msg`, `olefile` and friends are all read-only — which is why this is .NET.
