"""Scientific backing for field inspection readings.

Implements the statutory maximum permissible error (MPE) tables for
non-automatic weighing instruments as per OIML R 76-1 and the Indian
standard IS 14625 (parts 1 & 2), which the Legal Metrology Act, 2009
enforces for trade instruments.

The MPE bands depend on the accuracy class and the verification scale
interval ``e`` (the smallest reliable division of the instrument):

    Class I / II      0 < m <= 50_000 e  -> ±0.5e
                      50_000 e < m <= 200_000 e -> ±1.0e
                      200_000 e < m -> ±1.5e

    Class III         0 < m <= 500 e     -> ±0.5e
                      500 e < m <= 2_000 e -> ±1.0e
                      2_000 e < m <= 10_000 e -> ±1.5e

    Class IIII        0 < m <= 50 e      -> ±0.5e
                      50 e < m <= 200 e  -> ±1.0e
                      200 e < m <= 1_000 e -> ±1.5e

All comparisons are done in grams so results are independent of the
unit the officer enters (kg/g/tonnes are converted first).
"""

from typing import Tuple

STANDARD_REFERENCE = "OIML R 76-1 / IS 14625 (Legal Metrology Act, 2009)"


def _to_grams(value: float, unit: str = "kg") -> float:
    unit = (unit or "kg").strip().lower()
    factors = {"g": 1.0, "gram": 1.0, "kg": 1000.0, "kilogram": 1000.0,
               "t": 1_000_000.0, "tonne": 1_000_000.0, "ton": 1_000_000.0, "mg": 0.001}
    return value * factors.get(unit, 1000.0)


def e_for(class_label: str | None, capacity_max: float | None) -> float:
    """Derive a sensible verification scale interval ``e`` (grams) when the
    business did not declare one. Class III instruments typically divide
    their capacity into 3000 scale intervals."""
    if capacity_max:
        cap_g = _to_grams(capacity_max)
        classes = {"i": 100000, "ii": 100000, "iii": 3000, "iiii": 1000}
        n = classes.get((class_label or "").replace("class", "").strip().lower(), 3000)
        return round(cap_g / n, 2)
    return 10.0  # 10 g default when capacity is unknown


def mpe_grams(applied_load: float, e: float, accuracy_class: str | None) -> Tuple[float, str]:
    """Return ``(mpe_grams, band_reference)`` for a load expressed in the
    instrument's unit (``unit_of_measurement``, default kg)."""
    load_g = _to_grams(applied_load)
    cls = (accuracy_class or "Class III").replace("class", "").strip().lower()

    if cls in ("i", "ii"):
        band = "0 < m ≤ 50_000e → ±0.5e" if load_g <= 50_000 * e else (
            "50_000e < m ≤ 200_000e → ±1.0e" if load_g <= 200_000 * e else
            "200_000e < m → ±1.5e")
        factor = 0.5 if load_g <= 50_000 * e else (1.0 if load_g <= 200_000 * e else 1.5)
        table = "Class I / II"
    elif cls in ("iiii",):
        band = "0 < m ≤ 50e → ±0.5e" if load_g <= 50 * e else (
            "50e < m ≤ 200e → ±1.0e" if load_g <= 200 * e else
            "200e < m ≤ 1_000e → ±1.5e")
        factor = 0.5 if load_g <= 50 * e else (1.0 if load_g <= 200 * e else 1.5)
        table = "Class IIII"
    else:
        band = "0 < m ≤ 500e → ±0.5e" if load_g <= 500 * e else (
            "500e < m ≤ 2_000e → ±1.0e" if load_g <= 2_000 * e else
            "2_000e < m ≤ 10_000e → ±1.5e")
        factor = 0.5 if load_g <= 500 * e else (1.0 if load_g <= 2_000 * e else 1.5)
        table = "Class III"

    return factor * e, f"{table} — {band}"


def deviation_grams(measured: float, applied: float, unit: str = "kg") -> float:
    """Absolute deviation between the reading and the applied test load, in grams."""
    return abs(_to_grams(measured, unit) - _to_grams(applied, unit))