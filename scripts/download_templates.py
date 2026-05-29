#!/usr/bin/env python3
"""Download gitignore.io templates into the bundled data directory."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

API_BASE = "https://www.toptal.com/developers/gitignore/api"
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "src" / "gitignore_cli" / "data"
TEMPLATES_DIR = DATA_DIR / "templates"
USER_AGENT = "gitignore-cli-template-sync/1.0"
MAX_WORKERS = 4
MAX_ATTEMPTS = 5


def fetch_text(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in {403, 429, 503} and attempt + 1 < MAX_ATTEMPTS:
                time.sleep(0.5 * (2**attempt))
                continue
            raise
        except OSError as exc:
            last_error = exc
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(0.5 * (2**attempt))
                continue
            raise
    assert last_error is not None
    raise last_error


def download_template(name: str) -> tuple[str, str | None, str | None]:
    try:
        content = fetch_text(f"{API_BASE}/{name}")
        return name, content, None
    except urllib.error.HTTPError as exc:
        return name, None, f"HTTP {exc.code}"
    except OSError as exc:
        return name, None, str(exc)


def download_all(templates: list[str]) -> tuple[int, list[str]]:
    failures: list[str] = []
    downloaded = 0
    pending = [
        name
        for name in templates
        if not (TEMPLATES_DIR / f"{name}.gitignore").exists()
    ]
    if not pending:
        return 0, []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(download_template, name): name for name in pending}
        for index, future in enumerate(as_completed(futures), start=1):
            name, content, error = future.result()
            if error or content is None:
                failures.append(f"{name}: {error}")
                continue
            (TEMPLATES_DIR / f"{name}.gitignore").write_text(content, encoding="utf-8")
            downloaded += 1
            if index % 50 == 0 or index == len(pending):
                print(f"  {index}/{len(pending)}")
    return downloaded, failures


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching template list...")
    template_list = fetch_text(f"{API_BASE}/list?format=lines")
    templates = [line.strip().lower() for line in template_list.splitlines() if line.strip()]
    print(f"Found {len(templates)} templates")

    print("Fetching sort order...")
    order = json.loads(fetch_text(f"{API_BASE}/order"))

    print("Downloading templates...")
    failures: list[str] = []
    downloaded = 0
    pending = templates
    for attempt in range(1, 4):
        if attempt > 1:
            print(f"Retrying {len(pending)} failed templates (attempt {attempt})...")
        batch_downloaded, batch_failures = download_all(pending)
        downloaded += batch_downloaded
        if not batch_failures:
            failures = []
            break
        pending = [entry.split(":", 1)[0] for entry in batch_failures]
        failures = batch_failures

    (DATA_DIR / "list.txt").write_text("\n".join(templates) + "\n", encoding="utf-8")
    (DATA_DIR / "order.json").write_text(json.dumps(order, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "source": API_BASE,
        "downloaded_at": datetime.now(UTC).isoformat(),
        "template_count": len(templates),
    }
    (DATA_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Downloaded {len(list(TEMPLATES_DIR.glob('*.gitignore')))}/{len(templates)} templates to {TEMPLATES_DIR}")
    if failures:
        print(f"{len(failures)} failures:", file=sys.stderr)
        for failure in failures[:20]:
            print(f"  {failure}", file=sys.stderr)
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
