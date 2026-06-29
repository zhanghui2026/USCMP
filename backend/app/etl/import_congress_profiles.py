"""Import congress member profiles from parsed Markdown files.

Usage:
    python -m app.etl.import_congress_profiles [--dry-run] [--limit N]
"""

import argparse
import re
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import text, Column, Text
from sqlalchemy.orm import Session

from app.db.postgres import SessionLocal, engine, Base
from app.models.sqlalchemy.models import Member
from app.etl.parse_congress_profiles import parse_all_members, build_name_to_id_mapping, match_member_to_id


def ensure_columns():
    """Add new columns if they don't exist."""
    with engine.connect() as conn:
        # Check and add core_positions column
        try:
            conn.execute(text("SELECT core_positions FROM members LIMIT 1"))
        except Exception:
            conn.rollback()
            try:
                conn.execute(text("ALTER TABLE members ADD COLUMN core_positions TEXT"))
                conn.commit()
                print("Added core_positions column")
            except Exception as e:
                conn.rollback()
                print(f"core_positions column: {e}")

        # Check and add comprehensive_evaluation column
        try:
            conn.execute(text("SELECT comprehensive_evaluation FROM members LIMIT 1"))
        except Exception:
            conn.rollback()
            try:
                conn.execute(text("ALTER TABLE members ADD COLUMN comprehensive_evaluation TEXT"))
                conn.commit()
                print("Added comprehensive_evaluation column")
            except Exception as e:
                conn.rollback()
                print(f"comprehensive_evaluation column: {e}")


def normalize_name(name: str) -> str:
    """Normalize a name for matching."""
    if not name:
        return ''
    
    # Remove titles
    name = re.sub(r'^(Rep\.|Sen\.|Mr\.|Mrs\.|Ms\.|Dr\.)\s+', '', name)
    
    # Remove suffixes
    name = re.sub(r'\s+(Jr\.|Sr\.|III|II|IV)$', '', name)
    
    # Remove Chinese characters
    name = re.sub(r'[\u4e00-\u9fff]+', '', name)
    
    # Remove middle initials (single letters followed by period)
    # "Mark R. Warner" -> "Mark Warner"
    name = re.sub(r'\s+[A-Z]\.\s+', ' ', name)
    
    # Remove accents: Mónica -> Monica
    import unicodedata
    name = ''.join(c for c in unicodedata.normalize('NFD', name)
                   if unicodedata.category(c) != 'Mn')
    
    # Remove extra whitespace
    name = ' '.join(name.split())
    
    return name.strip()


# Common first name variations
NAME_VARIATIONS = {
    'dan': ['daniel', 'danny'],
    'daniel': ['dan', 'danny'],
    'chris': ['christopher', 'christian'],
    'christopher': ['chris', 'christian'],
    'rich': ['richard', 'rick', 'ricky'],
    'richard': ['rich', 'rick', 'ricky'],
    'bob': ['robert', 'bobby'],
    'robert': ['bob', 'bobby'],
    'bill': ['william', 'will', 'willy'],
    'william': ['bill', 'will', 'willy'],
    'jim': ['james', 'jimmy'],
    'james': ['jim', 'jimmy'],
    'mike': ['michael', 'mikey'],
    'michael': ['mike', 'mikey'],
    'tom': ['thomas', 'tommy'],
    'thomas': ['tom', 'tommy'],
    'greg': ['gregory', 'gregg'],
    'gregory': ['greg', 'gregg'],
    'tony': ['anthony'],
    'anthony': ['tony'],
    'joe': ['joseph', 'joey'],
    'joseph': ['joe', 'joey'],
    'john': ['jonathan', 'johnny'],
    'jonathan': ['john', 'johnny'],
    'matt': ['matthew', 'matty'],
    'matthew': ['matt', 'matty'],
    'nick': ['nicholas', 'nicky'],
    'nicholas': ['nick', 'nicky'],
    'pat': ['patrick', 'patty'],
    'patrick': ['pat', 'patty'],
    'sam': ['samuel', 'sammy'],
    'samuel': ['sam', 'sammy'],
    'steve': ['steven', 'stephen', 'stevie'],
    'steven': ['steve', 'stephen', 'stevie'],
    'stephen': ['steve', 'steven', 'stevie'],
    'ted': ['theodore', 'teddy'],
    'theodore': ['ted', 'teddy'],
    'tim': ['timothy', 'timmy'],
    'timothy': ['tim', 'timmy'],
    'ben': ['benjamin', 'benny'],
    'benjamin': ['ben', 'benny'],
    'alex': ['alexander', 'alexandra'],
    'alexander': ['alex'],
    'alexandra': ['alex'],
    'andy': ['andrew'],
    'andrew': ['andy'],
    'charlie': ['charles'],
    'charles': ['charlie'],
    'dave': ['david'],
    'david': ['dave'],
    'ed': ['edward', 'eddie'],
    'edward': ['ed', 'eddie'],
    'frank': ['francis', 'franklin'],
    'francis': ['frank'],
    'franklin': ['frank'],
    'fred': ['frederick', 'freddy'],
    'frederick': ['fred', 'freddy'],
    'henry': ['hank', 'harry'],
    'hank': ['henry', 'harry'],
    'harry': ['henry', 'hank'],
    'jack': ['john', 'johnny'],
    'jeff': ['jeffrey', 'geoffrey'],
    'jeffrey': ['jeff'],
    'geoffrey': ['jeff'],
    'jerry': ['gerald', 'jerome'],
    'gerald': ['jerry'],
    'jerome': ['jerry'],
    'josh': ['joshua'],
    'joshua': ['josh'],
    'ken': ['kenneth', 'kenny'],
    'kenneth': ['ken', 'kenny'],
    'kevin': ['kev'],
    'larry': ['lawrence', 'lars'],
    'lawrence': ['larry'],
    'leo': ['leonard', 'leonardo'],
    'leonard': ['leo'],
    'mark': ['marcus'],
    'marcus': ['mark'],
    'nat': ['nathan', 'nathaniel'],
    'nathan': ['nat'],
    'nathaniel': ['nat'],
    'neil': ['neal'],
    'neal': ['neil'],
    'peter': ['pete'],
    'pete': ['peter'],
    'phil': ['phillip', 'philip'],
    'phillip': ['phil'],
    'philip': ['phil'],
    'ray': ['raymond'],
    'raymond': ['ray'],
    'ron': ['ronald'],
    'ronald': ['ron'],
    'scott': ['scotty'],
    'sean': ['shawn'],
    'shawn': ['sean'],
    'terry': ['terrence', 'terence'],
    'terrence': ['terry'],
    'terence': ['terry'],
    'todd': ['tod'],
    'tom': ['thomas'],
    'thomas': ['tom'],
    'tony': ['anthony'],
    'anthony': ['tony'],
    'vic': ['victor'],
    'victor': ['vic'],
    'vincent': ['vinny', 'vince'],
    'walter': ['walt'],
    'walt': ['walter'],
    'zach': ['zachary', 'zack'],
    'zachary': ['zach', 'zack'],
    # Additional variations
    'alejandro': ['alex'],
    'alex': ['alejandro'],
    'gregorio': ['greg', 'gregory'],
    'greg': ['gregorio', 'gregory'],
    'gregory': ['greg', 'gregorio', 'gregg'],
    'valerie': ['val'],
    'val': ['valerie'],
    'nicolas': ['nick'],
    'nick': ['nicolas'],
    'robert': ['rob', 'bob'],
    'rob': ['robert', 'bob'],
    'monica': ['monika'],
    'monika': ['monica'],
}


def get_name_variations(first_name: str) -> list:
    """Get variations of a first name."""
    variations = [first_name.lower()]
    if first_name.lower() in NAME_VARIATIONS:
        variations.extend(NAME_VARIATIONS[first_name.lower()])
    return variations


def build_fuzzy_name_mapping(db_members: list) -> dict:
    """Build fuzzy name mapping for better matching."""
    mapping = {}
    
    for m in db_members:
        # Add various name forms
        names_to_try = []
        
        if m.display_name:
            names_to_try.append(m.display_name)
            names_to_try.append(normalize_name(m.display_name))
            
            # Also try without middle initial
            clean = re.sub(r'\s+[A-Z]\.\s+', ' ', m.display_name)
            names_to_try.append(clean)
            names_to_try.append(normalize_name(clean))
            
            # Also try without middle initial at start (e.g., "W. Gregory Steube" -> "Gregory Steube")
            clean_start = re.sub(r'^[A-Z]\.\s+', '', m.display_name)
            names_to_try.append(clean_start)
            names_to_try.append(normalize_name(clean_start))
            
            # Try without suffix
            no_suffix = re.sub(r',?\s+(Jr\.|Sr\.|III|II|IV)$', '', m.display_name)
            names_to_try.append(no_suffix)
            names_to_try.append(normalize_name(no_suffix))
            
            # Try with name variations
            parts = no_suffix.split()
            if len(parts) >= 2:
                first_name = parts[0]
                last_name = parts[-1]
                for variation in get_name_variations(first_name):
                    names_to_try.append(f"{variation} {last_name}")
        
        if m.canonical_name:
            names_to_try.append(m.canonical_name)
            names_to_try.append(normalize_name(m.canonical_name))
        
        # Try "First Last" -> "Last, First" conversion
        if m.display_name:
            parts = m.display_name.split()
            if len(parts) >= 2:
                # "Mike Johnson" -> "Johnson, Mike"
                last_first = f"{parts[-1]}, {' '.join(parts[:-1])}"
                names_to_try.append(last_first)
                names_to_try.append(normalize_name(last_first))
        
        for name in names_to_try:
            if name:
                mapping[name.lower()] = m.id
    
    return mapping


def match_parsed_to_db(parsed: dict, name_mapping: dict) -> Optional[str]:
    """Match a parsed member to a database member."""
    display_name = parsed.get('display_name') or ''
    full_name = parsed.get('full_name') or ''
    
    if not display_name and not full_name:
        return None
    
    # Handle "Name1 / Name2" format
    if '/' in display_name:
        names = [n.strip() for n in display_name.split('/')]
        for name in names:
            if name:
                key = name.lower()
                if key in name_mapping:
                    return name_mapping[key]
                normalized = normalize_name(name).lower()
                if normalized in name_mapping:
                    return name_mapping[normalized]
    
    # Try direct match
    for name in [display_name, full_name]:
        if name:
            key = name.lower()
            if key in name_mapping:
                return name_mapping[key]
    
    # Try normalized match
    for name in [display_name, full_name]:
        if name:
            normalized = normalize_name(name).lower()
            if normalized in name_mapping:
                return name_mapping[normalized]
    
    # Try last name + first name match
    if display_name:
        parts = display_name.split()
        if len(parts) >= 2:
            # Try "Johnson, Mike"
            last_first = f"{parts[-1]}, {' '.join(parts[:-1])}".lower()
            if last_first in name_mapping:
                return name_mapping[last_first]
            
            # Try just last name (if unique)
            last_name = parts[-1].lower()
            matches = [mid for n, mid in name_mapping.items() if n.endswith(last_name)]
            if len(matches) == 1:
                return matches[0]
    
    # Try with first name variations
    if display_name:
        parts = display_name.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = parts[-1]
            for variation in get_name_variations(first_name):
                variant_name = f"{variation} {last_name}".lower()
                if variant_name in name_mapping:
                    return name_mapping[variant_name]
    
    return None


def import_profiles(dry_run: bool = False, limit: Optional[int] = None) -> dict:
    """Import congress member profiles."""
    stats = {
        'total_parsed': 0,
        'matched': 0,
        'unmatched': 0,
        'updated_china_stance': 0,
        'updated_core_positions': 0,
        'updated_comprehensive_evaluation': 0,
        'updated_career_summary': 0,
        'updated_controversies': 0,
        'unmatched_names': [],
    }

    # Parse all member files - try multiple paths
    base_dir = Path('data/congress-profiles')
    if not base_dir.exists():
        base_dir = Path('../data/congress-profiles')
    if not base_dir.exists():
        base_dir = Path('../../data/congress-profiles')
    
    parsed_members = parse_all_members(base_dir)
    stats['total_parsed'] = len(parsed_members)

    if limit:
        parsed_members = parsed_members[:limit]

    # Get database members
    with SessionLocal() as db:
        db_members = db.query(Member).filter(
            Member.member_scope == 'current'
        ).all()

        # Build name mapping
        name_mapping = build_fuzzy_name_mapping(db_members)

        # Committee comparison
        db_committees = set()
        file_committees = set()
        committee_diff = []

        for m in db_members:
            if m.committee_memberships:
                for cm in m.committee_memberships:
                    db_committees.add(cm.get('committee', ''))

        for parsed in parsed_members:
            if parsed.get('committee_from_dir'):
                file_committees.add(parsed['committee_from_dir'])

        # Import each member
        for parsed in parsed_members:
            member_id = match_parsed_to_db(parsed, name_mapping)

            if not member_id:
                stats['unmatched'] += 1
                stats['unmatched_names'].append(parsed.get('display_name', 'Unknown'))
                continue

            stats['matched'] += 1

            if dry_run:
                continue

            # Get database member
            member = db.query(Member).filter(Member.id == member_id).first()
            if not member:
                continue

            # Update china_stance_summary (only if empty)
            if parsed.get('china_stance') and not member.china_stance_summary:
                member.china_stance_summary = parsed['china_stance']
                stats['updated_china_stance'] += 1

            # Update core_positions (new field)
            if parsed.get('core_positions'):
                member.core_positions = parsed['core_positions']
                stats['updated_core_positions'] += 1

            # Update comprehensive_evaluation (new field)
            if parsed.get('comprehensive_evaluation'):
                member.comprehensive_evaluation = parsed['comprehensive_evaluation']
                stats['updated_comprehensive_evaluation'] += 1

            # Update career_summary from career_history and policy_positions
            if parsed.get('career_history') or parsed.get('policy_positions'):
                existing_career = member.career_summary or []
                # Check if profile data already exists
                has_profile = any(c.get('source') == 'congress_profile' for c in existing_career)
                if not has_profile:
                    career_entry = {
                        'source': 'congress_profile',
                        'career_history': parsed.get('career_history', ''),
                        'policy_positions': parsed.get('policy_positions', ''),
                    }
                    existing_career.append(career_entry)
                    member.career_summary = existing_career
                    stats['updated_career_summary'] += 1

            # Update controversies (append media reports)
            if parsed.get('media_reports'):
                existing = member.controversies or []
                # Check if media reports already exist
                has_media = any(c.get('type') == 'media_report' for c in existing)
                if not has_media:
                    existing.append({
                        'type': 'media_report',
                        'description': parsed['media_reports'][:500],
                        'source_name': 'Congress Profiles Collection',
                        'status': 'collected',
                        'needs_review': True,
                    })
                    member.controversies = existing
                    stats['updated_controversies'] += 1

        if not dry_run:
            db.commit()

        # Committee comparison
        only_in_db = db_committees - file_committees
        only_in_file = file_committees - db_committees
        common = db_committees & file_committees

        committee_diff = {
            'common': sorted(list(common)),
            'only_in_db': sorted(list(only_in_db)),
            'only_in_file': sorted(list(only_in_file)),
        }

    return stats, committee_diff


def main():
    parser = argparse.ArgumentParser(description="Import congress member profiles")
    parser.add_argument("--dry-run", action="store_true", help="Only count, don't write")
    parser.add_argument("--limit", type=int, help="Limit number of members to import")
    args = parser.parse_args()

    print("Ensuring database columns exist...")
    if not args.dry_run:
        ensure_columns()

    print("Importing congress member profiles...")
    stats, committee_diff = import_profiles(dry_run=args.dry_run, limit=args.limit)

    print(f"\n{'='*60}")
    print("IMPORT RESULTS")
    print(f"{'='*60}")
    print(f"Total parsed: {stats['total_parsed']}")
    print(f"Matched to DB: {stats['matched']}")
    print(f"Unmatched: {stats['unmatched']}")
    print(f"\nUpdated fields:")
    print(f"  china_stance_summary: {stats['updated_china_stance']}")
    print(f"  core_positions: {stats['updated_core_positions']}")
    print(f"  comprehensive_evaluation: {stats['updated_comprehensive_evaluation']}")
    print(f"  career_summary: {stats['updated_career_summary']}")
    print(f"  controversies (media): {stats['updated_controversies']}")

    print(f"\n{'='*60}")
    print("COMMITTEE COMPARISON")
    print(f"{'='*60}")
    print(f"Common committees: {len(committee_diff['common'])}")
    print(f"Only in DB: {len(committee_diff['only_in_db'])}")
    print(f"Only in file: {len(committee_diff['only_in_file'])}")

    if committee_diff['only_in_db']:
        print(f"\nCommittees only in DB (not in files):")
        for c in committee_diff['only_in_db']:
            print(f"  - {c}")

    if committee_diff['only_in_file']:
        print(f"\nCommittees only in files (not in DB):")
        for c in committee_diff['only_in_file']:
            print(f"  - {c}")

    if stats['unmatched_names']:
        print(f"\nUnmatched names (first 20):")
        for name in stats['unmatched_names'][:20]:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
