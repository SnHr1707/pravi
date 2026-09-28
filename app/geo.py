"""Small geometry helpers: distances and snapping a point to a road polyline."""
import math
from typing import List, Sequence, Tuple

R = 6371000.0


def haversine(a: Sequence[float], b: Sequence[float]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(d))


def _xy(p, lat0):
    return (math.radians(p[1]) * R * math.cos(math.radians(lat0)), math.radians(p[0]) * R)


def polyline_length(pts: List[Sequence[float]]) -> float:
    return sum(haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def snap(point: Sequence[float], pts: List[Sequence[float]]) -> Tuple[float, float]:
    """Return (distance_m, fraction_along_0_to_1) of the closest point on the polyline."""
    lat0 = point[0]
    P = _xy(point, lat0)
    seg_lens = [haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg_lens) or 1.0
    best = (float("inf"), 0.0)
    run = 0.0
    for i in range(len(pts) - 1):
        A, B = _xy(pts[i], lat0), _xy(pts[i + 1], lat0)
        dx, dy = B[0] - A[0], B[1] - A[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((P[0] - A[0]) * dx + (P[1] - A[1]) * dy) / L2))
        cx, cy = A[0] + t * dx, A[1] + t * dy
        d = math.hypot(P[0] - cx, P[1] - cy)
        if d < best[0]:
            best = (d, (run + t * seg_lens[i]) / total)
        run += seg_lens[i]
    return best


def point_at(pts: List[Sequence[float]], frac: float) -> Tuple[float, float]:
    """Point at a fraction (0..1) along a polyline."""
    frac = max(0.0, min(1.0, frac))
    seg = [haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    target = frac * sum(seg)
    for i, L in enumerate(seg):
        if target <= L or i == len(seg) - 1:
            t = 0 if L == 0 else min(1.0, target / L)
            return (pts[i][0] + t * (pts[i + 1][0] - pts[i][0]), pts[i][1] + t * (pts[i + 1][1] - pts[i][1]))
        target -= L
    return tuple(pts[-1])


def slice_polyline(pts: List[Sequence[float]], f0: float, f1: float, steps: int = 12) -> List[List[float]]:
    """Sub-polyline between two fractions, keeping the original vertices in between."""
    seg = [haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg)
    out = [list(point_at(pts, f0))]
    run = 0.0
    for i, L in enumerate(seg):
        run += L
        f = run / total
        if f0 < f < f1:
            out.append(list(pts[i + 1]))
    out.append(list(point_at(pts, f1)))
    return [[round(a, 6), round(b, 6)] for a, b in out]
