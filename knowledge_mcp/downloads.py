"""Bounded, atomic operator downloads shared by archives and API snapshots."""
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen


def validate_download(path, size, sha256):
    if path.stat().st_size != size:
        raise ValueError("Archive size differs from the pinned publisher metadata")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != sha256:
        raise ValueError("Archive SHA256 differs from the pinned publisher checksum")


def download_file(url, destination, max_bytes, *, size=None, sha256=None):
    """Keep existing files intact on failure; reuse only checksum-verified archives."""
    target = Path(destination)
    if (size is None) != (sha256 is None):
        raise ValueError("Provide both expected size and SHA256, or neither")
    if size is not None and target.exists():
        validate_download(target, size, sha256)
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    if size is not None and partial.exists() and partial.stat().st_size == size:
        validate_download(partial, size, sha256)
    else:
        request = Request(url, headers={"User-Agent": "OfflineKnowledgeMCP/0.1 (personal offline snapshot)"})
        with urlopen(request, timeout=60) as response, partial.open("wb") as out:
            count = 0
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > max_bytes:
                    raise ValueError("Download exceeds the allowed size")
                out.write(block)
        if size is not None:
            validate_download(partial, size, sha256)
    partial.replace(target)
    return target
