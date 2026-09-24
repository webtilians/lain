shader_type canvas_item;
uniform sampler2D screen_texture : hint_screen_texture, filter_linear;
void fragment() {
	vec3 c = texture(screen_texture, SCREEN_UV).rgb;
	float luma = dot(c, vec3(.2126,.7152,.0722));
	c = mix(vec3(luma),c,.91);
	vec2 p = SCREEN_UV*2.0-1.0;
	c *= 1.0-.035*dot(p,p);
	COLOR = vec4(c,1.0);
}
