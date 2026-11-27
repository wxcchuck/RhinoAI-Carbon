"""Column schedule reader (wlca_column_schedule.py, D23) on an INVENTED schedule.
Drafted by an AI agent (Claude) - review before trusting."""
import pytest

import wlca_column_schedule as cs
import wlca_core as core


def W(x, y, text, h=6.0):
    return (x, y, x + 6.0 * len(text), y + h, text, 0, 0, 0)


def schedule(mid_row=True):
    """Level lines 12 pt apart, Roof at the top; a size row sits between two level lines (mid_row) or on one."""
    rows = [("Roof", None), ("Level 05", ["350x550", "350x550", "-"]), ("Level 04", ["350x550", "350x550", "-"]),
            ("Level 03", ["450x650", "550 x 650", "-"]), ("Level 02", ["450x650", "550x650", "D600"]),
            ("Level 01", ["450x1400", "450x1700", "D600"]), ("Ground", ["450x1400", "450x1700", "D600"])]
    words = [W(48, 40, "Level"), W(200, 40, "Column"), W(230, 40, "A"), W(260, 40, "Column"), W(290, 40, "B")]
    y = 60.0
    for label, sizes in rows:
        words += [W(48, y, t) if i == 0 else W(48 + 6 * len(label.split()[0]) + 4, y, t) for i, t in enumerate(label.split())]
        if sizes:
            ys = y - 6.0 if mid_row else y
            for k, s in enumerate(sizes):
                parts = s.split(" ")
                x = 200 + 60 * k
                for p in parts:
                    words.append(W(x, ys, p))
                    x += 6 * len(p) + 3
        y += 12.0
    words += [W(900, 700, "Level"), W(940, 700, "99"), W(1000, 720, "300x300")]   # title block: not the level column
    return words


@pytest.mark.parametrize("mid_row", [True, False])
def test_rows_belong_to_the_level_below(mid_row):
    got = cs.parse_words(schedule(mid_row))
    lv = dict((x["level"], x["sizes"]) for x in got["levels"])
    assert list(lv) == ["05", "04", "03", "02", "01", "00"]                       # top -> bottom; Roof has no row
    assert lv["05"] == ["350x550", "350x550"]                                      # "-" = no column of that type
    assert lv["03"] == ["450x650", "550x650"]                                      # "550 x 650" in three words
    assert lv["02"] == ["450x650", "550x650", "D600"] and lv["00"] == ["450x1400", "450x1700", "D600"]
    assert got["types"] == 3


def test_bands_and_the_take_off_reads_them():
    b = cs.bands(cs.parse_words(schedule())["levels"])
    assert b == [{"from": "00", "to": "01", "sizes": "450x1400, 450x1700, D600"},
                 {"from": "02", "to": "02", "sizes": "450x650, 550x650, D600"},
                 {"from": "03", "to": "03", "sizes": "450x650, 550x650"},
                 {"from": "04", "to": "05", "sizes": "350x550, 350x550"}]
    for x in b:
        assert core.parse_sections(x["sizes"]) is not None


def test_not_a_schedule():
    assert cs.parse_words([W(48, 60, "Level"), W(90, 60, "01"), W(200, 60, "450x450")]) is None
    assert cs.parse_words([W(10, 10 * i, "Note") for i in range(10)]) is None


def test_reads_a_pdf(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    doc.new_page()                                                                 # page 1: a drawing without a schedule
    pg = doc.new_page(width=842, height=595)
    for x, y, t in [(w[0], w[3], w[4]) for w in schedule()]:
        pg.insert_text((x, y), t, fontsize=6)
    p = str(tmp_path / "s.pdf")
    doc.save(p)
    got = cs.read_pdf(p)
    assert got["page"] == 2 and len(got["bands"]) == 4 and "6 levels (00 to 05)" in got["summary"]
    empty = str(tmp_path / "e.pdf")
    d2 = pymupdf.open()
    d2.new_page()
    d2.save(empty)
    with pytest.raises(ValueError):
        cs.read_pdf(empty)
