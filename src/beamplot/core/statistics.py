from __future__ import annotations

from collections import defaultdict
from statistics import median

from beamplot.domain import BeamplotResult, CitationRecord, YearBeamStats


def compute_beamplot_result(
    records: tuple[CitationRecord, ...],
    *,
    weighted: bool,
) -> BeamplotResult:
    if not records:
        raise ValueError("At least one citation record is required.")

    grouped: dict[int, list[float]] = defaultdict(list)
    for record in records:
        grouped[record.year].append(float(record.citations))

    years = sorted(grouped)
    all_citations = tuple(float(record.citations) for record in records)
    publication_counts = tuple(len(grouped[year]) for year in years)

    max_citations = max(all_citations)
    max_publication_count = max(publication_counts)
    scale_factor = max_citations / max_publication_count if max_publication_count else 0.0

    yearly_stats = tuple(
        _year_stats(
            year=year,
            y_position=index,
            citations=grouped[year],
            publication_scale_factor=scale_factor,
        )
        for index, year in enumerate(years, start=1)
    )

    return BeamplotResult(
        records=records,
        yearly_stats=yearly_stats,
        global_median=float(median(all_citations)),
        publication_count_median=float(median(publication_counts)),
        publication_scale_factor=float(scale_factor),
        weighted=weighted,
        x_label=(
            "Number of age-weighted citations"
            if weighted
            else "Number of citations"
        ),
    )


def _year_stats(
    *,
    year: int,
    y_position: int,
    citations: list[float],
    publication_scale_factor: float,
) -> YearBeamStats:
    values = tuple(float(value) for value in citations)
    publication_count = len(values)
    return YearBeamStats(
        year=year,
        y_position=y_position,
        citations=values,
        minimum=float(min(values)),
        maximum=float(max(values)),
        median=float(median(values)),
        publication_count=publication_count,
        publication_axis_value=float(publication_scale_factor * publication_count),
    )
