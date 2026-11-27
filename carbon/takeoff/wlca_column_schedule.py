#! python3
# r: pymupdf
"""
WLCA column schedule reader  v0.1  (draft for review)
Office WLCA template - column sections by level from the structural engineer's PDF (D23)

Drafted by an AI agent (Claude) - review before trusting.

Reads a column schedule table from a VECTOR PDF (text, not a scan): a column of level labels on the left
("Level 36", "Roof", "Ground", "B1", "L02" ...) and column sizes in the cells to the right ("450x1400",
"D600"; "-" = no column of that type). Each row of sizes sits between two level lines, and belongs to the
level line just below it (the floor the column stands on): sizes between "Roof" and "Level 36" are level 36's.
Rows with no level label below them are ignored.

Levels with the same sizes, next to each other, are grouped into bands for step 4 (Column sections):
[{"from": "00", "to": "01", "sizes": "450x1100, 450x1700, ..."}]. The sizes in a band are averaged in the
take-off, one per column type (no count of columns per type is read).

Run in Rhino 8 (Python 3, installs pymupdf), or any Python 3:  python wlca_column_schedule.py file.pdf
"""
import json
import re
import sys

SIZE = re.compile(r"^(\d{2,4}(?:\.\d+)?)\s*[xX×]\s*(\d{2,4}(?:\.\d+)?)$")
DIA = re.compile(r"^(?:[dD]|Ø|ø|⌀)\s*(\d{2,4})$|^(\d{2,4})\s*(?:Ø|ø|⌀|dia\.?)$")
NONE = {"-", "–", "—", "n/a", "N/A"}
NAMED = {"roof": "Roof", "ground": "00", "gf": "00", "mezzanine": "Mezzanine", "mezz": "Mezzanine", "podium": "Podium",
         "basement": "B1", "lg": "LG", "ug": "UG", "lgf": "LG", "ugf": "UG"}
LEVEL_WORD = {"level", "lvl", "floor", "storey"}


def _size(text):
    """'450x1400' -> '450x1400', 'D600' -> 'D600', '-' -> '', else None."""
    t = text.strip().replace(" ", "")
    if t in NONE:
        return ""
    m = SIZE.match(t)
    if m:
        a, b = sorted((float(m.group(1)), float(m.group(2))))
        return "%gx%g" % (a, b)
    m = DIA.match(t)
    if m:
        return "D%s" % (m.group(1) or m.group(2))
    return None


def _label(words, i):
    """Level label starting at words[i] ('Level 36', 'Roof', 'L02', 'B1') -> (name, words used) or None."""
    w = words[i][4].strip().rstrip(":")
    low = w.lower()
    if low in LEVEL_WORD and i + 1 < len(words):
        nxt = words[i + 1]
        same_line = abs(nxt[1] - words[i][1]) < 2 and 0 <= nxt[0] - words[i][2] < 20
        if same_line and re.fullmatch(r"-?\d{1,3}|[A-Za-z]{1,3}\d{0,2}", nxt[4].strip()):
            return nxt[4].strip(), 2
        return None
    if low in NAMED:
        return NAMED[low], 1
    if re.fullmatch(r"[Ll]\d{1,3}", w):
        return w[1:], 1
    if re.fullmatch(r"[Bb]\d", w):
        return w.upper(), 1
    return None


def parse_words(words):
    """Words (x0, y0, x1, y1, text, ...) of one page -> {"levels": [{"level", "sizes"}] top -> bottom, "types": n} or None
    when the page holds no column schedule (fewer than 3 level rows with sizes)."""
    words = sorted(words, key=lambda w: (round(w[1], 0), w[0]))
    labels = []
    for i in range(len(words)):
        lab = _label(words, i)
        if lab:
            w = words[i]
            labels.append((w[0], (w[1] + w[3]) / 2.0, w[2], lab[0]))
    if len(labels) < 3:
        return None
    # the level column: the left edge most labels share (title blocks and notes carry stray "Level" words)
    xs = {}
    for x, _, _, _ in labels:
        xs[round(x / 5.0)] = xs.get(round(x / 5.0), 0) + 1
    col = max(xs, key=xs.get)
    labels = sorted([l for l in labels if abs(round(l[0] / 5.0) - col) <= 1], key=lambda l: l[1])
    if len(labels) < 3:
        return None
    right = max(l[2] for l in labels)
    pitch = sorted(b[1] - a[1] for a, b in zip(labels, labels[1:]))[len(labels) // 2 - 1] or 12.0
    top, bottom = labels[0][1] - 1.5 * pitch, labels[-1][1] + 0.5 * pitch
    # merge "450 x 1400" written as three words on one line
    cells = []
    i = 0
    while i < len(words):
        w = words[i]
        t = w[4]
        if i + 2 < len(words) and words[i + 1][4].strip() in ("x", "X", "×") and abs(words[i + 2][1] - w[1]) < 2:
            s3 = _size(t + "x" + words[i + 2][4])
            if s3:
                cells.append((w[0], (w[1] + w[3]) / 2.0, s3))
                i += 3
                continue
        s = _size(t)
        if s is not None:
            cells.append((w[0], (w[1] + w[3]) / 2.0, s))
        i += 1
    cells = [c for c in cells if c[0] > right and top <= c[1] <= bottom]
    rows = {}
    for x, y, s in cells:
        below = next((l for l in labels if l[1] >= y - 1.0), None)     # the level line just below (or on) the row
        if below is None:
            continue
        rows.setdefault(below[3], []).append((x, s))
    levels = []
    for _, _, _, name in labels:
        got = sorted(rows.get(name, []))
        sizes = [s for _, s in got if s]
        if sizes:
            levels.append({"level": name, "sizes": sizes})
    if len(levels) < 3:
        return None
    return {"levels": levels, "types": max(len(l["sizes"]) for l in levels)}


def bands(levels):
    """Levels top -> bottom -> bands bottom -> top, grouping neighbours with the same sizes."""
    out = []
    for lv in reversed(levels):
        sizes = ", ".join(lv["sizes"])
        if out and out[-1]["sizes"] == sizes:
            out[-1]["to"] = lv["level"]
        else:
            out.append({"from": lv["level"], "to": lv["level"], "sizes": sizes})
    return out


def read_pdf(path, pages=None):
    """The column schedule in a PDF -> {"pdf", "page" (1-based), "levels", "bands", "types", "summary"}.
    Raises ValueError when no page holds one (a scanned drawing, or no level / size table)."""
    import pymupdf
    best = None
    with pymupdf.open(path) as doc:
        for n in (pages or range(len(doc))):
            got = parse_words(doc[n].get_text("words"))
            if got and (best is None or len(got["levels"]) > len(best["levels"])):
                best = dict(got, page=n + 1)
    if not best:
        raise ValueError("No column schedule found in %s: needs a table of level labels (Level 01, Roof, B1 ...) with column "
                         "sizes (450x1400, D600) as text - a scanned drawing cannot be read." % path)
    best["pdf"] = path
    best["bands"] = bands(best["levels"])
    best["summary"] = "Page %d: %d levels (%s to %s), up to %d column types, grouped into %d bands" % (
        best["page"], len(best["levels"]), best["levels"][-1]["level"], best["levels"][0]["level"], best["types"], len(best["bands"]))
    return best


if __name__ == "__main__":
    print(json.dumps(read_pdf(sys.argv[1]), indent=1))
