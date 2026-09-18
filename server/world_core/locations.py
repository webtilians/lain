from collections import deque


LOCATION_GRAPH = {

    "APARTMENT": {
        "APARTMENT_DISTRICT",
    },

    "APARTMENT_DISTRICT": {
        "APARTMENT",
        "STATION",
    },

    "STATION": {
        "APARTMENT_DISTRICT",
        "OLD_DISTRICT",
    },

    "OLD_DISTRICT": {
        "STATION",
    },
}


def shortest_hops(
    origin: str,
    destination: str,
) -> int | None:

    if origin == destination:
        return 0

    if origin not in LOCATION_GRAPH:
        return None

    if destination not in LOCATION_GRAPH:
        return None

    visited = {
        origin
    }

    queue = deque(
        [
            (
                origin,
                0,
            )
        ]
    )

    while queue:

        location, distance = (
            queue.popleft()
        )

        for neighbor in (
            LOCATION_GRAPH.get(
                location,
                set(),
            )
        ):

            if neighbor in visited:
                continue

            if (
                neighbor
                == destination
            ):
                return (
                    distance + 1
                )

            visited.add(
                neighbor
            )

            queue.append(
                (
                    neighbor,
                    distance + 1,
                )
            )

    return None


def spatial_priority_factor(
    origin: str,
    destination: str,
) -> float:

    """
    Distance affects urgency without
    completely suppressing distant crises.

    0 hops -> 1.00
    1 hop  -> 0.85
    2 hops -> 0.70
    3 hops -> 0.55

    Minimum -> 0.40
    """

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
