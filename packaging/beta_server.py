"""Packaged local-only World Core. Set LAIN_WORLD_DB before importing server.api."""
import multiprocessing
import os

import uvicorn


def main() -> None:
    multiprocessing.freeze_support()
    if not os.environ.get("LAIN_WORLD_DB"):
        raise SystemExit("LAIN_WORLD_DB is required for packaged builds")
    # No reload, no web listener, and exactly one process owns the SQLite save.
    from server.api import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        workers=1,
        reload=False,
        access_log=False,
        log_level="warning",
        lifespan="on",
    )


if __name__ == "__main__":
    main()
