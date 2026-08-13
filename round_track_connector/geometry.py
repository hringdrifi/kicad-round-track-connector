"""Geometry helpers for extending and filleting line/circular-arc tracks."""

from __future__ import annotations

from dataclasses import dataclass
import math


EPS = 1e-7
TAU = 2.0 * math.pi


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def __add__(self, other: "Point") -> "Point":
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point") -> "Point":
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, value: float) -> "Point":
        return Point(self.x * value, self.y * value)

    def __truediv__(self, value: float) -> "Point":
        return Point(self.x / value, self.y / value)

    def dot(self, other: "Point") -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: "Point") -> float:
        return self.x * other.y - self.y * other.x

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> "Point":
        length = self.length()
        if length < EPS:
            raise ValueError("Zero-length vector")
        return self / length

    def left(self) -> "Point":
        return Point(-self.y, self.x)


@dataclass(frozen=True)
class Line:
    start: Point
    end: Point


@dataclass(frozen=True)
class Circle:
    center: Point
    radius: float


@dataclass(frozen=True)
class Fillet:
    center: Point
    tangent_a: Point
    tangent_b: Point
    radius: float
    score: float


@dataclass(frozen=True)
class TangentArc:
    center: Point
    start: Point
    mid: Point
    end: Point
    radius: float


@dataclass(frozen=True)
class LineArcTangent:
    point: Point
    line_endpoint: str
    arc_endpoint: str
    score: float


def distance(a: Point, b: Point) -> float:
    return (a - b).length()


def line_line_intersections(a: Line, b: Line) -> list[Point]:
    p = a.start
    r = a.end - a.start
    q = b.start
    s = b.end - b.start
    denominator = r.cross(s)
    if abs(denominator) < EPS:
        return []
    t = (q - p).cross(s) / denominator
    return [p + r * t]


def line_circle_intersections(line: Line, circle: Circle) -> list[Point]:
    direction = line.end - line.start
    a = direction.dot(direction)
    if a < EPS:
        return []
    relative = line.start - circle.center
    b = 2.0 * relative.dot(direction)
    c = relative.dot(relative) - circle.radius * circle.radius
    discriminant = b * b - 4.0 * a * c
    if discriminant < -EPS:
        return []
    if abs(discriminant) <= EPS:
        return [line.start + direction * (-b / (2.0 * a))]
    root = math.sqrt(discriminant)
    return [
        line.start + direction * ((-b - root) / (2.0 * a)),
        line.start + direction * ((-b + root) / (2.0 * a)),
    ]


def tangent_points_from_point(point: Point, circle: Circle) -> list[Point]:
    """Return the points where lines from an external point touch a circle."""
    relative = point - circle.center
    distance_squared = relative.dot(relative)
    radius_squared = circle.radius * circle.radius
    if distance_squared < radius_squared - EPS:
        return []
    if abs(distance_squared - radius_squared) <= EPS:
        return [point]

    base = circle.center + relative * (radius_squared / distance_squared)
    offset_scale = circle.radius * math.sqrt(
        distance_squared - radius_squared
    ) / distance_squared
    offset = relative.left() * offset_scale
    return [base + offset, base - offset]


def line_arc_tangent(
    line: Line,
    circle: Circle,
    arc_start: Point,
    arc_end: Point,
) -> LineArcTangent | None:
    """Move the nearest line/arc endpoint pair to a common tangent point."""
    endpoint_pairs = [
        (distance(line.start, arc_start), "start", "start"),
        (distance(line.start, arc_end), "start", "end"),
        (distance(line.end, arc_start), "end", "start"),
        (distance(line.end, arc_end), "end", "end"),
    ]
    _, line_endpoint, arc_endpoint = min(endpoint_pairs, key=lambda item: item[0])
    fixed_line_point = line.end if line_endpoint == "start" else line.start
    original_line_point = line.start if line_endpoint == "start" else line.end
    original_arc_point = arc_start if arc_endpoint == "start" else arc_end

    candidates = tangent_points_from_point(fixed_line_point, circle)
    if not candidates:
        return None
    point = min(
        candidates,
        key=lambda candidate: (
            distance(original_line_point, candidate)
            + distance(original_arc_point, candidate)
        ),
    )
    return LineArcTangent(
        point=point,
        line_endpoint=line_endpoint,
        arc_endpoint=arc_endpoint,
        score=(
            distance(original_line_point, point)
            + distance(original_arc_point, point)
        ),
    )


def point_on_arc(
    point: Point,
    start: Point,
    mid: Point,
    end: Point,
    center: Point,
) -> bool:
    """Return whether a point on the supporting circle lies on the selected arc."""
    def angle(value: Point) -> float:
        return math.atan2(value.y - center.y, value.x - center.x) % TAU

    start_angle = angle(start)
    mid_angle = angle(mid)
    end_angle = angle(end)
    point_angle = angle(point)
    ccw_sweep = (end_angle - start_angle) % TAU
    mid_ccw = (mid_angle - start_angle) % TAU

    if mid_ccw <= ccw_sweep + EPS:
        return (point_angle - start_angle) % TAU <= ccw_sweep + EPS

    clockwise_sweep = (start_angle - end_angle) % TAU
    return (start_angle - point_angle) % TAU <= clockwise_sweep + EPS


def arc_sweep(start: Point, mid: Point, end: Point, center: Point) -> float:
    """Return an arc's directed sweep angle in the range (0, 2π)."""
    def angle(value: Point) -> float:
        return math.atan2(value.y - center.y, value.x - center.x) % TAU

    start_angle = angle(start)
    mid_angle = angle(mid)
    end_angle = angle(end)
    ccw_sweep = (end_angle - start_angle) % TAU
    if (mid_angle - start_angle) % TAU <= ccw_sweep + EPS:
        return ccw_sweep
    return TAU - ccw_sweep


def arc_sweep_change(
    start: Point,
    mid: Point,
    end: Point,
    center: Point,
    point: Point,
    endpoint: str,
) -> float:
    """Return the sweep-angle change from moving one endpoint to *point*."""
    def angle(value: Point) -> float:
        return math.atan2(value.y - center.y, value.x - center.x) % TAU

    original_start_angle = angle(start)
    original_mid_angle = angle(mid)
    original_end_angle = angle(end)
    original_ccw_sweep = (original_end_angle - original_start_angle) % TAU
    clockwise = (
        (original_mid_angle - original_start_angle) % TAU
        > original_ccw_sweep + EPS
    )
    original_sweep = (
        TAU - original_ccw_sweep if clockwise else original_ccw_sweep
    )
    start_angle = angle(point if endpoint == "start" else start)
    end_angle = angle(point if endpoint == "end" else end)
    new_ccw_sweep = (end_angle - start_angle) % TAU
    new_sweep = TAU - new_ccw_sweep if clockwise else new_ccw_sweep
    return abs(new_sweep - original_sweep)


def distance_to_arc(
    point: Point,
    circle: Circle,
    start: Point,
    mid: Point,
    end: Point,
) -> float:
    relative = point - circle.center
    if relative.length() > EPS:
        radial = circle.center + relative.normalized() * circle.radius
        if point_on_arc(radial, start, mid, end, circle.center):
            return abs(relative.length() - circle.radius)
    return min(distance(point, start), distance(point, end))


def circle_circle_intersections(a: Circle, b: Circle) -> list[Point]:
    delta = b.center - a.center
    d = delta.length()
    if d < EPS or d > a.radius + b.radius + EPS:
        return []
    if d < abs(a.radius - b.radius) - EPS:
        return []
    x = (a.radius * a.radius - b.radius * b.radius + d * d) / (2.0 * d)
    h2 = a.radius * a.radius - x * x
    if h2 < -EPS:
        return []
    base = a.center + delta * (x / d)
    if abs(h2) <= EPS:
        return [base]
    offset = delta.left() * (math.sqrt(h2) / d)
    return [base + offset, base - offset]


def intersections(a: Line | Circle, b: Line | Circle) -> list[Point]:
    if isinstance(a, Line) and isinstance(b, Line):
        return line_line_intersections(a, b)
    if isinstance(a, Line) and isinstance(b, Circle):
        return line_circle_intersections(a, b)
    if isinstance(a, Circle) and isinstance(b, Line):
        return line_circle_intersections(b, a)
    return circle_circle_intersections(a, b)


def nearest_endpoint_distance(line_or_endpoints, point: Point) -> float:
    return min(distance(line_or_endpoints.start, point), distance(line_or_endpoints.end, point))


def choose_intersection(
    candidates: list[Point], endpoints_a, endpoints_b
) -> Point | None:
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda p: nearest_endpoint_distance(endpoints_a, p)
        + nearest_endpoint_distance(endpoints_b, p),
    )


def _offset_loci(support: Line | Circle, radius: float) -> list[Line | Circle]:
    if isinstance(support, Line):
        direction = (support.end - support.start).normalized()
        normal = direction.left() * radius
        return [
            Line(support.start + normal, support.end + normal),
            Line(support.start - normal, support.end - normal),
        ]
    radii = [support.radius + radius]
    if support.radius > radius + EPS:
        radii.append(support.radius - radius)
    elif radius > support.radius + EPS:
        radii.append(radius - support.radius)
    return [Circle(support.center, value) for value in radii if value > EPS]


def _tangent_point(support: Line | Circle, center: Point) -> Point:
    if isinstance(support, Line):
        direction = (support.end - support.start).normalized()
        return support.start + direction * (center - support.start).dot(direction)
    radial = (center - support.center).normalized()
    toward = support.center + radial * support.radius
    away = support.center - radial * support.radius
    # The correct side is the point whose distance from the candidate fillet
    # center matches the requested fillet radius. The caller validates it.
    return toward if distance(center, toward) <= distance(center, away) else away


def fillet_candidates(
    a: Line | Circle,
    b: Line | Circle,
    endpoints_a,
    endpoints_b,
    radius: float,
) -> list[Fillet]:
    if radius <= EPS:
        return []
    result: list[Fillet] = []
    for locus_a in _offset_loci(a, radius):
        for locus_b in _offset_loci(b, radius):
            for center in intersections(locus_a, locus_b):
                try:
                    tangent_a = _tangent_point(a, center)
                    tangent_b = _tangent_point(b, center)
                except ValueError:
                    continue
                actual_a = distance(center, tangent_a)
                actual_b = distance(center, tangent_b)
                if abs(actual_a - radius) > max(1e-4, radius * 1e-5):
                    continue
                if abs(actual_b - radius) > max(1e-4, radius * 1e-5):
                    continue
                if distance(tangent_a, tangent_b) < EPS:
                    continue
                score = (
                    nearest_endpoint_distance(endpoints_a, tangent_a)
                    + nearest_endpoint_distance(endpoints_b, tangent_b)
                )
                result.append(Fillet(center, tangent_a, tangent_b, radius, score))
    result.sort(key=lambda item: item.score)
    return result


def arc_midpoint(start: Point, end: Point, center: Point, clockwise: bool) -> Point:
    a0 = math.atan2(start.y - center.y, start.x - center.x)
    a1 = math.atan2(end.y - center.y, end.x - center.x)
    if clockwise:
        sweep = -((a0 - a1) % TAU)
    else:
        sweep = (a1 - a0) % TAU
    angle = a0 + sweep / 2.0
    radius = distance(start, center)
    return Point(center.x + radius * math.cos(angle), center.y + radius * math.sin(angle))


def fillet_continuity_score(
    fillet: Fillet,
    retained_direction_a: Point,
    retained_direction_b: Point,
) -> tuple[float, bool]:
    """Return the best tangent-continuity score and whether it is CCW."""
    radial_a = (fillet.tangent_a - fillet.center).normalized()
    radial_b = (fillet.tangent_b - fillet.center).normalized()
    ccw_at_a = radial_a.left()
    ccw_at_b = radial_b.left()
    target_a = retained_direction_a.normalized() * -1.0
    target_b = retained_direction_b.normalized()

    ccw_score = ccw_at_a.dot(target_a) + ccw_at_b.dot(target_b)
    clockwise_score = (ccw_at_a * -1.0).dot(target_a) + (
        ccw_at_b * -1.0
    ).dot(target_b)
    return (
        (ccw_score, True)
        if ccw_score >= clockwise_score
        else (clockwise_score, False)
    )


def fillet_short_arc_continuity_score(
    fillet: Fillet,
    retained_direction_a: Point,
    retained_direction_b: Point,
) -> float:
    """Return tangent continuity for the minor arc that will be drawn."""
    radial_a = (fillet.tangent_a - fillet.center).normalized()
    radial_b = (fillet.tangent_b - fillet.center).normalized()
    start_angle = math.atan2(radial_a.y, radial_a.x)
    end_angle = math.atan2(radial_b.y, radial_b.x)
    use_ccw = (end_angle - start_angle) % TAU <= math.pi + EPS
    tangent_a = radial_a.left()
    tangent_b = radial_b.left()
    if not use_ccw:
        tangent_a = tangent_a * -1.0
        tangent_b = tangent_b * -1.0
    return tangent_a.dot(retained_direction_a.normalized() * -1.0) + (
        tangent_b.dot(retained_direction_b.normalized())
    )


def fillet_minor_sweep(fillet: Fillet) -> float:
    """Return the smaller angle between a fillet's two tangent radii."""
    start_angle = math.atan2(
        fillet.tangent_a.y - fillet.center.y,
        fillet.tangent_a.x - fillet.center.x,
    )
    end_angle = math.atan2(
        fillet.tangent_b.y - fillet.center.y,
        fillet.tangent_b.x - fillet.center.x,
    )
    return min((end_angle - start_angle) % TAU, (start_angle - end_angle) % TAU)


def fillet_midpoint(
    fillet: Fillet,
    retained_direction_a: Point,
    retained_direction_b: Point,
) -> Point:
    """Return the midpoint of the shortest arc between the tangent points.

    For a semicircle, both sweeps have the same angle, so use tangent
    continuity as the tie breaker.
    """
    start_angle = math.atan2(
        fillet.tangent_a.y - fillet.center.y,
        fillet.tangent_a.x - fillet.center.x,
    )
    end_angle = math.atan2(
        fillet.tangent_b.y - fillet.center.y,
        fillet.tangent_b.x - fillet.center.x,
    )
    ccw_sweep = (end_angle - start_angle) % TAU
    clockwise_sweep = -((start_angle - end_angle) % TAU)
    if ccw_sweep < -clockwise_sweep - EPS:
        sweep = ccw_sweep
    elif -clockwise_sweep < ccw_sweep - EPS:
        sweep = clockwise_sweep
    else:
        _, use_ccw = fillet_continuity_score(
            fillet, retained_direction_a, retained_direction_b
        )
        sweep = ccw_sweep if use_ccw else clockwise_sweep
    midpoint_angle = start_angle + sweep / 2.0
    return Point(
        fillet.center.x + fillet.radius * math.cos(midpoint_angle),
        fillet.center.y + fillet.radius * math.sin(midpoint_angle),
    )


def rotate_around(point: Point, center: Point, angle_radians: float) -> Point:
    relative = point - center
    cosine = math.cos(angle_radians)
    sine = math.sin(angle_radians)
    return center + Point(
        relative.x * cosine - relative.y * sine,
        relative.x * sine + relative.y * cosine,
    )


def tangent_arc_from_line(
    line: Line, center: Point, angle_degrees: float
) -> TangentArc:
    """Create an arc centered at center and tangent to line at its projection."""
    direction = (line.end - line.start).normalized()
    start = line.start + direction * (center - line.start).dot(direction)
    radius = distance(center, start)
    if radius < EPS:
        raise ValueError("The center must not lie on the selected track.")
    if abs(angle_degrees) < EPS:
        raise ValueError("The angle must not be zero.")
    if abs(angle_degrees) >= 360.0 - EPS:
        raise ValueError("The absolute angle must be less than 360 degrees.")

    # KiCad board coordinates use a downward-positive Y axis, so mathematical
    # positive rotation appears clockwise on screen. Reverse the sign to make
    # positive user input appear counterclockwise in the PCB Editor.
    angle_radians = math.radians(-angle_degrees)
    mid = rotate_around(start, center, angle_radians / 2.0)
    end = rotate_around(start, center, angle_radians)
    return TangentArc(center, start, mid, end, radius)
