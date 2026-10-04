# Visual 0.11 assets

## Third-party sources (Poly Haven, CC0 1.0)

All photographed sources come from Poly Haven under **CC0 1.0 Universal**
(https://polyhaven.com/license). They can be redistributed with the game.
Poly Haven branding and other website content are not included.
`tools/fetch_photoreal11.py` re-downloads them and checks the MD5 the Poly
Haven API publishes for every file.

| Folder | Poly Haven asset | Physical size used for UV scale |
| --- | --- | --- |
| `textures/asphalt_02` | https://polyhaven.com/a/asphalt_02 | 3.0 m |
| `textures/beige_wall_001` | https://polyhaven.com/a/beige_wall_001 | 3.0 m |
| `textures/concrete_block_wall` | https://polyhaven.com/a/concrete_block_wall | 2.0 m |
| `textures/concrete_pavement` | https://polyhaven.com/a/concrete_pavement | 1.8 m |
| `textures/exterior_wall_cladding_03` | https://polyhaven.com/a/exterior_wall_cladding_03 | 1.96 m |
| `textures/grey_plaster_02` | https://polyhaven.com/a/grey_plaster_02 | 1.0 m |
| `textures/grey_roof_tiles_02` | https://polyhaven.com/a/grey_roof_tiles_02 | 1.5 m |
| `textures/japanese_cedar_planks` | https://polyhaven.com/a/japanese_cedar_planks | 1.13 m |
| `textures/painted_metal_shutter` | https://polyhaven.com/a/painted_metal_shutter | 2.0 m |
| `sky/qwantani_late_afternoon_puresky_2k_nosun.hdr` | https://polyhaven.com/a/qwantani_late_afternoon_puresky | panorama |

Textures are the unmodified 2K JPG downloads (diffuse, OpenGL normal and ARM:
ambient occlusion in red, roughness in green, metallic in blue). The sky is
the 2K HDR with the solar disc clamped to a luminance of 6 so the
DirectionalLight is the only sun (see the comment in GraphicsDirector.gd).

## Original assets

Everything in `houses/`, `buildings/` and `props/` is original geometry
authored by the Blender scripts in `res://tools/blender/` (no third-party
meshes). The GLBs carry named materials only; `materials/*.tres` are built by
`res://tools/build_photoreal11_materials.gd` from the textures above.

## Visual 0.12 (gothic night) additions — Poly Haven, CC0 1.0

Stored in `res://art/gothic12/` and re-downloaded by `tools/fetch_gothic12.py`.

| Folder | Poly Haven asset | Physical size used |
| --- | --- | --- |
| `textures/concrete_wall_006` | https://polyhaven.com/a/concrete_wall_006 | 2.0 m |
| `textures/dark_brick_wall` | https://polyhaven.com/a/dark_brick_wall | 1.05 m |
| `textures/castle_wall_slates` | https://polyhaven.com/a/castle_wall_slates | 2.5 m |
| `textures/rust_coarse_01` | https://polyhaven.com/a/rust_coarse_01 | 2.2 m |
| `textures/metal_grate_rusty` | https://polyhaven.com/a/metal_grate_rusty | 0.5 m |
| `textures/black_painted_planks` | https://polyhaven.com/a/black_painted_planks | 1.6 m |
| `textures/floral_jacquard` | https://polyhaven.com/a/floral_jacquard | 0.38 m |
| `textures/leather_red_02` (colour variant `coll1`) | https://polyhaven.com/a/leather_red_02 | 0.6 m |
| `sky/qwantani_moonrise_puresky_2k_night.hdr` | https://polyhaven.com/a/qwantani_moonrise_puresky | panorama |

The sky is the 2K HDR with its brightest disc clamped to a luminance of 6 and
dimmed in the engine (`SKY_ENERGY`) to a faint night gradient.
