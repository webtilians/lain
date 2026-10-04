extends RefCounted
## Small physical bevels catch light on furniture. Collision shapes stay intact.
var cache: Dictionary = {}

func furniture_mesh(source: BoxMesh, label: String) -> Mesh:
	var selected := false
	for word in ["Desk", "Table", "Counter", "Chair", "Cabinet", "CRT", "CashRegister", "Shelf", "Fridge"]:
		selected = selected or word in label
	if not selected or minf(source.size.x,minf(source.size.y,source.size.z)) < .045:
		return source
	var key := str(source.size)
	if cache.has(key):
		return cache[key]
	var half := source.size*.5
	var radius := minf(.022,minf(half.x,minf(half.y,half.z))*.24)
	var inner := half-Vector3.ONE*radius
	var builder := SurfaceTool.new()
	builder.begin(Mesh.PRIMITIVE_TRIANGLES)
	# Each face has a flat centre and a ring of smoothly lit rounded edges.
	for axis in range(3):
		var u := (axis+1)%3
		var v := (axis+2)%3
		var us := [-half[u],-inner[u],inner[u],half[u]]
		var vs := [-half[v],-inner[v],inner[v],half[v]]
		for side in [-1.0,1.0]:
			for row in range(3):
				for col in range(3):
					var corners := [Vector2i(col,row),Vector2i(col+1,row),Vector2i(col+1,row+1),Vector2i(col,row+1)]
					var order := [0,2,1,0,3,2] if side>0 else [0,1,2,0,2,3]
					for index in order:
						var corner: Vector2i = corners[index]
						var pos := Vector3.ZERO
						pos[axis] = half[axis]*side
						pos[u] = us[corner.x]
						pos[v] = vs[corner.y]
						var anchor := pos.clamp(-inner,inner)
						var normal := (pos-anchor).normalized()
						builder.set_normal(normal)
						builder.set_uv(Vector2(pos[u]/source.size[u]+.5,pos[v]/source.size[v]+.5))
						builder.add_vertex(anchor+normal*radius)
	builder.generate_tangents()
	var result := builder.commit()
	result.resource_name = "Bevel10"
	cache[key] = result
	return result
