shader_type spatial;
// Visual 0.22 · interior floors projected from above in world space, so any
// box gets the same pattern: vinyl or ceramic tiles, or patterned carpet.
// pattern 0 = tiles (two colours in a chequer, grout lines), 1 = carpet.

uniform int pattern = 0;
uniform vec3 color_a : source_color = vec3(0.6);
uniform vec3 color_b : source_color = vec3(0.5);
uniform vec3 grout : source_color = vec3(0.35);
uniform float tile = 0.6;
uniform float grout_width = 0.012;
uniform float roughness_value = 0.55;
uniform float wear = 0.12;

varying vec3 world_position;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
		mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

void vertex() {
	world_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = world_position.xz;
	vec3 color;
	float rough = roughness_value;
	if (pattern == 0) {
		vec2 cell = floor(p / tile);
		vec2 local = fract(p / tile);
		float chequer = mod(cell.x + cell.y, 2.0);
		color = mix(color_a, color_b, chequer);
		// Each tile is a slightly different batch.
		color *= 0.94 + 0.08 * hash(cell);
		float edge = min(min(local.x, 1.0 - local.x), min(local.y, 1.0 - local.y)) * tile;
		float line = 1.0 - smoothstep(grout_width * 0.5, grout_width, edge);
		color = mix(color, grout, line);
		rough = mix(rough, 0.9, line);
	} else {
		// Carpet: a fine fibre noise over a repeating geometric motif.
		vec2 motif = fract(p / tile) - 0.5;
		float diamond = step(abs(motif.x) + abs(motif.y), 0.32) - step(abs(motif.x) + abs(motif.y), 0.24);
		color = mix(color_a, color_b, diamond);
		color *= 0.85 + 0.25 * noise(p * 90.0);
		rough = 0.97;
	}
	// Foot traffic: scuffs and dirt are larger, softer blotches.
	color *= 1.0 - wear * noise(p * 0.9) * noise(p * 4.0 + 7.0);
	ALBEDO = color;
	ROUGHNESS = rough;
	SPECULAR = pattern == 0 ? 0.5 : 0.2;
}
