"""Import congress profiles from JSON format.

Reads congress-profiles directory with per-member JSON files and
upserts into members and member_profiles tables.

Usage:
    python3 -m app.etl.import_json_profiles [--dry-run] [--limit N]
"""

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from app.db.postgres import SessionLocal
from app.models.sqlalchemy.models import Member
from app.core.logging import logger

BASE_DIR = Path("data/congress-profiles")


def load_config() -> dict:
    cfg = BASE_DIR / "config.json"
    if cfg.exists():
        with open(cfg, encoding="utf-8") as f:
            return json.load(f)
    return {}


def walk_profiles() -> list[dict]:
    profiles = []
    for chamber_dir in BASE_DIR.iterdir():
        if not chamber_dir.is_dir() or chamber_dir.name.startswith("."):
            continue
        for member_dir in chamber_dir.iterdir():
            json_file = member_dir / "profile.json"
            if json_file.exists():
                with open(json_file, encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        data["_chamber_dir"] = chamber_dir.name
                        data["_member_dir"] = member_dir.name
                        profiles.append(data)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON in {json_file}: {e}")
    return profiles


def _parse_profile_md(md_text: str) -> dict:
    result = {
        "core_positions": None,
        "china_stance_summary": None,
        "comprehensive_evaluation": None,
        "career_history": [],
        "controversies": [],
    }
    if not md_text:
        return result
    result["comprehensive_evaluation"] = md_text
    section = None
    for line in md_text.split("\n"):
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if section and line.strip():
            if "核心立场" in section or "核心政治立场" in section or "political position" in section:
                if result["core_positions"] is None:
                    result["core_positions"] = ""
                result["core_positions"] += line.strip() + "\n"
            elif "对华立场" in section or "对华" in section or "china" in section.lower():
                if result["china_stance_summary"] is None:
                    result["china_stance_summary"] = ""
                result["china_stance_summary"] += line.strip() + "\n"
            elif "争议" in section or "controvers" in section.lower():
                if line.strip():
                    result["controversies"].append(line.strip())
    for k in ("core_positions", "china_stance_summary"):
        if result[k]:
            result[k] = result[k].strip()
    return result


def import_json_profiles(dry_run: bool = False, limit: int | None = None) -> dict[str, int]:
    stats = {
        "total_found": 0,
        "matched_by_bioguide": 0,
        "matched_by_name": 0,
        "unmatched": 0,
        "updated": 0,
        "errors": 0,
    }

    config = load_config()
    profiles = walk_profiles()
    stats["total_found"] = len(profiles)

    if limit:
        profiles = profiles[:limit]

    db = SessionLocal()
    try:
        members = db.query(Member).all()
        bioguide_map = {}
        for m in members:
            if m.bioguide_id:
                bioguide_map[m.bioguide_id.lower()] = m

        for pdata in profiles:
            try:
                bioguide = (pdata.get("bioguide") or "").strip().lower()
                name_en = (pdata.get("name_en") or "").strip()
                profile_md = pdata.get("profile_md") or ""
                parsed = _parse_profile_md(profile_md)

                member = bioguide_map.get(bioguide) if bioguide else None
                if not member and name_en:
                    for m in members:
                        if m.display_name and m.display_name.lower() == name_en.lower():
                            member = m
                            break
                    if not member:
                        for m in members:
                            if m.canonical_name and m.canonical_name.lower() == name_en.lower():
                                member = m
                                break
                    if member:
                        stats["matched_by_name"] += 1
                elif member:
                    stats["matched_by_bioguide"] += 1

                if not member:
                    stats["unmatched"] += 1
                    logger.warning(f"No match for: {pdata.get('name_en')} ({pdata.get('bioguide')})")
                    continue

                updates = {}
                if pdata.get("party"):
                    party_raw = pdata["party"]
                    if "共和" in party_raw or "Republican" in party_raw:
                        updates["party"] = "Republican"
                    elif "民主" in party_raw or "Democratic" in party_raw or "Democrat" in party_raw:
                        updates["party"] = "Democratic"
                    elif "独立" in party_raw or "Independent" in party_raw:
                        updates["party"] = "Independent"
                    else:
                        updates["party"] = party_raw
                if pdata.get("state"):
                    updates["state"] = pdata["state"]
                if pdata.get("chamber"):
                    c = pdata["chamber"].lower()
                    updates["chamber"] = "senate" if c == "senate" else "house"
                if pdata.get("type"):
                    updates["person_type"] = pdata["type"]
                if pdata.get("display_name"):
                    updates["display_name"] = pdata["display_name"]
                if pdata.get("canonical_name"):
                    updates["canonical_name"] = pdata["canonical_name"]
                elif pdata.get("name_cn"):
                    updates["canonical_name"] = pdata["name_cn"]
                elif pdata.get("name_en"):
                    updates["canonical_name"] = pdata["name_en"]

                committees = pdata.get("committees", {})
                if committees:
                    updates["committee_memberships"] = json.dumps(committees, ensure_ascii=False)

                tier = pdata.get("tier")
                if tier is not None:
                    updates["member_scope"] = str(tier)

                if parsed["core_positions"]:
                    updates["core_positions"] = parsed["core_positions"]
                if parsed["china_stance_summary"]:
                    updates["china_stance_summary"] = parsed["china_stance_summary"]
                if parsed["comprehensive_evaluation"]:
                    updates["comprehensive_evaluation"] = parsed["comprehensive_evaluation"]
                if parsed.get("controversies"):
                    updates["controversies"] = json.dumps(parsed["controversies"], ensure_ascii=False)

                career = pdata.get("career_summary") or parsed.get("career_history")
                if career:
                    updates["career_summary"] = json.dumps(career, ensure_ascii=False) if isinstance(career, list) else career

                if not updates:
                    continue

                updates["updated_at"] = datetime.now(timezone.utc)
                if not dry_run:
                    for k, v in updates.items():
                        setattr(member, k, v)
                    db.flush()
                stats["updated"] += 1

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Error importing {pdata.get('name_en')}: {e}")

        if not dry_run:
            db.commit()
    finally:
        db.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Import JSON profiles")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, no writes")
    parser.add_argument("--limit", type=int, help="Limit profiles to process")
    args = parser.parse_args()

    stats = import_json_profiles(dry_run=args.dry_run, limit=args.limit)

    print(f"\n=== Import Statistics ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"\nConfig: {load_config().get('generated_at', 'N/A')}")


if __name__ == "__main__":
    main()
