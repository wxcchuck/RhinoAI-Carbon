// Drafted by an AI agent (Claude) - review before trusting.
using System.IO;
using Rhino;
using Rhino.Commands;

namespace Wlca
{
    /// <summary>WLCA: opens the whole life carbon dialog (wlca_dialog.py, next to WLCA.rhp).</summary>
    public class WlcaCommand : Command
    {
        public override string EnglishName
        {
            get { return "WLCA"; }
        }

        protected override Result RunCommand(RhinoDoc doc, RunMode mode)
        {
            var dialog = Path.Combine(WlcaPlugin.PackageFolder, "wlca_dialog.py");
            if (!File.Exists(dialog))
            {
                RhinoApp.WriteLine("WLCA: wlca_dialog.py is missing from {0} - reinstall the package.", WlcaPlugin.PackageFolder);
                return Result.Failure;
            }
            // The dialog is Python 3 ("#! python3"); RunPythonScript hands it to Rhino 8's script engine, which also
            // installs the packages it declares ("# r: openpyxl") on first use.
            return RhinoApp.RunScript("_-RunPythonScript \"" + dialog + "\"", false) ? Result.Success : Result.Failure;
        }
    }
}
