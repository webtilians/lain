shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled;
uniform vec4 stain_color : source_color = vec4(0.17,0.19,0.16,0.24);
float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p) {
	vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f);
	return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);
}
void fragment() {
	float runs=noise(vec2(UV.x*23.0,UV.y*1.7));
	float fade=smoothstep(0.0,0.09,UV.x)*smoothstep(0.0,0.09,1.0-UV.x);
	fade*=smoothstep(0.0,0.12,UV.y)*pow(1.0-UV.y,1.6);
	ALBEDO=stain_color.rgb;
	ALPHA=fade*runs*stain_color.a;
	ROUGHNESS=1.0;
}
