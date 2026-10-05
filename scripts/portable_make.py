"""Fetch a SHA-256 verified official MSYS2 GNU Make into this workspace only."""
from pathlib import Path
import hashlib
import io
import json
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = "https://mirror.msys2.org/mingw/mingw64/mingw-w64-x86_64-make-4.4.1-5-any.pkg.tar.zst"
SHA = "c19e7caf09bbc89b2730556b2da73004118d4e1f967a685cc48524c7ff80d864"


def main():
    folder = (ROOT / ".cache/tools/gnu-make-4.4.1-5").resolve()
    assert folder.is_relative_to(ROOT)
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / "make.pkg.tar.zst"
    if not archive.exists():
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open("xb") as target:
            target.write(response.read())
    data = archive.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SHA
    from compression import zstd
    with tarfile.open(fileobj=io.BytesIO(zstd.decompress(data)), mode="r:") as package:
        # Extract one explicitly named binary, no wildcard or archive paths.
        member = package.getmember("mingw64/bin/mingw32-make.exe")
        assert member.isfile()
        executable = folder / "make.exe"
        expected = package.extractfile(member).read()
        if executable.exists():
            assert executable.read_bytes() == expected
        else:
            with executable.open("xb") as target:
                target.write(expected)
    metadata = folder / "provenance.json"
    if not metadata.exists():
        with metadata.open("x", encoding="utf-8") as target:
            json.dump({"url": URL, "archive_sha256": SHA,
                       "publisher": "https://packages.msys2.org/packages/mingw-w64-x86_64-make",
                       "binary_sha256": hashlib.sha256(expected).hexdigest()}, target, indent=2)
    print(executable)


if __name__ == "__main__":
    main()
