shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;
uniform sampler2D albedo_map : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 tint : source_color = vec4(0.83,0.82,0.79,1.0);
uniform float repeats = 0.24;
uniform float grit = 0.10;
uniform float roughness_value = 0.91;
varying vec3 world_pos;
varying vec3 world_normal;
float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p) {
	vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f);
	return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);
}
void vertex() {
	world_pos=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
	world_normal=normalize((MODEL_NORMAL_MATRIX*NORMAL));
}
void fragment() {
	vec3 weights=pow(abs(world_normal),vec3(8.0)); weights/=max(dot(weights,vec3(1)),0.001);
	vec3 base=texture(albedo_map,world_pos.zy*repeats).rgb*weights.x
		+texture(albedo_map,world_pos.xz*repeats).rgb*weights.y
		+texture(albedo_map,world_pos.xy*repeats).rgb*weights.z;
	float micro=noise(world_pos.xz*210.0+world_pos.y*79.0);
	ALBEDO=base*tint.rgb*(1.0-grit*0.5+grit*micro);
	ROUGHNESS=clamp(roughness_value+(micro-0.5)*0.13,0.0,1.0);
	SPECULAR=0.25;
	NORMAL_MAP=texture(normal_texture,UV*8.0).rgb;
	NORMAL_MAP_DEPTH=0.16;
}
