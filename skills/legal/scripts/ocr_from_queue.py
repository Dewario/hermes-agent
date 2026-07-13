#!/usr/bin/env python3
"""Drive OCR from casegraph's needs_ocr.json queue (live-matter helper).

Does NOT invent text. Reads ``<matter>/.casegraph/needs_ocr.json`` (from
``casegraph build`` / ``export-ocr-queue``) and either:

* prints a PowerShell/bash plan (default), or
* runs ``ocrmypdf`` when ``--run`` and ``ocrmypdf`` are available.

For complex layouts, a separately installed local Docling may be used as an
optional alternative; plan output records that option but never invokes it.

After OCR, re-run ``casegraph build`` so text becomes cite-verifiable.

Synthetic-safe: operates only under the given matter directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def load_queue(matter_dir: Path) -> dict:
    path = matter_dir / ".casegraph" / "needs_ocr.json"
    if not path.exists():
        raise SystemExit(
            f"ERROR: missing {path} — run: casegraph build / export-ocr-queue first"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def contained_path(matter_dir: Path, value: Path) -> Path:
    """Resolve a path and reject values outside the matter directory."""
    path = value.resolve()
    try:
        path.relative_to(matter_dir)
    except ValueError as exc:
        raise ValueError(f"Path must stay inside the matter directory: {path}") from exc
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read OCR farm state: {path}: {exc}") from exc
    completed = payload.get("completed_sha256", [])
    if not isinstance(completed, list) or not all(isinstance(item, str) for item in completed):
        raise ValueError(f"Invalid completed_sha256 list in OCR farm state: {path}")
    return set(completed)


def save_state(path: Path, completed: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "completed_sha256": sorted(completed),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def pending_pdf_documents(
    matter_dir: Path, docs: list, completed: set[str], limit: int | None,
) -> list[dict]:
    """Return at most ``limit`` pending PDFs, each annotated with its content hash."""
    pending = []
    for document in docs:
        relpath = document.get("relpath")
        if not isinstance(relpath, str) or Path(relpath).suffix.lower() != ".pdf":
            continue
        try:
            source = contained_path(matter_dir, matter_dir / relpath)
        except ValueError:
            continue
        if not source.is_file():
            continue
        digest = sha256_file(source)
        if digest in completed:
            continue
        pending.append({**document, "_sha256": digest})
        if limit is not None and len(pending) >= limit:
            break
    return pending


def plan_commands(matter_dir: Path, docs: list, text_dir: Path) -> list[str]:
    cmds = []
    text_dir.mkdir(parents=True, exist_ok=True)
    if docs:
        cmds.append(
            "# Optional for complex layouts: use a separately installed local "
            "Docling extractor; it is not bundled or invoked by this helper."
        )
    for d in docs:
        rel = d["relpath"]
        src = matter_dir / rel
        stem = Path(rel).stem
        out_pdf = text_dir / f"{stem}.searchable.pdf"
        out_txt = text_dir / f"{stem}.txt"
        if Path(rel).suffix.lower() == ".pdf":
            cmds.append(f'ocrmypdf --skip-text "{src}" "{out_pdf}"')
            cmds.append(f'# then copy/extract text layer → "{out_txt}"')
        else:
            cmds.append(f"# Manual/vision OCR needed for non-PDF: {src} → {out_txt}")
    return cmds


def run_ocrmypdf(
    matter_dir: Path, docs: list, text_dir: Path, state_file: Path, completed: set[str],
) -> int:
    if not shutil.which("ocrmypdf"):
        print("ERROR: ocrmypdf not on PATH — install OCRmyPDF + Tesseract, or use --plan")
        return 2
    text_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for d in docs:
        rel = d["relpath"]
        src = matter_dir / rel
        if not src.exists():
            print(f"SKIP missing: {rel}")
            failed += 1
            continue
        if src.suffix.lower() != ".pdf":
            print(f"SKIP non-PDF (manual): {rel}")
            continue
        stem = Path(rel).stem
        out_pdf = text_dir / f"{stem}.searchable.pdf"
        print(f"OCR: {rel} → {out_pdf}")
        rc = subprocess.call(
            ["ocrmypdf", "--skip-text", str(src), str(out_pdf)],
        )
        if rc != 0:
            print(f"FAIL ocrmypdf exit {rc}: {rel}")
            failed += 1
            continue
        completed.add(d["_sha256"])
        save_state(state_file, completed)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("matter_dir", type=Path)
    p.add_argument(
        "--text-dir",
        type=Path,
        default=None,
        help="default: <matter>/01_production/text",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--plan",
        action="store_true",
        help="print the OCR plan without executing it (default)",
    )
    mode.add_argument(
        "--run",
        action="store_true",
        help="execute ocrmypdf",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="process only the first N pending PDFs",
    )
    p.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="default: <matter>/.casegraph/ocr_farm_state.json",
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    matter_dir = args.matter_dir.resolve()
    if args.limit is not None and args.limit < 0:
        p.error("--limit must be zero or greater")
    queue = load_queue(matter_dir)
    docs = queue.get("documents") or []
    try:
        text_dir = contained_path(
            matter_dir, args.text_dir or (matter_dir / "01_production" / "text")
        )
        state_file = contained_path(
            matter_dir, args.state_file or (matter_dir / ".casegraph" / "ocr_farm_state.json")
        )
        completed = load_state(state_file)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    pending = pending_pdf_documents(matter_dir, docs, completed, args.limit)

    plan = plan_commands(matter_dir, pending, text_dir)
    if args.json:
        print(json.dumps({
            "matter_id": queue.get("matter_id"),
            "count": len(pending),
            "queued_count": len(docs),
            "text_dir": str(text_dir),
            "state_file": str(state_file),
            "plan": plan,
        }, indent=2))
    else:
        print(f"OCR queue: {len(pending)} pending PDF(s) for matter '{queue.get('matter_id')}'")
        print(f"Text output dir: {text_dir}")
        print(f"State file: {state_file}")
        for line in plan:
            print(f"  {line}")
        print("After OCR: python skills/legal/casegraph/scripts/casegraph.py build "
              f"{matter_dir}")

    if args.run:
        return run_ocrmypdf(matter_dir, pending, text_dir, state_file, completed)
    return 0 if not pending else 1


if __name__ == "__main__":
    sys.exit(main())
