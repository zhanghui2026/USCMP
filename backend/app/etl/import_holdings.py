"""Import holdings data from Member.top_holdings JSON to structured tables.

v0.94: Migrates holdings from JSON field to HoldingAsset table.
Supports future House/Senate disclosure data sources.

Usage:
    python -m app.etl.import_holdings [--dry-run] [--clear]
"""

import argparse
import uuid
from datetime import datetime, timezone

from app.db.postgres import SessionLocal, engine, Base
from app.models.sqlalchemy.models import Member, HoldingAsset, HoldingDisclosure


def ensure_tables():
    """Create tables if they don't exist."""
    HoldingAsset.__table__.create(engine, checkfirst=True)
    HoldingDisclosure.__table__.create(engine, checkfirst=True)


def migrate_top_holdings(dry_run: bool = False) -> dict:
    """Migrate top_holdings JSON to HoldingAsset table."""
    stats = {"members_processed": 0, "holdings_created": 0, "skipped_empty": 0}

    with SessionLocal() as db:
        members = db.query(Member).filter(Member.top_holdings.isnot(None)).all()

        for member in members:
            holdings = member.top_holdings or []
            if not holdings:
                stats["skipped_empty"] += 1
                continue

            stats["members_processed"] += 1

            for holding in holdings:
                if dry_run:
                    stats["holdings_created"] += 1
                    continue

                asset_name = holding.get("company") or holding.get("asset_name") or "Unknown"
                ticker = holding.get("ticker")
                value_min = holding.get("amount_min")
                value_max = holding.get("amount_max")
                value_range = holding.get("value_range")
                asset_type = _infer_asset_type(asset_name, ticker)

                if not value_range and value_min is not None and value_max is not None:
                    value_range = f"${value_min:,.0f} - ${value_max:,.0f}"

                holding_asset = HoldingAsset(
                    id=f"holding_{member.id}_{uuid.uuid4().hex[:8]}",
                    member_id=member.id,
                    asset_name=asset_name,
                    asset_type=asset_type,
                    ticker=ticker,
                    value_min=value_min,
                    value_max=value_max,
                    value_range_label=value_range,
                    filing_year=holding.get("filing_year") or holding.get("year"),
                    disclosure_date=_parse_date(holding.get("disclosure_date")),
                    source=holding.get("source", "member_json"),
                    source_url=holding.get("source_url"),
                    source_reliability="official",
                    last_updated=datetime.now(timezone.utc),
                )
                db.add(holding_asset)
                stats["holdings_created"] += 1

            if not dry_run:
                db.commit()

    return stats


def _infer_asset_type(asset_name: str, ticker: str | None) -> str:
    """Infer asset type from name and ticker."""
    if ticker:
        return "stock"
    name_lower = (asset_name or "").lower()
    if any(kw in name_lower for kw in ["bond", "treasury", "note"]):
        return "bond"
    if any(kw in name_lower for kw in ["fund", "etf", "mutual", "index"]):
        return "fund"
    if any(kw in name_lower for kw in ["property", "real estate", "land", "house"]):
        return "real_estate"
    return "stock"


def _parse_date(date_str: str | None):
    """Parse date string to date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Import holdings data")
    parser.add_argument("--dry-run", action="store_true", help="Only count, don't write")
    parser.add_argument("--clear", action="store_true", help="Clear existing holdings first")
    args = parser.parse_args()

    print("Ensuring tables exist...")
    if not args.dry_run:
        ensure_tables()

    if args.clear and not args.dry_run:
        with SessionLocal() as db:
            count = db.query(HoldingAsset).delete()
            db.commit()
            print(f"Cleared {count} existing holding assets")

    print("Migrating top_holdings JSON to HoldingAsset table...")
    stats = migrate_top_holdings(dry_run=args.dry_run)

    print(f"\nImport complete:")
    print(f"  Members processed: {stats['members_processed']}")
    print(f"  Holdings created: {stats['holdings_created']}")
    print(f"  Skipped (empty): {stats['skipped_empty']}")


if __name__ == "__main__":
    main()
