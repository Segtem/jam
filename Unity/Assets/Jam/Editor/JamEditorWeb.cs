using System.Diagnostics;
using UnityEditor;

namespace Jam
{
    /// <summary>
    /// El editor de nodos de Jam (la web), desde el menú de Unity. Lo sirve el núcleo de Jam en un
    /// proceso aparte (<c>python3 -m jam.servidor --motor unity</c>, puerto 8796), que habla con este
    /// editor por el contrato (JamServidor, 8793). Si ya está corriendo, sólo abre otra ventana.
    /// </summary>
    [InitializeOnLoad]
    public static class JamEditorWeb
    {
        const string Url = "http://127.0.0.1:8796/";
        static Process _nucleo;

        // Al cerrar Unity se cierra también el núcleo, como hace el plugin de Godot. Si Unity recarga
        // scripts pierde esta referencia, y el núcleo nuevo le pide el puerto al viejo (servidor._ocupar).
        static JamEditorWeb()
        {
            EditorApplication.quitting += () =>
            {
                try { if (_nucleo != null && !_nucleo.HasExited) _nucleo.Kill(); } catch { }
            };
        }

        // Dónde está el núcleo y con qué Python: los escribe `tools/instalar.py` en
        // ProjectSettings/JamNucleo.json. Sin instalar, el lugar de la máquina de desarrollo.
        [System.Serializable] class Config { public string nucleo_python = ""; public string python = ""; }

        static Config Leer()
        {
            var archivo = System.IO.Path.Combine("ProjectSettings", "JamNucleo.json");
            var c = System.IO.File.Exists(archivo)
                ? UnityEngine.JsonUtility.FromJson<Config>(System.IO.File.ReadAllText(archivo)) : new Config();
            var windows = UnityEngine.Application.platform == UnityEngine.RuntimePlatform.WindowsEditor;
            if (string.IsNullOrEmpty(c.nucleo_python))
                c.nucleo_python = System.Environment.GetEnvironmentVariable(windows ? "USERPROFILE" : "HOME")
                                  + "/Dev/jam/Content/Python";
            if (string.IsNullOrEmpty(c.python)) c.python = windows ? "python" : "python3";
            return c;
        }

        static string RutaNucleo() => Leer().nucleo_python;

        static Process Python(string codigo)
        {
            var info = new ProcessStartInfo(Leer().python) { UseShellExecute = false, CreateNoWindow = true };
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
