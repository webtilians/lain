shader_type spatial;
// Visual 0.12: rain-soaked ground. World XZ mapping (ground boxes carry no
// useful UVs), a general wet darkening, and puddles from a separate, larger
// noise so they do not repeat with the texture tile.
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D arm_tex : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D puddle_noise : filter_linear, repeat_enable;
uniform vec4 tint : source_color = vec4(0.5, 0.5, 0.5, 1.0);
uniform float tile_size = 3.0;
uniform float puddle_scale = 11.0;
uniform float wetness = 0.55;
uniform float puddle_threshold = 0.63;

varying vec3 world_pos;
varying float up;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	up = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz).y;
}

void fragment() {
	vec2 uv = world_pos.xz / tile_size;
	vec3 base = texture(albedo_tex, uv).rgb * tint.rgb;
	vec3 arm = texture(arm_tex, uv).rgb;
	float noise = texture(puddle_noise, world_pos.xz / puddle_scale).r;
	float puddle = smoothstep(puddle_threshold, puddle_threshold + 0.07, noise) * step(0.7, up);
	ALBEDO = base * mix(1.0 - 0.45 * wetness, 0.5, puddle);
	ROUGHNESS = mix(arm.g * (1.0 - 0.6 * wetness), 0.02, puddle);
	SPECULAR = 0.5 + 0.35 * puddle;
	AO = arm.r;
	AO_LIGHT_AFFECT = 0.1;
	NORMAL_MAP = mix(texture(normal_tex, uv).rgb, vec3(0.5, 0.5, 1.0), puddle);
}
