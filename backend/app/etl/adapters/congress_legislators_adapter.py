"""Congress Legislators Adapter.

Loads pinned vendor data from UnitedStates/congress-legislators,
normalizes into standard schema, generates Claims and SourceDocuments,
and produces an ImportPlan — all without writing to main databases.

Usage (via dry_run module):
    python3 -m app.etl.dry_run --adapter congress_legislators --commit-sha {sha}
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.etl.dry_run import BaseAdapter


class CongressLegislatorsAdapter(BaseAdapter):
    """Loads UnitedStates/congress-legislators vendor data."""

    source_name = "unitedstates/congress-legislators"

    def __init__(self, commit_sha: str, vendor_dir: str | None = None):
        self.commit_sha = commit_sha
        if vendor_dir is None:
            # __file__ → adapters/congress_legislators_adapter.py
            # .parent.parent.parent = etl/ (wrong: was app/)
            from pathlib import Path as _Path
            _here = _Path(__file__).resolve()
            # go up: adapter.py → adapters → etl → app → backend
            vendor_dir = str(
                _here.parent.parent.parent.parent
                / "data" / "external" / "congress-legislators" / commit_sha
            )
        self.vendor_dir = vendor_dir
        self._raw: dict[str, Any] = {}
        self._normalized: dict[str, list[dict]] = {}

    # ── Step 1: Load ──

    def collect_raw(self) -> list[dict]:
        self.load_vendor_dataset(self.commit_sha)
        return [{"source": self.source_name, "commit_sha": self.commit_sha, "files": list(self._raw.keys())}]

    def load_vendor_dataset(self, commit_sha: str) -> dict[str, Any]:
        files = {
            "legislators-current.yaml": "legislators_current",
            "legislators-historical.yaml": "legislators_historical",
            "legislators-social-media.yaml": "social_media",
            "committees-current.yaml": "committees_current",
            "committee-membership-current.yaml": "committee_memberships",
        }
        for filename, key in files.items():
            filepath = os.path.join(self.vendor_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    self._raw[key] = yaml.safe_load(f)
        return self._raw

    # ── Step 2: Validate ──

    def validate_source_manifest(self, raw: dict[str, Any] | None = None) -> dict:
        manifest_path = os.path.join(self.vendor_dir, "source_manifest.json")
        if not os.path.exists(manifest_path):
            return {"valid": False, "error": "source_manifest.json not found", "eligible_for_sandbox_import": False}

        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        errors = []
        if manifest.get("commit_sha") != self.commit_sha:
            errors.append(f"commit_sha mismatch: manifest={manifest.get('commit_sha')}, expected={self.commit_sha}")

        # Validate checksums
        for fspec in manifest.get("files", []):
            filepath = os.path.join(self.vendor_dir, fspec["filename"])
            if not os.path.exists(filepath):
                errors.append(f"File missing: {fspec['filename']}")
                continue
            with open(filepath, "rb") as f:
                actual = hashlib.sha256(f.read()).hexdigest()
            if actual != fspec["sha256"]:
                errors.append(f"Checksum mismatch: {fspec['filename']} (expected={fspec['sha256'][:16]}..., actual={actual[:16]}...)")

        valid = len(errors) == 0
        return {
            "valid": valid,
            "errors": errors,
            "commit_sha": manifest.get("commit_sha"),
            "file_count": len(manifest.get("files", [])),
            "eligible_for_sandbox_import": valid and bool(manifest.get("commit_sha")),
        }

    # ── Step 3: Normalize ──

    def normalize(self, raw: list[dict]) -> list[dict]:
        result = {
            "persons": [],
            "person_terms": [],
            "political_entities": [],
            "committee_memberships": [],
            "social_accounts": [],
        }

        # LEGISLATORS CURRENT
        for leg in (self._raw.get("legislators_current") or []):
            person = self._normalize_person(leg)
            person["_scope"] = "current"
            result["persons"].append(person)
            for term in leg.get("terms", []):
                result["person_terms"].append(self._normalize_term(leg, term, person["person_id"]))

        # LEGISLATORS HISTORICAL
        for leg in (self._raw.get("legislators_historical") or []):
            person = self._normalize_person(leg)
            person["_scope"] = "historical"
            result["persons"].append(person)
            for term in leg.get("terms", []):
                result["person_terms"].append(self._normalize_term(leg, term, person["person_id"]))

        # COMMITTEES
        for comm in (self._raw.get("committees_current") or []):
            entity = self._normalize_committee(comm)
            result["political_entities"].append(entity)

        # COMMITTEE MEMBERSHIPS
        for thomas_id, members in (self._raw.get("committee_memberships") or {}).items():
            for member in members:
                result["committee_memberships"].append(
                    self._normalize_membership(member, thomas_id)
                )

        # SOCIAL MEDIA
        for sm in (self._raw.get("social_media") or []):
            bioguide = (sm.get("id") or {}).get("bioguide", "")
            social = sm.get("social", {})
            for platform, account in social.items():
                if account:
                    result["social_accounts"].append(
                        self._normalize_social(bioguide, platform, account)
                    )

        self._normalized = result
        return [
            {"stage": "normalize", "persons": len(result["persons"]),
             "terms": len(result["person_terms"]), "committees": len(result["political_entities"]),
             "memberships": len(result["committee_memberships"]), "social": len(result["social_accounts"])}
        ]

    def _normalize_person(self, leg: dict) -> dict:
        ids = leg.get("id", {})
        name = leg.get("name", {})
        terms = leg.get("terms", [])
        latest = terms[-1] if terms else {}
        bioguide = ids.get("bioguide", "")
        person_id = f"uscl_person_{bioguide}" if bioguide else f"uscl_person_{hashlib.sha256(str(leg).encode()).hexdigest()[:12]}"

        return {
            "person_id": person_id,
            "canonical_name": name.get("official_full", f"{name.get('first','')} {name.get('last','')}"),
            "display_name": name.get("official_full", f"{name.get('first','')} {name.get('last','')}"),
            "aliases": [name.get("first", ""), name.get("last", ""), name.get("nickname")] if name.get("nickname") else [],
            "person_type": "legislator",
            "party": latest.get("party"),
            "chamber": "senate" if latest.get("type") == "sen" else "house",
            "state": latest.get("state"),
            "district": str(latest.get("district")) if latest.get("district") is not None else None,
            "bioguide_id": bioguide or None,
            "govtrack_id": str(ids.get("govtrack")) if ids.get("govtrack") else None,
            "opensecrets_id": ids.get("opensecrets"),
            "fec_ids": ids.get("fec", []),
            "wikipedia_title": ids.get("wikipedia"),
            "wikidata_qid": ids.get("wikidata"),
            "latest_term_start": str(latest.get("start", "")),
            "latest_term_end": str(latest.get("end", "")),
            "data_namespace": "sandbox",
            "data_source": self.source_name,
            "source_reliability": "secondary",
            "etl_run_id": "",  # filled at import time
        }

    def _normalize_term(self, leg: dict, term: dict, person_id: str) -> dict:
        ids = leg.get("id", {})
        bioguide = ids.get("bioguide", "")
        congress = self._infer_congress(term.get("start", ""))
        term_id = f"uscl_term_{bioguide}_{term.get('start','')}_{term.get('type','')}"
        claim_id = f"uscl_claim_term_{bioguide}_{term.get('start','')}"

        return {
            "term_id": term_id,
            "person_id": person_id,
            "congress": congress,
            "chamber": "senate" if term.get("type") == "sen" else "house",
            "state": term.get("state"),
            "district": str(term.get("district")) if term.get("district") is not None else None,
            "party": term.get("party"),
            "term_type": term.get("type"),
            "start_date": str(term.get("start", "")),
            "end_date": str(term.get("end", "")),
            "claim_id": claim_id,
            "confidence_score": 0.90,
            "data_namespace": "sandbox",
            "data_source": self.source_name,
            "source_reliability": "secondary",
            "etl_run_id": "",
        }

    def _normalize_committee(self, comm: dict) -> dict:
        thomas_id = comm.get("thomas_id", "")
        entity_id = f"uscl_committee_{thomas_id}" if thomas_id else f"uscl_committee_{hashlib.sha256(str(comm).encode()).hexdigest()[:12]}"
        return {
            "entity_id": entity_id,
            "name": comm.get("name", ""),
            "entity_type": "committee",
            "chamber": comm.get("type", ""),
            "thomas_id": thomas_id,
            "url": comm.get("url"),
            "congress": 119,
            "data_namespace": "sandbox",
            "data_source": self.source_name,
            "source_reliability": "secondary",
            "etl_run_id": "",
        }

    def _normalize_membership(self, member: dict, thomas_id: str) -> dict:
        bioguide = member.get("bioguide", "")
        raw_rank = member.get("rank", "member")
        rank_text = self._rank_to_text(raw_rank)
        person_id = f"uscl_person_{bioguide}"
        entity_id = f"uscl_committee_{thomas_id}"
        membership_id = f"uscl_member_{bioguide}_{thomas_id}"
        claim_id = f"uscl_claim_member_{bioguide}_{thomas_id}"

        has_dates = bool(member.get("start_date"))
        confidence = 0.85 if has_dates else 0.80
        review = "needs_review" if not has_dates else "auto_extracted"

        return {
            "membership_id": membership_id,
            "person_id": person_id,
            "committee_entity_id": entity_id,
            "role": rank_text,
            "rank": raw_rank,
            "party": member.get("party"),
            "congress": 119,
            "start_date": member.get("start_date") or "2025-01-03",
            "end_date": member.get("end_date"),
            "claim_id": claim_id,
            "confidence_score": confidence,
            "review_status": review,
            "data_namespace": "sandbox",
            "data_source": self.source_name,
            "source_reliability": "secondary",
            "etl_run_id": "",
        }

    def _normalize_social(self, bioguide: str, platform: str, account: str) -> dict:
        person_id = f"uscl_person_{bioguide}"
        account_id = f"uscl_social_{bioguide}_{platform}"
        claim_id = f"uscl_claim_social_{bioguide}_{platform}"

        return {
            "account_id": account_id,
            "person_id": person_id,
            "platform": platform,
            "account": str(account) if account is not None else "",
            "official": True,
            "claim_id": claim_id,
            "confidence_score": 0.85,
            "data_namespace": "sandbox",
            "data_source": self.source_name,
            "source_reliability": "secondary",
            "etl_run_id": "",
        }

    @staticmethod
    def _rank_to_text(rank: int | str) -> str:
        try:
            r = int(rank)
        except (ValueError, TypeError):
            return str(rank)
        if r == 1:
            return "senior"
        return "member"

    @staticmethod
    def _infer_congress(start_date_str: str) -> int | None:
        if not start_date_str:
            return None
        try:
            year = int(start_date_str[:4])
        except ValueError:
            return None
        # Each congress term is 2 years, starting on odd years.
        # 1st Congress: 1789-1791, 2nd: 1791-1793, ...
        if year < 1789:
            return None
        congress = ((year - 1789) // 2) + 1
        return congress

    # ── Step 4: Generate Source Documents ──

    def generate_source_documents(self, raw: list[dict]) -> list[dict]:
        docs = []
        manifest_path = os.path.join(self.vendor_dir, "source_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            for fspec in manifest.get("files", []):
                filepath = os.path.join(self.vendor_dir, fspec["filename"])
                docs.append({
                    "document_id": f"uscl_sdoc_{fspec['filename'].replace('.yaml', '').replace('.', '_')}",
                    "source_name": self.source_name,
                    "source_url": f"https://github.com/unitedstates/congress-legislators/blob/{self.commit_sha}/{fspec['filename']}",
                    "title": f"{fspec['filename']} @ {self.commit_sha[:8]}",
                    "publisher": self.source_name,
                    "document_type": "structured_dataset",
                    "source_reliability": "secondary",
                    "license_note": "CC0-1.0",
                    "sha256": fspec["sha256"],
                    "record_count": fspec.get("approx_lines", 0),
                    "data_namespace": "sandbox",
                    "data_source": self.source_name,
                    "etl_run_id": "",
                })
        return docs

    # ── Step 5: Generate Claims ──

    def extract_claims(self, normalized: list[dict]) -> list[dict]:
        claims = []

        # Identity claims (one per person)
        for p in self._normalized.get("persons", []):
            claims.append({
                "claim_id": f"uscl_claim_identity_{p['bioguide_id'] or p['person_id'][-8:]}",
                "claim_type": "identity_claim",
                "subject_id": p["person_id"],
                "object_id": p["person_id"],
                "relation_type": "HAS_IDENTITY",
                "claim_text": f"Legislator identity record for {p['canonical_name']} (bioguide: {p.get('bioguide_id', 'N/A')})",
                "confidence_score": 0.95,
                "extraction_method": "yaml",
                "source_reliability": "secondary",
                "review_status": "auto_extracted",
                "data_namespace": "sandbox",
                "data_source": self.source_name,
                "etl_run_id": "",
            })

        # Term claims
        for t in self._normalized.get("person_terms", []):
            claims.append({
                "claim_id": t["claim_id"],
                "claim_type": "term_claim",
                "subject_id": t["person_id"],
                "object_id": f"congress_{t.get('congress', 'unknown')}",
                "relation_type": "SERVED_IN_TERM",
                "claim_text": f"Served as {t.get('chamber')} from {t.get('state')} ({t.get('party')}) from {t.get('start_date')} to {t.get('end_date')}",
                "confidence_score": t.get("confidence_score", 0.90),
                "extraction_method": "yaml",
                "source_reliability": "secondary",
                "review_status": "auto_extracted",
                "data_namespace": "sandbox",
                "data_source": self.source_name,
                "etl_run_id": "",
            })

        # Committee membership claims
        for cm in self._normalized.get("committee_memberships", []):
            claims.append({
                "claim_id": cm["claim_id"],
                "claim_type": "committee_membership_claim",
                "subject_id": cm["person_id"],
                "object_id": cm["committee_entity_id"],
                "relation_type": "SERVED_ON_COMMITTEE",
                "claim_text": f"Served on committee as {cm.get('role')} since {cm.get('start_date')}",
                "confidence_score": cm.get("confidence_score", 0.85),
                "extraction_method": "yaml",
                "source_reliability": "secondary",
                "review_status": cm.get("review_status", "needs_review"),
                "data_namespace": "sandbox",
                "data_source": self.source_name,
                "etl_run_id": "",
            })

        # Social account claims
        for sa in self._normalized.get("social_accounts", []):
            claims.append({
                "claim_id": sa["claim_id"],
                "claim_type": "official_social_account",
                "subject_id": sa["person_id"],
                "object_id": sa["account"],
                "relation_type": "HAS_SOCIAL_ACCOUNT",
                "claim_text": f"Official {sa['platform']} account: {sa['account']}",
                "confidence_score": 0.85,
                "extraction_method": "yaml",
                "source_reliability": "secondary",
                "review_status": "auto_extracted",
                "data_namespace": "sandbox",
                "data_source": self.source_name,
                "etl_run_id": "",
            })

        return claims

    # ── Step 6: Import Plan ──

    def generate_import_plan(
        self,
        normalized: list[dict] | None = None,
        claims: list[dict] | None = None,
        source_documents: list[dict] | None = None,
    ) -> dict:
        norm = self._normalized  # dict keyed by entity type
        if claims is None:
            claims = self.extract_claims([])
        if source_documents is None:
            source_documents = self.generate_source_documents([])

        validation = self.validate_source_manifest()
        eligible = validation.get("eligible_for_sandbox_import", False)

        plan = {
            "title": "Congress Legislators Sandbox Import Plan",
            "adapter": "congress_legislators",
            "commit_sha": self.commit_sha,
            "eligible_for_sandbox_import": eligible,
            "reason": "" if eligible else validation.get("error", "commit_sha validation failed"),
            "target_namespace": "sandbox",
            "will_not_overwrite": ["mock_members", "mock_organizations", "mock_events", "mock_claims", "mock_relationships"],
            "import_steps": [
                {"step": 1, "action": "Insert SandboxImportRun record", "status": "pending"},
                {"step": 2, "action": "Insert SourceDocuments", "count": len(source_documents), "status": "pending"},
                {"step": 3, "action": "Insert Persons", "count": len(norm.get("persons", [])), "status": "pending"},
                {"step": 4, "action": "Insert PersonTerms", "count": len(norm.get("person_terms", [])), "status": "pending"},
                {"step": 5, "action": "Insert PoliticalEntities", "count": len(norm.get("political_entities", [])), "status": "pending"},
                {"step": 6, "action": "Insert CommitteeMemberships", "count": len(norm.get("committee_memberships", [])), "status": "pending"},
                {"step": 7, "action": "Insert SocialAccounts", "count": len(norm.get("social_accounts", [])), "status": "pending"},
                {"step": 8, "action": "Insert Claims", "count": len(claims), "status": "pending"},
            ],
            "entity_resolution_required": True,
            "needs_review_default": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return plan

    # ── Accessors ──

    def get_normalized(self) -> dict[str, list[dict]]:
        return self._normalized

    def get_raw(self) -> dict[str, Any]:
        return self._raw
