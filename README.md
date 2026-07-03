# Round Track Connector for KiCad 10

Extends two selected PCB track segments/arcs to their geometric intersection,
or trims/extends them and inserts a tangent arc of a specified radius.

## Actions

- **Connect Tracks** — immediately connects the two selected items. If the
  selected items are on different copper layers, a through via is added at the
  connection point using KiCad's current via size and drill settings.
- **Connect Tracks with Radius** — asks for a radius in millimeters. The last
  entered value is remembered. The selected items must be on the same copper
  layer.
- **Draw Tangent Arc** asks for a center X/Y coordinate in millimeters and a
  signed angle in degrees. Select one straight track; its nearest endpoint is
  moved to the tangent point and an arc with the same net, layer, and width is
  added. Positive angles are counterclockwise and negative angles are clockwise.
- **Make Line Tangent to Arc** moves the nearest endpoints of one selected
  straight track and one selected arc to a shared tangent point. The arc keeps
  its original center, radius, and sweep direction.

Straight-to-straight, straight-to-arc, and arc-to-arc combinations are
supported. Different nets are allowed; a generated fillet arc inherits the first
selected item's net.

## Install on Windows

Copy the `round_track_connector` directory into:

```text
%APPDATA%\kicad\10.0\scripting\plugins\
```

In PCB Editor, open **Tools → External Plugins → Refresh Plugins**. The two
actions can then be enabled on the plugin toolbar.

## Development test

Run the geometry tests with KiCad's bundled Python:

```powershell
& 'C:\Program Files\KiCad\10.0\bin\python.exe' -m unittest discover -s tests -v
```

## Notes

- Intersections are calculated using the infinite supporting line/circle.
- If two supporting curves have multiple intersections, the solution requiring
  the least movement of the selected items' endpoints is used.
- The plugin uses KiCad's legacy `pcbnew` Python Action Plugin API because it is
  the KiCad 10 API that exposes toolbar action plugins directly.
