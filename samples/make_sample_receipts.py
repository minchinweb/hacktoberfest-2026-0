#!/usr/bin/env python3
"""Generate three FICTIONAL sample receipts (and their ground-truth JSON) for demos/tests.

    python samples/make_sample_receipts.py

Writes images to samples/receipts/ and the expected extraction to samples/expected/.
All merchants, names, addresses and tax numbers are made up.
"""

import json
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
IMG_DIR, EXP_DIR = HERE / "receipts", HERE / "expected"
IMG_DIR.mkdir(exist_ok=True)
EXP_DIR.mkdir(exist_ok=True)
FONTS = "/usr/share/fonts/truetype/dejavu/"


def font(size, bold=False, mono=False):
    name = (
        ("DejaVuSansMono" if mono else "DejaVuSans")
        + ("-Bold" if bold else "")
        + ".ttf"
    )
    return ImageFont.truetype(FONTS + name, size)


def photo_effect(img, angle, seed):
    """Make a flat render look like a quick phone photo on a table."""
    random.seed(seed)
    w, h = img.size
    bg = Image.new("RGB", (w + 240, h + 240), (92, 78, 66))
    bg.paste(img, (120, 120))
    bg = bg.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(92, 78, 66))
    # soft lighting gradient
    shade = Image.new("L", bg.size)
    sd = ImageDraw.Draw(shade)
    for y in range(bg.size[1]):
        sd.line([(0, y), (bg.size[0], y)], fill=int(255 - 70 * y / bg.size[1]))
    bg = Image.composite(bg, Image.new("RGB", bg.size, (0, 0, 0)), shade)
    bg = bg.filter(ImageFilter.GaussianBlur(0.8))
    noise = Image.effect_noise(bg.size, 14).convert("RGB")
    return Image.blend(bg, noise, 0.06)


# ------------------------------------------------ 1. print-shop order (document)
def print_order():
    W, H = 1275, 1500
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((90, 70), "maple print", font=font(64, True), fill=(30, 120, 60))
    d.text((92, 150), "& office", font=font(30), fill=(90, 90, 90))
    d.text((820, 120), "Order #: kx4m7q", font=font(40, True), fill=(30, 120, 60))
    meta = [
        ("Order Date:", "2026-10-01"),
        ("Time:", "14:07:52"),
        ("Authorization", "07A1QX"),
        ("Card Name:", "MasterCard"),
        ("Order #:", "kx4m7q"),
        ("Type:", "Sale"),
        ("Preferred Store Location:", "#204"),
    ]
    y = 230
    for k, v in meta:
        d.text((90, y), k, font=font(22, True), fill="black")
        d.text((460, y), v, font=font(22), fill="black")
        y += 32
    cols = [
        (
            90,
            "Client Information:",
            ["Sample, Jane", "100 Example Ave NW", "Edmonton, AB", "Canada, T5A0A1"],
        ),
        (
            470,
            "Billing Address:",
            ["Sample, Jane", "100 Example Ave NW", "Edmonton, AB", "Canada, T5A0A1"],
        ),
        (
            850,
            "Store Pickup Location:",
            [
                "Maple Print - Southgate",
                "1 Sample Rd.",
                "Edmonton, AB",
                "T6H 0A0, Canada",
            ],
        ),
    ]
    for x, title, rows in cols:
        d.text((x, 520), title, font=font(22, True), fill="black")
        for i, r in enumerate(rows):
            d.text((x, 556 + 30 * i), r, font=font(22), fill="black")
    d.text((90, 720), "Order Details", font=font(24, True), fill=(70, 70, 70))
    heads = [
        (90, "Qty"),
        (170, "Product/Sku"),
        (720, "Delivery"),
        (860, "Unit Price"),
        (1010, "Price"),
        (1130, "Taxes"),
    ]
    for x, t in heads:
        d.text((x, 765), t, font=font(22), fill="black")
    blocks = [
        ("1", "Service & Handling", "400000000001", "$1.99", "$1.99", None),
        (
            "30",
            "Colour (Letter) 10-99",
            "400000000002",
            "$0.59",
            "$17.70",
            "2026.10 flyer English.pdf",
        ),
        (
            "1",
            "COLOURLEDGER1-9",
            "400000000003",
            "$0.99",
            "$0.99",
            "2026.10 poster.pdf",
        ),
        (
            "30",
            "Colour (Letter) 10-99",
            "400000000002",
            "$0.59",
            "$17.70",
            "2026.10 flyer Francais.pdf",
        ),
        (
            "30",
            "Colour (Letter) 10-99",
            "400000000002",
            "$0.59",
            "$17.70",
            "2026.10 handout.pdf",
        ),
    ]
    y = 820
    for qty, name, sku, unit, price, filename in blocks:
        d.text((90, y), qty, font=font(22), fill="black")
        d.text((170, y), name, font=font(22), fill="black")
        d.text((170, y + 28), sku, font=font(20), fill=(60, 60, 60))
        d.text((720, y), "pickup in AB", font=font(20), fill="black")
        d.text((860, y), unit, font=font(22), fill="black")
        d.text((1010, y), price, font=font(22), fill="black")
        d.text((1130, y), "GST", font=font(22), fill="black")
        if filename:
            d.text(
                (170, y + 62), f'8.5" x 11" - {filename}', font=font(20), fill="black"
            )
        y += 110 if filename else 80
        d.line([(90, y - 14), (1180, y - 14)], fill=(150, 150, 150), width=2)
    y += 30
    d.line([(90, y), (1180, y)], fill=(70, 110, 190), width=3)
    d.text(
        (90, y + 20),
        "All prices listed here are in CAD Dollars",
        font=font(20),
        fill="black",
    )
    d.text((90, y + 46), "GST/HST No. 123456789 RT0001", font=font(20), fill="black")
    for i, (k, v) in enumerate(
        [("Subtotal:", "$56.08"), ("GST (5%):", "$2.80"), ("Total:", "$58.88")]
    ):
        d.text((760, y + 20 + 34 * i), k, font=font(24), fill="black")
        d.text((1060, y + 20 + 34 * i), v, font=font(24, True), fill="black")
    img.convert("RGB").save(IMG_DIR / "01_maple_print_order.jpg", quality=92)
    return {
        "merchant": "Maple Print & Office",
        "date": "2026-10-01",
        "currency": "CAD",
        "summary": "Colour printing",
        "subtotal": 56.08,
        "gst": 2.80,
        "total": 58.88,
        "payment_method": "MasterCard",
    }


# ------------------------------------------------ 2. thermal till receipt (phone photo)
def till_receipt(
    name,
    filename,
    header,
    date_line,
    items,
    subtotal,
    gst,
    total,
    payment,
    extra=None,
    angle=0,
    seed=1,
):
    W = 600
    H = 520 + 44 * len(items) + (60 if extra else 0)
    img = Image.new("RGB", (W, H), (250, 249, 245))
    d = ImageDraw.Draw(img)
    f, fb = font(26, mono=True), font(26, True, True)
    y = 30
    for line in header:
        d.text(
            (W // 2, y),
            line,
            font=fb if line == header[0] else f,
            fill=(25, 25, 25),
            anchor="ma",
        )
        y += 36
    y += 10
    d.text((30, y), date_line, font=f, fill=(25, 25, 25))
    y += 50
    d.text((30, y), "-" * 32, font=f, fill=(25, 25, 25))
    y += 40
    for desc, amt in items:
        d.text((30, y), desc, font=f, fill=(25, 25, 25))
        d.text((W - 30, y), f"{amt:.2f}", font=f, fill=(25, 25, 25), anchor="ra")
        y += 44
    d.text((30, y), "-" * 32, font=f, fill=(25, 25, 25))
    y += 40
    rows = (
        [("SUBTOTAL", subtotal), ("GST 5%", gst)]
        + ([extra] if extra else [])
        + [("TOTAL", total)]
    )
    for label, amt in rows:
        ff = fb if label == "TOTAL" else f
        d.text((30, y), label, font=ff, fill=(25, 25, 25))
        d.text((W - 30, y), f"{amt:.2f}", font=ff, fill=(25, 25, 25), anchor="ra")
        y += 44
    y += 14
    d.text((30, y), payment, font=f, fill=(25, 25, 25))
    d.text((W // 2, y + 56), "THANK YOU!", font=f, fill=(25, 25, 25), anchor="ma")
    photo_effect(img, angle, seed).convert("RGB").save(IMG_DIR / filename, quality=88)


def main():
    exp = {"01_maple_print_order": print_order()}

    till_receipt(
        "hardware",
        "02_prairie_hardware_photo.jpg",
        ["PRAIRIE HARDWARE", "456 Sample Blvd", "Edmonton AB", "GST# 987654321 RT0001"],
        "2026-10-02  16:41",
        [("SCREWS #8 BOX", 6.49), ("DUCT TAPE", 8.99), ("WORK GLOVES", 14.99)],
        30.47,
        1.52,
        31.99,
        "VISA CREDIT  APPROVED",
        angle=2.5,
        seed=2,
    )
    exp["02_prairie_hardware_photo"] = {
        "merchant": "Prairie Hardware",
        "date": "2026-10-02",
        "currency": "CAD",
        "summary": "Screws, tape, gloves",
        "subtotal": 30.47,
        "gst": 1.52,
        "total": 31.99,
        "payment_method": "VISA",
    }

    # A tip makes subtotal + GST != total: the checker should flag it for review.
    till_receipt(
        "cafe",
        "03_corner_cafe_tip_photo.jpg",
        ["CORNER CAFE", "789 Example St", "Edmonton AB"],
        "2026-10-03  08:15",
        [("LATTE", 5.25), ("BREAKFAST WRAP", 9.75), ("MUFFIN", 3.50)],
        18.50,
        0.93,
        21.43,
        "VISA CREDIT  APPROVED",
        extra=("TIP", 2.00),
        angle=-3.0,
        seed=3,
    )
    exp["03_corner_cafe_tip_photo"] = {
        "merchant": "Corner Cafe",
        "date": "2026-10-03",
        "currency": "CAD",
        "summary": "Coffee and breakfast",
        "subtotal": 18.50,
        "gst": 0.93,
        "total": 21.43,
        "payment_method": "VISA",
    }

    for stem, data in exp.items():
        (EXP_DIR / f"{stem}.json").write_text(json.dumps(data, indent=2) + "\n")
    print("wrote", len(exp), "receipts to", IMG_DIR)


if __name__ == "__main__":
    main()
