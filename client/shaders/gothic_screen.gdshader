shader_type spatial;
// Visual 0.12: glitching advertising screen. Screens are untextured boxes, so
// the pattern is built from world position: colour bands that scroll, fine
// scanlines and blocky noise that re-rolls several times a second.
uniform vec4 colour_a : source_color = vec4(1.0, 0.12, 0.52, 1.0);
uniform vec4 colour_b : source_color = vec4(0.12, 0.85, 1.0, 1.0);
uniform float energy = 3.2;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
	vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float along = wp.x + wp.z;
	float band = step(0.5, fract(wp.y * 0.7 + TIME * 0.21));
	float scan = 0.72 + 0.28 * sin(wp.y * 160.0);
	float blocks = hash(floor(vec2(along * 9.0, wp.y * 9.0)) + floor(TIME * 7.0));
	float flicker = 0.85 + 0.15 * sin(TIME * 31.0);
	vec3 colour = mix(colour_a.rgb, colour_b.rgb, band) * (0.45 + 0.55 * blocks) * scan * flicker;
	ALBEDO = vec3(0.02);
	ROUGHNESS = 0.15;
	EMISSION = colour * energy;
}
