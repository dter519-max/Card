#!/usr/bin/env python3
"""Rebuild the niche availability data in App.jsx from a company floor-plan PDF.

    python3 scripts/update_niche_data.py "Niche Floor Plan (04092026).pdf"
    python3 scripts/update_niche_data.py plan.pdf --check   # parse + validate only

The company's floor plans are native Excel -> PDF exports, so both the text and
each cell's fill colour can be read directly; no OCR, no guessing. Fill colour is
the status: yellow = sold, white / no fill = available, and the sheets' own
category shades for the rest.

Everything below that looks fussy is load-bearing. Each rule is here because the
sheets broke a simpler version of it, and the validation at the end exists so a
future run fails loudly instead of shipping quietly-wrong inventory.

Requires: pip install pymupdf
"""
import argparse
import collections
import json
import re
import statistics
import sys
from pathlib import Path

import fitz  # pymupdf

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "App.jsx"

LEVEL_RE = re.compile(r"^(10|[1-9]|3A|3B)$")
WING_HDR_RE = re.compile(r"^([A-Z])(\d{1,2})([RFL]|S)$")
CODE_PLAIN = re.compile(r"^(3A|3B|\d{2})(\d{2})(-\d[A-Z])?$")
CODE_HYPH = re.compile(r"^(3A|3B|\d{2})-(\d{2,4})$")
UPDATED_RE = re.compile(r"Updated\s*:?\s*(\d{2}\.\d{2}\.\d{4})")

STATUS_LETTER = {"available": "A", "sold": "S", "reserved": "R", "special": "X", "unavailable": "U"}
# R and L walls share a price tier; the pricing lookup keys off this coarser side.
WING_TO_SIDE = {"R": "RL", "L": "RL", "F": "F", "S": "S", "SEC": "SEC"}
BLOCK_ORDER = ["A", "B", "C", "D", "E", "F", "G", "K", "L", "M", "N", "P"]


def classify(fill):
    """Map a cell's fill colour to a status, using the sheets' own palette."""
    if fill is None:
        return "available"          # no fill drawn = plain white cell
    fill = tuple(round(c, 2) for c in fill)
    return {
        (1.0, 1.0, 0.0): "sold",
        (1.0, 1.0, 1.0): "available",
        (0.91, 0.9, 0.9): "unavailable",
    }.get(fill, "special")           # anything else is a category shade, status unknown


def cell_fill(drawings, bbox):
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    found = None
    for d in drawings:
        r = d.get("rect")
        if r and r.x0 - 0.5 <= cx <= r.x1 + 0.5 and r.y0 - 0.5 <= cy <= r.y1 + 0.5:
            if d.get("fill") is not None:
                found = d["fill"]
    return found


def parse(pdf_path):
    doc = fitz.open(pdf_path)
    out = []
    updated = None
    # Block/hall/section carry ACROSS pages: continuation pages don't repeat the header.
    block = hallnum = section = mode = None

    for pno in range(len(doc)):
        page = doc[pno]
        drawings = page.get_drawings()
        words = page.get_text("words")

        if updated is None:
            m = UPDATED_RE.search(page.get_text())
            if m:
                updated = m.group(1)

        # Group words into rows by CLUSTERING y, never by snapping to a fixed grid.
        # Cells in one visual row carry sub-pixel jitter (322.7 vs 323.1); a fixed
        # band boundary can fall between them, and the strays then sort after the NEXT
        # section's row label and get collected into that section instead.
        ys = sorted({w[1] for w in words})
        band_of, start = {}, None
        for y in ys:
            if start is None or y - start > 2.5:
                start = y
            band_of[y] = start
        bands = {y: i for i, y in enumerate(sorted(set(band_of.values())))}
        rowband = lambda w: bands[band_of[w[1]]]
        ws = sorted(words, key=lambda w: (rowband(w), w[0]))
        n = len(ws)

        anchors = []      # (x, hallcode, side, wing) for the header row being read
        pending = []      # headers seen, waiting to be paired with their "LEVEL" token
        last_area_y = last_level_y = None

        i = 0
        while i < n:
            w = ws[i]
            txt = w[4]

            if txt == "BLOCK":
                if i + 1 < n and re.match(r"^([A-Z])$", ws[i + 1][4]):
                    block = ws[i + 1][4]
                hallnum = mode = section = None
                anchors, pending = [], []
                i += 1
                continue

            # Ground/First-Floor pages glue the block letter onto the Chinese name
            # ("K（聖寶院）-") and can put it on a different line from the word "BLOCK",
            # so reading "the word after BLOCK" grabs "GROUND" and yields block G.
            glued = re.match(r"^([ABCDEFGKLMNP])[（(]", txt)
            if glued:
                block = glued.group(1)
                hallnum = mode = section = None
                anchors, pending = [], []
                i += 1
                continue

            if txt == "HALL" and i + 1 < n and re.match(r"^\d+$", ws[i + 1][4]):
                hallnum, mode = ws[i + 1][4], "wing"
                anchors, pending = [], []
                i += 1
                continue

            if txt == "Area":
                # Block L puts two sections side by side under one header line, so
                # "Area" recurs within a group. Only reset on a genuinely new group,
                # i.e. one sitting meaningfully lower on the page.
                if last_area_y is None or w[1] - last_area_y > 5:
                    anchors, pending = [], []
                last_area_y, mode = w[1], "section"
                i += 1
                continue

            if txt == "Section":
                j = i + 1
                while j < n and ws[j][4] == "-":
                    j += 1
                if j < n:
                    m = re.match(r"^([A-Z]?\d+)$", ws[j][4])
                    if m:
                        hc = m.group(1)
                        pending.append({"hallcode": ("A" + hc) if hc[0].isdigit() else hc, "wing": "SEC"})
                i = j + 1
                continue

            mw = WING_HDR_RE.match(txt)
            if mw and mode == "wing":
                bl, hn, wg = mw.groups()
                pending.append({"hallcode": f"{bl}{hn}", "wing": wg})
                i += 1
                continue

            if txt == "LEVEL":
                # Walls SIDE BY SIDE share a header row and must accumulate together.
                # Walls STACKED down the page (Block N puts N1L/N1S below N1R/N1F) begin
                # a fresh one — keeping the anchors above lets a stale anchor win the
                # nearest-x match and swallow the wall beneath it.
                if last_level_y is not None and w[1] - last_level_y > 5:
                    anchors = []
                last_level_y = w[1]
                if pending:
                    a = pending.pop(0)
                    anchors.append((w[0], a["hallcode"], WING_TO_SIDE[a["wing"]], a["wing"]))
                i += 1
                continue

            if LEVEL_RE.match(txt) and anchors:
                level, x0, myband = txt, w[0], rowband(w)
                j, collected = i + 1, []
                while j < n:
                    w2 = ws[j]
                    if rowband(w2) != myband:
                        break
                    if LEVEL_RE.match(w2[4]):
                        break   # next wall's row label on this same row
                    if CODE_PLAIN.match(w2[4]) or CODE_HYPH.match(w2[4]):
                        collected.append(w2)
                    j += 1
                if collected:
                    hallcode, side, wing = min(anchors, key=lambda a: abs(a[0] - x0))[1:]
                    for cw in collected:
                        out.append({
                            "block": block, "hallcode": hallcode, "side": side, "wing": wing,
                            "level": level, "code": cw[4],
                            "status": classify(cell_fill(drawings, cw[:4])),
                            "page": pno, "x": round(cw[0], 1), "y": round(cw[1], 1),
                        })
                i = j
                continue
            i += 1

    return out, updated


def build_faces(rows):
    """Snap each wall's cells onto a shared column grid.

    The sheets leave blank slots mid-wall to keep the two halves aligned. Rendering
    cells end-to-end collapses those, shifting every code after the gap out of place,
    so cells are placed by column index and a missing column stays missing.
    """
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r["block"], r["hallcode"], r["wing"])].append(r)

    tree, pos, collisions = {}, {}, 0
    for (block, hall, wing), items in groups.items():
        by_level = collections.defaultdict(list)
        for it in items:
            by_level[it["level"]].append(it)
        deltas = []
        for cs in by_level.values():
            cs.sort(key=lambda c: c["x"])
            deltas += [cs[i + 1]["x"] - cs[i]["x"] for i in range(len(cs) - 1)]
        pitch = statistics.median(deltas) if deltas else 1.0
        minx = min(it["x"] for it in items)
        ncols = max(round((it["x"] - minx) / pitch) for it in items) + 1
        lvl_y = {lv: sum(c["y"] for c in cs) / len(cs) for lv, cs in by_level.items()}

        out_rows = []
        for lv in sorted(by_level, key=lambda l: lvl_y[l]):
            slots = [None] * ncols
            for c in sorted(by_level[lv], key=lambda c: c["x"]):
                idx = round((c["x"] - minx) / pitch)
                if slots[idx] is not None:
                    collisions += 1
                slots[idx] = {"c": c["code"], "s": STATUS_LETTER[c["status"]]}
            out_rows.append({"level": lv, "cells": slots})

        tree.setdefault(block, {}).setdefault(hall, []).append({"w": wing, "rows": out_rows})
        pos[(block, hall, wing)] = (min(i["page"] for i in items),
                                    min(i["y"] for i in items), min(i["x"] for i in items))

    def hkey(h):
        m = re.match(r"^([A-Z]*)(\d+)([A-Z]*)$", h)
        return (m.group(1), int(m.group(2)), m.group(3)) if m else (h,)

    ordered = {b: {h: sorted(tree[b][h], key=lambda f: pos[(b, h, f["w"])])
                   for h in sorted(tree[b], key=hkey)}
               for b in BLOCK_ORDER if b in tree}
    return ordered, collisions


def build_avail(rows):
    def lk(lv):
        m = re.match(r"^(\d+)([A-Z]*)$", lv)
        return (-int(m.group(1)), m.group(2)) if m else (999, lv)
    a = sorted((r for r in rows if r["status"] == "available"),
               key=lambda r: (r["block"], r["hallcode"], lk(r["level"]), r["code"]))
    return [[r["block"], r["hallcode"], r["side"], r["level"], r["code"]] for r in a]


def validate(rows, faces, collisions):
    """Separate our own corruption from the sheets' quirks.

    Returns (problems, warnings). A problem means the parse went wrong and the data
    must not be shipped. A warning means the source sheet itself is odd — reported
    so someone can check with the office, but preserved as drawn rather than
    "corrected" into something the sheet doesn't say.
    """
    problems, warnings = [], []
    if collisions:
        problems.append(f"{collisions} cells collided when snapping to the column grid")
    if not rows:
        problems.append("no cells parsed at all")

    for b in faces:
        for h in faces[b]:
            seen = {}
            for f in faces[b][h]:
                if len({len(r["cells"]) for r in f["rows"]}) > 1:
                    problems.append(f"{b}/{h}/{f['w']}: rows have differing widths")
                codes = [c["c"] for r in f["rows"] for c in r["cells"] if c]
                # Twice on ONE wall means we merged rows that belong to different walls.
                if len(codes) != len(set(codes)):
                    problems.append(f"{b}/{h}/{f['w']}: duplicate codes within one wall")
                # Once on each of TWO walls is the sheet repeating a number (a typo in
                # the numbering, e.g. D/D1 prints 0120 twice with 0121 absent).
                for c in codes:
                    if c in seen and seen[c] != f["w"]:
                        warnings.append(f"{b}/{h}: code {c} printed on both wall {seen[c]} and wall {f['w']} — check with the office")
                    seen[c] = f["w"]
    return problems, warnings


def patch_app(faces, avail, updated):
    src = APP.read_text(encoding="utf-8")
    m = re.search(r"const AVAIL_RAW = \n\[.*?\];\n", src, re.S)
    if not m:
        sys.exit("could not find AVAIL_RAW in App.jsx")
    body = "[" + ",".join(json.dumps(a, ensure_ascii=False, separators=(",", ":")) for a in avail) + "]"
    src = src[:m.start()] + "const AVAIL_RAW = \n" + body + ";\n" + src[m.end():]

    m = re.search(r"const NICHE_STATUS = \{.*?\};\n", src, re.S)
    if not m:
        sys.exit("could not find NICHE_STATUS in App.jsx")
    src = src[:m.start()] + "const NICHE_STATUS = " + \
        json.dumps(faces, ensure_ascii=False, separators=(",", ":")) + ";\n" + src[m.end():]

    if updated:
        src = re.sub(r'const NICHE_STATUS_UPDATED = "[^"]*";',
                     f'const NICHE_STATUS_UPDATED = "{updated}";', src)
    APP.write_text(src, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--check", action="store_true", help="parse and validate without writing App.jsx")
    args = ap.parse_args()

    rows, updated = parse(args.pdf)
    faces, collisions = build_faces(rows)
    avail = build_avail(rows)
    problems, warnings = validate(rows, faces, collisions)

    by_block = collections.Counter(r["block"] for r in rows)
    print(f"sheet date : {updated or '(not found)'}")
    print(f"cells      : {len(rows)}   available: {len(avail)}")
    print(f"blocks     : {dict(sorted(by_block.items()))}")
    blanks = sum(1 for b in faces for h in faces[b] for f in faces[b][h]
                 for r in f["rows"] for c in r["cells"] if c is None)
    print(f"blank slots: {blanks}")

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
    patch_app(faces, avail, updated)
    print(f"wrote      : {APP}")
    print("\nnext: npm run build && npm run deploy")


if __name__ == "__main__":
    main()
