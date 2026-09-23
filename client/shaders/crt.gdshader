shader_type canvas_item;

uniform sampler2D screen_texture : hint_screen_texture, filter_linear;
uniform float scanline_strength = 0.012;
uniform float noise_strength = 0.012;
uniform float color_levels = 96.0;
uniform float saturation = 0.68;
uniform float contrast = 1.08;
uniform float brightness = 0.96;
uniform float vignette_strength = 0.20;
uniform vec3 shadow_tint = vec3(0.91, 0.89, 1.00);
uniform vec3 highlight_tint = vec3(1.00, 0.96, 0.90);
uniform float paper_grain = 0.018;

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 345.45));
	p += dot(p, p + 34.345);
	return fract(p.x * p.y);
}

void fragment() {
	vec2 uv = SCREEN_UV;
	vec3 color = texture(screen_texture, uv).rgb;

	float luma = dot(color, vec3(0.2126, 0.7152, 0.0722));
	color = mix(vec3(luma), color, saturation);
	color = (color - 0.5) * contrast + 0.5;
	color *= brightness;

	float split = smoothstep(0.24, 0.78, luma);
	color *= mix(shadow_tint, highlight_tint, split);

	float coarse = hash21(floor(uv * vec2(640.0, 360.0)) + floor(TIME * 12.0));
	float fine = hash21(uv * vec2(1733.0, 941.0) + TIME * 0.7);
	color += (coarse - 0.5) * noise_strength;
	color += (fine - 0.5) * paper_grain;

	float levels = max(color_levels, 8.0);
	color = floor(max(color, vec3(0.0)) * levels) / levels;

	float scanline = sin(uv.y * 720.0 * 3.14159265) * 0.5 + 0.5;
	color *= 1.0 - scanline * scanline_strength;

	vec2 centered = uv * 2.0 - 1.0;
	float vignette = smoothstep(0.45, 1.35, dot(centered, centered));
	color *= 1.0 - vignette * vignette_strength;

	COLOR = vec4(clamp(color, 0.0, 1.0), 1.0);
}
