using System.Diagnostics;
using UnityEditor;

namespace Jam
{
    /// <summary>
    /// El editor de nodos de Jam (la web), desde el menú de Unity. Lo sirve el núcleo de Jam en un
    /// proceso aparte (<c>python3 -m jam.servidor --motor unity</c>, puerto 8796), que habla con este
    /// editor por el contrato (JamServidor, 8793). Si ya está corriendo, sólo abre otra ventana.
    /// </summary>
    public static class JamEditorWeb
    {
        const string Url = "http://127.0.0.1:8796/";
        static Process _nucleo;

        static string RutaNucleo()
        {
            var ruta = EditorPrefs.GetString("Jam.NucleoPython", "");
            return string.IsNullOrEmpty(ruta)
                ? System.Environment.GetEnvironmentVariable("HOME") + "/Dev/jam/Content/Python"
                : ruta;
        }

        static Process Python(string codigo)
        {
            var info = new ProcessStartInfo("python3") { UseShellExecute = false, CreateNoWindow = true };
            info.ArgumentList.Add("-c");
            info.ArgumentList.Add("import sys; sys.path.insert(0, " + JsonUtilityQuote(RutaNucleo()) +
                                  "); from jam import servidor; " + codigo);
            return Process.Start(info);
        }

        static string JsonUtilityQuote(string s) => "'" + s.Replace("\\", "\\\\").Replace("'", "\\'") + "'";

        [MenuItem("Jam/Editor de nodos (web)")]
        public static void Abrir()
        {
            if (_nucleo != null && !_nucleo.HasExited)
            {
                Python("servidor.abrir_ventana('" + Url + "')");
                return;
            }
            _nucleo = Python("servidor.main(['--motor', 'unity', '--abrir'])");
            UnityEngine.Debug.Log("JAM_UNITY editor de nodos en " + Url + " (pid " + _nucleo.Id + ")");
        }
    }
}
