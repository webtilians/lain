shader_type spatial;
// Anime ink lines (ARTE.md): a full-screen pass over depth and normals draws a thin
// line wherever the depth jumps (a silhouette) or the surface turns sharply (a
// crease). It sits on a quad in front of the camera; Forward+ only (it needs normals).
render_mode unshaded, depth_test_disabled, depth_draw_never, cull_disabled, fog_disabled, shadows_disabled;

uniform sampler2D depth_texture : hint_depth_texture, filter_nearest;
uniform sampler2D normal_texture : hint_normal_roughness_texture, filter_nearest;
uniform vec4 line_color : source_color = vec4(0.09, 0.05, 0.14, 0.9);
uniform float thickness = 1.0;
uniform float depth_threshold = 0.08;
uniform float normal_threshold = 0.95;

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

float view_depth(vec2 uv, mat4 inverse_projection) {
	vec4 position = inverse_projection * vec4(uv * 2.0 - 1.0, texture(depth_texture, uv).r, 1.0);
	return -position.z / position.w;
}

void fragment() {
	vec2 step_size = thickness / VIEWPORT_SIZE;
	vec2 offsets[4] = vec2[](vec2(step_size.x, 0.0), vec2(-step_size.x, 0.0), vec2(0.0, step_size.y), vec2(0.0, -step_size.y));
	float depth = view_depth(SCREEN_UV, INV_PROJECTION_MATRIX);
	vec3 normal = texture(normal_texture, SCREEN_UV).xyz * 2.0 - 1.0;
	float depth_jump = 0.0;
	float turn = 0.0;
	for (int i = 0; i < 4; i++) {
		vec2 uv = SCREEN_UV + offsets[i];
		depth_jump = max(depth_jump, abs(view_depth(uv, INV_PROJECTION_MATRIX) - depth) / max(depth, 0.01));
		turn = max(turn, distance(normal, texture(normal_texture, uv).xyz * 2.0 - 1.0));
	}
	float edge = max(step(depth_threshold, depth_jump), step(normal_threshold, turn));
	// Nothing drawn far out, where the sky or the void begins.
	edge *= 1.0 - smoothstep(150.0, 400.0, depth);
	ALBEDO = line_color.rgb;
	ALPHA = edge * line_color.a;
}
