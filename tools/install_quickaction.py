"""Installs the 'Convert to MSG' Finder Quick Action.

Builds a macOS Services bundle in ~/Library/Services that hands the selected
.eml files to the eml2msg binary in this repo.

Usage:
    python3 tools/install_quickaction.py --from "Your Name <you@example.com>"
    python3 tools/install_quickaction.py --uninstall
"""
import argparse
import pathlib
import plistlib
import shutil
import subprocess
import sys
import uuid

REPO = pathlib.Path(__file__).resolve().parent.parent
BINARY = REPO / "bin" / "eml2msg"
SERVICES = pathlib.Path.home() / "Library" / "Services"
BUNDLE = SERVICES / "Convert to MSG.workflow"

SCRIPT_TEMPLATE = r'''# Convert selected .eml files to .msg, alongside the originals.
# FROM is used only when an .eml has no From: header - Outlook for Mac omits it
# on messages you sent yourself, which would otherwise land in Windows Outlook
# with a blank sender.
BIN="{binary}"
FROM="{sender}"

if [ ! -x "$BIN" ]; then
  osascript -e 'display alert "Convert to MSG" message "Converter not found. Build it first - see the README."'
  exit 1
fi

# Only pass through files that are actually .eml
FILES=()
for f in "$@"; do
  case "${{f:l}}" in
    *.eml) FILES+=("$f") ;;
  esac
done

if [ ${{#FILES[@]}} -eq 0 ]; then
  osascript -e 'display alert "Convert to MSG" message "No .eml files were selected."'
  exit 0
fi

if [ -n "$FROM" ]; then
  OUTPUT=$("$BIN" --from "$FROM" "${{FILES[@]}}" 2>&1)
else
  OUTPUT=$("$BIN" "${{FILES[@]}}" 2>&1)
fi
STATUS=$?
SUMMARY=$(echo "$OUTPUT" | tail -1)

if [ $STATUS -eq 0 ]; then
  osascript -e "display notification \"$SUMMARY\" with title \"Convert to MSG\""
else
  DETAIL=$(echo "$OUTPUT" | sed 's/"/\\"/g' | tail -20)
  osascript -e "display alert \"Convert to MSG - problem\" message \"$DETAIL\""
fi
'''


def build_document(script):
    action = {
        "action": {
            "AMAccepts": {
                "Container": "List",
                "Optional": False,
                "Types": ["com.apple.cocoa.string"],
            },
            "AMActionVersion": "2.0.3",
            "AMApplication": ["Automator"],
            "AMParameterProperties": {
                "COMMAND_STRING": {},
                "CheckedForUserDefaultShell": {},
                "inputMethod": {},
                "shell": {},
                "source": {},
            },
            "AMProvides": {"Container": "List", "Types": ["com.apple.cocoa.string"]},
            "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
            "ActionName": "Run Shell Script",
            "ActionParameters": {
                "COMMAND_STRING": script,
                "CheckedForUserDefaultShell": True,
                "inputMethod": 1,          # pass input as arguments, not stdin
                "shell": "/bin/zsh",
                "source": "",
            },
            "BundleIdentifier": "com.apple.RunShellScript",
            "CFBundleVersion": "2.0.3",
            "CanShowSelectedItemsWhenRun": False,
            "CanShowWhenRun": True,
            "Category": ["AMCategoryUtilities"],
            "Class Name": "RunShellScriptAction",
            "InputUUID": str(uuid.uuid4()).upper(),
            "Keywords": ["Shell", "Script", "Command", "Run", "Unix"],
            "OutputUUID": str(uuid.uuid4()).upper(),
            "UUID": str(uuid.uuid4()).upper(),
            "UnlocalizedApplications": ["Automator"],
            "arguments": {},
            "isViewVisible": 1,
            "location": "309.000000:253.000000",
            "nibPath": "/System/Library/Automator/Run Shell Script.action"
                       "/Contents/Resources/Base.lproj/main.nib",
        },
        "isViewVisible": 1,
    }

    return {
        "AMApplicationBuild": "528",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [action],
        "connectors": {},
        "workflowMetaData": {
            "applicationBundleIDsByPath": {},
            "applicationPaths": [],
            "inputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "outputTypeIdentifier": "com.apple.Automator.nothing",
            "presentationMode": 11,
            "processesInput": 0,
            "serviceApplicationBundleID": "com.apple.finder",
            "serviceApplicationPath": "/System/Library/CoreServices/Finder.app",
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "systemImageName": "NSActionTemplate",
            "useAutomaticInputType": 0,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }


INFO = {
    "NSServices": [
        {
            "NSMenuItem": {"default": "Convert to MSG"},
            "NSMessage": "runWorkflowAsService",
            "NSRequiredContext": {"NSApplicationIdentifier": "com.apple.finder"},
            "NSSendFileTypes": ["com.apple.mail.email", "public.data"],
        }
    ],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from", dest="sender", default="",
        help='sender for .eml files with no From: header, e.g. "You <you@example.com>"')
    parser.add_argument("--uninstall", action="store_true", help="remove the Quick Action")
    args = parser.parse_args()

    if args.uninstall:
        if BUNDLE.exists():
            shutil.rmtree(BUNDLE)
            print(f"removed: {BUNDLE}")
        else:
            print("nothing to remove")
        subprocess.run(["/System/Library/CoreServices/pbs", "-flush"], check=False)
        return 0

    if not BINARY.exists():
        print(f"error: {BINARY} not found - build it first:", file=sys.stderr)
        print("  dotnet publish src/Eml2Msg -c Release -o bin -r osx-arm64 "
              "--self-contained true -p:PublishSingleFile=true "
              "-p:IncludeNativeLibrariesForSelfExtract=true", file=sys.stderr)
        return 1

    script = SCRIPT_TEMPLATE.format(binary=BINARY, sender=args.sender)

    if BUNDLE.exists():
        shutil.rmtree(BUNDLE)
    contents = BUNDLE / "Contents"
    contents.mkdir(parents=True)

    with open(contents / "document.wflow", "wb") as f:
        plistlib.dump(build_document(script), f)
    with open(contents / "Info.plist", "wb") as f:
        plistlib.dump(INFO, f)

    # Services are registered by the pasteboard server, not Launch Services.
    subprocess.run(["/System/Library/CoreServices/pbs", "-flush"], check=False)

    print(f"installed: {BUNDLE}")
    print(f"binary   : {BINARY}")
    print(f"sender   : {args.sender or '(none - will warn on .eml with no From:)'}")
    print()
    print("Right-click an .eml in Finder -> Quick Actions -> Convert to MSG")
    print("If it is missing, enable it under System Settings -> General ->")
    print("Login Items & Extensions -> Services -> Files & Folders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
