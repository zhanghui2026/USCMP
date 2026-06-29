"""ETL Adapter abstract base class.

Phase 1: Mock only. Real adapters are stubs for Phase 2.
All adapters must declare source metadata for compliance.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional


class BaseAdapter(ABC):
    """Abstract ETL adapter for external data sources."""

    source_name: str = ""
    source_url: str = ""
    license_note: str = ""
    robots_policy_note: str = ""
    rate_limit: str = "N/A"
    supports_incremental: bool = False
    last_updated_at: Optional[datetime] = None
    data_freshness_window: str = "N/A"

    @abstractmethod
    def fetch(self, **kwargs) -> list[dict]:
        """Fetch data from the source. Returns list of entity dicts."""

    @abstractmethod
    def validate(self, data: dict) -> bool:
        """Validate a single record."""

    def get_metadata(self) -> dict:
        return {
            "source_name": self.source_name,
            "source_url": self.source_url,
            "license_note": self.license_note,
            "robots_policy_note": self.robots_policy_note,
            "rate_limit": self.rate_limit,
            "supports_incremental": self.supports_incremental,
            "last_updated_at": self.last_updated_at,
            "data_freshness_window": self.data_freshness_window,
        }


class MockAdapter(BaseAdapter):
    """Mock adapter that returns no data. Used when real sources are unavailable."""

    source_name = "mock"
    source_url = "N/A"
    license_note = "Mock data - synthetic"
    robots_policy_note = "N/A"
    rate_limit = "N/A"
    supports_incremental = False
    data_freshness_window = "N/A"

    def fetch(self, **kwargs) -> list[dict]:
        return []

    def validate(self, data: dict) -> bool:
        return False


class CongressGovAdapter(BaseAdapter):
    """Stub for Congress.gov API adapter. Phase 2 implementation."""

    source_name = "congress.gov"
    source_url = "https://api.congress.gov"
    license_note = "Public domain government data"
    robots_policy_note = "API rate limits apply"
    rate_limit = "1000/hour"
    supports_incremental = True
    data_freshness_window = "24h"

    def fetch(self, **kwargs) -> list[dict]:
        return []

    def validate(self, data: dict) -> bool:
        return False


class FECAdapter(BaseAdapter):
    """Stub for FEC.gov API adapter. Phase 2 implementation."""

    source_name = "fec.gov"
    source_url = "https://api.open.fec.gov"
    license_note = "Public domain government data"
    robots_policy_note = "API key required, rate limits apply"
    rate_limit = "1000/hour"
    supports_incremental = True
    data_freshness_window = "24h"

    def fetch(self, **kwargs) -> list[dict]:
        return []

    def validate(self, data: dict) -> bool:
        return False


class OpenSecretsAdapter(BaseAdapter):
    """Stub for OpenSecrets.org API adapter. Phase 2 implementation."""

    source_name = "opensecrets.org"
    source_url = "https://www.opensecrets.org/api"
    license_note = "Creative Commons, attribution required"
    robots_policy_note = "API key required, rate limits apply"
    rate_limit = "Varies by endpoint"
    supports_incremental = True
    data_freshness_window = "Annual"

    def fetch(self, **kwargs) -> list[dict]:
        return []

    def validate(self, data: dict) -> bool:
        return False
