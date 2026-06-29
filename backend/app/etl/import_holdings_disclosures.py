"""Import congressional disclosure transactions from local CSV/JSON files.

This importer expects already downloaded public disclosure exports. It keeps
reported value ranges as labels and does not convert them to exact amounts.

Usage:
    python -m app.etl.import_holdings_disclosures --file /data/house.json --source house_stock_watcher
    python -m app.etl.import_holdings_disclosures --file /data/senate.csv --source senate_stock_watcher
"""

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.postgres import Base, SessionLocal, engine
from app.models.sqlalchemy.models import HoldingAsset, HoldingDisclosure, Member


def ensure_tables():
    Base.metadata.create_all(bind=engine)


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _name_key(value: str) -> str:
    cleaned = " ".join(value.replace(",", " ").replace(".", " ").lower().split())
    parts = cleaned.split()
    if len(parts) >= 2 and parts[0] in {"rep", "sen", "representative", "senator", "hon"}:
        parts = parts[1:]
    return " ".join(parts)


def _parse_date(value: Any):
    raw = _norm(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_year(row: dict[str, Any]) -> int | None:
    for key in ("disclosure_year", "filing_year", "year"):
        raw = _norm(row.get(key))
        if raw.isdigit():
            return int(raw)
    for key in ("filed_date", "filing_date", "disclosure_date", "transaction_date"):
        parsed = _parse_date(row.get(key))
        if parsed:
            return parsed.year
    return None


def _member_name(row: dict[str, Any]) -> str:
    for key in ("representative", "senator", "member", "name", "owner_name"):
        val = _norm(row.get(key))
        if val:
            return val
    first = _norm(row.get("first_name"))
    last = _norm(row.get("last_name"))
    return f"{first} {last}".strip()


def _asset_name(row: dict[str, Any]) -> str:
    for key in ("asset_description", "asset_name", "asset", "description", "company", "issuer"):
        val = _norm(row.get(key))
        if val:
            return val
    ticker = _norm(row.get("ticker") or row.get("symbol"))
    return ticker or "Unknown Asset"


def _value_range(row: dict[str, Any]) -> str | None:
    for key in ("amount", "value", "value_range", "transaction_amount", "range"):
        val = _norm(row.get(key))
        if val:
            return val
    low = _norm(row.get("value_min") or row.get("amount_min"))
    high = _norm(row.get("value_max") or row.get("amount_max"))
    if low or high:
        return f"{low} - {high}".strip(" -")
    return None


def _asset_type(row: dict[str, Any], ticker: str | None, asset_name: str) -> str:
    raw = _norm(row.get("asset_type") or row.get("type") or row.get("transaction_type")).lower()
    name = asset_name.lower()
    if ticker:
        return "stock"
    if "bond" in raw or "bond" in name or "treasury" in name:
        return "bond"
    if "fund" in raw or "fund" in name or "etf" in name:
        return "fund"
    if "real estate" in raw or "property" in name:
        return "real_estate"
    return "other"


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in ("data", "transactions", "results"):
                if isinstance(data.get(key), list):
                    return data[key]
        if isinstance(data, list):
            return data
        raise ValueError("JSON file must contain a list of transactions")

    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def import_file(file_path: str, source: str, source_url: str | None = None, dry_run: bool = False) -> dict[str, int]:
    path = Path(file_path)
    rows = _load_rows(path)
    stats = {"rows": len(rows), "matched": 0, "assets_upserted": 0, "disclosures_upserted": 0, "unmatched": 0}

    with SessionLocal() as db:
        members = db.query(Member).filter(Member.is_current == True, Member.source != "mock").all()
        member_by_name = {_name_key(m.display_name): m for m in members}
        member_by_name.update({_name_key(m.canonical_name): m for m in members})

        for row in rows:
            member = member_by_name.get(_name_key(_member_name(row)))
            if not member:
                stats["unmatched"] += 1
                continue
            stats["matched"] += 1

            filing_year = _parse_year(row)
            filing_url = _norm(row.get("filing_url") or row.get("url") or row.get("document_url")) or source_url
            filing_type = _norm(row.get("filing_type") or row.get("report_type") or row.get("transaction_type")) or "transaction"
            disclosure_key = f"{member.id}|{filing_year}|{filing_type}|{filing_url or source}"
            disclosure_id = "disclosure_" + hashlib.sha1(disclosure_key.encode()).hexdigest()[:20]

            transaction_date = _parse_date(row.get("transaction_date") or row.get("date"))
            asset_name = _asset_name(row)
            ticker = _norm(row.get("ticker") or row.get("symbol")) or None
            value_range = _value_range(row)
            asset_type = _asset_type(row, ticker, asset_name)
            asset_key = f"{member.id}|{asset_name}|{ticker or ''}|{transaction_date or ''}|{value_range or ''}|{source}"
            asset_id = "holding_" + hashlib.sha1(asset_key.encode()).hexdigest()[:24]

            if dry_run:
                stats["assets_upserted"] += 1
                continue

            disclosure = db.query(HoldingDisclosure).filter(HoldingDisclosure.id == disclosure_id).first()
            if not disclosure:
                disclosure = HoldingDisclosure(
                    id=disclosure_id,
                    member_id=member.id,
                    filing_year=filing_year or datetime.now(timezone.utc).year,
                    filing_type=filing_type,
                    filing_url=filing_url,
                    filing_date=_parse_date(row.get("filed_date") or row.get("filing_date") or row.get("disclosure_date")),
                    asset_count=0,
                    source=source,
                    source_reliability="official" if "house" in source or "senate" in source else "external_public",
                )
                db.add(disclosure)
                stats["disclosures_upserted"] += 1

            asset = db.query(HoldingAsset).filter(HoldingAsset.id == asset_id).first()
            if not asset:
                db.add(HoldingAsset(
                    id=asset_id,
                    member_id=member.id,
                    asset_name=asset_name,
                    asset_type=asset_type,
                    ticker=ticker,
                    value_range_label=value_range,
                    filing_year=filing_year,
                    disclosure_date=transaction_date,
                    source=source,
                    source_url=filing_url,
                    source_reliability="official" if "house" in source or "senate" in source else "external_public",
                    last_updated=datetime.now(timezone.utc),
                ))
            else:
                asset.asset_name = asset_name
                asset.asset_type = asset_type
                asset.ticker = ticker
                asset.value_range_label = value_range
                asset.filing_year = filing_year
                asset.disclosure_date = transaction_date
                asset.source_url = filing_url
                asset.last_updated = datetime.now(timezone.utc)
            stats["assets_upserted"] += 1

            if stats["assets_upserted"] % 500 == 0:
                db.commit()

        if not dry_run:
            db.commit()
            db.query(HoldingDisclosure).filter(HoldingDisclosure.source == source).update({
                HoldingDisclosure.asset_count: 0,
            })
            db.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Import congressional disclosure transactions")
    parser.add_argument("--file", required=True, help="CSV or JSON disclosure export path")
    parser.add_argument("--source", required=True, help="Source identifier")
    parser.add_argument("--source-url", help="Source URL for rows without filing_url")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run:
        ensure_tables()
    stats = import_file(args.file, args.source, args.source_url, args.dry_run)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
