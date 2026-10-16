#! python3
"""
WLCA - one-time install for Rhino 8  v0.1  (draft for review)

Drafted by an AI agent (Claude) - review before trusting.

Run once per PC: drag this file onto the Rhino window (or Tools > Script > Run, or _RunPythonScript).
It
  1. adds a command alias  WLCA  that opens the dialog from this package folder, and
  2. writes a small WLCA toolbar (one button) to your Rhino settings folder and opens it.
Nothing is copied: the button runs the scripts in the shared package folder, so updates there reach
everyone automatically. Run it again if the package folder moves.
"""
import os
import uuid

import Rhino

PKG = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("WLCA_PKG_DIR", "")
DIALOG = os.path.join(PKG, "wlca_dialog.py")
MACRO = '! _-RunPythonScript "%s"' % DIALOG


def g():
    return str(uuid.uuid4())


def rui_xml():
    tb, grp, item, mac, grp_item = g(), g(), g(), g(), g()
    loc = lambda t: "<locale_1033>%s</locale_1033>" % t           # noqa: E731
    return """<?xml version="1.0" encoding="utf-8"?>
<RhinoUI major_ver="3" minor_ver="0" guid="{root}" localize="False" default_language_id="1033">
  <extend_rhino_menus />
  <menus />
  <tool_bar_groups>
    <tool_bar_group guid="{grp}" dock_bar_guid32="00000000-0000-0000-0000-000000000000" dock_bar_guid64="{grp}" active_tool_bar_group="{grp_item}" single_file="False" hide_single_tab="False" point_floating="400,200">
      <text>{name}</text>
      <tool_bar_group_item guid="{grp_item}" major_version="1" minor_version="1">
        <text>{name}</text>
        <tool_bar_id>{tb}</tool_bar_id>
      </tool_bar_group_item>
      <dock_bar_info dpi_scale="100" dock_bar="False" docking="True" horz="False" visible="True" floating="True" mru_float_style="8192" bar_id="59501" mru_width="160" point_pos="-2,-2" float_point="400,200" rect_mru_dock_pos="0,0,0,0" dock_location_u="59419" dock_location="top" float_size="160,60" />
    </tool_bar_group>
  </tool_bar_groups>
  <tool_bars>
    <tool_bar guid="{tb}" item_display_style="text_only">
      <text>{name}</text>
      <tool_bar_item guid="{item}" button_display_mode="control_and_text" button_style="normal">
        <text>{name}</text>
        <left_macro_id>{mac}</left_macro_id>
      </tool_bar_item>
    </tool_bar>
  </tool_bars>
  <macros>
    <macro_item guid="{mac}">
      <text>{name}</text>
      <tooltip>{tip}</tooltip>
      <help_text>{tip}</help_text>
      <button_text>{name}</button_text>
      <menu_text>{name}</menu_text>
      <script>{script}</script>
    </macro_item>
  </macros>
  <bitmaps />
  <scripts />
</RhinoUI>
""".format(root=g(), grp=grp, grp_item=grp_item, tb=tb, item=item, mac=mac,
           name=loc("WLCA"), tip=loc("Whole life carbon assessment (RICS PS)"),
           script=MACRO.replace("&", "&amp;").replace('"', "&quot;"))


def main():
    if not os.path.exists(DIALOG):
        print("WLCA install: wlca_dialog.py not found next to this installer (%s)" % PKG)
        return
    aliases = Rhino.ApplicationSettings.CommandAliasList
    if aliases.IsAlias("WLCA"):
        aliases.SetMacro("WLCA", MACRO)
    else:
        aliases.Add("WLCA", MACRO)
    ui_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "McNeel", "Rhinoceros", "8.0", "UI", "WLCA")
    os.makedirs(ui_dir, exist_ok=True)
    rui = os.path.join(ui_dir, "WLCA.rui")
    old = Rhino.RhinoApp.ToolbarFiles.FindByPath(rui)
    if old is not None:
        old.Close(False)
    with open(rui, "w", encoding="utf-8") as f:
        f.write(rui_xml())
    tf = Rhino.RhinoApp.ToolbarFiles.Open(rui)
    shown = False
    if tf is not None:
        # Rhino 8 shows toolbars in containers; this floats the WLCA toolbar in its own container
        Rhino.RhinoApp.RunScript('_-ShowToolbar "WLCA" "WLCA"', False)
        shown = True
    print("WLCA installed: type WLCA or use the WLCA toolbar%s. Package: %s" % ("" if shown else " (open it from Window > Toolbars)", PKG))
    return rui, tf is not None, shown


if __name__ == "__main__" and not globals().get("WLCA_NO_AUTORUN"):
    main()
