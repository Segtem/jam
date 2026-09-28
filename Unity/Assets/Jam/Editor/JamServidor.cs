using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Text;
using System.Threading;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace Jam
{
    [DataContract]
    public sealed class DatosMalla
    {
        [DataMember] public float[][] vertices;
        [DataMember] public int[][] triangulos;
        [DataMember] public float[][] normales;
        [DataMember] public float[][] uv0;
    }

    [DataContract]
    public sealed class Pedido
    {
        [DataMember] public string op;
        [DataMember] public string nombre;
        [DataMember] public DatosMalla malla;
    }

    [DataContract]
    public sealed class HechosMalla
    {
        [DataMember] public int triangulos;
        [DataMember] public int posiciones;
        [DataMember] public double[] min;
        [DataMember] public double[] max;
        [DataMember] public double area;
        [DataMember] public int caras_hacia_afuera;
        // Con signo, en cm³, sumado con la convención frontal de Unity: coincide con el de Unreal sólo
        // si Unity dibuja las mismas caras (vale también para un merge de dos piezas, donde el
        // centro de la caja envolvente no sirve para decir qué es «afuera»).
        [DataMember] public double volumen;
    }

    [DataContract]
    public sealed class MallaMedida
    {
        [DataMember] public string nodo;
        [DataMember] public HechosMalla hechos;
    }

    [DataContract]
    public sealed class Respuesta
    {
        [DataMember] public bool ok = true;
        [DataMember(EmitDefaultValue = false)] public string error;
        [DataMember(EmitDefaultValue = false)] public string motor;
        [DataMember(EmitDefaultValue = false)] public int contrato;
        [DataMember(EmitDefaultValue = false)] public string version;
        [DataMember(EmitDefaultValue = false)] public string[] primitivas;
        [DataMember(EmitDefaultValue = false)] public string nodo;
        [DataMember(EmitDefaultValue = false)] public HechosMalla hechos;
        [DataMember(EmitDefaultValue = false)] public MallaMedida[] mallas;
        [DataMember] public int descartados;
        [DataMember] public int fijados;
        [DataMember(EmitDefaultValue = false)] public string escena;
        [DataMember(EmitDefaultValue = false)] public MedicionCubo cubo_nativo;
        [DataMember(EmitDefaultValue = false)] public string modo;
        [DataMember] public int pid;
    }

    // Contrato 1: sólo materializa buffers; no calcula geometría ni evalúa código recibido.
    // Todo, incluso TCP, se atiende en el hilo principal: update en GUI; bucle explícito
    // en -executeMethod para batchmode. No dependemos de ticks de editor en batchmode.
    [InitializeOnLoad]
    public static class JamServidor
    {
        public const string Escena = "Assets/Scenes/JamBaseComun.unity";
        const string CarpetaMallas = "Assets/JamGenerado";
        const int Puerto = 8793;
        const int MaxLinea = 32 * 1024 * 1024;
        static TcpListener servidor;
        static readonly List<Conexion> clientes = new List<Conexion>();
        static MedicionCubo cubo;
        static bool salir;
        static int hilo;

        sealed class Conexion : IDisposable
        {
            public readonly TcpClient cliente;
            public readonly List<byte> linea = new List<byte>();
            public Conexion(TcpClient c) { cliente = c; c.NoDelay = true; c.SendTimeout = 1000; }
            public void Dispose() { cliente.Close(); }
        }

        static JamServidor()
        {
            if (!Application.isBatchMode) EditorApplication.delayCall += Iniciar;
            AssemblyReloadEvents.beforeAssemblyReload += Cerrar;
            EditorApplication.quitting += Cerrar;
        }

        [MenuItem("Jam/Iniciar servidor")]
        public static void Iniciar()
        {
            if (servidor != null) return;
            hilo = Thread.CurrentThread.ManagedThreadId;
            cubo = JamMedicion.MedirCubo();
            Debug.Log("JAM_UNITY_CUBO " + JsonUtility.ToJson(cubo));
            if (cubo.triangulos != 12 || cubo.cruz_ba_ca_afuera != 12 || cubo.cruz_ca_ba_afuera != 0)
                throw new InvalidOperationException("Cambió el winding del cubo nativo: revisar la traducción.");
            var escucha = new TcpListener(IPAddress.Loopback, Puerto);
            escucha.Start();
            servidor = escucha;
            salir = false;
            if (!Application.isBatchMode) EditorApplication.update += Bombear;
            Debug.Log("JAM_UNITY escuchando en 127.0.0.1:8793, contrato 1, hilo " + hilo);
        }

        [MenuItem("Jam/Abrir base común")]
        public static void AbrirEscena()
        {
            if (File.Exists(Escena) && (Application.isBatchMode ||
                EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()))
                EditorSceneManager.OpenScene(Escena);
        }

        // Invocar SIN -quit: salir contesta antes de finalizar el bucle y cerrar el editor.
        // La extensión «salir» sólo existe en batchmode; las primitivas siguen siendo contrato 1.
        public static void Lote()
        {
            int codigo = 0;
            try
            {
                AbrirEscena();
                Iniciar();
                while (!salir) { Bombear(); Thread.Sleep(5); }
            }
            catch (Exception e) { Debug.LogException(e); codigo = 1; }
            finally { Cerrar(); }
            EditorApplication.Exit(codigo);
        }

        [MenuItem("Jam/Detener servidor")]
        public static void Cerrar()
        {
            EditorApplication.update -= Bombear;
            foreach (var c in clientes) c.Dispose();
            clientes.Clear();
            servidor?.Stop();
            servidor = null;
        }

        static void Bombear()
        {
            if (Thread.CurrentThread.ManagedThreadId != hilo)
                throw new InvalidOperationException("La escena sólo se toca desde el hilo principal.");
            if (servidor == null) return;
            while (servidor.Pending()) clientes.Add(new Conexion(servidor.AcceptTcpClient()));
            foreach (var c in clientes.ToArray())
            {
                try
                {
                    var s = c.cliente.Client;
                    if (s.Poll(0, SelectMode.SelectRead) && s.Available == 0)
                    { c.Dispose(); clientes.Remove(c); continue; }
                    // Una conexión parcial no bloquea el editor ni a los demás clientes.
                    var buffer = new byte[Math.Min(s.Available, 65536)];
                    if (buffer.Length == 0) continue;
                    int n = s.Receive(buffer);
                    for (int i = 0; i < n; i++)
                    {
                        if (buffer[i] == 10)
                        {
                            Respuesta r;
                            try
                            {
                                using (var entrada = new MemoryStream(c.linea.ToArray()))
                                    r = Atender((Pedido)new DataContractJsonSerializer(typeof(Pedido)).ReadObject(entrada));
                            }
                            catch (Exception e) { r = new Respuesta { ok = false, error = e.Message }; }
                            c.linea.Clear();
                            using (var salida = new MemoryStream())
                            {
                                new DataContractJsonSerializer(typeof(Respuesta)).WriteObject(salida, r);
                                var datos = salida.ToArray();
                                c.cliente.GetStream().Write(datos, 0, datos.Length);
                                c.cliente.GetStream().WriteByte(10);
                            }
                        }
                        else c.linea.Add(buffer[i]);
                        if (c.linea.Count > MaxLinea) throw new IOException("Pedido demasiado grande.");
                    }
                }
                catch (Exception e) when (e is IOException || e is SocketException || e is ObjectDisposedException)
                { c.Dispose(); clientes.Remove(c); }
            }
        }

        static Respuesta Atender(Pedido p)
        {
            switch (p?.op)
            {
                case "hola": return new Respuesta { motor = "unity", contrato = 1,
                    version = Application.unityVersion, cubo_nativo = cubo,
                    modo = Application.isBatchMode ? "bucle principal" : "EditorApplication.update",
                    pid = System.Diagnostics.Process.GetCurrentProcess().Id,
                    primitivas = new[] { "mostrar_malla", "descartar", "fijar", "hechos" } };
                case "mostrar_malla": return Mostrar(p);
                case "descartar":
                    var raiz = Raiz(false);
                    int cuantos = raiz == null ? 0 : raiz.childCount;
                    if (raiz != null)
                        foreach (Transform t in raiz.Cast<Transform>().ToArray()) Borrar(t.gameObject);
                    return new Respuesta { descartados = cuantos };
                case "fijar": return Fijar();
                case "hechos":
                    var r = Raiz(false);
                    return new Respuesta { mallas = r == null ? new MallaMedida[0] :
                        r.GetComponentsInChildren<MeshFilter>().Select(m => new MallaMedida {
                            nodo = m.name, hechos = Medir(m.sharedMesh) }).ToArray() };
                case "salir":
                    if (Application.isBatchMode) { salir = true; return new Respuesta(); }
                    break;
            }
            return new Respuesta { ok = false, error = "Operación desconocida: " + p?.op };
        }

        static Transform Raiz(bool crear)
        {
            var escena = SceneManager.GetActiveScene();
            var r = escena.GetRootGameObjects().FirstOrDefault(g => g.name == "JamPreview");
            if (r == null && crear) r = new GameObject("JamPreview");
            return r == null ? null : r.transform;
        }

        // MEDIDO en Unity 6000.3.24f1, 2026-09-28: el cubo de CreatePrimitive tiene
        // (b-a)×(c-a) afuera en 12/12 y (c-a)×(b-a) en 0/12 (JamMedicion).
        // Núcleo → Unity: (x,y,z) cm → (x,z,y)/100 m. La reflexión Y/Z y la distinta
        // fórmula frontal se compensan: se CONSERVAN los índices. Godot sí los invierte.
        static Vector3 AUnity(float[] p) { return new Vector3(p[0], p[2], p[1]) * 0.01f; }
        static double[] ANucleo(Vector3 p)
        { return new[] { Math.Round(p.x * 100.0, 3), Math.Round(p.z * 100.0, 3), Math.Round(p.y * 100.0, 3) }; }

        static void Validar(float[][] valores, int dimension, string campo)
        {
            if (valores == null || valores.Any(v => v == null || v.Length != dimension ||
                v.Any(x => float.IsNaN(x) || float.IsInfinity(x))))
                throw new ArgumentException("Buffer inválido: " + campo);
        }

        static Respuesta Mostrar(Pedido p)
        {
            var d = p.malla ?? throw new ArgumentException("Falta la malla.");
            Validar(d.vertices, 3, "vertices");
            if (d.vertices.Length == 0 || d.triangulos == null || d.triangulos.Length == 0)
                throw new ArgumentException("La malla llegó vacía.");
            if (d.triangulos.Any(t => t == null || t.Length != 3 || t.Any(i => i < 0 || i >= d.vertices.Length)))
                throw new ArgumentException("Índice de triángulo inválido.");
            if (d.normales != null && d.normales.Length > 0)
            {
                Validar(d.normales, 3, "normales");
                if (d.normales.Length != d.vertices.Length) throw new ArgumentException("Faltan normales.");
            }
            if (d.uv0 != null && d.uv0.Length > 0)
            {
                Validar(d.uv0, 2, "uv0");
                if (d.uv0.Length != d.vertices.Length) throw new ArgumentException("Faltan UV.");
            }
            var nombre = string.IsNullOrEmpty(p.nombre) ? "JamPreview" : p.nombre;
            var mesh = new Mesh { name = nombre, indexFormat = IndexFormat.UInt32 };
            mesh.vertices = d.vertices.Select(AUnity).ToArray();
            mesh.triangles = d.triangulos.SelectMany(t => new[] { t[0], t[1], t[2] }).ToArray();
            if (d.normales != null && d.normales.Length > 0)
                mesh.normals = d.normales.Select(n => new Vector3(n[0], n[2], n[1])).ToArray();
            else mesh.RecalculateNormals();
            if (d.uv0 != null && d.uv0.Length > 0) mesh.uv = d.uv0.Select(v => new Vector2(v[0], v[1])).ToArray();
            mesh.RecalculateBounds();
            var raiz = Raiz(true);
            var viejo = raiz.Cast<Transform>().FirstOrDefault(t => t.name == nombre);
            if (viejo != null) Borrar(viejo.gameObject);
            var objeto = new GameObject(nombre) { hideFlags = HideFlags.DontSaveInEditor };
            objeto.transform.SetParent(raiz, false);
            objeto.AddComponent<MeshFilter>().sharedMesh = mesh;
            objeto.AddComponent<MeshRenderer>().sharedMaterial = AssetDatabase.GetBuiltinExtraResource<Material>("Default-Material.mat");
            SceneView.RepaintAll();
            return new Respuesta { nodo = nombre, hechos = Medir(objeto.GetComponent<MeshFilter>().sharedMesh) };
        }

        static void Borrar(GameObject objeto)
        {
            var filtro = objeto.GetComponent<MeshFilter>();
            var mesh = filtro == null ? null : filtro.sharedMesh;
            UnityEngine.Object.DestroyImmediate(objeto);
            if (mesh != null && !AssetDatabase.Contains(mesh)) UnityEngine.Object.DestroyImmediate(mesh);
        }

        static Respuesta Fijar()
        {
            var raiz = Raiz(false);
            if (raiz == null) return new Respuesta { fijados = 0 };
            if (!AssetDatabase.IsValidFolder("Assets/Scenes")) AssetDatabase.CreateFolder("Assets", "Scenes");
            if (!AssetDatabase.IsValidFolder(CarpetaMallas)) AssetDatabase.CreateFolder("Assets", "JamGenerado");
            foreach (var filtro in raiz.GetComponentsInChildren<MeshFilter>())
            {
                // Una escena no conserva un Mesh transitorio: se guarda como asset primero.
                if (!AssetDatabase.Contains(filtro.sharedMesh))
                    AssetDatabase.CreateAsset(filtro.sharedMesh,
                        AssetDatabase.GenerateUniqueAssetPath(CarpetaMallas + "/Malla.asset"));
                filtro.gameObject.hideFlags = HideFlags.None;
            }
            AssetDatabase.SaveAssets();
            if (!EditorSceneManager.SaveScene(raiz.gameObject.scene, Escena))
                throw new IOException("No se pudo guardar " + Escena);
            return new Respuesta { fijados = raiz.childCount, escena = Escena };
        }

        // Lee el Mesh de Unity, nunca el pedido. El área se expresa en cm² y la caja en cm.
        // «Afuera» usa el centro del AABB: discrimina cajas convexas; NO juzga concavidades.
        static HechosMalla Medir(Mesh mesh)
        {
            var v = mesh.vertices;
            var t = mesh.triangles;
            if (v.Length == 0 || t.Length == 0) throw new InvalidOperationException("No hay entidades para medir.");
            var posiciones = new HashSet<(double, double, double)>();
            // `+ 0.0` convierte -0 en +0: un vértice en el eje (ápice, polo) sale como -0.0000001 y,
            // redondeado, partiría un mismo punto en dos (lo mismo pasó en Godot).
            foreach (var p in v) { var n = ANucleo(p); posiciones.Add((n[0] + 0.0, n[1] + 0.0, n[2] + 0.0)); }
            double area = 0;
            double volumen = 0;
            int afuera = 0;
            for (int i = 0; i < t.Length; i += 3)
            {
                var a = v[t[i]]; var b = v[t[i + 1]]; var c = v[t[i + 2]];
                var cara = Vector3.Cross(b - a, c - a);
                area += cara.magnitude * 5000.0;
                volumen += Vector3.Dot(a, cara) / 6.0 * 1000000.0;
                if (Vector3.Dot(cara, (a + b + c) / 3f - mesh.bounds.center) > 0) afuera++;
            }
            return new HechosMalla { triangulos = t.Length / 3, posiciones = posiciones.Count,
                min = ANucleo(mesh.bounds.min), max = ANucleo(mesh.bounds.max),
                area = Math.Round(area, 3), caras_hacia_afuera = afuera, volumen = Math.Round(volumen, 3) };
        }
    }
}
