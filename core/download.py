"""
Shared, verified download helpers for official XMRig release assets.

The project only downloads an asset after it has matched the SHA256 value
published in the corresponding official XMRig release manifest.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import stat
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

log = logging.getLogger("xmr-miner")

_RELEASE_BASE = "https://github.com/xmrig/xmrig/releases/download"
_SHA256_RE = re.compile(r"^([0-9a-fA-F]{64})\s+[* ](.+?)\s*$")


def _manifest_url(version: str) -> str:
    return f"{_RELEASE_BASE}/v{version}/SHA256SUMS"


def _read_expected_sha256(version: str, asset_name: str) -> str:
    request = urllib.request.Request(
        _manifest_url(version),
        headers={"User-Agent": "crypto-miner-controller/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        manifest = response.read().decode("utf-8", errors="replace")

    for line in manifest.splitlines():
        match = _SHA256_RE.match(line.strip())
        if match and Path(match.group(2)).name == asset_name:
            return match.group(1).lower()

    raise RuntimeError(
        f"Official SHA256SUMS did not contain an entry for {asset_name!r}"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(
    url: str,
    destination: Path,
    *,
    version: str,
    asset_name: str,
    reporthook: Callable[[int, int, int], None] | None = None,
) -> None:
    """Download one official release asset and verify its SHA256 checksum."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected = _read_expected_sha256(version, asset_name)

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "crypto-miner-controller/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
            total = int(response.headers.get("Content-Length", "-1"))
            block = 1024 * 1024
            count = 0
            while True:
                chunk = response.read(block)
                if not chunk:
                    break
                output.write(chunk)
                count += 1
                if reporthook:
                    reporthook(count, block, total)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    actual = _sha256(destination)
    if actual != expected:
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            f"SHA256 verification failed for {asset_name}: expected {expected}, got {actual}"
        )

    log.info("Verified %s (SHA256 %s)", asset_name, actual)


def safe_extract_zip(archive: Path, destination: Path) -> None:
    """Extract a ZIP while rejecting traversal and symbolic-link entries."""
    root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if os.path.commonpath((str(root), str(target))) != str(root):
                raise RuntimeError(f"Unsafe ZIP member path: {member.filename!r}")
            mode = (member.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"Symbolic links are not allowed in release archives: {member.filename!r}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(member))
