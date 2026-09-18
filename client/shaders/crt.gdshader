shader_type canvas_item;

uniform sampler2D screen_texture : hint_screen_texture, filter_nearest;
uniform float scanline_strength = 0.10;
uniform float noise_strength = 0.018;
uniform float color_levels = 32.0;

float random_noise(vec2 uv) {
	return fract(
		sin(dot(uv, vec2(12.9898, 78.233)))
		* 43758.5453
	);
}

void fragment() {
	vec2 uv = SCREEN_UV;
	vec3 color = texture(screen_texture, uv).rgb;
	color = floor(color * color_levels) / color_levels;

	float scanline = sin(uv.y * 360.0 * 3.14159265) * 0.5 + 0.5;
	color *= 1.0 - scanline * scanline_strength;

	float noise = random_noise(uv + TIME) - 0.5;
	color += noise * noise_strength;
	COLOR = vec4(color, 1.0);
}
