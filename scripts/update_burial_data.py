#!/usr/bin/env python3
"""Rebuild the burial-plot availability data in App.jsx from a company floor-plan PDF.

    python3 scripts/update_burial_data.py "Burial Floor Plan (04092026).pdf"
    python3 scripts/update_burial_data.py plan.pdf --check   # parse + validate only

Same provenance as the niche plans: native Excel -> PDF exports, so the text and
each cell's fill colour are readable directly, no OCR. Yellow = sold, white / no
fill = available, a `*` in front of the code = Reserve Unit, and anything else the
sheet shades is a category colour that hides the real status.

The burial sheets are laid out far more simply than the niche ones -- one zone per
page, one flat row of plots per row label -- so this parser is correspondingly
shorter. The fussy parts are noted where they are; each exists because the sheets
broke a simpler version of it.

Requires: pip install pymupdf
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

import fitz  # pymupdf

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "App.jsx"

# Plot codes are <zone>-<row>-<plot>. Chinese numbering skips 4 and 5, so "A" and
# "B" stand in for them and turn up in every segment: rows run 1,2,3,3A,3B,6.. and
# plots run 18,28,38,A8,B8,68..208, plus a few suffixed variants (18A, A8A, A08).
CODE_RE = re.compile(r"^([A-Z]{1,3})-(\d{1,2}[AB]?)-([0-9AB]{1,4}[A-Z]?)$")
ROW_RE = re.compile(r"^(\d{1,2}[AB]?)$")
# Most pages are headed "Zone <code>"; the Imperial Zone names itself instead and
# takes its code from the IZ- plot prefix like every other page does.
ZONE_RE = re.compile(r"\bZone\s+([A-Z]{1,3})\b|\b(Imperial)\s+Zone\b")
UPDATED_RE = re.compile(r"Updated\s*:?\s*(\d{2}\.\d{2}\.\d{4})")

STATUS_LETTER = {"available": "A", "sold": "S", "reserved": "R", "special": "X"}

# The DB page carries a second, differently-sized product in its row 13: the plots
# there are coded DBS- and priced separately, so the app keeps them as their own
# zone rather than mixing two sizes under one heading.
PREFIX_TO_ZONE = {"DBS": "DB13"}
ZONE_ORDER = ["B", "CA", "CB", "DA", "DB", "DB13", "IZ"]


def classify(fill):
    """Map a plot's fill colour to a status, using the sheets' own palette."""
    if fill is None:
        return "available"          # no fill drawn = plain white cell
    fill = tuple(round(c, 2) for c in fill)
    return {
        (1.0, 1.0, 0.0): "sold",
        (1.0, 1.0, 1.0): "available",
    }.get(fill, "special")           # anything else is a category shade, status unknown


def cell_fill(drawings, bbox):
    """Fill colour painted under a plot's code, or None if the cell is bare.

    Two things to know about these sheets. Fills are drawn as *runs* -- one wide
    rectangle covering a whole stretch of sold plots -- so a cell is classified by
    whatever rectangle its text sits inside, not by a rectangle of its own. And the
    row rules are themselves filled rectangles, just flattened to a fraction of a
    point high; those have to be skipped or every plot next to a rule reads black.
    """
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    found = None
    for d in drawings:
        r = d.get("rect")
        if not r or d.get("fill") is None:
            continue
        if r.y1 - r.y0 < 2 or r.x1 - r.x0 < 2:
            continue                 # a rule or a hairline, not a cell
        if r.x0 - 0.5 <= cx <= r.x1 + 0.5 and r.y0 - 0.5 <= cy <= r.y1 + 0.5:
            found = d["fill"]        # later drawings paint over earlier ones
    return found


def parse(pdf_path):
    """Read every plot on every page as {zone, row, code, status, x}."""
    doc = fitz.open(pdf_path)
    out = []
    updated = None
    page_zones = []

    for pno in range(len(doc)):
        page = doc[pno]
        drawings = page.get_drawings()
        words = page.get_text("words")
        text = page.get_text("text")

        if updated is None:
            m = UPDATED_RE.search(text)
            if m:
                updated = m.group(1)
        m = ZONE_RE.search(text)
        page_zones.append((m.group(1) or m.group(2)) if m else None)

        # Row labels sit alone in the left margin. Everything else on that line is
        # a plot code, so the margin cut-off is what separates the two -- a plot's
        # code is never that far left on any of these sheets.
        labels = sorted(
            (w[1], w[3], w[4]) for w in words if ROW_RE.match(w[4]) and w[0] < 70
        )
        if not labels:
            continue

        # A `*` marks a Reserve Unit. It is usually its own word sitting immediately
        # to the left of the code, but the exporter sometimes glues it on instead
        # (*DA-13-118), so both forms have to be recognised.
        stars = [w for w in words if w[4] == "*"]

        codes = []
        for w in words:
            txt = w[4]
            starred = txt.startswith("*") and len(txt) > 1
            if starred:
                txt = txt[1:]
            m = CODE_RE.match(txt)
            if m:
                codes.append((w, m, starred))

        for w, m, glued in codes:
            prefix, row_seg, _plot = m.groups()
            ycen = (w[1] + w[3]) / 2
            # Rows are staggered across the page and the row label sits a couple of
            # points below its own line of codes, so a plot belongs to whichever
            # label is closest vertically -- not to a fixed y band.
            row = min(labels, key=lambda l: abs((l[0] + l[1]) / 2 - ycen))[2]
            starred = glued or any(
                abs((s[1] + s[3]) / 2 - ycen) < 3 and 0 <= w[0] - s[2] <= 3
                for s in stars
            )
            status = "reserved" if starred else classify(cell_fill(drawings, w[:4]))
            out.append({
                "zone": PREFIX_TO_ZONE.get(prefix, prefix),
                "row": row,
                "code": f"{prefix}-{row_seg}-{_plot}",
                "status": status,
                "page": pno,
                "x": round(w[0], 1),
                "y": round(w[1], 1),
            })

    return out, updated, page_zones


def build_zones(rows):
    """Group plots into {zone: [{row, cells:[{c,s}]}]}, keeping the printed order.

    Rows come out top-to-bottom as the sheet draws them and plots left-to-right,
    which is how an agent reads the paper plan. Note this is not numeric order:
    Zone B prints 1A and 1B above 1, and the Imperial Zone prints its rows the
    other way up entirely.
    """
    zones = {}
    for r in rows:
        zones.setdefault(r["zone"], {}).setdefault(r["row"], []).append(r)

    out = {}
    for zone in sorted(zones, key=lambda z: (ZONE_ORDER.index(z) if z in ZONE_ORDER else 99, z)):
        # Order rows by where the sheet puts them: topmost plot line first.
        row_keys = sorted(zones[zone], key=lambda k: min(c["y"] for c in zones[zone][k]))
        out[zone] = [{
            "row": k,
            "cells": [{"c": c["code"], "s": STATUS_LETTER[c["status"]]}
                      for c in sorted(zones[zone][k], key=lambda c: c["x"])],
        } for k in row_keys]
    return out


def validate(rows, zones, page_zones):
    """Split real parse failures from quirks the sheet itself contains."""
    problems, warnings = [], []

    if not rows:
        problems.append("no plots parsed at all — the sheet layout probably changed")

    for pno, z in enumerate(page_zones):
        if z is None:
            warnings.append(f"page {pno}: no 'Zone X' heading found")

    # A duplicated code inside one zone means rows were mis-assigned; that is a
    # parser failure, not something the sheets do.
    for zone, zrows in zones.items():
        seen = {}
        for zr in zrows:
            for cell in zr["cells"]:
                if cell["c"] in seen:
                    problems.append(
                        f"{zone}: code {cell['c']} appears in both row {seen[cell['c']]} "
                        f"and row {zr['row']} — rows were mis-assigned")
                seen[cell["c"]] = zr["row"]

    # Every plot's code carries its own row; if that disagrees with the row it was
    # filed under, the nearest-label match picked the wrong line.
    for zone, zrows in zones.items():
        for zr in zrows:
            for cell in zr["cells"]:
                m = CODE_RE.match(cell["c"])
                if m and m.group(2) != zr["row"]:
                    problems.append(
                        f"{zone}: {cell['c']} was filed under row {zr['row']} "
                        f"but its code says row {m.group(2)}")

    for zone, zrows in zones.items():
        for zr in zrows:
            if not zr["cells"]:
                problems.append(f"{zone} row {zr['row']}: no plots")

    unknown = [r for r in rows if r["status"] == "special"]
    if unknown:
        by_zone = collections.Counter(r["zone"] for r in unknown)
        warnings.append(
            f"{len(unknown)} plot(s) sit under a category colour, so available/sold "
            f"can't be read from the sheet — marked 待确认: {dict(by_zone)}")

    return problems, warnings


def patch_app(zones, updated):
    src = APP.read_text(encoding="utf-8")
    m = re.search(r"const BURIAL_STATUS = \{.*?\};\n", src, re.S)
    if not m:
        sys.exit("could not find BURIAL_STATUS in App.jsx")
    src = src[:m.start()] + "const BURIAL_STATUS = " + \
        json.dumps(zones, ensure_ascii=False, separators=(",", ":")) + ";\n" + src[m.end():]

    if updated:
        src = re.sub(r'const BURIAL_STATUS_UPDATED = "[^"]*";',
                     f'const BURIAL_STATUS_UPDATED = "{updated}";', src)
    APP.write_text(src, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--check", action="store_true", help="parse and validate without writing App.jsx")
    args = ap.parse_args()

    rows, updated, page_zones = parse(args.pdf)
    zones = build_zones(rows)
    problems, warnings = validate(rows, zones, page_zones)

    counts = collections.Counter(r["status"] for r in rows)
    print(f"sheet date : {updated or '(not found)'}")
    print(f"plots      : {len(rows)}   available: {counts['available']}   "
          f"sold: {counts['sold']}   reserved: {counts['reserved']}   待确认: {counts['special']}")
    for zone, zrows in zones.items():
        n = sum(len(zr["cells"]) for zr in zrows)
        avail = sum(1 for zr in zrows for c in zr["cells"] if c["s"] == "A")
        print(f"  {zone:<5} rows {len(zrows):>2}  plots {n:>4}  available {avail:>4}")

    if problems:
        print(f"\nFAILED — {len(problems)} problem(s); App.jsx NOT modified:")
        for p in problems[:20]:
            print("  -", p)
        sys.exit(1)
    print("validation : OK" + (f" ({len(warnings)} warning(s))" if warnings else ""))
    for w in warnings[:10]:
        print("  ! ", w)

    if args.check:
        print("(--check: App.jsx not modified)")
        return
    patch_app(zones, updated)
    print(f"wrote      : {APP}")
    print("\nnext: npm run build && npm run deploy")


if __name__ == "__main__":
    main()
