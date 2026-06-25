from .plugin import (
    ConnectTracksPlugin,
    ConnectTracksWithRadiusPlugin,
    DrawTangentArcPlugin,
    MakeLineTangentToArcPlugin,
)


ConnectTracksPlugin().register()
ConnectTracksWithRadiusPlugin().register()
DrawTangentArcPlugin().register()
MakeLineTangentToArcPlugin().register()
