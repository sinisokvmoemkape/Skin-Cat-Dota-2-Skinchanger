from pathlib import Path

from skin_studio.domain.models import Hero
from skin_studio.logging_setup import SecretRedactionFilter
from skin_studio.services.hero_catalog import SAMPLE_HEROES, search_heroes
from skin_studio.services.resource_service import SimulatedResourceAdapter


def test_sample_hero_search_is_case_insensitive_and_unicode_safe() -> None:
    assert len(search_heroes("")) == len(SAMPLE_HEROES)
    assert search_heroes("AXE") == (Hero("sample-axe", "Axe"),)
    assert search_heroes("неизвестный") == ()


def test_simulated_resource_adapter_does_not_write_to_disk(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())
    result = SimulatedResourceAdapter().preview("demo texture")
    assert result.simulated
    assert set(tmp_path.iterdir()) == before


def test_logging_filter_redacts_secret_values() -> None:
    import logging

    record = logging.LogRecord("test", logging.INFO, "", 0, "api_key=%s", ("secret-123",), None)
    SecretRedactionFilter().filter(record)
    assert "secret-123" not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()
