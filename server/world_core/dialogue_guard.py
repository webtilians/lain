"""D8-r2: explicit boundary between an NPC's story and World Core rules.

NPCs can remember what a player called a password. The current WorldNode
schema does NOT supply a verified access credential for NODE_07. A model
reply must not turn an overheard word into an objective access requirement.

This narrow rule guards the known failure mode. It is not a general
natural-language factuality checker.
"""
import re
import unicodedata


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


NODE_07 = re.compile(r"\b(?:node[_\s-]*0?7|nodo[_\s-]*0?7)\b")
# Recognize a credential word even when attached to a value (e.g. clave123).
KEY = re.compile(r"\b(?:clave|contrasena|codigo|password|pin)(?:[a-z0-9_-]+)?\b")
ACCESS = re.compile(
    r"\b(?:acceder|acceso|entrar|entrada|abrir|abre|activar|"
    r"desbloquear|desbloquea|habilita|permite)\b"
)
REQUIREMENT = re.compile(
    r"\b(?:debes|tienes\s+que|hay\s+que|necesitas|necesaria|"
    r"necesario|requiere|requerida|obligatoria|usar|introducir)\b"
)


def asks_about_node_access_code(text: str) -> bool:
    plain = _plain(text)
    return bool(NODE_07.search(plain) and KEY.search(plain) and ACCESS.search(plain))


def asserts_unverified_node_access_code(text: str) -> bool:
    """Fail closed for credential talk about NODE_07 in generated dialogue.

    Old guard required a word like "debes" or "usar" next to a credential.
    That missed "Necesito que uses Killo13 para acceder" and standalone
    codes like "clave123". Here there is no verified access-key field in
    World Core, so even a plausible affirmative *or negative* model
    statement about NODE_07 credentials is replaced with the
    authoritative "no verified access code" response.
    """
    plain = _plain(text)
    return bool(
        NODE_07.search(plain)
        and KEY.search(plain)
        and (
            ACCESS.search(plain)
            or REQUIREMENT.search(plain)
            or re.search(r"\b(?:clave|contrasena|codigo)\b", plain)
        )
    )


def misattributes_player_password(text: str) -> bool:
    """Catch a model claiming it told the player their own password."""
    plain = _plain(text)
    return bool(
        KEY.search(plain)
        and re.search(
            r"\b(?:que\s+te\s+dije|yo\s+te\s+dije|que\s+te\s+conte)\b",
            plain,
        )
    )


def no_verified_access_code_reply(context: dict) -> str:
    node = next(
        (
            item
            for item in context.get("beliefs", {}).get("nodes", [])
            if item.get("node_id") == "NODE_07"
        ),
        None,
    )
    if node is None:
        return (
            "No tengo información verificada sobre una clave de acceso "
            "a NODE_07. No quiero inventarte una."
        )
    return (
        "Tengo información sobre la señal de NODE_07, pero no tengo "
        "ninguna clave de acceso verificada. Una contraseña que me hayas "
        "contado no demuestra que sirva para entrar."
    )
