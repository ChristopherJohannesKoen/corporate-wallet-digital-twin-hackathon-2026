"""Create a safe, allow-listed, independently generated public mirror tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "tmp" / "public-mirror-export"
ALLOW_DIRS = ("src", "tests", "contracts", "prompts", "config", "infra", "services", "docs", ".github")
ALLOW_FILES = (
    "README.md", "pyproject.toml", "uv.lock", "requirements.txt", "Dockerfile",
    ".dockerignore", ".gitignore", ".gitattributes", ".python-version", ".env.example",
)
ALLOW_DATA = (
    "data/public_facts.csv", "data/v2/public_facts_expanded.csv", "data/v2/public_sources.json",
    "data/v2/external_dataset_registry.json", "data/v2/benchmark_rate_cards.json",
    "data/v2/representative_trade_finance_summary.json", "data/v2/golden_set/cases.jsonl",
    "data/v3/public_sensor_registry.json",
)
DENY_PARTS = {"ref", ".git", ".venv", "node_modules", "tmp", "output", "outputs", "deliverables", "external", "__pycache__"}
SECRET_PATTERNS = (
    re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AQ\.[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[oprsu]_[A-Za-z0-9]{20,}"),
)
CHALLENGE_DERIVED_PATTERNS = (
    "3,064,295",
    "3064295",
    "R17.018m",
    "R7.367m",
    "a79d5a995a43ebbf2039edad9e1b219675006e3f042b8587af371b4c4b44b072",
)


def copy_item(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(
            source,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "*.pyo", "*.egg-info",
                ".pytest_cache", ".ruff_cache", "node_modules", "dist", ".next",
            ),
        )
    elif source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def remove_tree(path: Path) -> None:
    """Remove an export tree, including read-only Git object files on Windows."""

    def make_writable_and_retry(function, target, _exc_info):
        os.chmod(target, 0o700)
        function(target)

    if path.exists():
        shutil.rmtree(path, onerror=make_writable_and_retry)


def safe_baseline() -> dict:
    sectors = ("advanced_manufacturing", "consumer_services", "resources", "infrastructure", "technology")
    products = ("Collections", "Payments", "Liquidity", "Cross-border FX", "Trade finance")
    clients = []
    opportunities = []
    months = [f"{year}-{month:02d}" for year in range(2023, 2027) for month in range(1, 13) if (year, month) >= (2023, 7) and (year, month) <= (2026, 6)]
    for idx in range(1, 21):
        entity_id = f"D{idx:02d}"
        entity_name = f"Demo Corporate {idx:02d}"
        sector = sectors[(idx - 1) % len(sectors)]
        monthly = {}
        client_total = 0.0
        for pidx, product in enumerate(products, start=1):
            base = 25_000_000.0 * idx * (0.45 + pidx * 0.22)
            values = []
            for midx, month in enumerate(months):
                seasonal = 1.0 + 0.12 * math.sin((midx + pidx) * math.pi / 6)
                trend = 1.0 + 0.003 * midx
                value = round(base * seasonal * trend, 2)
                values.append({"month": month, "value_zar": value})
            monthly[product] = values
            observed = round(sum(item["value_zar"] for item in values[-12:]), 2)
            client_total += observed
            opportunities.append({
                "entity_id": entity_id, "entity_name": entity_name, "sector": sector,
                "product": product, "opportunity_id": f"{entity_id}-{product.lower().replace(' ', '-').replace('cross-border-', 'cross-border-')}",
                "observed_activity_zar": observed, "recurrence": 1.0,
                "trend": round((values[-1]["value_zar"] / values[-12]["value_zar"]) - 1, 6),
                "timing_score": round(0.42 + 0.02 * ((idx + pidx) % 8), 6),
                "assumptions": {"economic_rate_bps": {"base": {"Collections": 8, "Payments": 7, "Liquidity": 45, "Cross-border FX": 65, "Trade finance": 140}[product]}},
                "anchor_impact": {"fact_ids": []}, "public_anchor": None,
            })
        clients.append({
            "entity_id": entity_id, "entity_name": entity_name, "sector": sector,
            "observed_ltm_zar": round(client_total, 2), "relationship_breadth": 5,
            "country_count": 3 + idx % 9,
            "top_countries": [{"name": f"Market {n}", "value_zar": round(client_total / (n + 2), 2)} for n in range(1, 4)],
            "top_currencies": [{"name": pair, "value_zar": round(client_total / (n + 4), 2)} for n, pair in enumerate(("USD/ZAR", "EUR/ZAR", "GBP/ZAR"))],
            "monthly": monthly,
        })
    return {
        "metadata": {"title": "Corporate Wallet Digital Twin public mirror", "model_version": "3.2.0-safe", "as_of": "2026-06-30", "generated_from": "independently generated anonymized aggregate fixture", "currency": "ZAR"},
        "clients": clients,
        "opportunities": opportunities,
    }


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    out = args.output.resolve()
    remove_tree(out)
    out.mkdir(parents=True)
    for relative in ALLOW_DIRS:
        copy_item(ROOT / relative, out / relative)
    for relative in ALLOW_FILES + ALLOW_DATA:
        copy_item(ROOT / relative, out / relative)
    copy_item(ROOT / "dashboard", out / "dashboard")
    copy_item(ROOT / "scripts", out / "scripts")

    # Remove private/submission-only builders and all legacy/challenge aggregates.
    for relative in (
        "scripts/build_finance_sme_review_pack.py", "scripts/export_public_mirror.py",
        "scripts/build_submission.py", "scripts/build_submission_pdf.py",
        "scripts/build_v31_notebook.py", "scripts/build_v3_notebook.py",
        "scripts/build_v31_presentation.mjs", "scripts/capture_wallet_heatmap.mjs",
        "scripts/write_presentation_fallback_manifest.py",
        "scripts/export_submission_truth.py",
    ):
        (out / relative).unlink(missing_ok=True)
    # The public mirror carries a safe-demo suite. Private V1/V3 regression
    # boundaries assert challenge-derived outputs and therefore cannot be
    # published or expected to pass against independently generated clients.
    for relative in ("tests",):
        path = out / relative
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)

    # The private dossier and judging map contain challenge-derived counts and
    # named commercial outputs. Publish a compact safe methodology instead of
    # trying to redact those long documents in place.
    remove_tree(out / "docs")
    (out / "docs").mkdir(parents=True, exist_ok=True)
    (out / "docs" / "METHODOLOGY.md").write_text(
        "# Safe-mirror methodology\n\n"
        "The Corporate Wallet Digital Twin models the identity `A = qT`, where "
        "the safe fixture observes anonymized aggregate activity `A` and treats "
        "total wallet `T` and share `q` as latent. It reports identification "
        "bounds, model-based posterior intervals and explicitly labelled "
        "commercial scenarios. The Decision Twin maps an interval to a role, "
        "problem, solution, timing and discovery question. The Promotion Twin "
        "evaluates REAL and REHEARSAL evidence separately.\n\n"
        "This mirror contains independently generated `D01`–`D20` aggregates "
        "and public-source registries only. It establishes software mechanics, "
        "not the confidential hackathon result, measured competitor share, bank "
        "economics, RM adoption, causal uplift or bank authorization.\n",
        encoding="utf-8",
    )
    (out / "docs" / "DATA_AND_CLAIM_BOUNDARY.md").write_text(
        "# Data and claim boundary\n\n"
        "Allowed: source code, schemas, prompts, infrastructure definitions, "
        "public issuer facts and independently generated anonymized aggregates.\n\n"
        "Excluded: supplied or derived row-level bank data, challenge-derived "
        "client aggregates, named-client provider packs, credentials, downloaded "
        "documents, private judging artifacts and caches.\n",
        encoding="utf-8",
    )
    baseline = safe_baseline()
    safe_path = out / "legacy/v1/fixtures/portfolio.json"
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")

    # The private tree's submission truth contains named-client evaluation
    # evidence. Replace it before any build or commit can observe the export.
    # The safe mirror demonstrates the same API shape with no provider claim.
    safe_truth = {
        "version": "3.2.0-safe",
        "as_of": "2026-06-30",
        "genai": {
            "evaluation_scope": "SAFE_PUBLIC_MIRROR_NOT_EXECUTED",
            "target_runs": 0,
            "runs": 0,
            "accepted_runs": 0,
            "blocked_runs": 0,
            "submission_gate_passed": False,
            "accepted_providers": [],
            "accepted_clients": [],
            "showcase_briefs": {},
            "blocked_evaluations": [],
            "bank_authorized_live_genai": False,
            "claim_boundary": "No provider evaluation or named-client pack is published in the safe mirror.",
        },
        "promotion": {
            "real_state": "OFFLINE_CANDIDATE",
            "rehearsed_state": "SHADOW_READY",
            "package_status": "SHADOW_DEPLOYMENT_PACKAGE_READY",
            "promotion_machinery_readiness": 1.0,
            "bank_evidence_readiness": 0.0,
            "bank_shadow_authorized": False,
            "bank_production_status": "NOT_PROMOTABLE",
            "shadow_rehearsal_days": 30,
            "elapsed_bank_shadow_days": 0,
        },
    }
    for safe_truth_path in (
        out / "data/v2/submission_truth_v3.2.0.json",
        out / "dashboard/app/data/submission-truth-v3.2.0.json",
    ):
        safe_truth_path.parent.mkdir(parents=True, exist_ok=True)
        safe_truth_path.write_text(json.dumps(safe_truth, indent=2) + "\n", encoding="utf-8")

    # The private registry records the supplied challenge archive and its
    # exact row count.  Neither belongs in a clean public history.  Retain the
    # licence-governed public/representative datasets and make the omission
    # explicit instead of redacting the private entry in place.
    registry_path = out / "data/v2/external_dataset_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["datasets"] = [
        dataset
        for dataset in registry["datasets"]
        if dataset.get("dataset_id") != "synbank-supplied-banking-data"
    ]
    registry["public_mirror_boundary"] = (
        "The supplied hackathon archive and every challenge-derived aggregate "
        "are intentionally absent from this clean public mirror."
    )
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    # The demo-data module is useful for generating independent rehearsal
    # panels, but its private manifest helper embeds the challenge archive row
    # count.  A public build has no supplied rows, so the exported source must
    # report zero rather than preserve that challenge-specific fingerprint.
    demo_data_path = out / "src/wallet_twin_v2/demo_data.py"
    demo_source = demo_data_path.read_text(encoding="utf-8")
    private_count_line = '"synbank_rows": 3064295,'
    if private_count_line not in demo_source:
        raise RuntimeError("expected private source-estate count was not found")
    demo_data_path.write_text(
        demo_source.replace(private_count_line, '"synbank_rows": 0,'),
        encoding="utf-8",
    )

    # The workbench source is publishable, but its committed private fixtures
    # are not. Rebuild every browser fixture inside the export process after the
    # anonymous baseline is installed, using only the exported code and data.
    # This prevents a clean public history from ever containing the challenge-
    # derived client aggregates, even for a single commit.
    public_env = {
        **dict(os.environ),
        "PYTHONPATH": str(out / "src"),
        "WALLET_TWIN_REPOSITORY_BACKEND": "fixture",
    }
    # The V3.2 exporters join this loop for the same reason the others are in
    # it: dashboard/ is copied wholesale, so promotion-fixture.json would
    # otherwise be published verbatim from the private tree rather than
    # regenerated from exported code and data. Its content is entirely synthetic
    # rehearsal evidence, but "we checked and it was safe" is a weaker guarantee
    # than "it was rebuilt inside the export".
    for script in (
        "export_v3_contracts.py",
        "export_v31_contracts.py",
        "export_v311_wallet_surface.py",
        "export_v32_contracts.py",
        "export_v32_workbench_fixture.py",
    ):
        subprocess.run(
            [sys.executable, str(out / "scripts" / script)],
            cwd=out,
            env=public_env,
            check=True,
        )
    for cache in sorted(out.rglob("__pycache__"), reverse=True):
        remove_tree(cache)
    for compiled in out.rglob("*.py[co]"):
        compiled.unlink(missing_ok=True)
    # Exporters also create analytical outputs. Those are useful only to the
    # private judging build; the public mirror keeps just the safe workbench
    # fixtures and the contract/schema surface.
    shutil.rmtree(out / "outputs", ignore_errors=True)

    safe_test = out / "tests/test_public_mirror_safe_demo.py"
    safe_test.parent.mkdir(parents=True, exist_ok=True)
    safe_test.write_text(
        '''"""Public-mirror smoke tests; no private result is asserted."""\n\nfrom wallet_twin_v2.fixtures import build_fixture\n\n\ndef test_independent_safe_fixture_executes_all_cells():\n    fixture = build_fixture()\n    assert len(fixture["clients"]) == 20\n    assert len(fixture["opportunities"]) == 100\n    assert all(item.entity_id.startswith("D") for item in fixture["opportunities"])\n    assert not any(item.evidence_tier.value == "E1" for item in fixture["opportunities"])\n\n\ndef test_safe_fixture_never_claims_measured_share_or_causal_value():\n    fixture = build_fixture()\n    for item in fixture["opportunities"]:\n        assert item.share_interval.claim_class.value == "POSTERIOR"\n        assert item.commercial.causal_expected_incremental_value is None\n''',
        encoding="utf-8",
    )

    public_readme = out / "PUBLIC_MIRROR.md"
    safe_readme = """# Corporate Wallet Digital Twin V3.2.0 — safe public mirror

This clean-history mirror contains the production-shaped source, contracts,
tests and infrastructure definitions, but it runs only on an independently
generated, anonymized 20-client aggregate fixture. It contains no supplied or
derived row-level Syn Bank data, challenge-derived client aggregates,
credentials, provider payloads or downloaded source documents.

The public result demonstrates mechanics only. It is not the confidential
hackathon result, measured competitor share, causal uplift or a bank-production
release.

## Reproduce

```bash
uv sync --frozen --all-extras
uv run python scripts/build_safe_demo.py
```

The command rebuilds the V2/V3/V3.1/V3.2 schemas, anonymous workbench fixtures
and synthetic-only Promotion Twin, runs the safe-demo tests, and checks the
mirror manifest. Promotion evidence remains rehearsal-only and cannot authorize
bank use.
"""
    public_readme.write_text(safe_readme, encoding="utf-8")
    (out / "README.md").write_text(safe_readme, encoding="utf-8")
    (out / "scripts" / "build_safe_demo.py").write_text(
        '''"""Rebuild and verify only the independently generated public demo."""\n\nfrom __future__ import annotations\n\nimport json\nimport shutil\nimport subprocess\nimport sys\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\n\ndef run(*args: str) -> None:\n    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)\n\n\ndef main() -> None:\n    run("scripts/export_v3_contracts.py")\n    run("scripts/export_v31_contracts.py")\n    run("-m", "pytest", "-q", "tests")\n    manifest = json.loads((ROOT / "public-mirror-manifest.json").read_text(encoding="utf-8"))\n    if manifest["status"] != "PASS":\n        raise SystemExit("public mirror manifest is not PASS")\n    # Export scripts create anonymous analytical intermediates. The committed\n    # mirror needs only the rebuilt browser fixtures and contracts.\n    shutil.rmtree(ROOT / "outputs", ignore_errors=True)\n    print(json.dumps({"status": "PASS", "version": "3.1.1-safe", "cells": 100}, indent=2))\n\n\nif __name__ == "__main__":\n    main()\n''',
        encoding="utf-8",
    )
    # Replace the frozen V3.1-safe helper above with the V3.2 additive build.
    # Keeping this as a second write avoids altering the historical string that
    # older clean-history mirrors may still compare in release notes.
    (out / "scripts" / "build_safe_demo.py").write_text(
        '''"""Rebuild and verify only the independently generated public demo."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def main() -> None:
    run("scripts/export_v3_contracts.py")
    run("scripts/export_v31_contracts.py")
    run("scripts/export_v311_wallet_surface.py")
    run("scripts/export_v32_contracts.py")
    run("scripts/export_v32_workbench_fixture.py")
    run("-m", "pytest", "-q", "tests")
    manifest = json.loads(
        (ROOT / "public-mirror-manifest.json").read_text(encoding="utf-8")
    )
    if manifest["status"] != "PASS":
        raise SystemExit("public mirror manifest is not PASS")
    shutil.rmtree(ROOT / "outputs", ignore_errors=True)
    print(json.dumps({
        "status": "PASS", "version": "3.2.0-safe", "cells": 100,
        "promotion_mode": "SYNTHETIC_REHEARSAL",
    }, indent=2))


if __name__ == "__main__":
    main()
''',
        encoding="utf-8",
    )
    # Do not inherit the private judging workflow: it asserts confidential
    # regression outputs that are intentionally absent from this mirror.
    # The public workflow proves the anonymous analytical path and browser
    # build independently from a clean clone.
    workflow_dir = out / ".github" / "workflows"
    shutil.rmtree(workflow_dir, ignore_errors=True)
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / "ci.yml").write_text(
        """name: public-mirror-safe-ci
on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  safe-demo:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: \"3.12\" }
      - uses: astral-sh/setup-uv@v6
        with: { version: \"0.9.2\", enable-cache: true }
      - run: uv lock --check
      - run: uv sync --frozen --extra dev --extra genai --extra production
      - run: uv run python scripts/build_safe_demo.py
      - run: git diff --exit-code -- contracts dashboard/app/data
      - run: test -z "$(git status --porcelain)"

  workbench:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: dashboard
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: \"22.14\"
          cache: npm
          cache-dependency-path: dashboard/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm test
      - run: npm run build
      - run: npm audit --omit=dev --audit-level=high
""",
        encoding="utf-8",
    )
    denial = []
    scanned = 0
    for path in out.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(out)
        if DENY_PARTS.intersection(relative.parts) or path.name.lower() in {"data.zip", ".env"}:
            denial.append(f"DENY_PATH:{relative.as_posix()}")
        if path.stat().st_size <= 5_000_000:
            data = path.read_bytes()
            scanned += 1
            text = data.decode("utf-8", errors="ignore")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    denial.append(f"SECRET_PATTERN:{relative.as_posix()}:{pattern.pattern[:12]}")
            for pattern in CHALLENGE_DERIVED_PATTERNS:
                if pattern in text:
                    denial.append(f"CHALLENGE_DERIVED_PATTERN:{relative.as_posix()}:{pattern[:12]}")
            if b"PK\x03\x04" in data and path.suffix.lower() == ".zip":
                denial.append(f"ZIP_ARCHIVE:{relative.as_posix()}")
    status = "PASS" if not denial else "FAIL"
    manifest = {
        "version": "3.2.0", "status": status, "history": "CLEAN_HISTORY_REQUIRED",
        "data_mode": "INDEPENDENTLY_GENERATED_ANONYMIZED_AGGREGATES",
        "files": sum(1 for p in out.rglob("*") if p.is_file()), "scanned_files": scanned,
        "safe_fixture_sha256": sha256(safe_path), "denial_findings": denial,
        "excluded": ["ref/", "Data.zip", "row-level derivatives", "challenge-derived client fixtures", "downloaded snapshots", ".env and credentials", "provider payloads", "caches", "rendered intermediates"],
    }
    (out / "public-mirror-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (ROOT / "public-mirror-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), **manifest}, indent=2))
    if denial:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
