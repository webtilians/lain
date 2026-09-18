from collections import deque


LOCATION_GRAPH = {

    "APARTMENT": (
        "APARTMENT_DISTRICT",
    ),

    "APARTMENT_DISTRICT": (
        "APARTMENT",
        "STATION",
    ),

    "STATION": (
        "APARTMENT_DISTRICT",
        "OLD_DISTRICT",
    ),

    "OLD_DISTRICT": (
        "STATION",
    ),
}


def is_known_location(
    location: str,
) -> bool:

    return (
        location
        in LOCATION_GRAPH
    )


def shortest_path(
    origin: str,
    destination: str,
) -> list[str] | None:

    if origin == destination:

        if is_known_location(
            origin
        ):
            return [origin]

        return None

    if not is_known_location(
        origin
    ):
        return None

    if not is_known_location(
        destination
    ):
        return None

    visited = {
        origin
    }

    queue = deque(
        [
            (
                origin,
                [origin],
            )
        ]
    )

    while queue:

        location, path = (
            queue.popleft()
        )

        for neighbor in (
            LOCATION_GRAPH.get(
                location,
                (),
            )
        ):

            if neighbor in visited:
                continue

            new_path = (
                path
                + [neighbor]
            )

            if (
                neighbor
                == destination
            ):
                return new_path

            visited.add(
                neighbor
            )

            queue.append(
                (
                    neighbor,
                    new_path,
                )
            )

    return None


def shortest_hops(
    origin: str,
    destination: str,
) -> int | None:

    path = shortest_path(
        origin,
        destination,
    )

    if path is None:
        return None

    return (
        len(path) - 1
    )


def next_hop(
    origin: str,
    destination: str,
) -> str | None:

    path = shortest_path(
        origin,
        destination,
    )

    if path is None:
        return None

    if len(path) == 1:
        return origin

    return path[1]


def spatial_priority_factor(
    origin: str,
    destination: str,
) -> float:

    distance = shortest_hops(
        origin,
        destination,
    )

    if distance is None:

        return 0.35

    return max(
        0.40,
        1.0 - (
            distance * 0.15
        ),
    )
