"""Validate an operator-owned JSON catalogue without opening any game save."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.world_core.arcade_catalog import DEFAULT_PATH, GAMES, load

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path",nargs="?",type=Path,default=DEFAULT_PATH)
    args = parser.parse_args()
    try:
        spec = load(args.path)
    except (ValueError,OSError) as error:
        parser.exit(1, f"Catálogo no válido: {error}\n")
    print(f"Catálogo válido · revisión {spec['revision']} · {len(spec['entries'])} entradas")
    for item in spec["entries"]:
        print(f"{item['id']}: {GAMES[item['game']]} -> {item['prize']['kind']}:{item['prize']['model']}")
