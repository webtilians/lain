# Visual 0.5 — materiales y procedencia

Texturas originales creadas con la herramienta integrada ImageGen de Codex,
no con el CLI/API. Copiadas al repositorio: ninguna referencia de ejecución
apunta al directorio personal de imágenes generadas. Tamaño nativo de cada
PNG: 1254×1254. `foliage.png` conserva canal alfa real; las otras son RGB.
Los `.png.import` habilitan mipmaps. Godot genera sus `.ctex` localmente;
no se deben copiar cachés entre equipos.

La imagen `pantalla lain.jpeg` proporcionada por el usuario se usó como guía
de estilo y material para el hormigón. No se insertó como fondo del juego.
La geometría y las asignaciones de materiales se crean con
`client/tools/build_visual05.gd` y se entregan ya guardadas en `models/`.

## Prompts utilizados

### textures/concrete.png

Use case: stylized-concept. Asset type: production game material texture,
single seamless tile, square 1024x1024. The input image is ONLY a mood/material
reference, not an edit target. Create a flat orthographic close-up surface of
the aged grey-beige Japanese residential concrete walls and station concrete
from this reference: hand painted detailed late 1990s anime background,
subdued taupe charcoal lilac-grey palette, fine porous plaster aggregate,
subtle rain streaks, faint water stains, tiny hairline cracks. Medium light
albedo values, not dark. Uniform diffuse lighting with no cast shadows, no
highlights, no objects, no lettering, no frame, no perspective. One
uninterrupted seamless concrete material filling entire image, matching
edges, suitable as repeatable albedo texture over 3D walls. This is a usable
texture not a scene illustration.

### textures/asphalt.png

Use case: stylized-concept. Asset type: seamless albedo game texture, square
1024x1024. One uninterrupted aged narrow Japanese residential street ASPHALT
surface viewed orthographically straight down, no perspective. Fine worn
asphalt aggregate, dusty pale warm grey, faint patches, narrow irregular
hairline cracks, restrained grime variation. Painterly but finely detailed
late 1990s psychological anime background material, muted taupe purple-grey
palette, medium grey overall rather than black, calm abandoned atmosphere.
Uniform diffuse lighting, no shadows, no road markings, no curbs, no objects,
no text, no borders. Seamless repeating tile; even flat brightness.
Production texture for a 3D isometric game, not an illustration of a street.

### textures/wood.png

Use case: stylized-concept. Asset type: seamless albedo game texture, square
1024x1024. Flat straight-down orthographic uninterrupted aged Japanese
apartment wooden floor. Many narrow parallel planks running vertically from
top to bottom, dark desaturated grey brown oak, delicate worn wood grain,
subtle scratches and discoloration, a few staggered narrow end joints, fine
dark gaps. Detailed hand-painted late 1990s anime background aesthetic, muted
umber taupe cool violet-grey shadows but NO baked lighting or cast shadows.
Medium brightness, not black, not orange. No perspective, no objects, no
border, no text. Seamless tile on all four edges for repeating 3D game floors
and furniture. The surface fills the whole square.

### textures/foliage.png

Use case: stylized-concept. Asset type: game vegetation cutout texture,
square. One dense irregular cluster of small camellia and Japanese privet
leaves on fine branching twigs, muted very dark dusty olive green with
occasional dull burgundy leaf, detailed hand painted late-1990s anime
background art. Side elevation flat botanical foliage spray roughly circular
but irregular outline, hundreds of tiny leaves, visible holes between
leaves, no pot no ground no trunk no scenery. Neutral diffuse lighting,
no drop shadow, desaturated mid-to-dark values, subtle pale grey-green
highlights. GENUINELY TRANSPARENT BACKGROUND with clean alpha around
individual leaves and gaps, no checkerboard pattern or solid backdrop
painted into image. This is a production alpha-cutout material for foliage
cards in a moody isometric 3D game.
