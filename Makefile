# eml2msg - build and install the .eml -> .msg converter and its Finder Quick Action.
#
#   make build              build the self-contained binary into ./bin
#   make install FROM=...   build, then install the "Convert to MSG" Quick Action
#   make uninstall          remove the Quick Action
#   make verify             fail if the third-party lock file has drifted
#   make lock               regenerate packages.lock.json after a dependency change
#   make clean              remove build output
#
# FROM is the sender used for .eml files that have no From: header (Outlook for
# Mac omits it on messages you sent). Example:
#   make install FROM="Andre Atkinson <andre@example.com>"

# Pick the .NET runtime identifier from the current CPU unless overridden on the
# command line (make build RID=osx-x64).
ARCH := $(shell uname -m)
ifeq ($(ARCH),arm64)
  RID ?= osx-arm64
else
  RID ?= osx-x64
endif

PROJECT := src/Eml2Msg
FROM ?=

.DEFAULT_GOAL := help

.PHONY: help build install uninstall verify lock clean

help:
	@echo "eml2msg targets:"
	@echo "  make build              build the self-contained binary into ./bin ($(RID))"
	@echo "  make install FROM=...   build, then install the Finder Quick Action"
	@echo "  make uninstall          remove the Quick Action"
	@echo "  make verify             fail if the third-party lock file has drifted"
	@echo "  make lock               regenerate packages.lock.json after a dependency change"
	@echo "  make clean              remove build output"
	@echo ""
	@echo "FROM sets the sender for .eml files with no From: header, e.g."
	@echo '  make install FROM="Andre Atkinson <andre@example.com>"'

# The self-contained publish restores runtime packs and ILLink that are not in
# the third-party lock, so its restore would rewrite packages.lock.json (and
# NuGet forbids disabling the lock while the file exists). Snapshot the committed
# lock and move it back afterward - even on failure or Ctrl-C - so the build
# leaves it untouched. Supply-chain pinning is enforced separately by 'make
# verify', and building this way lets the binary ship the latest runtime patch.
build:
	cp $(PROJECT)/packages.lock.json $(PROJECT)/packages.lock.json.bak
	trap 'mv -f $(PROJECT)/packages.lock.json.bak $(PROJECT)/packages.lock.json' EXIT INT TERM; \
	dotnet publish $(PROJECT) -c Release -o bin -r $(RID) \
		--self-contained true -p:PublishSingleFile=true \
		-p:IncludeNativeLibrariesForSelfExtract=true

install: build
	python3 tools/install_quickaction.py --from "$(FROM)"

uninstall:
	python3 tools/install_quickaction.py --uninstall

# Fail closed if the resolved third-party graph no longer matches the committed
# lock - a changed version, or a package whose bytes differ from what was locked.
# This is the supply-chain gate; CI runs it too.
verify:
	dotnet restore $(PROJECT) --locked-mode

# Regenerate the lock after intentionally changing a dependency, then review and
# commit the diff. Framework-dependent, so it captures only the third-party
# packages (with portable nuget.org content hashes), never SDK-shipped ones.
lock:
	dotnet restore $(PROJECT) --force-evaluate
	@echo "packages.lock.json regenerated - review and commit the diff."

clean:
	rm -rf bin obj src/Eml2Msg/bin src/Eml2Msg/obj
