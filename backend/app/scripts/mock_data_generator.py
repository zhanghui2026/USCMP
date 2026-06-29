"""Mock data generator for Phase 1 MVP.

Generates all mock entities with fixed random seed for reproducibility.
All data is marked with source_reliability='mock' and extraction_method='mock'.
"""

import random
import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

random.seed(42)


# ---------------------------------------------------------------------------
# Static data pools
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Barbara",
    "Elizabeth", "Susan", "Jessica", "Sarah", "Karen", "Nancy", "Margaret",
    "Lisa", "Betty", "Dorothy", "Sandra", "Ashley", "Kimberly", "Donna",
    "Emily", "Michelle", "Carol", "Amanda", "Melissa", "Deborah", "Stephanie",
    "Rebecca", "Laura", "Sharon", "Cynthia", "Kathleen", "Amy", "Angela",
    "Shirley", "Anna", "Brenda", "Pamela", "Emma", "Nicole", "Helen",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts",
]

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

COMMITTEES = [
    "Agriculture", "Appropriations", "Armed Services", "Banking, Housing, and Urban Affairs",
    "Budget", "Commerce, Science, and Transportation", "Energy and Natural Resources",
    "Environment and Public Works", "Finance", "Foreign Relations",
    "Health, Education, Labor, and Pensions", "Homeland Security and Governmental Affairs",
    "Indian Affairs", "Intelligence", "Judiciary", "Rules and Administration",
    "Small Business and Entrepreneurship", "Veterans' Affairs",
    "Select Committee on Intelligence", "Select Committee on Ethics",
    "Joint Economic Committee", "Select Committee on the Climate Crisis",
    "Subcommittee on Cybersecurity", "Subcommittee on East Asia",
]

INDUSTRIES = [
    "Defense", "Technology", "Pharmaceuticals", "Energy", "Finance",
    "Healthcare", "Agriculture", "Telecommunications", "Aerospace",
    "Real Estate", "Insurance", "Automotive", "Retail", "Media",
    "Transportation", "Construction", "Education", "Entertainment",
    "Chemical", "Mining",
]

ORG_PREFIXES = [
    "American", "National", "United", "Global", "International",
    "Pacific", "Atlantic", "Continental", "Federal", "Strategic",
]

ORG_SUFFIXES = [
    "Corporation", "Group", "Industries", "Technologies", "Partners",
    "Associates", "Holdings", "Enterprises", "Solutions", "Systems",
]

EVENT_TEMPLATES = [
    {
        "type": "bill",
        "titles": [
            "National Defense Authorization Act for Fiscal Year {year}",
            "Affordable Healthcare Enhancement Act",
            "Clean Energy Innovation Act",
            "Border Security and Immigration Reform Act",
            "Digital Privacy Protection Act",
            "Infrastructure Investment and Jobs Act",
            "Tax Reform and Simplification Act",
            "Cybersecurity Enhancement Act",
            "Veterans Healthcare Improvement Act",
            "Education Equity and Access Act",
        ],
    },
    {
        "type": "hearing",
        "titles": [
            "Hearing on Semiconductor Supply Chain Security",
            "Hearing on China's Trade Practices",
            "Hearing on Social Media Content Moderation",
            "Hearing on Climate Change Preparedness",
            "Hearing on Military Readiness in the Indo-Pacific",
            "Hearing on Big Tech Market Power",
            "Hearing on Pharmaceutical Drug Pricing",
            "Hearing on Election Security",
            "Hearing on Artificial Intelligence Regulation",
            "Hearing on Energy Independence",
        ],
    },
    {
        "type": "stock_trade",
        "titles": [
            "Stock Purchase: {company} ({ticker})",
            "Stock Sale: {company} ({ticker})",
            "Option Exercise: {company} ({ticker})",
        ],
    },
]

CONTROVERSY_ALLEGATIONS = [
    "Alleged insider trading based on congressional briefings",
    "Investigation into campaign finance irregularities",
    "Lawsuit filed regarding conflict of interest in committee oversight",
    "Ethics committee review of undisclosed stock transactions",
    "Alleged violation of STOCK Act disclosure requirements",
    "Investigation into lobbying connections with former staff",
    "Civil suit regarding discrimination allegations",
    "Ethics inquiry into use of official position for personal benefit",
]


def _hash_id(prefix: str, *args) -> str:
    """Generate a deterministic ID from arguments."""
    raw = "|".join(str(a) for a in (prefix,) + args)
    return f"{prefix}_{hashlib.md5(raw.encode()).hexdigest()[:8]}"


def _pick(items, index):
    return items[index % len(items)]


def _gen_date(base: date, offset_days: int) -> date:
    return base + timedelta(days=offset_days)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class MockDataGenerator:
    """Generates all mock data for Phase 1 MVP."""

    def __init__(self):
        self.members: list[dict] = []
        self.orgs: list[dict] = []
        self.pol_entities: list[dict] = []
        self.events: list[dict] = []
        self.claims: list[dict] = []
        self.source_docs: list[dict] = []
        self.relationships: list[dict] = []

    def generate_all(self):
        self._gen_members(count=50)
        self._gen_organizations(count=100)
        self._gen_political_entities(count=20)
        self._gen_events(count=100)
        self._gen_source_docs(count=500)
        self._gen_relationships()

    # ---- Members ----
    def _gen_members(self, count: int):
        for i in range(count):
            name = f"{_pick(FIRST_NAMES, i)} {_pick(LAST_NAMES, i)}"
            party = _pick(["Democratic", "Republican", "Independent"], i)
            chamber = "senate" if i < 17 else "house"
            state = _pick(STATES, i)
            congress = _pick([117, 118, 119], i)
            member_id = _hash_id("person", name, state, chamber)
            bioguide_id = "MOCK" + str(i).zfill(6)
            govtrack_id = str(400000 + i)
            fec_id = "H" + str(i).zfill(2) + "TX" + str(i).zfill(2)
            prefix = "Sen." if chamber == "senate" else "Rep."
            display_name = prefix + " " + name

            committees = []
            for j in range(random.randint(1, 4)):
                c_idx = (i * 3 + j) % len(COMMITTEES)
                committees.append({
                    "committee": COMMITTEES[c_idx],
                    "role": _pick(["Chair", "Ranking Member", "Member"], j),
                    "committee_type": _pick(["committee", "subcommittee"], j),
                    "congress": congress,
                    "start_date": str(_gen_date(date(2019, 1, 3), i * 7)),
                })

            top_contrib = []
            for j in range(5):
                org_id = _hash_id("org", "mock_contrib", i, j)
                top_contrib.append({
                    "organization": f"Mock Contributor {i}-{j}",
                    "organization_id": org_id,
                    "amount": random.randint(10000, 500000),
                    "cycle": congress,
                })

            top_hold = []
            for j in range(5):
                ticker = f"MCK{i % 26 + 65}{j}"
                top_hold.append({
                    "company": f"Mock Holdings Corp {i}-{j}",
                    "ticker": ticker,
                    "amount_min": random.randint(15000, 100000),
                    "amount_max": random.randint(100000, 500000),
                })

            controversies = []
            if i % 4 == 0:
                for j in range(random.randint(1, 3)):
                    c_idx = (i + j) % len(CONTROVERSY_ALLEGATIONS)
                    controversies.append({
                        "type": _pick(["allegation", "investigation", "lawsuit"], j),
                        "description": CONTROVERSY_ALLEGATIONS[c_idx],
                        "source_name": f"Mock News Source {j + 1}",
                        "source_url": f"https://mock-news-{j+1}.example.com/article/{i}",
                        "published_at": str(_gen_date(date(2020, 1, 1), i * 30 + j * 10)),
                        "snippet": f"Mock snippet about investigation of {name}...",
                        "status": _pick(["ongoing", "resolved", "dismissed"], j),
                        "official_confirmed": False,
                        "judicial_confirmed": False,
                        "needs_review": True,
                    })

            aliases = []
            if i % 5 == 0:
                aliases.append(f"{_pick(FIRST_NAMES, i+50)} {name.split()[1]}")

            china_stance = ""
            if i % 3 == 0:
                china_stance = (
                    f"公开资料显示，{name}参议员参与了多项涉华立法，"
                    f"在涉华贸易和军事议题上持较强硬立场。该记录尚需人工复核。"
                )

            member = {
                "id": member_id,
                "canonical_name": name,
                "display_name": display_name,
                "aliases": aliases,
                "person_type": "senator" if chamber == "senate" else "representative",
                "party": party,
                "chamber": chamber,
                "state": state,
                "district": (
                    f"{state}-{str(i % 32 + 1).zfill(2)}" if chamber == "house" else None
                ),
                "official_photo_url": None,
                "bioguide_id": bioguide_id,
                "govtrack_id": govtrack_id,
                "fec_candidate_id": fec_id,
                "opensecrets_id": f"N{str(i).zfill(9)}",
                "top_contributors": top_contrib,
                "top_holdings": top_hold,
                "committee_memberships": committees,
                "career_summary": [
                    {
                        "position": f"Position {k}",
                        "organization": f"Organization {i}-{k}",
                        "start_date": str(date(2000 + k, 1, 1)),
                        "end_date": str(date(2010 + k, 12, 31)),
                    }
                    for k in range(random.randint(1, 4))
                ],
                "china_stance_summary": china_stance,
                "controversies": controversies,
                "source": "mock",
                "source_reliability": "mock",
                "extraction_method": "mock",
                "congress": congress,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "latest_term_start": None,
                "latest_term_end": None,
                "official_ids": {},
                "member_scope": "mock",
                "is_current": True,
            }
            self.members.append(member)

    # ---- Organizations ----
    def _gen_organizations(self, count: int):
        for i in range(count):
            prefix = _pick(ORG_PREFIXES, i // 10)
            suffix = _pick(ORG_SUFFIXES, i % 10)
            industry = _pick(INDUSTRIES, i % 20)
            name = f"{prefix} {industry} {suffix}"
            org_id = _hash_id("org", name, i)
            entity_type = _pick([
                "corporation", "pac", "super_pac", "think_tank",
                "lobbying_firm", "trade_association", "nonprofit",
            ], i)
            industry = _pick(INDUSTRIES, i)
            ticker = (
                f"{name[:3].upper()}" if entity_type == "corporation" and i % 3 == 0
                else None
            )
            aliases = [f"{prefix} {suffix}"] if i % 7 == 0 else []

            org = {
                "id": org_id,
                "canonical_name": name,
                "display_name": name,
                "aliases": aliases,
                "entity_type": entity_type,
                "industry": industry,
                "ticker": ticker,
                "country": "US",
                "source_reliability": "mock",
                "extraction_method": "mock",
            }
            self.orgs.append(org)

    # ---- Political Entities ----
    def _gen_political_entities(self, count: int):
        for i in range(count):
            if i < 2:
                name = _pick(["United States Senate", "United States House of Representatives"], i)
                entity_type = _pick(["senate", "house"], i)
                chamber = entity_type
                state = None
            elif i < 14:
                c_idx = (i - 2) % len(COMMITTEES)
                name = f"Senate Committee on {COMMITTEES[c_idx]}"
                entity_type = "committee"
                chamber = "senate"
                state = None
            else:
                s_idx = (i - 14) % len(STATES)
                name = f"State Delegation - {STATES[s_idx]}"
                entity_type = "state"
                chamber = None
                state = STATES[s_idx]

            pe = {
                "id": _hash_id("pol", name),
                "name": name,
                "entity_type": entity_type,
                "chamber": chamber,
                "state": state,
                "congress": _pick([117, 118, 119], i),
            }
            self.pol_entities.append(pe)

    # ---- Events ----
    def _gen_events(self, count: int):
        for i in range(count):
            template = _pick(EVENT_TEMPLATES, i)
            event_type = template["type"]
            title_tmpl = _pick(template["titles"], i)

            if event_type == "stock_trade":
                org = _pick(self.orgs, i) if self.orgs else {"canonical_name": "Mock Corp", "ticker": "MCK"}
                title = title_tmpl.format(company=org.get("canonical_name", "Mock Corp"), ticker=org.get("ticker", "MCK"))
            else:
                title = title_tmpl.format(year=2020 + i % 6)

            event_date = _gen_date(date(2019, 1, 3), i * 15)
            congress = _pick([117, 118, 119], i)

            event = {
                "id": _hash_id("event", title, i),
                "event_type": event_type,
                "title": title,
                "description": f"Mock description for {title}. This is synthetic data for testing.",
                "event_date": str(event_date),
                "congress": congress,
                "source_reliability": "mock",
            }
            self.events.append(event)

    # ---- Source Documents ----
    def _gen_source_docs(self, count: int):
        doc_types = [
            "financial_disclosure", "campaign_finance", "news_article",
            "lobbyist_disclosure", "gov_record",
        ]
        publishers = [
            "Mock Congressional Record", "Mock FEC Database", "Mock News Agency",
            "Mock Lobbying Disclosure DB", "Mock Government Publishing Office",
        ]
        for i in range(count):
            doc_type = _pick(doc_types, i)
            publisher = _pick(publishers, i)
            source_name = f"{publisher} - Document {i}"

            doc = {
                "id": _hash_id("sdoc", source_name, i),
                "source_name": source_name,
                "source_url": f"https://mock-source-{(i % 5) + 1}.example.com/doc/{i}",
                "title": f"Mock Document #{i}: {doc_type.replace('_', ' ').title()}",
                "publisher": publisher,
                "published_at": str(_gen_date(date(2019, 1, 1), i * 3)),
                "collected_at": str(datetime(2025, 6, 16, 12, 0, 0)),
                "last_seen_at": str(datetime(2025, 6, 16, 12, 0, 0)),
                "document_type": doc_type,
                "raw_text_hash": hashlib.md5(f"mock_text_{i}".encode()).hexdigest(),
                "snippet": f"Mock text snippet for document {i}. This is synthetic data.",
                "source_reliability": "mock",
                "license_note": "Mock license - synthetic data",
            }
            self.source_docs.append(doc)

    # ---- Claims and Relationships ----
    def _gen_relationships(self):
        """Generate claims, relationships (edges between graph nodes), and evidence links."""
        claim_idx = 0
        rel_id = 0

        # Map edge types to claim types and flow categories
        edge_type_map = {
            # Financial flow
            "RECEIVED_CONTRIBUTION": ("financial", "Person", "Organization"),
            "HOLDS_STOCK": ("financial", "Person", "Organization"),
            "RECEIVED_LOBBYING_SUPPORT": ("financial", "Person", "Organization"),
            # Social flow
            "ALUMNI_OF": ("social", "Person", "Organization"),
            "RELATED_TO": ("social", "Person", "Person"),
            "FORMER_EMPLOYER": ("social", "Person", "Organization"),
            "FUTURE_EMPLOYER": ("social", "Person", "Organization"),
            # Political flow
            "SPONSORED_BILL": ("political", "Person", "Event"),
            "COSPONSORED_BILL": ("political", "Person", "Event"),
            "VOTED_FOR": ("political", "Person", "Event"),
            "VOTED_AGAINST": ("political", "Person", "Event"),
            "SERVED_ON_COMMITTEE": ("political", "Person", "PoliticalEntity"),
            "MADE_STATEMENT": ("political", "Person", "Event"),
            # Event flow
            "PARTICIPATED_IN": ("event_participation", "Person", "Event"),
            "ASSOCIATED_WITH_EVENT": ("event_participation", "Person", "Event"),
        }

        edge_types = list(edge_type_map.keys())

        for i in range(300):
            rel_type = _pick(edge_types, i)
            claim_type, source_label, target_label = edge_type_map[rel_type]

            # Pick source and target based on label types
            if source_label == "Person" and target_label == "Organization":
                source = self.members[i % len(self.members)]
                target = self.orgs[i % len(self.orgs)]
            elif source_label == "Person" and target_label == "Person":
                source = self.members[i % len(self.members)]
                target = self.members[(i + 7) % len(self.members)]
            elif source_label == "Person" and target_label == "Event":
                source = self.members[i % len(self.members)]
                target = self.events[i % len(self.events)]
            elif source_label == "Person" and target_label == "PoliticalEntity":
                source = self.members[i % len(self.members)]
                target = self.pol_entities[i % len(self.pol_entities)]
            else:
                source = self.members[i % len(self.members)]
                target = self.orgs[i % len(self.orgs)]

            # Determine confidence
            confidence = round(random.uniform(0.3, 1.0), 2)
            is_low_confidence = i >= 280  # Last 20 are low confidence

            if is_low_confidence:
                confidence = round(random.uniform(0.25, 0.45), 2)

            claim_id = f"claim_{str(i).zfill(4)}"
            target_name = (
                target.get("canonical_name", target.get("name", target.get("title", str(target))))
            )
            claim_text_templates = {
                "RECEIVED_CONTRIBUTION": f"Source documents indicate that {source['canonical_name']} received campaign contributions from {target_name}.",
                "HOLDS_STOCK": f"Financial disclosure records show {source['canonical_name']} holds stock in {target_name}.",
                "RECEIVED_LOBBYING_SUPPORT": f"Lobbyist disclosure records show {target_name} lobbied on behalf of {source['canonical_name']}.",
                "SERVED_ON_COMMITTEE": f"Congressional records show {source['canonical_name']} served on {target_name}.",
                "VOTED_FOR": f"Voting records show {source['canonical_name']} voted FOR {target_name}.",
                "VOTED_AGAINST": f"Voting records show {source['canonical_name']} voted AGAINST {target_name}.",
            }
            claim_text = claim_text_templates.get(rel_type, f"Mock claim: {source['canonical_name']} {rel_type} {target_name}.")

            review_status = "needs_review" if (is_low_confidence or confidence < 0.5) else "unreviewed"

            claim = {
                "claim_id": claim_id,
                "claim_type": claim_type,
                "subject_id": source["id"],
                "object_id": target["id"],
                "relation_type": rel_type,
                "claim_text": claim_text,
                "original_snippet": f"Mock snippet for claim {i}: This is synthetic data for testing.",
                "confidence_score": confidence,
                "extraction_method": "mock",
                "source_reliability": "mock",
                "review_status": review_status,
            }
            self.claims.append(claim)

            # Link claim to 1-2 source documents
            num_ev = min(1 + (i % 2), len(self.source_docs))
            for j in range(num_ev):
                sdoc_idx = (i * 3 + j) % len(self.source_docs)
                ev_rel = {
                    "type": "HAS_CLAIM",
                    "source_id": (
                        source["id"] if j == 0
                        else target["id"]
                    ),
                    "target_id": claim_id,
                    "source_label": source_label if j == 0 else target_label,
                    "target_label": "Claim",
                }
                self.relationships.append(ev_rel)
                ev_rel2 = {
                    "type": "EVIDENCED_BY",
                    "source_id": claim_id,
                    "target_id": self.source_docs[sdoc_idx]["id"],
                    "source_label": "Claim",
                    "target_label": "SourceDocument",
                }
                self.relationships.append(ev_rel2)

            # Build the main relationship
            start_date_str = str(_gen_date(date(2018, 1, 1), i * 30))
            end_date_str = (
                str(_gen_date(date(2025, 1, 1), i * 10)) if i % 3 != 0
                else None
            )

            rel = {
                "id": f"rel_{str(rel_id).zfill(4)}",
                "type": rel_type,
                "source_id": source["id"],
                "target_id": target["id"],
                "source_label": source_label,
                "target_label": target_label,
                "claim_id": claim_id,
                "confidence_score": confidence,
                "start_date": start_date_str,
                "end_date": end_date_str,
                "source_type": "mock",
                "amount_min": random.randint(1000, 50000) if claim_type == "financial" else None,
                "amount_max": random.randint(50000, 200000) if claim_type == "financial" else None,
                "congress": _pick([117, 118, 119], i),
            }
            self.relationships.append(rel)
            rel_id += 1
            claim_idx += 1

    # ---- Output Accessors ----
    def to_postgres_data(self) -> dict[str, list[dict]]:
        return {
            "members": self.members,
            "organizations": self.orgs,
            "events": self.events,
            "claims": self.claims,
            "source_documents": self.source_docs,
        }

    def to_neo4j_nodes(self) -> list[dict]:
        nodes = []
        for m in self.members:
            nodes.append({"label": "Person", "id": m["id"], "properties": m})
        for o in self.orgs:
            nodes.append({"label": "Organization", "id": o["id"], "properties": o})
        for p in self.pol_entities:
            nodes.append({"label": "PoliticalEntity", "id": p["id"], "properties": p})
        for e in self.events:
            nodes.append({"label": "Event", "id": e["id"], "properties": e})
        for c in self.claims:
            nodes.append({"label": "Claim", "id": c["claim_id"], "properties": c})
        for s in self.source_docs:
            nodes.append({"label": "SourceDocument", "id": s["id"], "properties": s})
        return nodes

    def to_neo4j_edges(self) -> list[dict]:
        return self.relationships

    def get_statistics(self) -> dict:
        """Return statistics about generated data."""
        low_conf_rels = sum(
            1 for r in self.relationships
            if r.get("confidence_score", 1.0) < 0.5
            and r["type"] not in ("HAS_CLAIM", "EVIDENCED_BY")
        )
        congress_counts = {}
        for m in self.members:
            c = m.get("congress", 0)
            congress_counts[c] = congress_counts.get(c, 0) + 1
        return {
            "members": len(self.members),
            "organizations": len(self.orgs),
            "political_entities": len(self.pol_entities),
            "events": len(self.events),
            "claims": len(self.claims),
            "source_documents": len(self.source_docs),
            "relationships": len(self.relationships),
            "low_confidence_relationships": low_conf_rels,
            "congress_coverage": congress_counts,
            "aliases_generated": sum(1 for m in self.members if m.get("aliases")),
        }
