"""Integration checks using KiCad's bundled Python, without GUI registration."""

import importlib
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

try:
    import pcbnew
    import wx
except ImportError:
    pcbnew = None

if pcbnew is not None:
    package = types.ModuleType("_connector_test")
    package.__path__ = [str(Path(__file__).resolve().parents[1] / "round_track_connector")]
    sys.modules[package.__name__] = package
    plugin = importlib.import_module(package.__name__ + ".plugin")


@unittest.skipIf(pcbnew is None, "Requires KiCad's bundled Python")
class FilletIntegrationTests(unittest.TestCase):
    def make_board(self, reverse_a=False, reverse_b=False, swap=False):
        board = pcbnew.BOARD()
        endpoints = [
            ((142.875, 83.34375), (143.271875, 83.34375)),
            ((143.271875, 83.34375), (143.271875, 83.740625)),
        ]
        tracks = []
        for points, reverse in zip(endpoints, (reverse_a, reverse_b)):
            start, end = points[::-1] if reverse else points
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(*[pcbnew.FromMM(v) for v in start]))
            track.SetEnd(pcbnew.VECTOR2I(*[pcbnew.FromMM(v) for v in end]))
            track.SetLayer(pcbnew.F_Cu)
            track.SetWidth(pcbnew.FromMM(0.2))
            track.SetSelected()
            tracks.append(track)
        for track in tracks[::-1] if swap else tracks:
            board.Add(track)
        return board, tracks

    def test_fillet_preserves_far_endpoints_for_large_and_small_radii(self):
        for radius in (0.1, 0.39):
            for reverse_a in (False, True):
                for reverse_b in (False, True):
                    for swap in (False, True):
                        with self.subTest(radius=radius, a=reverse_a, b=reverse_b, swap=swap):
                            board, tracks = self.make_board(reverse_a, reverse_b, swap)
                            with patch.object(pcbnew, "GetBoard", return_value=board), patch.object(pcbnew, "Refresh"):
                                plugin.connect_selected(radius)
                            a, b = tracks
                            self.assertEqual(
                                a.GetEnd() if reverse_a else a.GetStart(),
                                pcbnew.VECTOR2I(pcbnew.FromMM(142.875), pcbnew.FromMM(83.34375)),
                            )
                            self.assertEqual(
                                b.GetStart() if reverse_b else b.GetEnd(),
                                pcbnew.VECTOR2I(pcbnew.FromMM(143.271875), pcbnew.FromMM(83.740625)),
                            )
                            arcs = [t for t in board.GetTracks() if isinstance(t, pcbnew.PCB_ARC)]
                            self.assertEqual(len(arcs), 1)
                            expected_mid = (
                                143.271875 - radius + radius / math.sqrt(2),
                                83.34375 + radius - radius / math.sqrt(2),
                            )
                            for actual, expected in zip(arcs[0].GetMid(), expected_mid):
                                self.assertLessEqual(abs(actual - pcbnew.FromMM(expected)), 1)
                            self.assertEqual(
                                {tuple(arcs[0].GetStart()), tuple(arcs[0].GetEnd())},
                                {(pcbnew.FromMM(143.271875 - radius), pcbnew.FromMM(83.34375)),
                                 (pcbnew.FromMM(143.271875), pcbnew.FromMM(83.34375 + radius))},
                            )
                            self.assertEqual(
                                {tuple(arcs[0].GetStart()), tuple(arcs[0].GetEnd())},
                                {tuple(a.GetStart() if reverse_a else a.GetEnd()),
                                 tuple(b.GetEnd() if reverse_b else b.GetStart())},
                            )

    def test_fillet_still_rejects_foldback_beyond_far_endpoints(self):
        board, tracks = self.make_board()
        original = [(tuple(t.GetStart()), tuple(t.GetEnd())) for t in tracks]
        with patch.object(pcbnew, "GetBoard", return_value=board), patch.object(pcbnew, "Refresh"):
            with self.assertRaises(plugin.ConnectorError):
                plugin.connect_selected(0.4)
        self.assertEqual([(tuple(t.GetStart()), tuple(t.GetEnd())) for t in tracks], original)
        self.assertEqual(len(list(board.GetTracks())), 2)


if __name__ == "__main__":
    unittest.main()
