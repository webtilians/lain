shader_type canvas_item;
uniform sampler2D screen_texture : hint_screen_texture, filter_linear;
// Restrained print-like grade; text/UI are drawn above this layer.
void fragment() {
	vec3 c = texture(screen_texture, SCREEN_UV).rgb;
	float luma = dot(c, vec3(0.2126, 0.7152, 0.0722));
	c = mix(vec3(luma), c, 0.78);
	c = (c - 0.5) * 1.06 + 0.5;
	c += vec3(0.010, 0.006, 0.021) * (1.0-luma);
	vec2 p = SCREEN_UV * 2.0 - 1.0;
	c *= 1.0 - 0.08 * dot(p,p);
	float grain = fract(sin(dot(FRAGCOORD.xy,vec2(12.9898,78.233)))*43758.5453);
	COLOR = vec4(c + (grain-0.5)*0.008, 1.0);
}
