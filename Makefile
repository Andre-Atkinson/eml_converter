# eml2msg - build and install the .eml -> .msg converter and its Finder Quick Action.
#
#   make build              build the self-contained binary into ./bin
#   make install FROM=...   build, then install the "Convert to MSG" Quick Action
#   make uninstall          remove the Quick Action
#   make lock               regenerate packages.lock.json after changing a dependency
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

# The single publish invocation that 'build' and 'lock' share, so the lock file
# is always regenerated under the exact inputs the build consumes. A
# self-contained single-file publish pulls in the target RID graph and
# Microsoft.NET.ILLink.Tasks; a plain 'dotnet restore' captures neither and
# produces a lock that then fails locked-mode restore.
PUBLISH := dotnet publish $(PROJECT) -c Release -o bin -r $(RID) \
	--self-contained true -p:PublishSingleFile=true \
	-p:IncludeNativeLibrariesForSelfExtract=true

.DEFAULT_GOAL := help

.PHONY: help build install uninstall lock clean

help:
	@echo "eml2msg targets:"
	@echo "  make build              build the self-contained binary into ./bin ($(RID))"
	@echo "  make install FROM=...   build, then install the Finder Quick Action"
	@echo "  make uninstall          remove the Quick Action"
	@echo "  make lock               regenerate packages.lock.json after a dependency change"
	@echo "  make clean              remove build output"
	@echo ""
	@echo "FROM sets the sender for .eml files with no From: header, e.g."
	@echo '  make install FROM="Andre Atkinson <andre@example.com>"'

# RestoreLockedMode=true makes the build fail rather than silently update the
# lock file, so a distributed binary always matches the pinned dependency graph.
# Run 'make lock' after intentionally changing a package version.
build:
	$(PUBLISH) -p:RestoreLockedMode=true

install: build
	python3 tools/install_quickaction.py --from "$(FROM)"

uninstall:
	python3 tools/install_quickaction.py --uninstall

# Regenerate the lock through the same publish path the build uses, so both RID
# graphs and the single-file publish packages are captured. Review the diff.
lock:
	$(PUBLISH) -p:RestoreLockedMode=false -p:RestoreForceEvaluate=true
	@echo "packages.lock.json regenerated - review and commit the diff."

clean:
	rm -rf bin obj src/Eml2Msg/bin src/Eml2Msg/obj
