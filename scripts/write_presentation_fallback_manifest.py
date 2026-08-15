"""Bind the committed judging deck to every authoring input.

The Codex artifact runtime authors and visually verifies the deck. Evaluators
without that runtime can still reproduce the rest of the build: the
presentation step verifies the committed PPTX and all source hashes, then
preserves it. Source drift cannot pass by reusing an old deck.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from wallet_twin_v2.canonical import write_canonical_json

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "output/presentation/Corporate-Wallet-Digital-Twin.pptx"
MANIFEST = ROOT / "assets/presentation/v3.2-committed-artifact-manifest.json"
SOURCES = (
    ROOT / "scripts/build_v31_presentation.mjs",
    ROOT / "scripts/capture_wallet_heatmap.mjs",
    ROOT / "assets/presentation/Corporate-Wallet-Digital-Twin-V3.2-Starter.pptx",
    ROOT / "data/v2/submission_truth_v3.2.0.json",
    ROOT / "dashboard/app/data/wallet-v311-fixture.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_sha256(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".js", ".json", ".mjs", ".ts", ".tsx"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    if not DECK.exists():
        raise RuntimeError("judging deck does not exist")
    missing = [str(path) for path in SOURCES if not path.exists()]
    if missing:
        raise RuntimeError(f"presentation authoring sources missing: {missing}")
    payload = {
        "version": "3.2.0",
        "artifact": DECK.relative_to(ROOT).as_posix(),
        "deck_sha256": sha256(DECK),
        "sources": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": source_sha256(path),
                "hash_mode": "LF_NORMALIZED_TEXT" if path.suffix.lower()
                in {".js", ".json", ".mjs", ".ts", ".tsx"}
                else "BYTE_EXACT",
            }
            for path in SOURCES
        ],
        "fallback_policy": "VERIFY_EXACT_COMMITTED_PPTX_WHEN_CODEX_ARTIFACT_RUNTIME_IS_UNAVAILABLE",
    }
    write_canonical_json(MANIFEST, payload)
    print(json.dumps({"status": "PASS", "manifest": str(MANIFEST)}, indent=2))


if __name__ == "__main__":
    main()
