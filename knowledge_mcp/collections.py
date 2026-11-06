"""Pinned Kiwix snapshots. Network access is confined to the install command."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from .store import DEFAULT_DB

COLLECTIONS = {
    "wikivoyage": {
        "filename": "wikivoyage_en_all_maxi_2026-09.zim",
        "source_id": "wikivoyage_en", "size": 1071168673,
        "sha256": "ebaf235b4f95aa7f8666e0a613578577569eb6c81562ebcf397a7ba52173c848",
    },
    "ifixit": {
        "filename": "ifixit_en_all_2025-12.zim",
        "source_id": "ifixit_en", "size": 3570695757,
        "sha256": "9bb5f3408707fd0300c6ef47a425c3217187f144cd9154a928183816aa72eead",
    },
    "gutenberg": {
        "filename": "gutenberg_en_lcc-pn_2026-03.zim",
        "source_id": "gutenberg_en_literature", "size": 3248473917,
        "sha256": "1e1bd1fdf7464fb31f026e7a02e2bfbc77427802a2cbd7acb7402c09a046be19",
    },
}


def validate_download(path, spec):
    if path.stat().st_size != spec["size"]:
        raise ValueError("Archive size differs from the pinned publisher metadata")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != spec["sha256"]:
        raise ValueError("Archive SHA256 differs from the pinned publisher checksum")


def install_collection(name, db_path=DEFAULT_DB):
    from .ingest import register_zim
    spec = COLLECTIONS[name]
    directory = Path(db_path).resolve().parent / "archives"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / spec["filename"]
    if not target.exists():
        partial = target.with_suffix(target.suffix + ".part")
        # Reuse a complete staged download only after verifying both size and SHA256.
        if partial.exists() and partial.stat().st_size == spec["size"]:
            validate_download(partial, spec)
        else:
            url = "https://download.kiwix.org/zim/" + name + "/" + spec["filename"]
            request = Request(url, headers={"User-Agent": "OfflineKnowledgeMCP/0.1"})
            with urlopen(request, timeout=60) as response, partial.open("wb") as out:
                count = 0
                while block := response.read(1024 * 1024):
                    count += len(block)
                    if count > spec["size"]:
                        raise ValueError("Download exceeds the pinned archive size")
                    out.write(block)
            validate_download(partial, spec)
        partial.replace(target)
    validate_download(target, spec)
    return register_zim(db_path, target, spec["source_id"], spec["sha256"], collection=name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("collection", choices=[*COLLECTIONS, "all"])
    args = parser.parse_args()
    for name in COLLECTIONS if args.collection == "all" else [args.collection]:
        print(json.dumps(install_collection(name, args.db), indent=2), flush=True)


if __name__ == "__main__":
    main()
