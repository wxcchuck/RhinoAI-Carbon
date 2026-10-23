"""Package build helpers (no Windows / Rhino needed). Drafted by an AI agent (Claude) - review before trusting."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rhino_plugin"))
import build_package as bp  # noqa: E402


def test_versions_and_escaping():
    assert bp.numeric_version("0.1.0-beta") == "0.1.0.0" and bp.numeric_version("1.2") == "1.2.0.0"
    assert bp.cs('A "B" C:\\x') == 'A \\"B\\" C:\\\\x'
    info = bp.assembly_info(dict(bp.load_config(None), title='Office "WLCA"', version="0.2.0-beta"))
    assert '[assembly: AssemblyTitle("Office \\"WLCA\\"")]' in info and 'AssemblyVersion("0.2.0.0")' in info
    assert 'AssemblyInformationalVersion("0.2.0-beta")' in info


def test_config_and_manifest(tmp_path):
    cfg_path = tmp_path / "pkg.json"
    cfg_path.write_text(json.dumps({"name": "Office WLCA", "version": "0.3.0", "authors": ["A. Person"],
                                    "icon": "icon.png", "out": "dist"}))
    cfg = bp.load_config(str(cfg_path))
    assert cfg["icon"] == str(tmp_path / "icon.png") and cfg["out"] == str(tmp_path / "dist")   # relative to the config
    m = bp.manifest(cfg, "icon.png")
    assert "name: Office WLCA" in m and "version: 0.3.0" in m and "- A. Person" in m and "icon: icon.png" in m


def test_package_ships_every_module_the_dialog_imports():
    here = os.path.join(os.path.dirname(__file__), "..")
    shipped = {name for _, name in bp.SCRIPTS}
    for _, name in bp.SCRIPTS:
        assert os.path.exists(os.path.join(here, _, name))
    for name in bp.WEB:
        assert os.path.exists(os.path.join(here, "rhino_ui", "web", name))
    page = open(os.path.join(here, "rhino_ui", "web", "index.html"), encoding="utf-8").read()
    import re as _re
    assert set(_re.findall(r'(?:src|href)="([^"]+)"', page)) <= set(bp.WEB)     # the page loads only shipped files
    src = "".join(open(os.path.join(here, f, n), encoding="utf-8").read() for f, n in bp.SCRIPTS)
    import re
    used = {m + ".py" for m in re.findall(r"^\s*(?:import|from) (wlca_\w+)", src, re.M)}
    assert used <= shipped, used - shipped


def test_toolbar_icon_is_embedded(tmp_path):
    import base64
    png = b"\x89PNG\r\n\x1a\nfake"
    icons = {}
    for size in ("16", "24", "32"):
        (tmp_path / ("i%s.png" % size)).write_bytes(png + size.encode())
        icons[size] = str(tmp_path / ("i%s.png" % size))
    rui = open(os.path.join(os.path.dirname(bp.__file__), "WLCA.rui"), encoding="utf-8").read()
    out = bp.rui_with_icon(rui, icons)
    import re
    bid = re.search(r'<macro_item guid="[^"]+" bitmap_id="([^"]+)">', out).group(1)
    for tag, size in (("small_bitmap", "16"), ("normal_bitmap", "24"), ("large_bitmap", "32")):
        block = re.search(r"<%s item_width=\"%s\".*?</%s>" % (tag, size, tag), out, re.S).group(0)
        assert bid in block and base64.b64encode(png + size.encode()).decode() in block
    assert 'item_display_style="control_and_text"' in out and "<bitmaps />" not in out
    assert bp.rui_with_icon(rui, {}) == rui
    import xml.dom.minidom
    xml.dom.minidom.parseString(out.encode("utf-8"))           # still well-formed


def test_plugin_sources_and_panel():
    import build_package as bp
    here = os.path.join(os.path.dirname(__file__), "..", "rhino_plugin")
    for s in bp.SOURCES:
        assert os.path.exists(os.path.join(here, s)) and s.endswith(".ai.cs")
    panel = open(os.path.join(here, "WlcaPanel.ai.cs"), encoding="utf-8").read()
    web = open(os.path.join(here, "..", "rhino_ui", "wlca_web.py"), encoding="utf-8").read()
    for key in ("WLCA.WebView", "WLCA.Attached"):              # the C# panel and the Python page meet on these keys
        assert '"%s"' % key in panel and '"%s"' % key in web
    assert "Panels.RegisterPanel(this, typeof(WlcaPanel)" in open(os.path.join(here, "WlcaPlugin.ai.cs"), encoding="utf-8").read()
    assert "Panels.OpenPanel(WlcaPanel.PanelId)" in open(os.path.join(here, "WlcaCommand.ai.cs"), encoding="utf-8").read()
