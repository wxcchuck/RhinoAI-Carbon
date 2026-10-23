// Drafted by an AI agent (Claude) - review before trusting.
using System.IO;
using Rhino;
using Rhino.Commands;

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
    }

    /// <summary>WLCA: opens the whole life carbon window (wlca_web.py - the web interface with results).</summary>
    public class WlcaCommand : Command
    {
        public override string EnglishName
        {
            get { return "WLCA"; }
        }

        protected override Result RunCommand(RhinoDoc doc, RunMode mode)
        {
            return ScriptRunner.Run("wlca_web.py");
        }
    }
}
