"""Owner console for a small invited online world. Never edits offline saves."""

import argparse
import json
import os
from pathlib import Path
import re


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
)


def configure(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    os.environ["LAIN_WORLD_DB"] = str((directory / "online-world.db").resolve())
    os.environ["LAIN_ONLINE"] = "1"
    for flag in FEATURES:
        os.environ[flag] = "1"
    os.environ.setdefault("LAIN_LLM_ENABLED", "0")


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
    args = parser.parse_args()
    configure(args.data_dir)
    from server.world_core import online
    from server.world_core.simulation import Simulation
    from server.world_core.database import get_connection

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
            proxy_headers=False,
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
    else:
        online.initialize()
        if args.command == "revoke-player":
            online.revoke_player(args.id)
            print("Acceso revocado. Se conserva el progreso del jugador.")
        else:
            with get_connection() as conn:
                for row in conn.execute(
                    """SELECT a.id,a.name,o.revoked FROM online_credentials o
                    JOIN agents a ON a.id=o.actor_id ORDER BY o.created_at,a.id"""
                ):
                    print(row[0], row[1], "REVOCADO" if row[2] else "ACTIVO")


if __name__ == "__main__":
    main()
