extends RefCounted
## Physical presentation coordinates only. Semantic locations remain in World Core.
const DOORS := {
	"BOOKSHOP": Vector3(11, 1.15, 7.75),
	"GROCERY": Vector3(21, 1.15, 7.25),
	"VIDEO_CLUB": Vector3(18, 1.15, -45.25),
	"CAFE": Vector3(-10, 1.15, -45.75),
	"IZAKAYA": Vector3(-11, 1.15, -80.25),
	"ARCADE": Vector3(12, 1.15, -81.25),
	"APARTMENT": Vector3(-12, 1.15, 7.7),
	"SCHOOL": Vector3(-18, 1.15, -20.8),
	"NIGHTCLUB": Vector3(25.15, 1.15, -65),
	"STATION": Vector3(0, 1.15, -106.5),
}
const ENTRIES := {
	"BOOKSHOP": Vector3(11, 0.91, 9.8),
	"GROCERY": Vector3(21, 0.91, 9.3),
	"VIDEO_CLUB": Vector3(18, 0.91, -43.2),
	"CAFE": Vector3(-10, 0.91, -43.7),
	"IZAKAYA": Vector3(-11, 0.91, -78.2),
	"ARCADE": Vector3(12, 0.91, -79.2),
	"APARTMENT": Vector3(-12, 0.91, 5.7),
	"SCHOOL": Vector3(-18, 0.91, -18.9),
	"NIGHTCLUB": Vector3(27.1, 0.91, -65),
	"STATION": Vector3(0, 0.91, -104.5),
}
const BOUNDS := Rect2(-46, -114, 92, 132)
const CROSS_STREETS := [-16.0, -41.0, -76.0, -102.0]
const LONG_STREETS := [-29.0, 0.0, 29.0]
const TITLES := {
	"APARTMENT":"Casa", "SCHOOL":"Colegio", "NIGHTCLUB":"AZUL", "STATION":"Estación",
	"BOOKSHOP":"Librería Tsuki", "GROCERY":"Tienda Inoue", "VIDEO_CLUB":"Video Hoshi",
	"CAFE":"Café Kissa", "IZAKAYA":"Izakaya Akari", "ARCADE":"Salón de recreativos",
}
