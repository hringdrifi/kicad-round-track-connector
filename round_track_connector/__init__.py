from .plugin import (
    ConnectTracksPlugin,
    ConnectTracksWithRadiusPlugin,
    DrawTangentArcPlugin,
)


ConnectTracksPlugin().register()
ConnectTracksWithRadiusPlugin().register()
DrawTangentArcPlugin().register()
