"""Results for the WLCA window, read from the calculated workbook. Drafted by an AI agent (Claude) - review before trusting.

The workbook is the single source of the numbers: openpyxl writes formulas only, so Excel (hidden) opens the
workbook, calculates and saves it (calculate_in_excel), and the cached values are read back here (read_results).
No calculation is repeated in Python.
"""
import os
import subprocess

# the keys the window shows, from each option's O<k>_Results summary (column X key, column Y value)
KEYS = ["NAME", "GIA", "UP_T", "AC_T", "UP_ALL", "UP_X8", "UP_SC", "UP_WB", "AC_ALL", "AC_X8", "AC_DEC",
        "M_A13", "M_A4", "M_A5", "M_B2", "M_B3", "M_B4", "M_C", "M_D", "B2_BASIS",
        "E_0", "E_1", "E_2", "E_3", "E_4", "E_5", "E_6", "E_7", "E_CONT",
        "B_MOD", "B_ASM", "B_BM", "B_SITE", "B_CONT", "SH_ASM",
        "BIO_STORED", "BIO_RELEASED", "BC_ALL", "QA_FLAGS", "EUI", "EUI_LIM", "B6_ND", "B6_D", "B7_ND", "B7_D", "WLC_ND", "WLC_D", "OP_STATUS"]
# Dashboard rows 13-22 (wlca_dashboard trows): the summary key each target is judged on
TARGET_KEYS = ["UP_SC", "UP_WB", "UP_X8", "UP_X8", "AC_X8", "AC_X8", "UP_ALL", "UP_ALL", "AC_ALL", "AC_ALL"]
TARGET_ROW0 = 13

PS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$path = $env:WLCA_XLSX
$x = New-Object -ComObject Excel.Application
try {
  $x.Visible = $false; $x.DisplayAlerts = $false; $x.ScreenUpdating = $false
  $wb = $x.Workbooks.Open($path, 0, $false)
  $x.CalculateFull()
  $wb.Save()
  $wb.Close($false)
} finally {
  $x.Quit()
  [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($x)
}
"""


def is_locked(path):
    """True when another program (usually Excel) has the workbook open."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r+b"):
            return False
    except (IOError, OSError):
        return True


def start_excel_calculation(path):
    """Start Excel (hidden, separate process) to calculate and save the workbook; returns the Popen to poll."""
    env = dict(os.environ, WLCA_XLSX=os.path.abspath(path))
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", PS_SCRIPT],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def read_results(path):
    """Values the window shows: {"calculated", "cont", "stage", "options": [{"k", "values"}], "targets": [...]}.
    "calculated" is False when the workbook has no cached values (not yet opened by Excel)."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        def named(nm):
            dn = wb.defined_names.get(nm) if hasattr(wb.defined_names, "get") else wb.defined_names[nm]
            if dn is None:
                return None
            sheet, ref = list(dn.destinations)[0]
            return wb[sheet][ref.replace("$", "")].value
        opts, k = [], 1
        while "O%d_Results" % k in wb.sheetnames:
            R = wb["O%d_Results" % k]
            vals = {}
            for row in R.iter_rows(min_row=5, max_row=120, min_col=24, max_col=25, values_only=True):
                if row[0] in KEYS:
                    vals[row[0]] = row[1] if row[0] in ("NAME", "OP_STATUS", "B2_BASIS") else _num(row[1])
            opts.append({"k": k, "values": vals, "traj": read_trajectory(wb, k)})
            k += 1
        D = wb["Dashboard"]
        targets = []
        for i, key in enumerate(TARGET_KEYS):
            r = TARGET_ROW0 + i
            label, tgt = D.cell(r, 1).value, _num(D.cell(r, 8).value)
            if label and tgt:
                targets.append({"label": label, "key": key, "target": tgt})
        calculated = any(o["values"].get("UP_ALL") is not None for o in opts)
        sc = dict((k, _num(named(nm))) for k, nm in (("fin", "SC_FIN"), ("ffe", "SC_FFE"), ("mep", "SC_MEP")))
        return {"calculated": calculated, "cont": _num(named("CONT")) or 0.0, "stage": _num(named("STAGE")) or 2,
                "sc": dict((k, 1.0 if v is None else v) for k, v in sc.items()), "catb": _num(named("CATB")),
                "options": opts, "targets": targets, "workbook": os.path.abspath(path)}
    finally:
        wb.close()


# O<k>_Traj (wlca_calc_template.build_trajectory): first data row and columns
TRAJ_FIRST, TRAJ_COLS = 6, dict(t=1, year=2, b4_first=5, emb_nd=20, emb_d=21, wlc_nd=22, wlc_d=23)
TRAJ_GROUPS = 8


def read_trajectory(wb, k):
    """Per-year series for the trajectory chart, or None for workbooks made before it existed.
    {"t", "year", "emb_nd", "emb_d", "wlc_nd", "wlc_d": [...], "b4": [[tCO2e per GLA group] per year]}"""
    name = "O%d_Traj" % k
    if name not in wb.sheetnames:
        return None
    T, c = wb[name], TRAJ_COLS
    out = dict((key, []) for key in ("t", "year", "emb_nd", "emb_d", "wlc_nd", "wlc_d", "b4"))
    for row in T.iter_rows(min_row=TRAJ_FIRST, max_col=24, values_only=True):
        if row[c["t"] - 1] is None:
            break
        for key in ("t", "year", "emb_nd", "emb_d", "wlc_nd", "wlc_d"):
            out[key].append(_num(row[c[key] - 1]))
        out["b4"].append([_num(row[c["b4_first"] - 1 + j]) or 0.0 for j in range(TRAJ_GROUPS)])
    return out if out["t"] and out["emb_nd"][-1] is not None else None


def judge(value, target, cont):
    """The Dashboard's verdict: Meets / Meets before contingency only / Above / Not assessed."""
    if value is None or not target:
        return "Not assessed"
    if value <= target:
        return "Meets"
    if value / (1 + (cont or 0)) <= target:
        return "Meets before contingency only"
    return "Above"
