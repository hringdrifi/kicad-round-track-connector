from __future__ import annotations

from dataclasses import dataclass
import os

import pcbnew
import wx

from . import geometry as geo


class ConnectorError(RuntimeError):
    pass


def _read_setting(config, key: str, default: str) -> str:
    legacy = wx.Config("TrackConnector")
    return config.Read(key, legacy.Read(key, default))


@dataclass
class TrackGeometry:
    item: object
    support: geo.Line | geo.Circle
    start: geo.Point
    end: geo.Point
    mid: geo.Point | None = None


def _point(value) -> geo.Point:
    return geo.Point(float(value.x), float(value.y))


def _vector(point: geo.Point):
    return pcbnew.VECTOR2I(int(round(point.x)), int(round(point.y)))


def _circle_from_three_points(a: geo.Point, b: geo.Point, c: geo.Point) -> geo.Circle:
    d = 2.0 * (
        a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y)
    )
    if abs(d) < geo.EPS:
        raise ConnectorError("The selected arc is degenerate.")
    aa = a.x * a.x + a.y * a.y
    bb = b.x * b.x + b.y * b.y
    cc = c.x * c.x + c.y * c.y
    center = geo.Point(
        (aa * (b.y - c.y) + bb * (c.y - a.y) + cc * (a.y - b.y)) / d,
        (aa * (c.x - b.x) + bb * (a.x - c.x) + cc * (b.x - a.x)) / d,
    )
    return geo.Circle(center, geo.distance(center, a))


def _track_geometry(item) -> TrackGeometry:
    start = _point(item.GetStart())
    end = _point(item.GetEnd())
    if isinstance(item, pcbnew.PCB_ARC):
        mid = _point(item.GetMid())
        return TrackGeometry(item, _circle_from_three_points(start, mid, end), start, end, mid)
    return TrackGeometry(item, geo.Line(start, end), start, end)


def _selected_tracks(board) -> list:
    tracks = [
        item
        for item in board.GetTracks()
        if item.IsSelected()
        and isinstance(item, (pcbnew.PCB_TRACK, pcbnew.PCB_ARC))
        and not isinstance(item, pcbnew.PCB_VIA)
    ]
    if len(tracks) != 2:
        raise ConnectorError("Select exactly two track segments or track arcs.")
    if tracks[0].GetLayer() != tracks[1].GetLayer():
        raise ConnectorError("The selected tracks must be on the same copper layer.")
    return tracks


def _selected_straight_track(board):
    tracks = [
        item
        for item in board.GetTracks()
        if item.IsSelected()
        and isinstance(item, pcbnew.PCB_TRACK)
        and not isinstance(item, (pcbnew.PCB_ARC, pcbnew.PCB_VIA))
    ]
    selected_copper_items = [
        item
        for item in board.GetTracks()
        if item.IsSelected()
        and isinstance(item, (pcbnew.PCB_TRACK, pcbnew.PCB_ARC, pcbnew.PCB_VIA))
    ]
    if len(tracks) != 1 or len(selected_copper_items) != 1:
        raise ConnectorError("Select exactly one straight track segment.")
    return tracks[0]


def _endpoint_to_move(track: TrackGeometry, target: geo.Point) -> str:
    return "start" if geo.distance(track.start, target) <= geo.distance(track.end, target) else "end"


def _set_endpoint(track: TrackGeometry, target: geo.Point) -> None:
    if _endpoint_to_move(track, target) == "start":
        track.item.SetStart(_vector(target))
    else:
        track.item.SetEnd(_vector(target))


def _retained_direction(track: TrackGeometry, tangent: geo.Point) -> geo.Point:
    moved = _endpoint_to_move(track, tangent)
    other = track.end if moved == "start" else track.start
    if isinstance(track.support, geo.Line):
        return other - tangent

    radial = (tangent - track.support.center).normalized()
    candidate = radial.left()
    if candidate.dot(other - tangent) < 0.0:
        candidate = candidate * -1.0
    return candidate


def connect_selected(radius_mm: float | None = None) -> None:
    board = pcbnew.GetBoard()
    if board is None:
        raise ConnectorError("No board is open.")
    items = _selected_tracks(board)
    a, b = (_track_geometry(item) for item in items)

    if radius_mm is None:
        point = geo.choose_intersection(
            geo.intersections(a.support, b.support), a, b
        )
        if point is None:
            raise ConnectorError("The selected tracks do not have an intersection.")
        _set_endpoint(a, point)
        _set_endpoint(b, point)
    else:
        radius = float(pcbnew.FromMM(radius_mm))
        solutions = geo.fillet_candidates(a.support, b.support, a, b, radius)
        if not solutions:
            raise ConnectorError(
                "No tangent connection exists for the specified radius."
            )
        ranked = []
        for candidate in solutions:
            candidate_direction_a = _retained_direction(
                a, candidate.tangent_a
            )
            candidate_direction_b = _retained_direction(
                b, candidate.tangent_b
            )
            continuity, _ = geo.fillet_continuity_score(
                candidate, candidate_direction_a, candidate_direction_b
            )
            ranked.append(
                (
                    -continuity,
                    candidate.score,
                    candidate,
                    candidate_direction_a,
                    candidate_direction_b,
                )
            )
        _, _, fillet, direction_a, direction_b = min(
            ranked, key=lambda entry: (entry[0], entry[1])
        )
        _set_endpoint(a, fillet.tangent_a)
        _set_endpoint(b, fillet.tangent_b)

        arc = pcbnew.PCB_ARC(board)
        arc.SetStart(_vector(fillet.tangent_a))
        arc.SetMid(
            _vector(geo.fillet_midpoint(fillet, direction_a, direction_b))
        )
        arc.SetEnd(_vector(fillet.tangent_b))
        arc.SetLayer(items[0].GetLayer())
        arc.SetWidth(items[0].GetWidth())
        arc.SetNetCode(items[0].GetNetCode())
        board.Add(arc)

    board.BuildConnectivity()
    pcbnew.Refresh()


def draw_tangent_arc(center_x_mm: float, center_y_mm: float, angle_degrees: float) -> None:
    board = pcbnew.GetBoard()
    if board is None:
        raise ConnectorError("No board is open.")
    item = _selected_straight_track(board)
    track = _track_geometry(item)
    center = geo.Point(
        float(pcbnew.FromMM(center_x_mm)),
        float(pcbnew.FromMM(center_y_mm)),
    )
    try:
        tangent_arc = geo.tangent_arc_from_line(
            track.support, center, angle_degrees
        )
    except ValueError as exc:
        raise ConnectorError(str(exc)) from exc

    _set_endpoint(track, tangent_arc.start)
    arc = pcbnew.PCB_ARC(board)
    arc.SetStart(_vector(tangent_arc.start))
    arc.SetMid(_vector(tangent_arc.mid))
    arc.SetEnd(_vector(tangent_arc.end))
    arc.SetLayer(item.GetLayer())
    arc.SetWidth(item.GetWidth())
    arc.SetNetCode(item.GetNetCode())
    board.Add(arc)

    board.BuildConnectivity()
    pcbnew.Refresh()


class RadiusDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Connect Tracks with Radius")
        config = wx.Config("RoundTrackConnector")

        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label="Radius:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.radius = wx.TextCtrl(
            panel,
            value=_read_setting(config, "radius_mm", "1.0"),
            size=(110, -1),
        )
        row.Add(self.radius, 1)
        row.Add(wx.StaticText(panel, label="mm"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)
        outer.Add(row, 0, wx.EXPAND | wx.ALL, 12)

        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.FindWindowById(wx.ID_OK).SetLabel("Connect")
        outer.Add(buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        panel.SetSizer(outer)
        top = wx.BoxSizer(wx.VERTICAL)
        top.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(top)
        self.radius.SetFocus()
        self.radius.SelectAll()

    def get_radius(self) -> float:
        try:
            value = float(self.radius.GetValue())
        except ValueError as exc:
            raise ConnectorError("Radius must be a number.") from exc
        if value <= 0:
            raise ConnectorError("Radius must be greater than zero.")
        wx.Config("RoundTrackConnector").Write("radius_mm", self.radius.GetValue())
        wx.Config("RoundTrackConnector").Flush()
        return value


class TangentArcDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Draw Tangent Arc")
        config = wx.Config("RoundTrackConnector")
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(3, 3, 8, 8)
        grid.AddGrowableCol(1)

        self.center_x = self._add_field(
            panel, grid, "Center X:",
            _read_setting(config, "center_x_mm", "0.0"), "mm"
        )
        self.center_y = self._add_field(
            panel, grid, "Center Y:",
            _read_setting(config, "center_y_mm", "0.0"), "mm"
        )
        self.angle = self._add_field(
            panel, grid, "Angle:",
            _read_setting(config, "angle_degrees", "90.0"), "deg"
        )
        outer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        outer.Add(
            wx.StaticText(
                panel,
                label="Positive: counterclockwise / Negative: clockwise",
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            12,
        )

        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.FindWindowById(wx.ID_OK).SetLabel("Draw")
        outer.Add(buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        panel.SetSizer(outer)
        top = wx.BoxSizer(wx.VERTICAL)
        top.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(top)
        self.center_x.SetFocus()
        self.center_x.SelectAll()

    @staticmethod
    def _add_field(panel, grid, label, value, unit):
        grid.Add(wx.StaticText(panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
        control = wx.TextCtrl(panel, value=value, size=(120, -1))
        grid.Add(control, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label=unit), 0, wx.ALIGN_CENTER_VERTICAL)
        return control

    def get_values(self) -> tuple[float, float, float]:
        try:
            values = (
                float(self.center_x.GetValue()),
                float(self.center_y.GetValue()),
                float(self.angle.GetValue()),
            )
        except ValueError as exc:
            raise ConnectorError(
                "Center coordinates and angle must be numbers."
            ) from exc

        if abs(values[2]) < geo.EPS or abs(values[2]) >= 360.0:
            raise ConnectorError(
                "Angle must be non-zero and less than 360 degrees."
            )
        config = wx.Config("RoundTrackConnector")
        config.Write("center_x_mm", self.center_x.GetValue())
        config.Write("center_y_mm", self.center_y.GetValue())
        config.Write("angle_degrees", self.angle.GetValue())
        config.Flush()
        return values


class _BasePlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.category = "Round Track Connector"
        self.show_toolbar_button = True

    def _set_icon(self, filename):
        self.icon_file_name = os.path.join(os.path.dirname(__file__), filename)

    def _run(self, radius):
        try:
            connect_selected(radius)
        except ConnectorError as exc:
            wx.MessageBox(str(exc), self.name, wx.OK | wx.ICON_ERROR)
        except Exception as exc:
            wx.MessageBox(
                f"Unexpected error:\n{exc}", self.name, wx.OK | wx.ICON_ERROR
            )


class ConnectTracksPlugin(_BasePlugin):
    def defaults(self):
        super().defaults()
        self.name = "Connect Tracks"
        self.description = "Extend two selected straight/arc tracks to their intersection"
        self._set_icon("connect_tracks.png")

    def Run(self):
        self._run(None)


class ConnectTracksWithRadiusPlugin(_BasePlugin):
    def defaults(self):
        super().defaults()
        self.name = "Connect Tracks with Radius"
        self.description = "Connect two selected straight/arc tracks with a tangent arc"
        self._set_icon("connect_tracks_with_radius.png")

    def Run(self):
        dialog = RadiusDialog()
        try:
            if dialog.ShowModal() == wx.ID_OK:
                try:
                    radius = dialog.get_radius()
                except ConnectorError as exc:
                    wx.MessageBox(str(exc), self.name, wx.OK | wx.ICON_ERROR)
                    return
                self._run(radius)
        finally:
            dialog.Destroy()


class DrawTangentArcPlugin(_BasePlugin):
    def defaults(self):
        super().defaults()
        self.name = "Draw Tangent Arc"
        self.description = "Draw a centered arc tangent to one selected straight track"
        self._set_icon("draw_tangent_arc.png")

    def Run(self):
        dialog = TangentArcDialog()
        try:
            if dialog.ShowModal() == wx.ID_OK:
                try:
                    draw_tangent_arc(*dialog.get_values())
                except ConnectorError as exc:
                    wx.MessageBox(str(exc), self.name, wx.OK | wx.ICON_ERROR)
                except Exception as exc:
                    wx.MessageBox(
                        f"Unexpected error:\n{exc}",
                        self.name,
                        wx.OK | wx.ICON_ERROR,
                    )
        finally:
            dialog.Destroy()
