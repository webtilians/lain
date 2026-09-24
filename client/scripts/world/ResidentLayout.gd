extends RefCounted
## Authored walkable local circuits. The server chooses the waypoint; the
## client only interpolates it. Stable slots never depend on who is visible.
const STEPS := [Vector3.ZERO, Vector3(0.7,0,0), Vector3(0.7,0,0.7), Vector3(0,0,0.7)]
const DISTRICT := [
	Vector3(-4.0,0,2.8), Vector3(25.4,0,4.8), Vector3(-26.0,0,-7.0), Vector3(4.0,0,-12.0),
	Vector3(5.0,0,-33), Vector3(10.5,0,-30), Vector3(-4.3,0,-36), Vector3(23,0,-29),
	Vector3(13,0,-30), Vector3(23,0,-24), Vector3(8,0,-19), Vector3(10.2,0,-24),
	Vector3(4.0,0,-59), Vector3(-4.5,0,-68), Vector3(31.5,0,-92), Vector3(-27,0,-96),
]
static func at(location: String, slot: int, step: int) -> Vector3:
	var origin := Vector3.ZERO
	if location == "APARTMENT_DISTRICT":
		origin = DISTRICT[clampi(slot,0,15)]
	elif location == "SCHOOL":
		origin = Vector3(-2.8+float(slot%4)*2.0,0,-4.4+floorf(float(slot)/4.0)*4.4)
	elif location == "SCHOOL_LAB":
		origin = Vector3(-2.7+float(slot%2)*4.0,0,-2.4+floorf(float(slot)/2.0)*4.2)
	elif location == "NIGHTCLUB":
		origin = Vector3(-4+float(slot%3)*2.5,0,-2.5+floorf(float(slot)/3.0)*4.6)
	elif location == "STATION":
		origin = Vector3(0.8,0,[-8.0,-4.0,3.0,7.0][clampi(slot,0,3)])
	else:
		origin = [Vector3(3.8,0,-4.7),Vector3(-1.0,0,0.4),Vector3(2.8,0,2.7)][clampi(slot,0,2)]
	return origin + STEPS[posmod(step,4)]
