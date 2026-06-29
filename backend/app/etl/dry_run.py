"""ETL Dry Run Framework.

Dry run mode: runs a source adapter through all ETL stages (load, validate,
normalize, source_documents, claims, import_plan) and writes intermediate
outputs to data/etl_runs/{run_id}/ without touching the main database.

Usage:
    # Mock adapter (default)
    python3 -m app.etl.dry_run

    # Congress Legislators adapter with pinned commit
    python3 -m app.etl.dry_run --adapter congress_legislators --commit-sha {sha}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BaseAdapter(ABC):
    """Abstract ETL adapter.

    Adapters must implement collect_raw().  For richer integrations,
    override normalize(), extract_claims(), generate_source_documents(),
    and generate_import_plan().
    """

    source_name: str = "base"

    @abstractmethod
    def collect_raw(self) -> list[dict]:
        """Collect raw data from source. Returns list of raw dicts."""
        ...

    def validate_source_manifest(self, raw: list[dict] | None = None) -> dict:
        """Validate source manifest / checksums. Returns {valid, ...}."""
        return {"valid": True, "eligible_for_sandbox_import": True}

    def normalize(self, raw: list[dict]) -> list[dict]:
        return raw

    def generate_source_documents(self, raw: list[dict]) -> list[dict]:
        return []

    def extract_claims(self, normalized: list[dict]) -> list[dict]:
        return []

    def generate_import_plan(
        self,
        normalized: list[dict] | None = None,
        claims: list[dict] | None = None,
        source_documents: list[dict] | None = None,
    ) -> dict:
        return {"eligible_for_sandbox_import": True}


class MockAdapter(BaseAdapter):
    """Mock adapter returning sample data for dry run testing."""

    source_name = "mock"

    def collect_raw(self) -> list[dict]:
        return [
            {
                "source": "mock_fec_gov",
                "record_id": "mock_raw_001",
                "filer_name": "American Enterprise Group",
                "recipient_name": "James Smith",
                "amount": 5000.00,
                "date": "2025-03-15",
                "filing_type": "quarterly",
            },
            {
                "source": "mock_congress_gov",
                "record_id": "mock_raw_002",
                "bill_number": "H.R. 1234",
                "title": "National Defense Authorization Act",
                "sponsor_bioguide": "B000001",
                "cosponsors": ["B000002", "B000003"],
                "introduced_date": "2025-01-15",
            },
            {
                "source": "mock_opensecrets",
                "record_id": "mock_raw_003",
                "organization": "Defense Alliance PAC",
                "total_contributions": 1250000.00,
                "cycle": "2024",
            },
        ]

    def normalize(self, raw: list[dict]) -> list[dict]:
        normalized = []
        for r in raw:
            norm = {
                "normalized_id": f"norm_{hashlib.md5(json.dumps(r, sort_keys=True).encode()).hexdigest()[:8]}",
                "source": r.get("source", "unknown"),
                "record_id": r.get("record_id", ""),
                "entity_type": self._infer_entity_type(r),
                "primary_name": self._extract_primary_name(r),
                "secondary_name": self._extract_secondary_name(r),
                "amount": r.get("amount"),
                "date": r.get("date") or r.get("introduced_date"),
                "raw": r,
            }
            normalized.append(norm)
        return normalized

    def extract_claims(self, normalized: list[dict]) -> list[dict]:
        claims = []
        for n in normalized:
            if n["source"] == "mock_fec_gov":
                claims.append({
                    "claim_id": f"dryrun_claim_{n['normalized_id']}",
                    "claim_type": "financial_contribution",
                    "subject_name": n["primary_name"],
                    "object_name": n["secondary_name"],
                    "relation_type": "HAS_CONTRIBUTED_TO",
                    "claim_text": f"{n['primary_name']} contributed ${n.get('amount', 0):,.0f} to {n['secondary_name']}",
                    "confidence_score": 0.85,
                    "extraction_method": "rule_based",
                    "source_reliability": "mock",
                })
            elif n["source"] == "mock_congress_gov":
                claims.append({
                    "claim_id": f"dryrun_claim_{n['normalized_id']}_sponsor",
                    "claim_type": "bill_sponsorship",
                    "subject_name": n["primary_name"],
                    "object_name": n["raw"].get("title", ""),
                    "relation_type": "SPONSORED_BILL",
                    "claim_text": f"{n['primary_name']} sponsored {n['raw'].get('title', '')}",
                    "confidence_score": 0.95,
                    "extraction_method": "rule_based",
                    "source_reliability": "mock",
                })
        return claims

    @staticmethod
    def _infer_entity_type(record: dict) -> str:
        if "filer_name" in record or "recipient_name" in record:
            return "financial"
        if "bill_number" in record or "sponsor_bioguide" in record:
            return "legislative"
        if "organization" in record or "total_contributions" in record:
            return "organization"
        return "unknown"

    @staticmethod
    def _extract_primary_name(record: dict) -> str:
        return record.get("filer_name") or record.get("sponsor_bioguide") or record.get("organization") or ""

    @staticmethod
    def _extract_secondary_name(record: dict) -> str:
        return record.get("recipient_name") or record.get("title") or ""


# ── Adapter registry ──

ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    "mock": MockAdapter,
}

try:
    from app.etl.adapters.congress_legislators_adapter import CongressLegislatorsAdapter
    ADAPTER_REGISTRY["congress_legislators"] = CongressLegislatorsAdapter
except ImportError:
    pass


def _resolve_adapter(name: str, **kwargs: Any) -> BaseAdapter:
    if name not in ADAPTER_REGISTRY:
        available = ", ".join(ADAPTER_REGISTRY.keys())
        raise ValueError(f"Unknown adapter '{name}'. Available: {available}")
    return ADAPTER_REGISTRY[name](**kwargs)


# ── Dry Run Orchestrator ──

class EtlDryRun:
    """Orchestrates a full ETL dry run without touching main databases.

    Six-stage pipeline:
      1. collect_raw()
      2. validate_source_manifest()
      3. normalize()
      4. generate_source_documents()
      5. extract_claims()
      6. generate_import_plan()
    """

    def __init__(self, adapter: BaseAdapter, output_dir: str | None = None):
        self.adapter = adapter
        self.run_id = f"dryrun_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        if output_dir is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            output_dir = str(project_root / "data" / "etl_runs" / self.run_id)
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def run(self) -> dict:
        print(f"ETL Dry Run [{self.adapter.source_name}] starting...")
        print(f"  Run ID: {self.run_id}")
        print(f"  Output: {self.output_dir}")

        # Stage 1: Collect raw data
        print("  [1/6] Collecting raw data...")
        raw = self.adapter.collect_raw()
        print(f"    -> {len(raw)} raw records")

        # Stage 2: Validate source manifest
        print("  [2/6] Validating source manifest...")
        validation = self.adapter.validate_source_manifest(raw)
        eligible = validation.get("eligible_for_sandbox_import", True)
        print(f"    -> eligible_for_sandbox_import = {eligible}")

        # Stage 3: Normalize
        print("  [3/6] Normalizing...")
        normalized = self.adapter.normalize(raw)
        nk = list(normalized[0].keys()) if normalized and isinstance(normalized, list) and normalized else None
        print(f"    -> {len(normalized)} normalized records (or dict with keys: {nk})")

        # Adapters with internal state: write full normalized data
        full_norm = getattr(self.adapter, 'get_normalized', lambda: None)()
        if full_norm:
            self._write_json("normalized_full.json", full_norm)
            print(f"    -> full normalized data written (keys: {list(full_norm.keys())})")

        # Stage 4: Generate source documents
        print("  [4/6] Generating source documents...")
        source_documents = self.adapter.generate_source_documents(raw)
        print(f"    -> {len(source_documents)} source documents")

        # Stage 5: Extract claims
        print("  [5/6] Extracting claims...")
        claims = self.adapter.extract_claims(normalized)
        print(f"    -> {len(claims)} claims")

        # Stage 6: Generate import plan
        print("  [6/6] Generating import plan...")
        import_plan = self.adapter.generate_import_plan(
            normalized=normalized, claims=claims, source_documents=source_documents
        )

        # Write outputs
        print("  Writing output files...")
        self._write_json("raw.json", raw)
        self._write_json("normalized.json", normalized)
        self._write_json("source_documents.json", source_documents)
        self._write_json("claims.json", claims)
        self._write_json("import_plan.json", import_plan)
        self._write_json("run_metadata.json", {
            "run_id": self.run_id,
            "adapter": self.adapter.source_name,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "raw_count": len(raw),
            "normalized_count": len(normalized) if isinstance(normalized, list) else None,
            "source_document_count": len(source_documents),
            "claim_count": len(claims),
            "eligible_for_sandbox_import": eligible,
            "target_namespace": "sandbox",
        })
        self._write_entity_resolution_report(claims, normalized)
        self._write_data_quality_report(raw, normalized, claims, source_documents)

        results = {
            "run_id": self.run_id,
            "adapter": self.adapter.source_name,
            "raw_count": len(raw),
            "source_documents": len(source_documents),
            "claims_count": len(claims),
            "eligible_for_sandbox_import": eligible,
            "output_dir": self.output_dir,
        }

        print(f"\nETL Dry Run complete!")
        print(f"  Raw: {len(raw)} records")
        print(f"  Source Documents: {len(source_documents)}")
        print(f"  Claims: {len(claims)}")
        print(f"  Eligible for sandbox import: {eligible}")
        print(f"  Output: {self.output_dir}")
        return results

    # ── Helpers ──

    def _write_json(self, filename: str, data: Any):
        path = os.path.join(self.output_dir, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def _write_entity_resolution_report(self, claims: list[dict], normalized: list[dict] | None = None):
        report = f"""# Entity Resolution Report

**Run ID**: {self.run_id}
**Generated**: {datetime.now(timezone.utc).isoformat()}
**Total Claims**: {len(claims)}

## Entities Detected

| Entity ID | Occurrences |
|-----------|-------------|
"""
        entity_counts: dict[str, int] = {}
        for c in claims:
            for key in ("subject_id", "object_id", "subject_name", "object_name"):
                ident = c.get(key)
                if ident:
                    entity_counts[str(ident)] = entity_counts.get(str(ident), 0) + 1

        for name, count in sorted(entity_counts.items(), key=lambda x: -x[1])[:100]:
            report += f"| {name} | {count} |\n"

        report += """
## Entity Resolution Status
"""
        needs_review = sum(1 for c in claims if c.get("review_status") == "needs_review")
        auto_extracted = sum(1 for c in claims if c.get("review_status") == "auto_extracted")
        report += f"- Auto extracted: {auto_extracted}\n"
        report += f"- Needs review (fuzzy match / missing data): {needs_review}\n"

        if needs_review > 0:
            report += "\n## Recommendations\n"
            report += "- Claims with `needs_review` should be manually verified before sandbox import\n"
            report += "- Fuzzy-matched entities require manual confirmation of bioguide_id/govtrack_id\n"

        path = os.path.join(self.output_dir, "entity_resolution_report.md")
        with open(path, "w") as f:
            f.write(report)

    def _write_data_quality_report(
        self,
        raw: list[dict],
        normalized: list[dict],
        claims: list[dict],
        source_documents: list[dict],
    ):
        # Count claims by type
        claim_types: dict[str, int] = {}
        for c in claims:
            ct = c.get("claim_type", "unknown")
            claim_types[ct] = claim_types.get(ct, 0) + 1

        # Confidence distribution
        conf_buckets = {"high (>=0.90)": 0, "medium (>=0.70)": 0, "low (<0.70)": 0}
        for c in claims:
            conf = c.get("confidence_score", 0)
            if conf >= 0.90:
                conf_buckets["high (>=0.90)"] += 1
            elif conf >= 0.70:
                conf_buckets["medium (>=0.70)"] += 1
            else:
                conf_buckets["low (<0.70)"] += 1

        report = f"""# Data Quality Report

**Run ID**: {self.run_id}
**Generated**: {datetime.now(timezone.utc).isoformat()}
**Mode**: Dry Run (no data written to main database)

## Pipeline Summary

| Stage | Count |
|-------|-------|
| Raw Records | {len(raw)} |
| Source Documents | {len(source_documents)} |
| Claims | {len(claims)} |

## Source Distribution

| Source | Reliability |
|--------|-------------|
"""
        sources: dict[str, str] = {}
        for r in raw:
            src = r.get("source", "unknown") if isinstance(r, dict) else "unknown"
            rel = r.get("source_reliability", "n/a") if isinstance(r, dict) else "n/a"
            sources[src] = rel

        for src, rel in sorted(sources.items()):
            report += f"| {src} | {rel} |\n"

        report += """
## Confidence Score Distribution

"""
        for bucket, count in conf_buckets.items():
            report += f"- **{bucket}**: {count} claims\n"

        report += f"""
## Quality Metrics

- **Claim Extraction Rate**: {len(claims) / max(1, len(raw)):.2f} claims per raw record
"""
        report += """
## Issues

- Entity resolution requires live database connection; not performed in dry run
- Fuzzy-matched entities may need manual review

## Recommendations
- Review claims with confidence < 0.70
- Run deduplication after entity resolution
- Set `review_status="needs_review"` for fuzzy-matched entities
"""
        path = os.path.join(self.output_dir, "data_quality_report.md")
        with open(path, "w") as f:
            f.write(report)


# ── CLI ──

def run_dry_run(output_dir: str | None = None) -> dict:
    """Run default (mock) dry run."""
    runner = EtlDryRun(adapter=MockAdapter(), output_dir=output_dir)
    return runner.run()


def main():
    parser = argparse.ArgumentParser(description="ETL Dry Run")
    parser.add_argument("--adapter", default="mock", help="Adapter name (mock, congress_legislators)")
    parser.add_argument("--commit-sha", default=None, help="Vendor commit SHA (required for congress_legislators)")
    parser.add_argument("--output-dir", default=None, help="Output directory override")
    args = parser.parse_args()

    adapter_name = args.adapter

    if adapter_name == "congress_legislators":
        if not args.commit_sha:
            print("ERROR: --commit-sha is required for congress_legislators adapter", file=sys.stderr)
            sys.exit(1)
        from app.etl.adapters.congress_legislators_adapter import CongressLegislatorsAdapter
        adapter = CongressLegislatorsAdapter(commit_sha=args.commit_sha)
    else:
        adapter = _resolve_adapter(adapter_name)

    runner = EtlDryRun(adapter=adapter, output_dir=args.output_dir)
    result = runner.run()

    if not result.get("eligible_for_sandbox_import"):
        print("\nWARNING: Dry run is not eligible for sandbox import.")
        print("  Fix the issues above and re-run.", file=sys.stderr)

    return result


if __name__ == "__main__":
    main()
