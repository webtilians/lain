# Realism 0.10 assets

The twelve texture source files in `materials/` are unmodified 2K downloads
from Poly Haven. Each set includes diffuse color, an OpenGL normal map and an
ARM map (ambient occlusion in red, roughness in green, metallic in blue).
Godot uses the first two ARM channels for these non-metallic surfaces.

| Set | Source |
| --- | --- |
| Asphalt | https://polyhaven.com/a/aerial_asphalt_01 |
| Plaster | https://polyhaven.com/a/plastered_wall_02 |
| Concrete | https://polyhaven.com/a/concrete_floor_02 |
| Timber floor | https://polyhaven.com/a/wood_floor |

License: **CC0 1.0 Universal**, per https://polyhaven.com/license.
License text: https://creativecommons.org/publicdomain/zero/1.0/legalcode.
These assets can be redistributed with the game. The Poly Haven website's
other content and branding are not included.

`materials/manifest.json` records the exact download URL, original filename's
local destination and source MD5 for each file. Verified on 2026-09-24.
The `.import` files enable mipmaps, GPU compression and correct normal-map
handling. Godot regenerates `.ctex` caches on first import; the source images
are all committed, so no manual download is needed to play.

`Foliage.tscn` is original geometric foliage authored by
`res://tools/build_foliage10.gd`: 26,940 individual leaves in 32 batches, with
deterministic placement from the existing City09 plant locations. Rebuild
with a real Godot renderer, not headless: headless cannot preserve MultiMesh
transform buffers. The generated scene is included and ready to load.

Furniture bevels are generated from the existing box dimensions by
`SoftEdges.gd`, without changing collision shapes. No anime frames or
generated mockups are used as gameplay backgrounds.
