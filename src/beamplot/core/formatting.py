from __future__ import annotations


def fmt_num(value: float | int | str | None, *, weighted: bool = False) -> str:
    """Format a numeric value for display.

    Whole numbers are shown without decimals; any fractional value uses 2 decimal places.
    The ``weighted`` argument is kept for call-site compatibility and does not change formatting.
    """
    _ = weighted
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}"
