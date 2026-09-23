extends SceneTree
## Deterministic visual-rig regression, never contacts World Core.
var failed := false

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, message: String) -> void:
	if not condition:
		failed=true
		push_error(message)

func run() -> void:
	root.get_node("WorldApi").set_script(load("res://tools/offline_world_api.gd"))
	var player := CharacterBody3D.new()
	root.add_child(player)
	var rig: Node3D = load("res://art/characters/LainSlender.tscn").instantiate()
	player.add_child(rig)
	rig.set_process(false)
	var bounds := AABB()
	var first := true
	for part in rig.find_children("*","MeshInstance3D",true,false):
		check(part.mesh is ArrayMesh,"Avatar contains an unshaped primitive")
		var box: AABB = part.global_transform * part.get_aabb()
		bounds = box if first else bounds.merge(box)
		first=false
	check(bounds.size.y > 1.55 and bounds.size.y < 1.8,"Avatar height mismatches player scale")
	check(bounds.size.x < 0.5,"Resting silhouette exceeds intended width")
	check(bounds.position.y >= -0.90 and bounds.position.y < -0.80,"Feet would float or sink at player origin")
	player.velocity = Vector3(2,0,0)
	rig._process(0.1)
	check(rig.rotation.y > 0,"Avatar did not face travel direction")
	check(rig.get_node("LeftLeg").rotation.x > 0 and rig.get_node("RightLeg").rotation.x < 0,"Walking legs did not alternate")
	check(rig.get_node("LeftArm").rotation.x < 0 and rig.get_node("RightArm").rotation.x > 0,"Arms did not counter-swing")
	check(rig.get_node("RightLeg/Knee").rotation.x < 0,"Trailing leg did not bend")
	player.velocity = Vector3.ZERO
	rig._process(1.0/60.0)
	for path in ["LeftLeg","RightLeg","LeftArm","RightArm","LeftLeg/Knee","RightLeg/Knee"]:
		check(is_zero_approx(rig.get_node(path).rotation.x),"Joint failed to return to rest: "+path)
	print("CHARACTER06_CHECK_", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
