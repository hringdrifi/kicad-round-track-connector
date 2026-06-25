import math
import os
import sys
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "round_track_connector")
)

from geometry import (
    Circle,
    Line,
    Point,
    circle_circle_intersections,
    distance_to_arc,
    Fillet,
    fillet_continuity_score,
    fillet_midpoint,
    fillet_candidates,
    line_circle_intersections,
    line_line_intersections,
    point_on_arc,
    tangent_arc_from_line,
    tangent_points_from_point,
)


class GeometryTests(unittest.TestCase):
    def assertPointAlmostEqual(self, actual, expected):
        self.assertAlmostEqual(actual.x, expected.x, places=6)
        self.assertAlmostEqual(actual.y, expected.y, places=6)

    def test_line_line(self):
        points = line_line_intersections(
            Line(Point(0, 0), Point(10, 0)),
            Line(Point(5, -3), Point(5, 3)),
        )
        self.assertEqual(len(points), 1)
        self.assertPointAlmostEqual(points[0], Point(5, 0))

    def test_line_circle(self):
        points = line_circle_intersections(
            Line(Point(-10, 0), Point(10, 0)), Circle(Point(0, 0), 5)
        )
        self.assertEqual(len(points), 2)
        self.assertEqual(sorted(round(p.x) for p in points), [-5, 5])

    def test_tangent_points_from_external_point(self):
        points = tangent_points_from_point(
            Point(10, 0), Circle(Point(0, 0), 5)
        )
        self.assertEqual(len(points), 2)
        for point in points:
            self.assertAlmostEqual((point - Point(0, 0)).length(), 5)
            self.assertAlmostEqual(
                (point - Point(10, 0)).dot(point - Point(0, 0)), 0
            )

    def test_no_tangent_from_inside_circle(self):
        self.assertEqual(
            tangent_points_from_point(Point(1, 0), Circle(Point(0, 0), 5)),
            [],
        )

    def test_point_on_arc_uses_midpoint_to_select_sweep(self):
        center = Point(0, 0)
        self.assertTrue(
            point_on_arc(
                Point(0, 5),
                Point(5, 0),
                Point(0, 5),
                Point(-5, 0),
                center,
            )
        )
        self.assertFalse(
            point_on_arc(
                Point(0, -5),
                Point(5, 0),
                Point(0, 5),
                Point(-5, 0),
                center,
            )
        )

    def test_distance_to_arc_uses_arc_body_when_projection_is_on_sweep(self):
        circle = Circle(Point(0, 0), 5)
        self.assertAlmostEqual(
            distance_to_arc(
                Point(0, 8),
                circle,
                Point(5, 0),
                Point(0, 5),
                Point(-5, 0),
            ),
            3,
        )

    def test_circle_circle(self):
        points = circle_circle_intersections(
            Circle(Point(0, 0), 5), Circle(Point(8, 0), 5)
        )
        self.assertEqual(len(points), 2)
        self.assertEqual(sorted(round(p.y) for p in points), [-3, 3])

    def test_right_angle_line_fillet(self):
        horizontal = Line(Point(-10, 0), Point(-2, 0))
        vertical = Line(Point(0, -10), Point(0, -2))
        candidates = fillet_candidates(
            horizontal, vertical, horizontal, vertical, 2
        )
        self.assertTrue(candidates)
        best = candidates[0]
        self.assertAlmostEqual(best.radius, 2)
        self.assertAlmostEqual(best.center.x, -2)
        self.assertAlmostEqual(best.center.y, -2)
        self.assertAlmostEqual(best.tangent_a.y, 0)
        self.assertAlmostEqual(best.tangent_b.x, 0)

    def test_line_circle_fillet(self):
        line = Line(Point(-10, 8), Point(10, 8))
        circle = Circle(Point(0, 0), 5)
        candidates = fillet_candidates(line, circle, line, line, 2)
        self.assertTrue(candidates)
        self.assertTrue(
            any(
                math.isclose((c.center - c.tangent_a).length(), 2, abs_tol=1e-6)
                and math.isclose((c.center - c.tangent_b).length(), 2, abs_tol=1e-6)
                for c in candidates
            )
        )

    def test_fillet_midpoint_uses_smooth_direction(self):
        fillet = Fillet(
            center=Point(0, 0),
            tangent_a=Point(1, 0),
            tangent_b=Point(0, -1),
            radius=1,
            score=0,
        )
        midpoint = fillet_midpoint(
            fillet,
            retained_direction_a=Point(0, 1),
            retained_direction_b=Point(-1, 0),
        )
        root_half = math.sqrt(0.5)
        self.assertPointAlmostEqual(midpoint, Point(root_half, -root_half))

    def test_fillet_midpoint_uses_long_arc_when_smoothness_requires_it(self):
        fillet = Fillet(
            center=Point(0, 0),
            tangent_a=Point(1, 0),
            tangent_b=Point(0, -1),
            radius=1,
            score=0,
        )
        midpoint = fillet_midpoint(
            fillet,
            retained_direction_a=Point(0, -1),
            retained_direction_b=Point(1, 0),
        )
        root_half = math.sqrt(0.5)
        self.assertPointAlmostEqual(midpoint, Point(-root_half, root_half))

    def test_continuity_score_rejects_foldback_candidate(self):
        smooth = Fillet(
            center=Point(0, 0),
            tangent_a=Point(1, 0),
            tangent_b=Point(0, 1),
            radius=1,
            score=10,
        )
        foldback = Fillet(
            center=Point(0, 0),
            tangent_a=Point(1, 0),
            tangent_b=Point(0, -1),
            radius=1,
            score=1,
        )
        retained_a = Point(0, -1)
        retained_b = Point(-1, 0)
        smooth_score, _ = fillet_continuity_score(
            smooth, retained_a, retained_b
        )
        foldback_score, _ = fillet_continuity_score(
            foldback, retained_a, retained_b
        )
        self.assertGreater(smooth_score, foldback_score)

    def test_tangent_arc_projects_center_to_line(self):
        arc = tangent_arc_from_line(
            Line(Point(0, 0), Point(10, 0)), Point(3, 4), 90
        )
        self.assertPointAlmostEqual(arc.start, Point(3, 0))
        self.assertPointAlmostEqual(
            arc.mid, Point(3 - math.sqrt(8), 4 - math.sqrt(8))
        )
        self.assertPointAlmostEqual(arc.end, Point(-1, 4))
        self.assertAlmostEqual(arc.radius, 4)

    def test_negative_tangent_arc_angle_turns_clockwise(self):
        arc = tangent_arc_from_line(
            Line(Point(0, 0), Point(10, 0)), Point(3, 4), -90
        )
        self.assertPointAlmostEqual(arc.end, Point(7, 4))

    def test_tangent_arc_rejects_center_on_line(self):
        with self.assertRaises(ValueError):
            tangent_arc_from_line(
                Line(Point(0, 0), Point(10, 0)), Point(3, 0), 90
            )

if __name__ == "__main__":
    unittest.main()
