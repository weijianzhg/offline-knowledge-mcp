"""Single source of truth for supported collection names and download settings."""
import json
from importlib.resources import files

COLLECTIONS = json.loads(files("knowledge_mcp").joinpath("collection_manifest.json").read_text(encoding="utf-8"))


def select_collections(names):
    if not names:
        raise ValueError("Select one or more collections, or all; use --list to see choices")
    if "all" in names:
        if len(names) != 1:
            raise ValueError("Use all on its own, without other collection names")
        return list(COLLECTIONS)
    unknown = set(names) - COLLECTIONS.keys()
    if unknown:
        raise ValueError("Unknown collections: " + ", ".join(sorted(unknown)))
    return list(dict.fromkeys(names))
