"""Online client self-update from GitHub Releases. Standard library only.

The release publishes manifest.json next to its assets:
    {"version": "0.13.0", "tag": "v0.13.0",
     "files": {"Game/LAIN-Game.pck": {"asset": "LAIN-Game.pck", "sha256": "...", "size": 123}, ...}}
Only listed client files can change, every byte is checked against its
SHA-256 before anything on disk is replaced, and downloads may only come from
GitHub over HTTPS. If anything fails the installed version keeps working.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ALLOWED_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
}
ALLOWED_FILES = {"LAIN.exe", "Game/LAIN-Game.exe", "Game/LAIN-Game.pck", "LEEME.txt"}
MAX_BYTES = 1_900_000_000
CHUNK = 1 << 20
INSTALLED = "version.json"
STAGING = ".update"


class UpdateError(Exception):
    pass


def check_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password:
        raise UpdateError("Origen de actualización no permitido: " + str(parsed.hostname))
    return url


class _GitHubOnly(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url: str, timeout: float):
    opener = build_opener(_GitHubOnly())
    return opener.open(Request(check_url(url), headers={"User-Agent": "LAIN-Launcher"}), timeout=timeout)


def fetch_manifest(releases: str, timeout: float = 8.0, opener=None) -> dict:
    url = releases.rstrip("/") + "/latest/download/manifest.json"
    with (opener or _open)(url, timeout) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise UpdateError("Manifiesto demasiado grande.")
    return validate_manifest(json.loads(raw.decode("utf-8")))


def validate_manifest(data) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        raise UpdateError("Manifiesto inválido.")
    version, tag = data.get("version"), data.get("tag")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9A-Za-z.+-]{1,40}", version):
        raise UpdateError("Versión inválida.")
    if not isinstance(tag, str) or not re.fullmatch(r"[0-9A-Za-z._-]{1,60}", tag):
        raise UpdateError("Etiqueta inválida.")
    files = {}
    for path, entry in data["files"].items():
        if path not in ALLOWED_FILES or not isinstance(entry, dict):
            raise UpdateError("Archivo no permitido en el manifiesto: " + str(path))
        sha, size, asset = entry.get("sha256"), entry.get("size"), entry.get("asset")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise UpdateError("Huella inválida para " + path)
        if not isinstance(size, int) or not 0 < size <= MAX_BYTES:
            raise UpdateError("Tamaño inválido para " + path)
        if not isinstance(asset, str) or not re.fullmatch(r"[0-9A-Za-z._-]{1,80}", asset):
            raise UpdateError("Nombre de descarga inválido para " + path)
        files[path] = {"sha256": sha, "size": size, "asset": asset}
    if "Game/LAIN-Game.pck" not in files or "Game/LAIN-Game.exe" not in files:
        raise UpdateError("El manifiesto no incluye el juego.")
    return {"version": version, "tag": tag, "files": files}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def installed_version(root: Path) -> str:
    try:
        return str(json.loads((root / INSTALLED).read_text(encoding="utf-8")).get("version", ""))
    except (OSError, ValueError, AttributeError):
        return ""


def plan(root: Path, manifest: dict) -> list[str]:
    """Files whose content differs from the release (a quick size check first)."""
    changed = []
    for path, entry in manifest["files"].items():
        local = root / path
        if not local.is_file() or local.stat().st_size != entry["size"] or sha256_file(local) != entry["sha256"]:
            changed.append(path)
    return changed


def download(url: str, target: Path, entry: dict, progress=None, opener=None) -> None:
    digest = hashlib.sha256()
    done = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with (opener or _open)(url, 60.0) as response, target.open("wb") as handle:
        while True:
            block = response.read(CHUNK)
            if not block:
                break
            done += len(block)
            if done > entry["size"]:
                raise UpdateError("La descarga es más grande de lo anunciado.")
            digest.update(block)
            handle.write(block)
            if progress:
                progress(len(block))
    if done != entry["size"] or digest.hexdigest() != entry["sha256"]:
        target.unlink(missing_ok=True)
        raise UpdateError("La descarga no coincide con su huella. No se ha cambiado nada.")


def update(root: Path, releases: str, manifest: dict, report=None, opener=None) -> bool:
    """Download every changed file, then swap them in. Returns True if LAIN.exe changed."""
    changed = plan(root, manifest)
    if not changed:
        (root / INSTALLED).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return False
    staging = root / STAGING
    shutil.rmtree(staging, ignore_errors=True)
    total = sum(manifest["files"][path]["size"] for path in changed)
    received = 0

    def advance(count: int) -> None:
        nonlocal received
        received += count
        if report:
            report(f"Descargando la versión {manifest['version']}…", received / total)

    base = releases.rstrip("/") + "/download/" + manifest["tag"] + "/"
    for path in changed:
        entry = manifest["files"][path]
        download(base + entry["asset"], staging / path, entry, advance, opener)
    if report:
        report("Instalando…", 1.0)
    launcher_changed = False
    for path in changed:
        if path == "LAIN.exe":
            launcher_changed = True
            continue
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging / path, root / path)
    if launcher_changed:
        # Windows lets a running program be renamed, not overwritten.
        old = root / "LAIN.old.exe"
        old.unlink(missing_ok=True)
        if (root / "LAIN.exe").exists():
            os.replace(root / "LAIN.exe", old)
        os.replace(staging / "LAIN.exe", root / "LAIN.exe")
    shutil.rmtree(staging, ignore_errors=True)
    (root / INSTALLED).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return launcher_changed


def cleanup(root: Path) -> None:
    for leftover in (root / "LAIN.old.exe", root / STAGING):
        try:
            if leftover.is_dir():
                shutil.rmtree(leftover)
            else:
                leftover.unlink(missing_ok=True)
        except OSError:
            pass
