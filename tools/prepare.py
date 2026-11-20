"""Fetch byte-pinned upstream archives into the ignored build directory (Python 3.12+)."""
import hashlib
import json
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
DEST = {"abc": LOCAL / "abc", "pexact": LOCAL / "abc/src/ext-pexact",
        "tcjap": LOCAL / "reference"}


def prepare(name, spec):
    cache = LOCAL / "downloads"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / (name + ".tar.gz")
    if not archive.exists():
        url = f"https://codeload.github.com/{spec['repository']}/tar.gz/{spec['commit']}"
        with urllib.request.urlopen(url, timeout=90) as response, tempfile.NamedTemporaryFile(
                dir=cache, delete=False) as tmp:
            shutil.copyfileobj(response, tmp)
        path = Path(tmp.name)
    else:
        path = archive
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != spec["archive_sha256"]:
            raise RuntimeError(f"Archive checksum mismatch: {path}")
    if path != archive:
        path.replace(archive)
    dest = DEST[name]
    if dest.exists():
        print(f"{name}: verified archive; preserving existing working directory {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as staging:
        with tarfile.open(archive) as source:
            source.extractall(staging, filter="data")
        children = list(Path(staging).iterdir())
        if len(children) != 1 or not children[0].name.endswith(spec["commit"]):
            raise RuntimeError(f"Unexpected archive directory in {archive}")
        children[0].rename(dest)
    print(f"{name}: prepared {spec['commit']}")


if __name__ == "__main__":
    for key, value in json.loads((ROOT / "sources.json").read_text()).items():
        prepare(key, value)
