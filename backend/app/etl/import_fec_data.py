"""
FEC bulk data import script.

Downloads and imports campaign committee and contribution data from FEC bulk data files.

Data sources:
  - Committees: https://www.fec.gov/files/bulk-downloads/{year}/cm{year}.zip
  - Contributions: https://www.fec.gov/files/bulk-downloads/{year}/indiv{year}.zip

Usage:
  python -m app.etl.import_fec_data [--cycle 2024] [--limit 10000]
  python -m app.etl.import_fec_data --cycle 2024 --contributions-zip /path/to/indiv24.zip
"""

import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
import zipfile
import urllib.request
from datetime import datetime, timezone, date
from typing import Any

from app.db.postgres import SessionLocal, engine
from app.models.sqlalchemy.models import CampaignCommittee, Donor, Contribution, Member, Base
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert


FEC_BASE_URL = "https://www.fec.gov/files/bulk-downloads"


def ensure_tables():
    """Create campaign finance tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
    print("Tables ensured.")


def download_and_extract_csv(url: str) -> tuple[list[list[str]], str]:
    """Download a FEC bulk data zip and extract the CSV file.
    
    Returns (rows, detected_delimiter).
    """
    print(f"Downloading {url} ...")
    with urllib.request.urlopen(url) as resp:
        data = resp.read()
    rows: list[list[str]] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        csv_files = [n for n in zf.namelist() if n.endswith(".csv") or n.endswith(".txt")]
        if not csv_files:
            print(f"  No CSV found in zip, files: {zf.namelist()}")
            return rows, ""
        csv_name = csv_files[0]
        print(f"  Extracting {csv_name} ...")
        with zf.open(csv_name) as f:
            text = f.read().decode("latin-1")
            sample = text[:5000]
            # Detect delimiter: count | vs , in the first sample
            pipe_count = sample.count("|")
            comma_count = sample.count(",")
            delimiter = "|" if pipe_count > comma_count else ","
            print(f"  Detected delimiter: '{delimiter}' (pipes={pipe_count}, commas={comma_count})")
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            for row in reader:
                rows.append(row)
    return rows, delimiter


def parse_amount(val: str) -> float:
    try:
        return float(val.replace(",", "").replace("$", ""))
    except (ValueError, AttributeError):
        return 0.0


ALLOWED_CYCLES = {2022, 2024}


def import_committees(cycle: int, db: SessionLocal, limit: int | None = None) -> int:
    """Import campaign committees from FEC committee master file."""
    if cycle not in ALLOWED_CYCLES:
        print(f"  Skipped cycle {cycle}: only {sorted(ALLOWED_CYCLES)} are allowed.")
        return 0
    suffix = str(cycle)[-2:]
    url = f"{FEC_BASE_URL}/{cycle}/cm{suffix}.zip"
    rows, _ = download_and_extract_csv(url)
    if not rows:
        print(f"  No data from {url}")
        return 0

    header = rows[0]
    rows = rows[1:]
    if limit:
        rows = rows[:limit]

    count = 0
    for row in rows:
        if len(row) < 15:
            continue
        try:
            fec_id = row[0].strip()
            name = row[1].strip() if len(row) > 1 else ""
            party = row[10].strip() if len(row) > 10 else ""
            state = row[6].strip() if len(row) > 6 else ""
            chamber = "house" if "H" in fec_id[:1] else "senate" if "S" in fec_id[:1] else ""
            cand_id = row[14].strip() if len(row) > 14 else ""

            if not fec_id or not name:
                continue

            member = None
            if cand_id:
                member = db.query(Member).filter(
                    Member.fec_candidate_id == cand_id,
                    Member.is_current == True,
                ).first()

            existing = db.query(CampaignCommittee).filter(
                CampaignCommittee.fec_committee_id == fec_id
            ).first()

            if existing:
                existing.name = name
                existing.party = party or existing.party
                existing.cycle = cycle
                if member and not existing.candidate_id:
                    existing.candidate_id = member.fec_candidate_id
                    existing.chamber = chamber or existing.chamber
            else:
                committee = CampaignCommittee(
                    id=f"fec_cm_{fec_id}_{cycle}",
                    fec_committee_id=fec_id,
                    name=name,
                    party=party or None,
                    state=state or None,
                    chamber=chamber or None,
                    candidate_id=member.fec_candidate_id if member else None,
                    cycle=cycle,
                    source="fec",
                    fec_data={"raw_party": party, "raw_cand_id": cand_id},
                )
                db.add(committee)
            count += 1
        except Exception as e:
            print(f"  Error processing committee row: {e}")
            continue

    db.commit()
    print(f"  Imported {count} committees for cycle {cycle}")
    return count


def import_contributions_from_file(
    cycle: int, zip_path: str, db: SessionLocal,
    limit: int | None = None,
) -> int:
    """Import contributions from a locally stored FEC bulk-data zip file.
    
    Processes the itcont.txt in streaming fashion without loading all rows into memory.
    Pre-filters by committees linked to current members to skip irrelevant contributions.
    """
    suffix = str(cycle)[-2:]
    target_name = f"it{suffix}.txt" if suffix else "itcont.txt"

    # Build set of committee IDs we care about (those linked to current members only)
    relevant_committee_ids = set()
    committee_map = {}
    rows = db.execute(
        text("""
            SELECT cm.id, cm.fec_committee_id
            FROM campaign_committees cm
            JOIN members m ON m.id = cm.candidate_id
            WHERE m.is_current = TRUE
        """)
    ).fetchall()
    for r in rows:
        relevant_committee_ids.add(r.fec_committee_id)
        committee_map[r.fec_committee_id] = r.id

    print(f"  Found {len(relevant_committee_ids)} relevant committees (linked to members)", flush=True)

    if not os.path.exists(zip_path):
        print(f"  File not found: {zip_path}")
        return 0

    count = 0
    skipped_no_cmte = 0
    skipped_amount = 0
    skipped_parse = 0
    donor_cache: dict[str, str] = {}
    donor_rows = db.execute(text("SELECT id, name, state FROM donors")).fetchall()
    for row in donor_rows:
        donor_cache[f"{row.name}|{row.state or ''}"] = row.id

    donor_batch: dict[str, dict[str, Any]] = {}
    contrib_batch: list[dict[str, Any]] = []

    def flush_batches() -> None:
        nonlocal donor_batch, contrib_batch
        if donor_batch:
            stmt = pg_insert(Donor).values(list(donor_batch.values()))
            stmt = stmt.on_conflict_do_update(
                index_elements=[Donor.id],
                set_={
                    "name": stmt.excluded.name,
                    "donor_type": stmt.excluded.donor_type,
                    "city": stmt.excluded.city,
                    "state": stmt.excluded.state,
                    "employer": stmt.excluded.employer,
                    "industry": stmt.excluded.industry,
                    "source": stmt.excluded.source,
                    "source_reliability": stmt.excluded.source_reliability,
                    "fec_data": stmt.excluded.fec_data,
                },
            )
            db.execute(stmt)
            donor_batch = {}

        if contrib_batch:
            stmt = pg_insert(Contribution).values(contrib_batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Contribution.id],
                set_={
                    "committee_id": stmt.excluded.committee_id,
                    "donor_id": stmt.excluded.donor_id,
                    "amount": stmt.excluded.amount,
                    "contribution_date": stmt.excluded.contribution_date,
                    "cycle": stmt.excluded.cycle,
                    "contribution_type": stmt.excluded.contribution_type,
                    "source": stmt.excluded.source,
                    "source_reliability": stmt.excluded.source_reliability,
                    "fec_data": stmt.excluded.fec_data,
                },
            )
            db.execute(stmt)
            contrib_batch = []
        db.commit()

    with zipfile.ZipFile(zip_path) as zf:
        # Find the correct file inside zip
        csv_files = [n for n in zf.namelist() if n.endswith(".txt")]
        if not csv_files:
            print(f"  No txt files in zip: {zf.namelist()}")
            return 0
        csv_name = csv_files[0]
        print(f"  Processing {csv_name} (size={zf.getinfo(csv_name).file_size:,} bytes) ...", flush=True)

        # Read in chunks of 1000 lines for batch processing
        with zf.open(csv_name) as raw:
            text_stream = io.TextIOWrapper(raw, encoding="latin-1")
            reader = csv.reader(text_stream, delimiter="|")

            for row in reader:
                try:
                    if len(row) < 15:
                        continue

                    cmte_id = row[0].strip()
                    if cmte_id not in relevant_committee_ids:
                        skipped_no_cmte += 1
                        continue

                    committee_pk = committee_map[cmte_id]
                    donor_name = row[7].strip() if len(row) > 7 else "Unknown"
                    if not donor_name or donor_name == "Unknown":
                        continue

                    city = row[8].strip() if len(row) > 8 else ""
                    donor_state = row[9].strip() if len(row) > 9 else ""
                    employer = row[11].strip() if len(row) > 11 else ""
                    occupation = row[12].strip() if len(row) > 12 else ""
                    amount_str = row[14].strip() if len(row) > 14 else "0"
                    amount = parse_amount(amount_str)
                    if amount <= 0:
                        skipped_amount += 1
                        continue

                    date_str = row[13].strip() if len(row) > 13 else ""
                    contrib_date = None
                    if date_str and len(date_str) == 8:
                        try:
                            # MMDDYYYY format
                            month = int(date_str[:2])
                            day = int(date_str[2:4])
                            year = int(date_str[4:8])
                            contrib_date = date(year, month, day)
                        except (ValueError, IndexError):
                            pass

                    other_id = row[15].strip() if len(row) > 15 else ""
                    contrib_type = "other"
                    if other_id:
                        contrib_type = "conduit"  # Earmarked through another committee
                    elif row[6].strip() == "IND" if len(row) > 6 else "":
                        contrib_type = "individual"
                    elif row[6].strip() == "PAC" if len(row) > 6 else "":
                        contrib_type = "pac"
                    elif row[6].strip() == "CC" if len(row) > 6 else "":
                        contrib_type = "party"
                    elif row[6].strip() == "PTY" if len(row) > 6 else "":
                        contrib_type = "party"
                    elif row[6].strip() == "ORG" if len(row) > 6 else "":
                        contrib_type = "organization"

                    # Donor dedup by (name, state)
                    donor_key = f"{donor_name}|{donor_state}"
                    donor_id = donor_cache.get(donor_key)
                    if not donor_id:
                        digest = hashlib.sha1(donor_key.encode("utf-8")).hexdigest()[:16]
                        donor_id = f"fec_donor_{digest}"
                        donor_batch[donor_id] = {
                            "id": donor_id,
                            "name": donor_name,
                            "donor_type": contrib_type if contrib_type != "other" else "individual",
                            "city": city or None,
                            "state": donor_state or None,
                            "employer": employer or None,
                            "industry": occupation or None,
                            "source": "fec",
                            "source_reliability": "official",
                            "fec_data": {},
                        }
                        donor_cache[donor_key] = donor_id

                    tran_id = row[17].strip() if len(row) > 17 else ""
                    memo_code = row[16].strip() if len(row) > 16 else ""
                    contrib_key = "|".join([
                        str(cycle), cmte_id, tran_id, memo_code, donor_name,
                        donor_state, date_str, amount_str, str(count),
                    ])
                    contrib_digest = hashlib.sha1(contrib_key.encode("utf-8")).hexdigest()[:20]
                    contrib_id = f"fec_contrib_{contrib_digest}"
                    contrib_batch.append({
                        "id": contrib_id,
                        "committee_id": committee_pk,
                        "donor_id": donor_id,
                        "amount": amount,
                        "contribution_date": contrib_date,
                        "cycle": cycle,
                        "contribution_type": contrib_type,
                        "source": "fec",
                        "source_reliability": "official",
                        "fec_data": {"transaction_id": tran_id, "memo_code": memo_code},
                    })
                    count += 1

                    if len(contrib_batch) >= 5000:
                        flush_batches()
                        print(f"    ... {count} contributions imported (skipped_no_cmte={skipped_no_cmte}, skipped_amount={skipped_amount})", flush=True)
                        if limit and count >= limit:
                            break

                    if limit and count >= limit:
                        flush_batches()
                        print(f"    ... {count} contributions imported (skipped_no_cmte={skipped_no_cmte}, skipped_amount={skipped_amount})", flush=True)
                        break

                except Exception:
                    skipped_parse += 1
                    continue

                if limit and count >= limit:
                    break

    flush_batches()
    print(f"  Imported {count} contributions for cycle {cycle}")
    print(f"    Skipped (no matching committee): {skipped_no_cmte}")
    print(f"    Skipped (zero/negative amount): {skipped_amount}")
    print(f"    Skipped (parse errors): {skipped_parse}")
    return count


def import_contributions_by_cycle(
    cycle: int, db: SessionLocal,
    limit: int | None = None,
    zip_path: str | None = None,
) -> int:
    """Import individual contributions from FEC data file.
    
    Only cycles in ALLOWED_CYCLES are processed.
    First checks for a pre-downloaded zip file, falls back to HTTP download.
    """
    if cycle not in ALLOWED_CYCLES:
        print(f"  Skipped cycle {cycle}: only {sorted(ALLOWED_CYCLES)} are allowed.")
        return 0
    if zip_path:
        print(f"  Using provided file: {zip_path}")
        return import_contributions_from_file(cycle, zip_path, db, limit)

    suffix = str(cycle)[-2:]
    local_path = f"/tmp/indiv{suffix}_full.zip"
    if os.path.exists(local_path):
        print(f"  Using local file: {local_path}")
        return import_contributions_from_file(cycle, local_path, db, limit)

    url = f"{FEC_BASE_URL}/{cycle}/indiv{suffix}.zip"
    print(f"  Downloading {url} (large file, may take a while) ...")
    rows, delimiter = download_and_extract_csv(url)
    if not rows:
        print(f"  No data from {url}")
        return 0

    header = rows[0]
    rows = rows[1:]
    if limit:
        rows = rows[:limit]

    count = 0
    donor_cache: dict[str, str] = {}

    for row in rows:
        try:
            cmte_id = row[0].strip() if len(row) > 0 else ""
            if not cmte_id:
                continue

            committee = db.query(CampaignCommittee).filter(
                CampaignCommittee.fec_committee_id == cmte_id
            ).first()
            if not committee:
                continue

            donor_name = row[7].strip() if len(row) > 7 else "Unknown"
            city = row[8].strip() if len(row) > 8 else ""
            donor_state = row[9].strip() if len(row) > 9 else ""
            employer = row[11].strip() if len(row) > 11 else ""
            occupation = row[12].strip() if len(row) > 12 else ""
            amount_str = row[14].strip() if len(row) > 14 else "0"
            amount = parse_amount(amount_str)

            if amount <= 0:
                continue

            date_str = row[13].strip() if len(row) > 13 else ""
            contrib_date = None
            if date_str and len(date_str) == 8:
                try:
                    month = int(date_str[:2])
                    day = int(date_str[2:4])
                    year = int(date_str[4:8])
                    contrib_date = date(year, month, day)
                except (ValueError, IndexError):
                    pass

            contrib_type = "individual"
            other_id = row[15].strip() if len(row) > 15 else ""
            if other_id:
                contrib_type = "conduit"

            donor_key = f"{donor_name}|{donor_state}"
            donor_id = donor_cache.get(donor_key)
            if not donor_id:
                existing_donor = db.query(Donor).filter(
                    Donor.name == donor_name,
                    Donor.state == donor_state,
                ).first()
                if existing_donor:
                    donor_id = existing_donor.id
                else:
                    donor_id = f"fec_donor_{abs(hash(donor_key))}"
                    donor = Donor(
                        id=donor_id,
                        name=donor_name,
                        donor_type="individual",
                        city=city or None,
                        state=donor_state or None,
                        employer=employer or None,
                        industry=occupation or None,
                        source="fec",
                    )
                    db.add(donor)
                donor_cache[donor_key] = donor_id

            tran_id = row[17].strip() if len(row) > 17 else ""
            contribution_id = f"fec_contrib_{cycle}_{cmte_id}_{tran_id or count}"

            existing_contrib = db.query(Contribution).filter(Contribution.id == contribution_id).first()
            if existing_contrib:
                existing_contrib.committee_id = committee.id
                existing_contrib.donor_id = donor_id
                existing_contrib.amount = amount
                existing_contrib.contribution_date = contrib_date
                existing_contrib.contribution_type = contribution_type
                existing_contrib.fec_data = {"transaction_id": tran_id, "memo_code": row[16].strip() if len(row) > 16 else ""}
            else:
                contrib = Contribution(
                    id=contribution_id,
                    committee_id=committee.id,
                    donor_id=donor_id,
                    amount=amount,
                    contribution_date=contrib_date,
                    cycle=cycle,
                    contribution_type=contrib_type,
                    source="fec",
                    fec_data={"transaction_id": tran_id, "memo_code": row[16].strip() if len(row) > 16 else ""},
                )
                db.add(contrib)
            count += 1

            if count % 1000 == 0:
                db.commit()
                print(f"    ... {count} contributions processed")

        except Exception:
            continue

    db.commit()
    print(f"  Imported {count} contributions for cycle {cycle}")
    return count


def main():
    parser = argparse.ArgumentParser(description="Import FEC bulk data")
    parser.add_argument("--cycles", type=int, nargs="+", default=[2022, 2024],
                        help="Election cycles to import (default: 2022 2024)")
    parser.add_argument("--limit", type=int, default=None, help="Max records per file")
    parser.add_argument("--contributions-zip", help="Path to downloaded FEC indiv zip for streaming full import")
    parser.add_argument("--committees-only", action="store_true", help="Only import committees")
    parser.add_argument("--contributions-only", action="store_true", help="Only import contributions")
    args = parser.parse_args()

    invalid = [c for c in args.cycles if c not in ALLOWED_CYCLES]
    if invalid:
        print(f"Cycles {invalid} are not allowed. Only {sorted(ALLOWED_CYCLES)} are supported.")
        return

    db = SessionLocal()
    try:
        ensure_tables()

        for cycle in sorted(args.cycles):
            print(f"\n=== Processing cycle {cycle} ===")
            if not args.contributions_only:
                cmte_count = import_committees(cycle, db, args.limit)
                print(f"Committees imported: {cmte_count}")

            if not args.committees_only:
                contrib_count = import_contributions_by_cycle(cycle, db, args.limit, args.contributions_zip)
                print(f"Contributions imported: {contrib_count}")

        print(f"\nImport complete for cycles: {args.cycles}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
