"""Exact source time grid for the disposable native validation harness."""

import math
from fractions import Fraction
from functools import reduce


def exact_frame_rate(keys):
    """Smallest legal rate preserving all tick/base times; no rounded time edits."""
    times = [Fraction(key.ticks, key.time_base) for key in keys if key.ticks]
    if not times:
        return 30.0
    denominator = math.lcm(*(time.denominator for time in times))
    numerator = reduce(math.gcd, (abs(time.numerator) * (denominator // time.denominator) for time in times))
    minimum = Fraction(denominator, numerator)
    rate = minimum * max(1, math.ceil(1 / minimum))
    if rate > 1000:
        return None
    value = float(rate)
    return value if all(math.isclose(round(float(time) * value) / value, float(time),
                                    rel_tol=1e-12, abs_tol=1e-9) for time in times) else None
