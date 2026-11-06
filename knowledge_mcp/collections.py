"""Install all or selected offline collections through one operator command."""
import argparse
import json
from pathlib import Path

from .catalog import COLLECTIONS, select_collections
from .downloads import download_file
from .store import DEFAULT_DB, Store


def install_collection(name, db_path=DEFAULT_DB, *, refresh=False):
    from .ingest import register_zim, sync_world_bank
    spec = COLLECTIONS[name]
    db_path = Path(db_path).expanduser().resolve()
    if spec["kind"] == "world-bank":
        if db_path.exists() and not refresh:
            store = Store(db_path)
            catalog = store.list_sources()
            has_table = any(d["id"] == "world_bank" and d["source_id"] == spec["source_id"]
                            for d in catalog["datasets"])
            if has_table and store.query_data("world_bank", limit=1)["rows"]:
                for source in catalog["sources"]:
                    if source["id"] == spec["source_id"]:
                        return {"status": "reused", "collection": name, "source": source}
        result = sync_world_bank(db_path, spec["countries"], spec["first_year"], spec["last_year"])
        return {"status": "installed", "collection": name, **result}
    if spec["kind"] != "zim":
        raise ValueError("Unsupported collection kind: " + spec["kind"])
    target = db_path.parent / "archives" / spec["filename"]
    archive = download_file(spec["url"], target, spec["size"], size=spec["size"], sha256=spec["sha256"])
    source = register_zim(db_path, archive, spec["source_id"], spec["sha256"], collection=name)
    return {"status": "installed", "collection": name, "source": source}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", metavar="COLLECTION")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--list", action="store_true", help="List collection names and sizes without downloading")
    parser.add_argument("--refresh", action="store_true", help="Refresh selected World Bank data using catalog defaults; pinned ZIMs are reused")
    args = parser.parse_args()
    if args.list:
        if args.names or args.refresh:
            parser.error("Use --list without collection names or --refresh")
        for name, spec in COLLECTIONS.items():
            size = f"{spec['size'] / 1e9:.2f} GB" if "size" in spec else "small API snapshot"
            print(f"{name:12} {size:18} {spec['description']}")
        return
    try:
        selected = select_collections(args.names)
    except ValueError as exc:
        parser.error(str(exc))
    for name in selected:
        print(f"Installing {name}...", flush=True)
        print(json.dumps(install_collection(name, args.db, refresh=args.refresh), indent=2), flush=True)


if __name__ == "__main__":
    main()
