#!/usr/bin/env python3
"""
receipt2bean - turn photos of receipts into staged Beancount transactions,
using a local open-weight vision model served by Ollama.

Nothing leaves your machine. Entries are written with the pending flag (!)
to a staging file so a human reviews them before they join the real ledger.

    python receipt2bean.py ~/receipts/ --config rules.toml --out staging.bean
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

DEFAULT_MODEL = "qwen3-vl:8b"  # any Ollama vision model tag works: --model ...
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}  # PDFs: first page only
TOL = Decimal("0.02")  # rounding tolerance when checking the arithmetic
CENT = Decimal("0.01")

# What we ask the model to return. Only merchant and total are required.
SCHEMA = {
    "type": "object",
    "properties": {
        "merchant": {"type": "string"},
        "date": {"type": "string", "description": "YYYY-MM-DD"},
        "currency": {"type": "string", "description": "ISO code, e.g. CAD"},
        "summary": {"type": "string", "description": "3-6 words: what was bought"},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "amount": {"type": "number"},
                },
                "required": ["description", "amount"],
            },
        },
        "subtotal": {"type": "number", "description": "before tax"},
        "gst": {"type": "number", "description": "total of all GST/tax lines"},
        "total": {"type": "number", "description": "amount actually charged"},
        "payment_method": {"type": "string", "description": "e.g. VISA, cash"},
    },
    "required": ["merchant", "total"],
}

PROMPT = """You are reading a photo of a retail receipt. Extract the fields in the JSON schema.
Rules:
- Amounts are plain numbers in the receipt's currency: no symbols, no thousands separators.
- date is YYYY-MM-DD. If you cannot read it, omit it.
- gst is the sum of all GST/tax lines. If the receipt shows no tax, omit it.
- total is the final amount charged.
- If a field is not visible, OMIT it. Never guess or invent numbers.
Respond with JSON only."""

DEFAULT_CONFIG = {
    "currency": "CAD",
    "default_expense": "Expenses:Uncategorized",
    "default_payment": "Liabilities:CreditCard",
    "gst_account": "Assets:GST-Receivable",
    "merchants": {},
    "payment_methods": {},
}


# ----------------------------------------------------------------- helpers
def load_config(path: str | None) -> dict:
    cfg = {**DEFAULT_CONFIG, "merchants": {}, "payment_methods": {}}
    if path:
        with open(path, "rb") as fh:
            cfg.update(tomllib.load(fh))
    # case-insensitive matching
    cfg["merchants"] = {k.lower(): v for k, v in cfg["merchants"].items()}
    cfg["payment_methods"] = {k.lower(): v for k, v in cfg["payment_methods"].items()}
    return cfg


def to_dec(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        cleaned = str(value).replace("$", "").replace(",", "").strip()
        return Decimal(cleaned).quantize(CENT)
    except InvalidOperation:
        return None


def q(text) -> str:
    """Quote a string for Beancount."""
    clean = str(text).replace("\\", "").replace('"', "'").replace("\n", " ").strip()
    return f'"{clean}"'


def lookup(table: dict, text: str | None, default: str) -> str:
    low = (text or "").lower()
    for needle, account in table.items():
        if needle in low:
            return account
    return default


def parse_date(raw) -> tuple[date, str | None]:
    try:
        d = datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today(), "date not found or unreadable - used today's date"
    if d > date.today():
        return d, "date is in the future - check it"
    if (date.today() - d).days > 400:
        return d, "date is over a year old - check it"
    return d, None


# --------------------------------------------------------------- the model
def pdf_first_page(path: Path) -> bytes:
    """Render page 1 of a PDF (e.g. an online order receipt) to PNG using poppler's pdftoppm."""
    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / "page"
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-r",
                    "150",
                    "-png",
                    "-f",
                    "1",
                    "-l",
                    "1",
                    "-singlefile",
                    str(path),
                    str(stem),
                ],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError:
            raise RuntimeError("PDF support needs poppler-utils (the pdftoppm command)")
        return stem.with_suffix(".png").read_bytes()


def load_image_bytes(path: Path, max_side: int = 1600) -> bytes:
    """Read the image; shrink big phone photos if Pillow is installed."""
    if path.suffix.lower() == ".pdf":
        raw = pdf_first_page(path)
    else:
        raw = path.read_bytes()
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return raw
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def extract(image_path: Path, model: str) -> dict:
    import ollama  # imported lazily so --from-json works without it

    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": PROMPT,
                "images": [load_image_bytes(image_path)],
            }
        ],
        format=SCHEMA,  # constrains the output to our JSON schema
        options={"temperature": 0},
    )
    return json.loads(response["message"]["content"])


# ----------------------------------------------- plain-Python checking + output
def build_entry(data: dict, cfg: dict, source: str, sha: str, model: str):
    """Return (beancount_text, warnings). Raises ValueError if unusable."""
    warnings: list[str] = []

    total = to_dec(data.get("total"))
    if total is None:
        raise ValueError("no total found on the receipt")
    gst = to_dec(data.get("gst")) or Decimal("0.00")
    subtotal = to_dec(data.get("subtotal"))

    # Arithmetic is checked by code, not trusted from the model.
    if subtotal is not None and abs(subtotal + gst - total) > TOL:
        warnings.append(f"subtotal {subtotal} + GST {gst} != total {total}")
    if subtotal is None:
        subtotal = total - gst
    items = [to_dec(i.get("amount")) for i in data.get("line_items", [])]
    items = [i for i in items if i is not None]
    if items and abs(sum(items) - subtotal) > TOL:
        warnings.append(f"line items add to {sum(items)}, subtotal is {subtotal}")
    if gst and gst > subtotal * Decimal("0.055") + TOL:
        warnings.append(f"GST {gst} is more than 5% of {subtotal} - check it")

    when, date_warning = parse_date(data.get("date"))
    if date_warning:
        warnings.append(date_warning)

    merchant = data.get("merchant") or "Unknown merchant"
    expense = lookup(cfg["merchants"], merchant, cfg["default_expense"])
    if expense == cfg["default_expense"]:
        warnings.append("no category rule for this merchant")
    payment = lookup(
        cfg["payment_methods"], data.get("payment_method"), cfg["default_payment"]
    )
    cur = data.get("currency") or cfg["currency"]

    # The expense posting is total - GST, so the entry always balances.
    expense_amt = total - gst
    lines = [
        f"{when} ! {q(merchant)} {q(data.get('summary', ''))}",
        f"  receipt: {q(source)}",
        f"  receipt-sha: {q(sha)}",
        f"  scanned-by: {q(model)}",
        f"  {expense:<42}{expense_amt:>10} {cur}",
    ]
    if gst:
        lines.append(f"  {cfg['gst_account']:<42}{gst:>10} {cur}")
    lines.append(f"  {payment:<42}{-total:>10} {cur}")
    for w in warnings:
        lines.append(f"  ; REVIEW: {w}")
    return "\n".join(lines) + "\n", warnings


# --------------------------------------------------------------------- CLI
def collect(paths: list[str], exts: set[str]) -> list[Path]:
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in exts)
        elif p.exists():
            files.append(p)
        else:
            print(f"not found: {p}", file=sys.stderr)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Receipt photos -> staged Beancount entries"
    )
    ap.add_argument("paths", nargs="+", help="receipt images and/or folders of them")
    ap.add_argument("--config", help="rules.toml (accounts + merchant rules)")
    ap.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"Ollama model (default {DEFAULT_MODEL})"
    )
    ap.add_argument("--out", default="staging.bean", help="staging file to append to")
    ap.add_argument(
        "--dry-run", action="store_true", help="print entries, write nothing"
    )
    ap.add_argument(
        "--from-json",
        action="store_true",
        help="inputs are saved extraction .json files (testing, no model needed)",
    )
    args = ap.parse_args()

    cfg = load_config(args.config)
    out = Path(args.out)
    seen = out.read_text() if out.exists() else ""
    files = collect(args.paths, {".json"} if args.from_json else IMAGE_EXTS)
    if not files:
        print("No receipts found!", file=sys.stderr)
        return 1

    new_entries, skipped, failed = [], 0, 0
    for f in files:
        sha = hashlib.sha256(f.read_bytes()).hexdigest()[:12]
        if sha in seen:
            print(f"skip  {f.name} (already staged)")
            skipped += 1
            continue
        try:
            data = (
                json.loads(f.read_text()) if args.from_json else extract(f, args.model)
            )
            text, warnings = build_entry(
                data, cfg, f.name, sha, "from-json" if args.from_json else args.model
            )
        except Exception as exc:  # keep going; one bad receipt shouldn't stop the batch
            print(f"FAIL  {f.name}: {exc}", file=sys.stderr)
            failed += 1
            continue
        mark = "check" if warnings else "ok   "
        print(f"{mark} {f.name}: {data.get('merchant', '?')} {data.get('total', '?')}")
        for w in warnings:
            print(f"        - {w}")
        new_entries.append(text)
        seen += text

    if args.dry_run:
        print("\n" + "\n".join(new_entries))
    elif new_entries:
        with out.open("a") as fh:
            fh.write("\n".join(new_entries) + "\n")
        print(
            f"\nappended {len(new_entries)} entr{'y' if len(new_entries) == 1 else 'ies'} to {out}"
        )
    print(f"done: {len(new_entries)} new, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
