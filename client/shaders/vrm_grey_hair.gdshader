shader_type spatial;
// Hair from VRoid, greyed (the teacher's): the texture's own strands and highlights,
// without its colour, lit the anime way like the rest of the character (VrmAvatar.gd).
render_mode diffuse_toon, specular_toon, cull_disabled;

uniform sampler2D hair : source_color, filter_linear_mipmap;
uniform vec3 tint : source_color = vec3(0.64, 0.62, 0.60);
uniform float lightening = 0.4;

void fragment() {
	vec4 strands = texture(hair, UV);
	float light = dot(strands.rgb, vec3(0.3, 0.59, 0.11));
	ALBEDO = mix(vec3(light), vec3(1.0), lightening) * tint;
	ALPHA = strands.a;
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	ROUGHNESS = 0.75;
	RIM = 0.3;
	RIM_TINT = 0.6;
	EMISSION = ALBEDO * 0.08;
}
