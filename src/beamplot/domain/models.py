from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CitationRecord:
    """A single WoS publication with the two fields used by BibPlots."""

    year: int
    citations: float


@dataclass(frozen=True)
class YearBeamStats:
    year: int
    y_position: int
    citations: tuple[float, ...]
    minimum: float
    maximum: float
    median: float
    publication_count: int
    publication_axis_value: float


@dataclass(frozen=True)
class BeamplotResult:
    records: tuple[CitationRecord, ...]
    yearly_stats: tuple[YearBeamStats, ...]
    global_median: float
    publication_count_median: float
    publication_scale_factor: float
    weighted: bool
    x_label: str

    @property
    def years(self) -> tuple[int, ...]:
        return tuple(stats.year for stats in self.yearly_stats)
