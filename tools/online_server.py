"""Owner console for a small invited online world. Never edits offline saves."""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3


FEATURES = (
    "LAIN_PROLOGUE_ENABLED",
    "LAIN_CITY_RESIDENTS_ENABLED",
    "LAIN_CHAPTER_ONE",
    "LAIN_CORPORATION",
    "LAIN_WORKSHOP",
    "LAIN_NOEMA",
    "LAIN_CIRCLES",
    "LAIN_CAFE_EVENTS",
    "LAIN_ARCADE_CATALOG",
    "LAIN_CODE_EXCHANGE",
    "LAIN_LAYER_THREE",
    "LAIN_LAYER_FOUR",
    "LAIN_LAYER_FIVE",
    "LAIN_LAYER_SIX",
    "LAIN_LAYER_SEVEN",
    "LAIN_LAYER_ONE",
    "LAIN_LAYER_TWO",
)


def configure(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    os.environ["LAIN_WORLD_DB"] = str((directory / "online-world.db").resolve())
    os.environ["LAIN_ONLINE"] = "1"
    for flag in FEATURES:
        os.environ[flag] = "1"
    os.environ.setdefault("LAIN_LLM_ENABLED", "0")


def list_players(directory: Path):
    database = directory / "online-world.db"
    rows = []
    if database.exists():
        # Listing must not create a partial world or change a running server.
        with closing(
            sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        ) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if {"agents", "online_credentials"} <= tables:
                rows = conn.execute(
                    """SELECT a.id,a.name,o.revoked FROM online_credentials o
                    JOIN agents a ON a.id=o.actor_id ORDER BY o.created_at,a.id"""
                ).fetchall()
    if not rows:
        print("Todavía no hay jugadores. Crea el primero con add-player.")
    for actor_id, name, revoked in rows:
        print(actor_id, name, "REVOCADO" if revoked else "ACTIVO")


def main():
    parser = argparse.ArgumentParser(
        description="Servidor compartido de LAIN para una beta privada"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.getenv("LOCALAPPDATA", str(Path.home())))
        / "LAIN"
        / "OnlineHost",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser(
        "add-player", help="Crear una identidad nueva y un archivo de acceso privado"
    )
    add.add_argument("--name", required=True)
    add.add_argument(
        "--url", required=True, help="URL HTTPS pública o HTTP de red local"
    )
    serve = commands.add_parser("serve", help="Arrancar un único World Core compartido")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--ai-gateway",
        default="",
        help="URL HTTPS del servicio de IA compartida, cuando esté listo",
    )
    commands.add_parser(
        "list-players", help="Mostrar identidades sin revelar sus claves"
    )
    revoke = commands.add_parser("revoke-player")
    revoke.add_argument("--id", required=True)
    reset = commands.add_parser(
        "reset-password", help="Dar una contraseña nueva a quien olvidó la suya"
    )
    reset.add_argument("--name", required=True)
    args = parser.parse_args()
    if args.command == "list-players":
        list_players(args.data_dir)
        return
    configure(args.data_dir)
    from server.world_core import online
    from server.world_core.simulation import Simulation

    if args.command == "serve":
        if args.ai_gateway:
            from urllib.parse import urlsplit

            url = args.ai_gateway.strip().rstrip("/")
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
                or parsed.port not in (None, 443)
            ):
                parser.error(
                    "La IA compartida necesita una URL HTTPS sin claves ni rutas."
                )
            os.environ.update(
                {
                    "LAIN_AI_GATEWAY_URL": url,
                    "LAIN_LLM_ENABLED": "1",
                    "LAIN_AI_SESSION_FILE": str(
                        (args.data_dir / "ai-session.json").resolve()
                    ),
                    "LAIN_LLM_TIMEOUT": "25",
                    "LAIN_REALITY_TIMEOUT": "25",
                }
            )
        import uvicorn

        # No reload/multiple workers: each world has exactly one simulation and clock.
        from server.api import app

        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            workers=1,
            reload=False,
            access_log=False,
            # Only a local reverse proxy (Caddy, cloudflared) may set the client
            # address; registration and login limits are per address.
            proxy_headers=True,
            forwarded_allow_ips="127.0.0.1",
            log_level="warning",
        )
        return
    if args.command == "add-player":
        # Reuse exactly the same origin validation as the portable launcher.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "lain_launcher",
            Path(__file__).resolve().parents[1] / "packaging" / "launcher.py",
        )
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        url = launcher.validate_world_url(args.url)
        with online.world_host_lock():
            Simulation()
            actor, token = online.create_player(args.name)
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", args.name)[:24]
        destination = (
            args.data_dir / "access" / (slug + "-" + actor[-8:]) / "lain-online.json"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps({"server_url": url, "player_token": token}, indent=2),
            encoding="utf-8",
        )
        # Never print the secret. The owner gives this file to ONE player.
        print("Jugador:", actor)
        print("Archivo privado:", destination.resolve())
        print(
            "Cópialo junto al LAIN.exe online de ESA persona. No publiques el archivo."
        )
    elif args.command == "reset-password":
        from server.world_core import online_accounts

        try:
            password = online_accounts.reset_password(args.name)
        except ValueError:
            parser.error("No hay ningún jugador con ese nombre.")
        print("Contraseña nueva de", args.name + ":", password)
        print("Pásasela solo a esa persona. Puede cambiarla desde el menú de inicio.")
    else:
        online.initialize()
        online.revoke_player(args.id)
        print("Acceso revocado. Se conserva el progreso del jugador.")


if __name__ == "__main__":
    main()
