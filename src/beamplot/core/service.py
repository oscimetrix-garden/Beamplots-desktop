from __future__ import annotations

from pathlib import Path

from beamplot.core.statistics import compute_beamplot_result
from beamplot.core.weighting import apply_age_weighting
from beamplot.domain import BeamplotResult, CitationRecord
from beamplot.io import read_wos_records


def analyze_wos_file(
    path: str | Path,
    *,
    do_weight: bool = False,
    current_year: int | None = None,
) -> BeamplotResult:
    records = read_wos_records(path)
    return build_beamplot_result(
        records,
        do_weight=do_weight,
        current_year=current_year,
    )


def build_beamplot_result(
    records: tuple[CitationRecord, ...],
    *,
    do_weight: bool = False,
    current_year: int | None = None,
) -> BeamplotResult:
    prepared_records = (
        apply_age_weighting(records, current_year=current_year)
        if do_weight
        else records
    )
    return compute_beamplot_result(prepared_records, weighted=do_weight)
