// Drafted by an AI agent (Claude) - review before trusting.
using System;
using System.IO;
using Rhino;
using Rhino.Commands;
using Rhino.UI;

namespace Wlca
{
    /// <summary>Runs one of the Python scripts that ship next to WLCA.rhp.</summary>
    static class ScriptRunner
    {
        public static Result Run(string script)
        {
            var path = Path.Combine(WlcaPlugin.PackageFolder, script);
            if (!File.Exists(path))
            {
                RhinoApp.WriteLine("WLCA: {0} is missing from {1} - reinstall the package.", script, WlcaPlugin.PackageFolder);
                return Result.Failure;
            }
            // The scripts are Python 3 ("#! python3"); RunPythonScript hands them to Rhino 8's script engine, which
            // also installs the packages they declare ("# r: openpyxl") on first use.
            return RhinoApp.RunScript("_-RunPythonScript \"" + path + "\"", false) ? Result.Success : Result.Failure;
        }

        /// <summary>Run a script once Rhino is idle, unless the WLCA page is attached by then.</summary>
        public static void RunWhenIdle(string script)
        {
            EventHandler handler = null;
            handler = (s, e) =>
            {
                RhinoApp.Idle -= handler;
                if (!WlcaPanel.Attached)
                    Run(script);
            };
            RhinoApp.Idle += handler;
        }
    }

    /// <summary>
    /// WLCA: opens the dockable WLCA panel and (re)draws the page in it (wlca_web.py - the web interface with results).
    /// Running it again reloads the page for the open model.
    /// </summary>
    public class WlcaCommand : Command
    {
        public override string EnglishName
        {
            get { return "WLCA"; }
        }

        protected override Result RunCommand(RhinoDoc doc, RunMode mode)
        {
            Panels.OpenPanel(WlcaPanel.PanelId);
            if (WlcaPanel.View == null)
            {
                // the panel is built when Rhino first shows it; its LoadComplete runs the script
                ScriptRunner.RunWhenIdle("wlca_web.py");
                return Result.Success;
            }
            return ScriptRunner.Run("wlca_web.py");
        }
    }
}
