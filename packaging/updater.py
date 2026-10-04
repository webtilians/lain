"""Online client self-update from GitHub Releases. Standard library only.

The release publishes manifest.json next to its assets:
    {"version": "0.13.0", "tag": "v0.13.0",
     "files": {"Game/LAIN-Game.pck": {"asset": "LAIN-Game.pck", "sha256": "...", "size": 123}, ...},
     "parts": {"asset": "parts.json.gz", "sha256": "...", "size": 456}}
Only listed client files can change, every byte is checked against its
SHA-256 before anything on disk is replaced, and downloads may only come from
GitHub over HTTPS. If anything fails the installed version keeps working.

Patches: "parts" (optional) lists every big file as content-defined parts
(length and hash). The launcher cuts its installed copy the same way, keeps
the parts it already has and downloads only the missing byte ranges of the
release asset. A small change to the game then costs a few MB instead of the
whole pck. Any doubt, and it downloads the whole file as before.
"""

from __future__ import annotations

import gzip
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import ssl
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zlib

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
# A part ends after an anchor byte whose preceding PARTS_WINDOW bytes hash to
# zero under PARTS_MASK (about every 16 KB), never before PARTS_MIN nor after
# PARTS_MAX. The cut depends only on nearby bytes, so an insertion changes the
# parts around it and the rest of the file still matches. Measured on v0.22.0
# -> v0.23.0: 3.2 MB of 291 MB. Changing these values invalidates every cut.
PARTS_MIN = 2 << 10
PARTS_MAX = 256 << 10
PARTS_WINDOW = 32
PARTS_MASK = 63
PARTS_ANCHOR = b"\xa5"
PARTS_LIMIT = 16_000_000
PATCH_SHARE = 0.7           # a patch above this share of the file is not worth it
RANGE_GAP = 32 << 10        # parts already here but this close are fetched in the same range
RANGE_MAX = 8 << 20


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


def _open(url: str, timeout: float, headers: dict | None = None):
    opener = build_opener(_GitHubOnly())
    request = Request(check_url(url), headers={"User-Agent": "LAIN-Launcher", **(headers or {})})
    return opener.open(request, timeout=timeout)


def fetch_manifest(releases: str, timeout: float = 8.0, opener=None) -> dict:
    url = releases.rstrip("/") + "/latest/download/manifest.json"
    with (opener or _open)(url, timeout) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise UpdateError("Manifiesto demasiado grande.")
    return validate_manifest(json.loads(raw.decode("utf-8")))


def _asset(entry, label: str, limit: int) -> dict:
    if not isinstance(entry, dict):
        raise UpdateError("Entrada inválida para " + label)
    sha, size, asset = entry.get("sha256"), entry.get("size"), entry.get("asset")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise UpdateError("Huella inválida para " + label)
    if not isinstance(size, int) or not 0 < size <= limit:
        raise UpdateError("Tamaño inválido para " + label)
    if not isinstance(asset, str) or not re.fullmatch(r"[0-9A-Za-z._-]{1,80}", asset):
        raise UpdateError("Nombre de descarga inválido para " + label)
    return {"sha256": sha, "size": size, "asset": asset}


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
        if path not in ALLOWED_FILES:
            raise UpdateError("Archivo no permitido en el manifiesto: " + str(path))
        files[path] = _asset(entry, path, MAX_BYTES)
    if "Game/LAIN-Game.pck" not in files or "Game/LAIN-Game.exe" not in files:
        raise UpdateError("El manifiesto no incluye el juego.")
    result = {"version": version, "tag": tag, "files": files}
    if data.get("parts") is not None:
        result["parts"] = _asset(data["parts"], "la lista de trozos", PARTS_LIMIT)
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def part_digest(data) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def split(path: Path) -> list[tuple[int, int, str]]:
    """The file's content-defined parts as (offset, length, digest)."""
    parts = []
    with path.open("rb") as handle:
        buffer, offset, eof = b"", 0, False
        while True:
            if not eof:
                block = handle.read(8 * CHUNK)
                eof = not block
                buffer += block
            pos = 0
            # A cut is decided only once the whole window after it is read, so
            # the parts never depend on how the file was read.
            while len(buffer) - pos > PARTS_MAX or (eof and pos < len(buffer)):
                limit = pos + PARTS_MAX
                hit = buffer.find(PARTS_ANCHOR, pos + PARTS_MIN - 1, limit)
                while hit >= 0 and zlib.crc32(buffer[hit - PARTS_WINDOW:hit + 1]) & PARTS_MASK:
                    hit = buffer.find(PARTS_ANCHOR, hit + 1, limit)
                cut = min(len(buffer), hit + 1 if hit >= 0 else limit)
                parts.append((offset + pos, cut - pos, part_digest(memoryview(buffer)[pos:cut])))
                pos = cut
            buffer, offset = buffer[pos:], offset + pos
            if eof and not buffer:
                return parts


def validate_parts(data, manifest: dict) -> dict[str, list[tuple[int, str]]]:
    if not isinstance(data, dict):
        raise UpdateError("Lista de trozos inválida.")
    table = {}
    for path, parts in data.items():
        if path not in manifest["files"] or not isinstance(parts, list):
            raise UpdateError("Lista de trozos inválida para " + str(path))
        clean = []
        for item in parts:
            if not (isinstance(item, list) and len(item) == 2):
                raise UpdateError("Trozo inválido en " + path)
            length, digest = item
            if type(length) is not int or not 0 < length <= PARTS_MAX \
                    or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{16}", digest):
                raise UpdateError("Trozo inválido en " + path)
            clean.append((length, digest))
        if sum(length for length, _ in clean) != manifest["files"][path]["size"]:
            raise UpdateError("Los trozos de " + path + " no suman su tamaño.")
        table[path] = clean
    return table


def fetch_parts(base: str, manifest: dict, staging: Path, opener=None) -> dict:
    entry = manifest.get("parts")
    if not entry:
        return {}
    target = staging / "parts.json.gz"
    download(base + entry["asset"], target, entry, opener=opener)
    with gzip.open(target, "rb") as handle:
        raw = handle.read(16 * PARTS_LIMIT + 1)
    target.unlink()
    if len(raw) > 16 * PARTS_LIMIT:
        raise UpdateError("Lista de trozos demasiado grande.")
    return validate_parts(json.loads(raw.decode("utf-8")), manifest)


def recipe(local: Path, parts: list[tuple[int, str]]) -> tuple[list[tuple[int, int, str, int | None]], int]:
    """For each part of the new file (offset, length, digest, where it is in the local copy or None),
    and how many bytes have to be downloaded."""
    have = {}
    for offset, length, digest in split(local):
        have.setdefault((length, digest), offset)
    steps, offset, remote = [], 0, 0
    for length, digest in parts:
        origin = have.get((length, digest))
        steps.append((offset, length, digest, origin))
        if origin is None:
            remote += length
        offset += length
    return steps, remote


def runs(steps: list) -> list[list]:
    """Missing parts grouped into byte ranges; parts already here between two close ones are fetched too."""
    groups, current, between = [], [], []
    for step in steps:
        if step[3] is None:
            end = step[0] + step[1]
            if current and sum(s[1] for s in between) <= RANGE_GAP and end - current[0][0] <= RANGE_MAX:
                current += between + [step]
            else:
                if current:
                    groups.append(current)
                current = [step]
            between = []
        elif current:
            between.append(step)
    if current:
        groups.append(current)
    return groups


class Ranges:
    """Byte ranges of one release asset over a single kept-alive HTTPS connection."""

    def __init__(self, url: str, timeout: float = 60.0):
        self.timeout = timeout
        self.connection = None
        # GitHub redirects to signed storage: follow that once, then reuse it.
        with _open(url, timeout, {"Range": "bytes=0-0"}) as response:
            final = urlsplit(check_url(response.geturl()))
            response.read()
        self.host = final.hostname
        self.target = final.path + ("?" + final.query if final.query else "")

    def read(self, start: int, end: int) -> bytes:
        for attempt in range(3):
            try:
                if self.connection is None:
                    self.connection = http.client.HTTPSConnection(
                        self.host, timeout=self.timeout, context=ssl.create_default_context())
                self.connection.request("GET", self.target, headers={
                    "Range": f"bytes={start}-{end - 1}", "User-Agent": "LAIN-Launcher"})
                response = self.connection.getresponse()
                data = response.read(end - start + 1)
                expected = f"bytes {start}-{end - 1}/"
                if response.status != 206 or not str(response.getheader("Content-Range", "")).startswith(expected) \
                        or len(data) != end - start:
                    raise UpdateError("El servidor de descargas no devolvió el trozo pedido.")
                return data
            except (OSError, http.client.HTTPException) as error:
                self.close()
                if attempt == 2:
                    raise UpdateError("Se cortó la descarga del parche.") from error
        raise UpdateError("Se cortó la descarga del parche.")

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None


def patch(url: str, local: Path, target: Path, entry: dict, steps: list, progress=None, ranges=None) -> None:
    """Rebuild the new file from the parts already here plus byte ranges of the release asset."""
    groups = {group[0][0]: group for group in runs(steps)}
    digest = hashlib.sha256()
    reader = None
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with local.open("rb") as source, target.open("wb") as handle:
            index = 0
            while index < len(steps):
                offset, length, part, origin = steps[index]
                group = groups.get(offset)
                if group:
                    if reader is None:
                        reader = (ranges or Ranges)(url)
                    data = reader.read(offset, group[-1][0] + group[-1][1])
                    if progress:
                        progress(len(data))
                    pieces = [(s[1], s[2], data[s[0] - offset:s[0] - offset + s[1]]) for s in group]
                    index += len(group)
                else:
                    source.seek(origin)
                    pieces = [(length, part, source.read(length))]
                    index += 1
                for size, expected, data in pieces:
                    if len(data) != size or part_digest(data) != expected:
                        raise UpdateError("Un trozo del parche no coincide con su huella.")
                    digest.update(data)
                    handle.write(data)
    finally:
        if reader is not None:
            reader.close()
    if target.stat().st_size != entry["size"] or digest.hexdigest() != entry["sha256"]:
        target.unlink(missing_ok=True)
        raise UpdateError("El archivo reconstruido no coincide con su huella.")


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


def update(root: Path, releases: str, manifest: dict, report=None, opener=None, ranges=None) -> bool:
    """Download every changed file (or just its changes), then swap them in. Returns True if LAIN.exe changed."""
    changed = plan(root, manifest)
    if not changed:
        (root / INSTALLED).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return False
    staging = root / STAGING
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    base = releases.rstrip("/") + "/download/" + manifest["tag"] + "/"
    if report:
        report("Comprobando qué ha cambiado…", 0.0)
    patches = {}
    try:
        table = fetch_parts(base, manifest, staging, opener)
        for path in changed:
            if path in table and (root / path).is_file():
                steps, remote = recipe(root / path, table[path])
                if remote <= PATCH_SHARE * manifest["files"][path]["size"]:
                    patches[path] = (steps, remote)
    except (OSError, EOFError, ValueError, zlib.error, UpdateError):
        patches = {}  # no patch this time: whole files, as before
    total = max(1, sum(patches[path][1] if path in patches else manifest["files"][path]["size"] for path in changed))
    megabytes = f"{total / 1e6:.1f}".replace(".", ",")
    text = f"Descargando la versión {manifest['version']} ({megabytes} MB)…"
    received = 0

    def advance(count: int) -> None:
        nonlocal received
        received += count
        if report:
            report(text, min(1.0, received / total))

    for path in changed:
        entry = manifest["files"][path]
        if path in patches:
            try:
                patch(base + entry["asset"], root / path, staging / path, entry, patches[path][0], advance, ranges)
                continue
            except (OSError, UpdateError):
                (staging / path).unlink(missing_ok=True)  # the whole file instead
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
