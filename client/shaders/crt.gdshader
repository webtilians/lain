shader_type canvas_item;

uniform sampler2D screen_texture : hint_screen_texture, filter_linear_mipmap;

uniform float scanline_strength = 0.018;
uniform float noise_strength = 0.012;
uniform float color_levels = 96.0;

// Visual 0.5: painterly/isometric grading inspired by late-90s psychological
// anime background paintings. This remains a presentation layer only.
uniform float saturation = 0.72;
uniform float contrast = 1.08;
uniform float exposure = 0.94;
uniform float vignette_strength = 0.20;
uniform float edge_strength = 0.24;
uniform float paper_grain = 0.018;
uniform vec3 shadow_tint = vec3(0.20, 0.18, 0.25);
uniform vec3 highlight_tint = vec3(0.88, 0.78, 0.68);

float random_noise(vec2 uv) {
	return fract(
		sin(dot(uv, vec2(12.9898, 78.233)))
		* 43758.5453
	);
}

float luma(vec3 color) {
	return dot(color, vec3(0.299, 0.587, 0.114));
}

vec3 graded(vec3 color) {
	float y = luma(color);
	color = mix(vec3(y), color, saturation);
	color = (color - 0.5) * contrast + 0.5;
	color *= exposure;

	// Cool, violet shadows / slightly warm paper-like highlights.
	float shadow_mix = clamp((0.46 - y) * 1.35, 0.0, 0.34);
	float high_mix = clamp((y - 0.56) * 0.72, 0.0, 0.16);
	color = mix(color, color * (shadow_tint * 1.65), shadow_mix);
	color = mix(color, color * highlight_tint, high_mix);
	return color;
}

void fragment() {
	vec2 uv = SCREEN_UV;
	ivec2 tex_size = textureSize(screen_texture, 0);
	vec2 px = 1.0 / vec2(max(tex_size.x, 1), max(tex_size.y, 1));

	vec3 color = texture(screen_texture, uv).rgb;
	float center_luma = luma(color);

	// Cheap screen-space contour: darkens strong luminance discontinuities,
	// giving simple 3D meshes the softer illustrated/inked appearance of the
	// supplied reference without changing collision or world geometry.
	float left_l = luma(texture(screen_texture, uv - vec2(px.x, 0.0)).rgb);
	float right_l = luma(texture(screen_texture, uv + vec2(px.x, 0.0)).rgb);
	float up_l = luma(texture(screen_texture, uv - vec2(0.0, px.y)).rgb);
	float down_l = luma(texture(screen_texture, uv + vec2(0.0, px.y)).rgb);
	float edge = abs(right_l - left_l) + abs(down_l - up_l);
	edge = smoothstep(0.035, 0.24, edge);

	color = graded(color);
	color *= 1.0 - edge * edge_strength;

	// Gentle tonal compression removes the "clean realtime render" look.
	color = floor(clamp(color, 0.0, 1.0) * color_levels) / color_levels;

	float scanline = sin(uv.y * 540.0 * 3.14159265) * 0.5 + 0.5;
	color *= 1.0 - scanline * scanline_strength;

	float grain = random_noise(uv * vec2(tex_size) * 0.37 + TIME * 0.17) - 0.5;
	float fine_noise = random_noise(uv + TIME) - 0.5;
	color += grain * paper_grain + fine_noise * noise_strength;

	vec2 centered = uv * 2.0 - 1.0;
	float vignette = smoothstep(0.32, 1.36, dot(centered, centered));
	color *= 1.0 - vignette * vignette_strength;

	COLOR = vec4(clamp(color, 0.0, 1.0), 1.0);
}
