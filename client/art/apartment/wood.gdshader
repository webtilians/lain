shader_type spatial;
render_mode diffuse_lambert_wrap;
uniform vec4 tint : source_color = vec4(0.28,0.23,0.22,1.0);
float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
void fragment() {
	float grain = sin(UV.x*220.0 + sin(UV.y*13.0)*3.0)*0.015;
	float worn = hash(floor(UV*vec2(230.0,35.0)))*0.035;
	ALBEDO = tint.rgb + grain + worn;
	ROUGHNESS = 0.93;
}
