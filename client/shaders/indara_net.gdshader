shader_type spatial;
// The Indara net under the rooms (IndaraNet.gd): threads of light on a square grid, fading
// into the dark; a small jewel on some of its knots; slow pulses running along a few threads;
// a halo round the knots of the city's zones (brighter while players are there) and of the cables.
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

uniform float cell = 3.0;
uniform vec2 centre = vec2(0.0);
uniform float reach = 46.0;
uniform float strength = 1.0;
uniform vec3 thread : source_color = vec3(0.05, 0.085, 0.21);
uniform vec3 light : source_color = vec3(0.45, 0.72, 1.0);
uniform vec4 knots[24];  // world x, world z, brightness, unused
uniform int knot_count = 0;

varying vec2 world;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz;
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void fragment() {
	vec2 p = world / cell;
	vec2 aa = fwidth(p);
	vec2 off = abs(fract(p - 0.5) - 0.5);
	vec2 lines = 1.0 - smoothstep(vec2(0.0), aa * 1.5, off);
	float threads = max(lines.x, lines.y);
	vec2 knot = floor(p + 0.5);
	float jewel = step(0.78, hash(knot)) * (1.0 - smoothstep(0.03, 0.03 + aa.x * 1.5, length(p - knot)));
	// Slow pulses along one thread in four: those along x one way, those along z the other.
	float row = hash(vec2(knot.y, 3.7));
	float column = hash(vec2(5.1, knot.x));
	float pulse = 0.0;
	if (row > 0.75) {
		pulse += lines.y * smoothstep(0.93, 1.0, fract(p.x / 24.0 - TIME * (0.03 + 0.03 * row) + row * 7.0));
	}
	if (column > 0.75) {
		pulse += lines.x * smoothstep(0.93, 1.0, fract(-p.y / 24.0 - TIME * (0.03 + 0.03 * column) + column * 7.0));
	}
	float halo = 0.0;
	for (int i = 0; i < knot_count; i++) {
		float r = length(world - knots[i].xy);
		float ring = 1.0 - smoothstep(0.0, 0.06 + aa.x * cell, abs(r - 0.75 - 0.1 * sin(TIME * 2.0 + float(i))));
		halo += knots[i].z * (0.7 * ring + 0.25 * exp(-r * r * 1.2));
	}
	float fade = 1.0 - smoothstep(reach * 0.25, reach, length(world - centre));
	ALBEDO = (thread * threads + light * (jewel * 0.35 + pulse * 0.8 + halo)) * fade * strength;
}
