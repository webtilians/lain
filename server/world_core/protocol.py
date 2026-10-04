"""The Protocolo de presencia as a whole: seven layers, one fragment of Sesión Cero each.

Layers 01 and 02 arrived after the others had shipped, so a player can finish
them in any order. Fragments therefore count completed layers, and the client
shows whichever layer the player is in the middle of.
"""
LAYERS = ("layer_one", "layer_two", "layer_three", "layer_four", "layer_five", "layer_six", "layer_seven")


def fragments(c, player: str) -> int:
    """How many layers the player has decided: Sesión Cero's fragments recovered so far."""
    count = 0
    for table in LAYERS:
        if c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
            row = c.execute(f"SELECT decision FROM {table} WHERE player_id=?", (player,)).fetchone()
            count += bool(row and row[0])
    return count


def current_layer(view: dict):
    """The layer to show: the lowest open one until Capa 03 is decided, then the main thread first."""
    active = {key: view[key] for key in LAYERS if isinstance(view.get(key), dict) and view[key].get("active")}
    if not active:
        return None
    three = active.get("layer_three")
    order = LAYERS[3:] + LAYERS[:3] if three and three.get("decision") else LAYERS
    for key in order:
        if key in active and not active[key].get("decision"):
            return key
    return max(active, key=LAYERS.index)
