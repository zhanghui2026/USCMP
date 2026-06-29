"""Stress test mock data generator.

Generates large-scale mock data for stress testing:
- 535 members (full Congress)
- 3000 organizations
- 20 political entities
- 200 events
- 50000 edges (relationships)

Usage:
    python app/scripts/generate_stress_mock_data.py [--seed 42] [--clear-first]

Output files (in data/stress/):
    members.json, organizations.json, political_entities.json,
    events.json, claims.json, source_documents.json,
    relationships.json, stress_seed_summary.md
"""

import hashlib
import json
import os
import sys
import argparse
from datetime import date, timedelta
from pathlib import Path
from random import Random


US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

PARTIES = ["Democratic", "Republican", "Independent"]
CHAMBERS = ["house", "senate"]

FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan", "Jessica",
    "Sarah", "Karen", "Nancy", "Lisa", "Margaret", "Betty", "Sandra", "Ashley",
    "Christopher", "Daniel", "Paul", "Mark", "Donald", "George", "Kenneth", "Steven",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
]

ORG_PREFIXES = [
    "American", "National", "United", "International", "Global", "Federal", "State",
    "Pacific", "Atlantic", "Central", "Western", "Eastern", "Northern", "Southern",
    "Strategic", "Advanced", "Premier", "Elite", "Summit", "Heritage", "Liberty",
    "Freedom", "Justice", "Patriot", "Eagle", "Capitol", "Senate", "Congress",
]
ORG_TYPES = [
    "Group", "Association", "Institute", "Foundation", "Council", "Alliance",
    "Committee", "Coalition", "Federation", "Union", "Society", "Center",
    "Forum", "Network", "Partnership", "Trust",
]
ORG_INDUSTRIES = [
    "Defense", "Technology", "Finance", "Healthcare", "Energy", "Pharmaceuticals",
    "Agriculture", "Education", "Transportation", "Telecommunications",
    "Real Estate", "Insurance", "Media", "Retail", "Manufacturing", "Mining",
]

RELATION_TYPES = [
    "RECEIVED_CONTRIBUTION", "HOLDS_STOCK", "RECEIVED_LOBBYING_SUPPORT",
    "ALUMNI_OF", "RELATED_TO", "FORMER_EMPLOYER", "FUTURE_EMPLOYER",
    "SPONSORED_BILL", "COSPONSORED_BILL", "VOTED_FOR", "VOTED_AGAINST",
    "SERVED_ON_COMMITTEE", "MADE_STATEMENT", "PARTICIPATED_IN",
    "ASSOCIATED_WITH_EVENT", "HAS_CLAIM",
]

EVENT_TYPES = [
    "bill_introduced", "hearing", "vote", "committee_meeting",
    "press_conference", "investigation", "executive_order",
]

COMMITTEE_NAMES = [
    "Armed Services", "Foreign Relations", "Intelligence", "Judiciary",
    "Finance", "Appropriations", "Budget", "Commerce", "Energy",
    "Homeland Security", "Agriculture", "Education", "Veterans Affairs",
    "Health", "Rules", "Ethics", "Small Business", "Transportation",
]

CLAIM_TYPES = [
    "financial_contribution", "stock_ownership", "lobbying_activity",
    "employment_history", "education_background", "bill_sponsorship",
    "vote_record", "committee_service", "public_statement",
    "event_participation",
]


def _hex_id(prefix: str, seed: str, index: int) -> str:
    h = hashlib.sha256(f"{seed}:{index}".encode()).hexdigest()[:8]
    return f"{prefix}_{h}"


def generate_stress_mock_data(seed: int = 42, output_dir: str | None = None):
    rng = Random(seed)

    if output_dir is None:
        output_dir = str(Path(__file__).resolve().parent.parent.parent / "data" / "stress")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Generating stress test data with seed={seed}...")

    # ── Members (535: 435 House + 100 Senate) ──
    print("  Generating 535 members...")
    members = []
    for i in range(535):
        chamber = "senate" if i < 100 else "house"
        state_idx = i % 50
        party = PARTIES[i % 3] if chamber == "senate" else PARTIES[rng.randint(0, 1)]
        district = None if chamber == "senate" else rng.randint(1, 53)
        congresses = []
        for c in [117, 118, 119]:
            if rng.random() < 0.7:
                congresses.append(c)
        committees = []
        for _ in range(rng.randint(0, 4)):
            committees.append({
                "committee": rng.choice(COMMITTEE_NAMES),
                "role": rng.choice(["Chair", "Ranking Member", "Member"]),
                "congress": rng.choice(congresses) if congresses else 119,
                "committee_type": "standing",
            })
        members.append({
            "id": _hex_id("person", "stress", i),
            "canonical_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            "display_name": f"{'Sen.' if chamber == 'senate' else 'Rep.'} {rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            "aliases": [],
            "person_type": "politician",
            "party": party,
            "chamber": chamber,
            "state": US_STATES[state_idx],
            "district": str(district) if district else None,
            "congress": rng.choice(congresses) if congresses else 119,
            "bioguide_id": f"B{str(i).zfill(6)}",
            "govtrack_id": str(400000 + i),
            "fec_candidate_id": f"H{str(i).zfill(6)}",
            "opensecrets_id": f"N{str(i).zfill(9)}",
            "top_contributors": [
                {
                    "organization": f"{rng.choice(ORG_PREFIXES)} {rng.choice(ORG_TYPES)}",
                    "amount": rng.randint(5000, 500000),
                }
                for _ in range(rng.randint(1, 5))
            ],
            "top_holdings": [
                {
                    "company": f"{rng.choice(ORG_PREFIXES)} Corp",
                    "ticker": f"{''.join(rng.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=rng.randint(2, 4)))}",
                    "amount_min": rng.randint(1000, 50000),
                    "amount_max": rng.randint(50000, 500000),
                }
                for _ in range(rng.randint(0, 3))
            ],
            "committee_memberships": committees,
            "career_summary": [
                {
                    "position": rng.choice(["Attorney", "Business Executive", "Professor", "Physician", "Engineer"]),
                    "organization": f"{rng.choice(ORG_PREFIXES)} {rng.choice(ORG_TYPES)}",
                }
                for _ in range(rng.randint(0, 3))
            ],
            "china_stance_summary": rng.choice([
                "对中国采取强硬立场，支持多项制裁法案。",
                "主张在贸易和人权问题上对中国施压。",
                "支持与中国的经贸合作，但关注知识产权问题。",
                "在涉华议题上立场较为温和。",
            ]),
            "controversies": [
                {
                    "type": rng.choice(["allegation", "investigation", "lawsuit"]),
                    "description": f"Mock controversy #{_ + 1} for stress testing",
                    "source_name": f"{rng.choice(ORG_PREFIXES)} Times",
                    "status": rng.choice(["pending", "dismissed", "settled"]),
                    "needs_review": rng.choice([True, False]),
                }
                for _ in range(rng.randint(0, 2))
            ],
        })

    # ── Organizations (3000) ──
    print("  Generating 3000 organizations...")
    organizations = []
    for i in range(3000):
        organizations.append({
            "id": _hex_id("org", "stress", i),
            "canonical_name": f"{rng.choice(ORG_PREFIXES)} {rng.choice(ORG_TYPES)}",
            "display_name": f"{rng.choice(ORG_PREFIXES)} {rng.choice(ORG_TYPES)} of {rng.choice(US_STATES)}",
            "entity_type": rng.choice(["corporation", "nonprofit", "pac", "lobbying_firm", "think_tank"]),
            "industry": rng.choice(ORG_INDUSTRIES),
            "ticker": rng.choice([None, f"{''.join(rng.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=rng.randint(2, 4)))}"]),
            "country": "US",
        })

    # ── Political Entities (20) ──
    print("  Generating 20 political entities...")
    political_entities = []
    for i in range(20):
        political_entities.append({
            "id": _hex_id("pol", "stress", i),
            "name": f"{rng.choice(US_STATES)} {rng.choice(['State Legislature', 'Governor Office', 'Department of State', 'Election Commission'])}",
            "entity_type": rng.choice(["state_government", "federal_agency", "regulatory_body"]),
            "chamber": None,
            "state": rng.choice(US_STATES),
            "congress": rng.choice([117, 118, 119]),
        })

    # ── Events (200) ──
    print("  Generating 200 events...")
    events = []
    base_date = date(2019, 1, 1)
    for i in range(200):
        ev_date = base_date + timedelta(days=rng.randint(0, 2500))
        events.append({
            "id": _hex_id("event", "stress", i),
            "event_type": rng.choice(EVENT_TYPES),
            "title": f"{rng.choice(EVENT_TYPES).replace('_', ' ').title()} #{i}",
            "description": f"Stress test event {i} for load testing.",
            "event_date": ev_date.isoformat(),
            "congress": rng.choice([117, 118, 119]),
            "source_reliability": "mock",
        })

    # ── Claims (5000) ──
    print("  Generating 5000 claims...")
    claims = []
    for i in range(5000):
        rel_type = rng.choice(RELATION_TYPES)
        subject_type = "Person" if rel_type in [
            "RECEIVED_CONTRIBUTION", "HOLDS_STOCK", "ALUMNI_OF",
            "FORMER_EMPLOYER", "FUTURE_EMPLOYER",
        ] else "Organization"
        claims.append({
            "claim_id": _hex_id("claim", "stress", i),
            "claim_type": rng.choice(CLAIM_TYPES),
            "subject_id": _hex_id("person", "stress", rng.randint(0, 534)),
            "object_id": _hex_id("org", "stress", rng.randint(0, 2999)),
            "relation_type": rel_type,
            "claim_text": f"Stress test claim {i}: relationship between entities.",
            "original_snippet": f"Mock snippet for claim {i}",
            "confidence_score": round(rng.uniform(0.3, 1.0), 2),
            "extraction_method": "mock",
            "source_reliability": "mock",
            "review_status": "needs_review" if rng.random() < 0.25 else "verified",
        })

    # ── Source Documents (5000) ──
    print("  Generating 5000 source documents...")
    source_documents = []
    for i in range(5000):
        doc_date = base_date + timedelta(days=rng.randint(0, 2500))
        source_documents.append({
            "id": _hex_id("sdoc", "stress", i),
            "source_name": f"{rng.choice(ORG_PREFIXES)} {rng.choice(['Times', 'Chronicle', 'Post', 'Gazette', 'Journal'])}",
            "source_url": f"https://example.com/docs/stress_{i}",
            "title": f"Document Title {i}",
            "publisher": f"{rng.choice(ORG_PREFIXES)} Publishing",
            "published_at": doc_date.isoformat(),
            "collected_at": (doc_date + timedelta(days=rng.randint(1, 30))).isoformat(),
            "document_type": rng.choice(["news_article", "report", "filing", "transcript", "press_release"]),
            "snippet": f"Mock document snippet for stress test doc {i}.",
            "source_reliability": "mock",
            "license_note": None,
        })

    # ── Relationships (50000 edges) ──
    print("  Generating 50000 relationships...")
    relationships = []
    for i in range(50000):
        claim_idx = i % 5000
        sd_idx = i % 5000
        rel_type = rng.choice(RELATION_TYPES)
        mock_claim_id = _hex_id("claim", "stress", claim_idx)
        mock_sdoc_id = _hex_id("sdoc", "stress", sd_idx)
        confidence = round(rng.uniform(0.3, 1.0), 2)
        is_low = confidence < 0.5
        relationships.append({
            "source": _hex_id("person", "stress", rng.randint(0, 534)),
            "target": _hex_id("org", "stress", rng.randint(0, 2999)),
            "type": rel_type,
            "claim_id": mock_claim_id,
            "source_doc_id": mock_sdoc_id,
            "confidence_score": confidence,
            "is_low_confidence": is_low,
        })

    # Write output files
    files = {
        "members.json": members,
        "organizations.json": organizations,
        "political_entities.json": political_entities,
        "events.json": events,
        "claims.json": claims,
        "source_documents.json": source_documents,
        "relationships.json": relationships,
    }

    for filename, data in files.items():
        path = os.path.join(output_dir, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  Wrote {filename} ({len(data)} records)")

    # Generate summary
    low_conf_count = sum(1 for r in relationships if r["is_low_confidence"])
    summary = f"""# Stress Mock Data Summary

- **Seed**: {seed}
- **Members**: {len(members)}
- **Organizations**: {len(organizations)}
- **Political Entities**: {len(political_entities)}
- **Events**: {len(events)}
- **Claims**: {len(claims)}
- **Source Documents**: {len(source_documents)}
- **Relationships**: {len(relationships)}
- **Low-confidence Edges**: {low_conf_count} ({100*low_conf_count/max(1,len(relationships)):.1f}%)
- **Generated At**: {date.today().isoformat()}

## Data Quality Flags
- All data marked `source_reliability="mock"`
- All claims marked `extraction_method="mock"`
- {low_conf_count} edges below confidence threshold (0.5)

## Usage
```bash
# Seed to PostgreSQL + Neo4j
python app/scripts/seed_stress_data.py

# Or load manually
python app/scripts/seed_stress_data.py --members data/stress/members.json --skip-neo4j
```
"""
    summary_path = os.path.join(output_dir, "stress_seed_summary.md")
    with open(summary_path, "w") as f:
        f.write(summary)
    print(f"  Wrote stress_seed_summary.md")

    print(f"\nDone! {len(members)} members, {len(organizations)} orgs, {len(relationships)} edges")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate stress test mock data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    args = parser.parse_args()
    generate_stress_mock_data(seed=args.seed, output_dir=args.output)
