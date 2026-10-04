shader_type canvas_item;
// Visual 0.12 grade: crimson-violet shadows, deeper blacks, a faint chromatic
// fringe toward the edges, vignette and fine film grain.
uniform sampler2D screen_texture : hint_screen_texture, filter_linear;

void fragment() {
	vec2 uv = SCREEN_UV;
	vec2 p = uv * 2.0 - 1.0;
	float edge = dot(p, p);
	float fringe = 0.0014 * edge;
	vec3 c = vec3(
		texture(screen_texture, uv + p * fringe).r,
		texture(screen_texture, uv).g,
		texture(screen_texture, uv - p * fringe).b);
	float luma = dot(c, vec3(0.2126, 0.7152, 0.0722));
	c = mix(c * vec3(1.1, 0.86, 1.04), c, smoothstep(0.04, 0.55, luma));
	c = mix(vec3(luma), c, 0.9);
	c = pow(max(c, vec3(0.0)), vec3(1.07));
	c *= 1.0 - 0.24 * edge;
	float grain = fract(sin(dot(uv * vec2(1931.0, 1087.0) + fract(TIME) * 61.0, vec2(12.9898, 78.233))) * 43758.5453) - 0.5;
	COLOR = vec4(c + grain * 0.016, 1.0);
}
