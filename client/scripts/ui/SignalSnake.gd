extends RefCounted
## Local animation model only. World Core replays the submitted moves.
var layout: Dictionary = {}
var body: Array[Vector2i] = []
var food := Vector2i.ZERO
var food_index := 0
var collected := 0
var direction := "R"
var next_direction := "R"
var moves := ""
var finished := false
var collision := false
const OFFSETS := {"U":Vector2i.UP,"D":Vector2i.DOWN,"L":Vector2i.LEFT,"R":Vector2i.RIGHT}

func reset(board: Dictionary) -> void:
	layout = board
	body.clear()
	for p in board.snake: body.append(Vector2i(int(p[0]),int(p[1])))
	food_index = 0
	collected = 0
	direction = str(board.direction)
	next_direction = direction
	moves = ""
	finished = false
	collision = false
	_spawn_food()

func _spawn_food() -> void:
	var pair: Array = layout.foods[food_index % layout.foods.size()]
	food = Vector2i(int(pair[0]),int(pair[1]))
	while food in body:
		food_index += 1
		pair = layout.foods[food_index % layout.foods.size()]
		food = Vector2i(int(pair[0]),int(pair[1]))

func turn(value: String) -> void:
	if OFFSETS.has(value) and OFFSETS[value] != -OFFSETS[direction]:
		next_direction = value

func step(value: String = "") -> void:
	if finished: return
	direction = next_direction if value.is_empty() else value
	next_direction = direction
	moves += direction
	var head: Vector2i = body[0] + OFFSETS[direction]
	var growing := head == food
	var occupied: Array[Vector2i] = body.duplicate()
	if not growing: occupied.pop_back()
	if head.x < 0 or head.y < 0 or head.x >= 8 or head.y >= 8 or head in occupied:
		finished = true
		collision = true
		return
	body.push_front(head)
	if growing:
		collected += 1
		food_index += 1
		_spawn_food()
	else:
		body.pop_back()
	finished = collected >= int(layout.goal) or moves.length() >= int(layout.max_moves)
