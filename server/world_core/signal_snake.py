"""Version 1 deterministic snake rules. No submitted code or client score runs."""
OFFSETS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
NAME = "Serpiente de señal"
RULES = "La serpiente avanza sola. Gira con las flechas; recoge 6 señales y evita paredes y tu cuerpo. Tres señales bastan para clasificar, incluso si después chocas. Máximo 80 pasos."


def board(variant=0):
    def transform(point):
        x, y = point
        return [7-x if variant & 1 else x, 7-y if variant & 2 else y]
    foods = [[3,1], [5,1], [6,3], [4,4], [2,5], [1,6]]
    # Occupied food positions are skipped on spawn, identically on client/server.
    queue = foods + [[x,y] for y in range(8) for x in range(8) if [x,y] not in foods]
    return dict(game_id="signal_snake", game_name=NAME, rules=RULES, version=1,
                variant=variant, size=8, start=transform([1,1]),
                snake=[transform(p) for p in [[1,1],[0,1],[0,0]]],
                foods=[transform(p) for p in queue], goal=6, minimum=3,
                walls=[], max_moves=80, direction="L" if variant & 1 else "R")


def replay(moves, layout):
    if layout.get("version") != 1:
        raise ValueError("UNSUPPORTED_ARCADE_VERSION")
    if not isinstance(moves, str) or len(moves) > layout["max_moves"] or any(m not in OFFSETS for m in moves):
        raise ValueError("INVALID_ARCADE_MOVES")
    body = [list(p) for p in layout["snake"]]
    foods = layout["foods"]
    pointer = 0
    collected = 0
    finished = False
    collision = False
    while foods[pointer % len(foods)] in body:
        pointer += 1
    for direction in moves:
        if finished:
            raise ValueError("ARCADE_ALREADY_FINISHED")
        dx, dy = OFFSETS[direction]
        head = [body[0][0]+dx, body[0][1]+dy]
        growing = head == foods[pointer % len(foods)]
        occupied = body if growing else body[:-1]
        if not (0 <= head[0] < 8 and 0 <= head[1] < 8) or head in occupied:
            finished = collision = True
            continue
        body.insert(0, head)
        if growing:
            collected += 1
            pointer += 1
            while foods[pointer % len(foods)] in body:
                pointer += 1
        else:
            body.pop()
        if collected >= layout["goal"]:
            finished = True
    finished = finished or len(moves) == layout["max_moves"]
    return dict(score=max(0, collected*100-len(moves)*2) if finished else 0,
                collected=collected, finished=finished,
                won=finished and collected >= layout["minimum"], collision=collision,
                snake=body, food=foods[pointer % len(foods)], food_index=pointer)


def npc_route(variant, signals):
    parts = ["RR","RR","RDD","DLL","DLL","DL"]
    route = "".join(parts[:signals])
    horizontal = {"L":"R","R":"L"} if variant & 1 else {}
    vertical = {"U":"D","D":"U"} if variant & 2 else {}
    def transform(path):
        return "".join(horizontal.get(ch, vertical.get(ch, ch)) for ch in path)
    route = transform(route)
    layout = board(variant)
    while not replay(route, layout)["finished"]:
        route += route[-1]
    return route
