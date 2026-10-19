// Drafted by an AI agent (Claude) - review before trusting.
using System;
using System.IO;
using System.Runtime.InteropServices;
using Rhino;
using Rhino.ApplicationSettings;
using Rhino.PlugIns;

[assembly: Guid("6f0c9c0e-6c51-4d8b-9a55-4a3f2f5d7b21")]
// title, version, organisation and web site: AssemblyInfo.g.cs, written by build_package.py

namespace Wlca
{
    /// <summary>
    /// Launcher for the WLCA dialog. The Python scripts ship next to WLCA.rhp; the command runs wlca_dialog.py
    /// from there, so a package update replaces the scripts and the plug-in together.
    /// </summary>
    public class WlcaPlugin : PlugIn
    {
        // Plain C# 5 throughout, so the .NET Framework compiler that ships with Windows can build it (build_package.py).
        public WlcaPlugin() { Instance = this; }

        public static WlcaPlugin Instance { get; private set; }

        /// <summary>Folder holding WLCA.rhp and the Python scripts.</summary>
        public static string PackageFolder
        {
            get { return Path.GetDirectoryName(typeof(WlcaPlugin).Assembly.Location); }
        }

        public override PlugInLoadTime LoadTime
        {
            get { return PlugInLoadTime.AtStartup; }
        }

        protected override LoadReturnCode OnLoad(ref string errorMessage)
        {
            RemoveScriptInstall();
            return LoadReturnCode.Success;
        }

        /// <summary>
        /// Before the package, install_wlca.py added a WLCA command alias and a WLCA toolbar that ran the scripts in
        /// a shared folder. The alias would shadow this plug-in's command, so it is removed (only when it points
        /// at wlca_dialog.py), and that toolbar file is closed.
        /// </summary>
        static void RemoveScriptInstall()
        {
            try
            {
                if (CommandAliasList.IsAlias("WLCA"))
                {
                    var macro = CommandAliasList.GetMacro("WLCA") ?? "";
                    if (macro.IndexOf("wlca_dialog.py", StringComparison.OrdinalIgnoreCase) >= 0)
                        CommandAliasList.Delete("WLCA");
                }
                var appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
                var oldRui = Path.Combine(appData, "McNeel", "Rhinoceros", "8.0", "UI", "WLCA", "WLCA.rui");
                var old = RhinoApp.ToolbarFiles.FindByPath(oldRui);
                if (old != null)
                    old.Close(false);
            }
            catch (Exception e)
            {
                RhinoApp.WriteLine("WLCA: could not tidy the earlier script install ({0})", e.Message);
            }
        }
    }
}
