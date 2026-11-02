"""Explicit operator-only imports. Only sync-world-bank uses the internet."""
import argparse
import csv
import hashlib
import json
import re
import time
from contextlib import closing
from pathlib import Path
from urllib.request import Request, urlopen

from .store import DEFAULT_DB, connect, initialize, put_document, put_source, utc_now, zim_path


def fetch_json(url, destination):
    # This module is never imported by the serving process.
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "OfflineKnowledgeMCP/0.1 (personal offline data snapshot)",
                                       "Accept": "application/json"})
            with urlopen(req, timeout=45) as response:
                raw = response.read(20_000_001)
            if len(raw) > 20_000_000:
                raise ValueError("Response exceeds 20 MB")
            value = json.loads(raw)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            return value
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def register_zim(db_path, path, source_id, expected_sha256=None):
    from libzim.reader import Archive
    path = Path(path).resolve(strict=True)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError("Archive SHA256 does not match supplied publisher checksum")
    archive = Archive(zim_path(path))
    if not archive.has_checksum or not archive.check():
        raise ValueError("ZIM internal checksum validation failed")
    if not archive.has_fulltext_index:
        raise ValueError("ZIM must contain a full-text search index")
    if archive.get_metadata("Language").decode() != "eng":
        raise ValueError("This Wikipedia adapter currently supports English archives only")
    metadata = {"id": source_id, "kind": "zim", "name": archive.get_metadata("Title").decode(),
                "scope": archive.get_metadata("Description").decode(),
                "snapshot_date": archive.get_metadata("Date").decode(),
                "source_url": "https://download.kiwix.org/zim/wikipedia/" + path.name,
                "license": "Wikipedia text: CC BY-SA; see article attribution/history. Media licenses vary.",
                "license_url": "https://en.wikipedia.org/wiki/Wikipedia:Copyrights",
                "archive_path": str(path), "archive_sha256": digest,
                "publisher_checksum_verified": bool(expected_sha256),
                "archive_article_count": archive.article_count,
                "article_revision_dates": "Not extracted; snapshot_date is the archive build date"}
    initialize(db_path)
    with closing(connect(db_path, True)) as db, db:
        put_source(db, metadata)
    return metadata


def sync_world_bank(db_path, countries, first_year, last_year):
    if not all(re.fullmatch(r"[A-Z]{3}", c) for c in countries.split(";")):
        raise ValueError("Use semicolon-separated ISO3 country codes, or WLD")
    if not 1960 <= first_year <= last_year <= 2100:
        raise ValueError("Invalid year range")
    batch = Path(db_path).resolve().parent / "raw" / ("world-bank-" + utc_now().replace(":", "").replace("+", "-"))
    indicators = {"SP.POP.TOTL": ("population", "people"), "NY.GDP.MKTP.CD": ("gdp_current_usd", "current US dollars")}
    records, definitions, updated = [], {}, []
    for indicator in indicators:
        metadata_url = f"https://api.worldbank.org/v2/indicator/{indicator}?format=json"
        definitions[indicator] = fetch_json(metadata_url, batch / f"{indicator}-definition.json")[1][0]
        url = (f"https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}"
               f"?format=json&date={first_year}:{last_year}&per_page=20000")
        result = fetch_json(url, batch / f"{indicator}.json")
        if not isinstance(result, list) or len(result) != 2 or not isinstance(result[1], list):
            raise ValueError("World Bank returned an unexpected response; existing snapshot retained")
        if int(result[0]["pages"]) != 1:
            raise ValueError("Response needs pagination; reduce scope before importing")
        updated.append(result[0].get("lastupdated"))
        for record in result[1]:
            records.append({"country_code": record["countryiso3code"], "country": record["country"]["value"],
                            "indicator": indicator, "indicator_name": record["indicator"]["value"],
                            "year": int(record["date"]), "value": record["value"],
                            "unit": indicators[indicator][1], "obs_status": record.get("obs_status", ""),
                            "citation_url": f"https://data.worldbank.org/indicator/{indicator}?locations={record['country']['id']}"})
    snapshot = utc_now()[:10]
    metadata = {"id": "world_bank", "name": "World Bank World Development Indicators (selected series)",
                "kind": "statistics", "source_url": "https://data.worldbank.org/",
                "license": "World Bank open data terms; dataset-specific third-party restrictions may apply",
                "license_url": "https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets",
                "scope": f"{countries}; population and GDP (current US$); {first_year}-{last_year}. Null values mean missing observations.",
                "snapshot_date": snapshot, "publisher_last_updated": sorted({v for v in updated if v}),
                "raw_files": str(batch.relative_to(Path(db_path).resolve().parent)),
                "raw_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in batch.glob('*.json')}}
    initialize(db_path)
    # Fetch everything first, then replace all tables in one transaction.
    with closing(connect(db_path, True)) as db, db:
        put_source(db, metadata)
        db.execute("DELETE FROM facts WHERE source_id='world_bank'")
        db.execute("DELETE FROM dataset_rows WHERE dataset_id='world_bank'")
        columns = list(records[0]) if records else []
        db.execute("INSERT OR REPLACE INTO datasets VALUES(?,?,?,?)",
                   ("world_bank", "world_bank", metadata["scope"], json.dumps(columns)))
        for n, record in enumerate(sorted(records, key=lambda r: (r["country_code"], r["indicator"], -r["year"]))):
            db.execute("INSERT INTO dataset_rows VALUES(?,?,?)", ("world_bank", n, json.dumps(record)))
            if record["value"] is None:
                continue
            definition = definitions[record["indicator"]]
            predicate, unit = indicators[record["indicator"]]
            qualifiers = {"indicator": record["indicator"], "definition": definition.get("sourceNote"),
                          "publisher_source": definition.get("sourceOrganization"), "country_name": record["country"],
                          "obs_status": record["obs_status"], "scope": "country/aggregate, not city or metropolitan area"}
            identifier = f"wb:{record['country_code']}:{record['indicator']}:{record['year']}"
            db.execute("INSERT INTO facts VALUES(?,?,?,?,?,?,?,?,?)",
                       (identifier, "world_bank", record["country_code"], predicate, json.dumps(record["value"]),
                        unit, str(record["year"]), json.dumps(qualifiers), record["citation_url"]))
        for indicator, definition in definitions.items():
            put_document(db, "world_bank", {"id": indicator, "title": definition["name"],
                         "text": definition.get("sourceNote", "") + "\nSource: " + definition.get("sourceOrganization", ""),
                         "citation_url": f"https://data.worldbank.org/indicator/{indicator}"})
    return {"rows": len(records), "source": metadata}


def import_jsonl(db_path, path, source_path, kind):
    metadata = json.loads(Path(source_path).read_text(encoding="utf-8-sig"))
    initialize(db_path)
    count = 0
    with closing(connect(db_path, True)) as db, db:
        put_source(db, metadata)
        with Path(path).open(encoding="utf-8-sig") as stream:
            for line in stream:
                if not line.strip():
                    continue
                item = json.loads(line)
                if kind == "documents":
                    put_document(db, metadata["id"], item)
                else:
                    db.execute("INSERT OR REPLACE INTO facts VALUES(?,?,?,?,?,?,?,?,?)",
                               (f"{metadata['id']}:{item['id']}", metadata["id"], item["subject"], item["predicate"],
                                json.dumps(item["value"]), item.get("unit"), item.get("observation_date"),
                                json.dumps(item.get("qualifiers", {})), item["citation_url"]))
                count += 1
    return {"imported": count, "kind": kind}


def import_csv(db_path, path, source_path, dataset_id):
    metadata = json.loads(Path(source_path).read_text(encoding="utf-8-sig"))
    initialize(db_path)
    with closing(connect(db_path, True)) as db, db, Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        if not columns or len(columns) != len(set(columns)) or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", c) for c in columns):
            raise ValueError("CSV headers must be unique simple identifiers")
        put_source(db, metadata)
        db.execute("DELETE FROM dataset_rows WHERE dataset_id=?", (dataset_id,))
        db.execute("INSERT OR REPLACE INTO datasets VALUES(?,?,?,?)",
                   (dataset_id, metadata["id"], metadata["scope"], json.dumps(columns)))
        count = 0
        for count, row in enumerate(reader, 1):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Malformed CSV row {count}")
            db.execute("INSERT INTO dataset_rows VALUES(?,?,?)", (dataset_id, count, json.dumps(row)))
    return {"rows": count, "dataset_id": dataset_id, "value_types": "CSV values remain strings"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    zim = sub.add_parser("register-zim")
    zim.add_argument("path", type=Path)
    zim.add_argument("--source-id", required=True)
    zim.add_argument("--sha256")
    wb = sub.add_parser("sync-world-bank")
    wb.add_argument("--countries", default="GBR;USA;JPN;CHN;IND;DEU;FRA;CAN;AUS;WLD")
    wb.add_argument("--first-year", type=int, default=2000)
    wb.add_argument("--last-year", type=int, default=2025)
    for kind in ("documents", "facts", "csv"):
        cmd = sub.add_parser(kind)
        cmd.add_argument("path", type=Path)
        cmd.add_argument("--source", type=Path, required=True)
        if kind == "csv":
            cmd.add_argument("--dataset-id", required=True)
    args = parser.parse_args()
    args.db = args.db.expanduser().resolve()
    if args.command == "init":
        initialize(args.db)
        result = {"database": str(args.db)}
    elif args.command == "register-zim":
        result = register_zim(args.db, args.path, args.source_id, args.sha256)
    elif args.command == "sync-world-bank":
        result = sync_world_bank(args.db, args.countries, args.first_year, args.last_year)
    elif args.command == "csv":
        result = import_csv(args.db, args.path, args.source, args.dataset_id)
    else:
        result = import_jsonl(args.db, args.path, args.source, args.command)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
