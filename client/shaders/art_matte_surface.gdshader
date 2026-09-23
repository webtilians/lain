shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

// World-space matte micro-variation: the same procedural grain continues
// across neighboring concrete slabs, without new textures or UV seams.
uniform vec4 base_color : source_color = vec4(0.47, 0.45, 0.48, 1.0);
uniform float grain_size : hint_range(0.5, 32.0) = 8.0;
uniform float wear : hint_range(0.0, 0.4) = 0.12;
uniform float surface_roughness : hint_range(0.0, 1.0) = 0.96;
varying vec3 surface_world;

float hash31(vec3 position) {
    return fract(sin(dot(position, vec3(127.1, 311.7, 74.7))) * 43758.5453123);
}

float noise3(vec3 position) {
    vec3 cell = floor(position);
    vec3 fraction = fract(position);
    fraction = fraction * fraction * (3.0 - 2.0 * fraction);
    float a = mix(hash31(cell), hash31(cell + vec3(1.0, 0.0, 0.0)), fraction.x);
    float b = mix(hash31(cell + vec3(0.0, 1.0, 0.0)),
                  hash31(cell + vec3(1.0, 1.0, 0.0)), fraction.x);
    float c = mix(hash31(cell + vec3(0.0, 0.0, 1.0)),
                  hash31(cell + vec3(1.0, 0.0, 1.0)), fraction.x);
    float d = mix(hash31(cell + vec3(0.0, 1.0, 1.0)),
                  hash31(cell + vec3(1.0, 1.0, 1.0)), fraction.x);
    return mix(mix(a, b, fraction.y), mix(c, d, fraction.y), fraction.z);
}

void vertex() {
    surface_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    float broad = noise3(surface_world * 0.85);
    float dust = noise3(surface_world * grain_size);
    float mottling = noise3(surface_world * 2.4);
    float shade = 0.90 + broad * 0.15 + dust * 0.10
        - smoothstep(0.63, 0.91, mottling) * wear;
    ALBEDO = clamp(base_color.rgb * shade, vec3(0.0), vec3(1.0));
    ROUGHNESS = surface_roughness;
    METALLIC = 0.0;
}
