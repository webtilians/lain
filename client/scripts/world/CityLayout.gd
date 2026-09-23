extends RefCounted
## Physical presentation coordinates only. Semantic locations remain in World Core.
const DOORS := {
	"APARTMENT": Vector3(-12, 1.15, 7.7),
	"SCHOOL": Vector3(-18, 1.15, -20.8),
	"NIGHTCLUB": Vector3(25.15, 1.15, -65),
	"STATION": Vector3(0, 1.15, -106.5),
}
const ENTRIES := {
	"APARTMENT": Vector3(-12, 0.91, 5.7),
	"SCHOOL": Vector3(-18, 0.91, -18.9),
	"NIGHTCLUB": Vector3(27.1, 0.91, -65),
	"STATION": Vector3(0, 0.91, -104.5),
}
const BOUNDS := Rect2(-46, -114, 92, 132)
const CROSS_STREETS := [-16.0, -41.0, -76.0, -102.0]
const LONG_STREETS := [-29.0, 0.0, 29.0]
