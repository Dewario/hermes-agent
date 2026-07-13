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


def run_ocrmypdf(matter_dir: Path, docs: list, text_dir: Path) -> int:
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
    p.add_argument(
        "--run",
        action="store_true",
        help="execute ocrmypdf (default: print plan only)",
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    matter_dir = args.matter_dir.resolve()
    queue = load_queue(matter_dir)
    docs = queue.get("documents") or []
    text_dir = (args.text_dir or (matter_dir / "01_production" / "text")).resolve()
    if not str(text_dir).startswith(str(matter_dir)):
        print("ERROR: --text-dir must stay inside the matter directory")
        return 2

    plan = plan_commands(matter_dir, docs, text_dir)
    if args.json:
        print(json.dumps({
            "matter_id": queue.get("matter_id"),
            "count": len(docs),
            "text_dir": str(text_dir),
            "plan": plan,
        }, indent=2))
    else:
        print(f"OCR queue: {len(docs)} doc(s) for matter '{queue.get('matter_id')}'")
        print(f"Text output dir: {text_dir}")
        for line in plan:
            print(f"  {line}")
        print("After OCR: python skills/legal/casegraph/scripts/casegraph.py build "
              f"{matter_dir}")

    if args.run:
        return run_ocrmypdf(matter_dir, docs, text_dir)
    return 0 if not docs else 1


if __name__ == "__main__":
    sys.exit(main())
