// Drafted by an AI agent (Claude) - review before trusting.
using System;
using System.Runtime.InteropServices;
using Eto.Forms;

namespace Wlca
{
    /// <summary>
    /// The dockable WLCA panel: one WebView and nothing else. The page and everything behind it is Python
    /// (wlca_web.py): the script finds this WebView through the AppDomain (ViewKey), attaches to it and loads the page.
    /// Like any Rhino panel it can be docked, tabbed with other panels or floated, and Rhino stays usable while it is open.
    /// </summary>
    [Guid("b6a3e3f0-2d1c-4f7e-9b0a-5c8e1d2f3a41")]
    public class WlcaPanel : Panel
    {
        /// <summary>AppDomain data key holding the panel's WebView.</summary>
        public const string ViewKey = "WLCA.WebView";
        /// <summary>AppDomain data key set by wlca_web.py once it has attached to the WebView.</summary>
        public const string AttachedKey = "WLCA.Attached";

        public static Guid PanelId
        {
            get { return typeof(WlcaPanel).GUID; }
        }

        public WlcaPanel()
        {
            var view = new WebView();
            Content = view;
            AppDomain.CurrentDomain.SetData(ViewKey, view);
            // Rhino reopens the panel by itself if it was open when Rhino closed: draw the page then too.
            LoadComplete += (s, e) => ScriptRunner.RunWhenIdle("wlca_web.py");
        }

        public static object View
        {
            get { return AppDomain.CurrentDomain.GetData(ViewKey); }
        }

        public static bool Attached
        {
            get { return AppDomain.CurrentDomain.GetData(AttachedKey) is bool && (bool)AppDomain.CurrentDomain.GetData(AttachedKey); }
        }
    }
}
