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
    src = "".join(open(os.path.join(here, f, n), encoding="utf-8").read() for f, n in bp.SCRIPTS)
    import re
    used = {m + ".py" for m in re.findall(r"^\s*(?:import|from) (wlca_\w+)", src, re.M)}
    assert used <= shipped, used - shipped
