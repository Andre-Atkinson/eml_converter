"""pytest fixtures: locate the eml2msg binary and expose it as a callable."""
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
# Make the test-support modules (oracle, emlgen) importable no matter how pytest
# was launched.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))


def _resolve_binary():
    override = os.environ.get("EML2MSG_BIN")
    if override:
        return pathlib.Path(override)

    prebuilt = REPO / "bin" / "eml2msg"
    if prebuilt.exists():
        return prebuilt

    # No prebuilt binary (e.g. a fresh CI checkout): build a framework-dependent
    # one. RestorePackagesWithLockFile=false keeps this restore from rewriting
    # the committed lock file, which is generated for the self-contained publish
    # and would otherwise be pruned to this smaller graph.
    subprocess.run(
        ["dotnet", "build", str(REPO / "src" / "Eml2Msg"), "-c", "Release",
         "-p:RestorePackagesWithLockFile=false"],
        check=True, cwd=str(REPO),
    )
    built = REPO / "src" / "Eml2Msg" / "bin" / "Release" / "net10.0" / "eml2msg"
    if not built.exists():
        raise RuntimeError("build did not produce " + str(built))
    return built


@pytest.fixture(scope="session")
def converter():
    """A callable that runs eml2msg with the given args and returns the
    CompletedProcess (stdout/stderr captured as text)."""
    binary = _resolve_binary()

    def run(*args):
        return subprocess.run(
            [str(binary), *[str(a) for a in args]],
            capture_output=True, text=True,
        )

    run.path = binary
    return run
