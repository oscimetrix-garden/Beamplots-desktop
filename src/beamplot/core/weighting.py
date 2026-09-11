from __future__ import annotations

from datetime import datetime

from beamplot.domain import CitationRecord


def apply_age_weighting(
    records: tuple[CitationRecord, ...],
    current_year: int | None = None,
) -> tuple[CitationRecord, ...]:
    """Apply the BibPlots age weighting formula to citation counts."""

    year_now = current_year or datetime.now().year
    return tuple(
        CitationRecord(
            year=record.year,
            citations=record.citations / _age_weight(record.year, year_now),
        )
        for record in records
    )


def _age_weight(publication_year: int, current_year: int) -> int:
    weight = current_year - publication_year + 1
    return min(weight, 11)
