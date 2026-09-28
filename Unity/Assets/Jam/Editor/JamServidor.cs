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
        [DataMember] public string ruta;
        [DataMember] public Instancia[] instancias;
        [DataMember] public Rayo[] rayos;
    }

    [DataContract]
    public sealed class Instancia
    {
        [DataMember] public float[] pos;
        [DataMember] public float yaw;
        [DataMember] public float[] escala;
    }

    [DataContract]
    public sealed class Rayo
    {
        [DataMember] public float[] desde;
        [DataMember] public float[] hacia;
    }

    [DataContract]
    public sealed class Caja
    {
        [DataMember] public double[] min;
        [DataMember] public double[] max;
    }

    [DataContract]
    public sealed class Golpe
    {
        [DataMember] public bool golpe;
        [DataMember(EmitDefaultValue = false)] public double[] punto;
        [DataMember(EmitDefaultValue = false)] public double[] normal;
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
        [DataMember(EmitDefaultValue = false)] public string ruta;
        [DataMember(EmitDefaultValue = false)] public double[] min;
        [DataMember(EmitDefaultValue = false)] public double[] max;
        [DataMember(EmitDefaultValue = false)] public Caja[] instancias;
        [DataMember(EmitDefaultValue = false)] public Golpe[] golpes;
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
                    primitivas = new[] { "mostrar_malla", "descartar", "fijar", "hechos",
                        "guardar_malla", "resolver_asset", "colocar", "raycast" } };
                case "mostrar_malla": return Mostrar(p);
                case "guardar_malla": return GuardarMalla(p);
                case "resolver_asset": return ResolverAsset(p);
                case "colocar": return Colocar(p);
                case "raycast": return Raycast(p);
                case "descartar":
                    // Sólo lo que no se fijó: lo fijado ya es escena y descartar no lo toca.
                    var raiz = Raiz(false);
                    var sueltos = raiz == null ? new GameObject[0] : raiz.Cast<Transform>()
                        .Where(t => EsPreview(t)).Select(t => t.gameObject).ToArray();
                    foreach (var g in sueltos) Borrar(g);
                    return new Respuesta { descartados = sueltos.Length };
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

        static Mesh ArmarMalla(Pedido p)
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
            return mesh;
        }

        static Respuesta Mostrar(Pedido p)
        {
            var mesh = ArmarMalla(p);
            var nombre = mesh.name;
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

        static Respuesta GuardarMalla(Pedido p)
        {
            if (string.IsNullOrWhiteSpace(p.nombre) || p.nombre == "." || p.nombre == ".." ||
                p.nombre.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0 || p.nombre.Contains("\\"))
                throw new ArgumentException("Nombre de malla inválido.");
            var malla = ArmarMalla(p);
            try
            {
                if (!AssetDatabase.IsValidFolder(CarpetaMallas)) AssetDatabase.CreateFolder("Assets", "JamGenerado");
                if (!AssetDatabase.IsValidFolder(CarpetaMallas + "/Mallas"))
                    AssetDatabase.CreateFolder(CarpetaMallas, "Mallas");
                string ruta = CarpetaMallas + "/Mallas/" + p.nombre + ".asset";
                var anterior = AssetDatabase.LoadMainAssetAtPath(ruta);
                if (anterior != null && !(anterior is Mesh))
                    throw new ArgumentException("La ruta ya contiene un asset que no es malla: " + ruta);
                // Conservar GUID y referencias de las instancias que ya usan este asset.
                if (anterior != null) { EditorUtility.CopySerialized(malla, anterior); EditorUtility.SetDirty(anterior); }
                else AssetDatabase.CreateAsset(malla, ruta);
                AssetDatabase.SaveAssets();
                return new Respuesta { ruta = ruta };
            }
            finally
            {
                if (!AssetDatabase.Contains(malla)) UnityEngine.Object.DestroyImmediate(malla);
            }
        }

        static UnityEngine.Object CargarAsset(string ruta)
        {
            if (string.IsNullOrEmpty(ruta) || !ruta.StartsWith("Assets/", StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("Se necesita una ruta de asset bajo Assets/.");
            var asset = AssetDatabase.LoadMainAssetAtPath(ruta);
            if (!(asset is Mesh) && !(asset is GameObject))
                throw new ArgumentException("No hay un asset Mesh o GameObject en " + ruta);
            return asset;
        }

        // Una caja girada requiere sus OCHO esquinas; transformar sólo min/max pierde extremos.
        static Bounds TransformarCaja(Bounds caja, Matrix4x4 matriz)
        {
            var resultado = new Bounds(matriz.MultiplyPoint3x4(caja.min), Vector3.zero);
            for (int i = 0; i < 8; i++)
                resultado.Encapsulate(matriz.MultiplyPoint3x4(new Vector3(
                    (i & 1) == 0 ? caja.min.x : caja.max.x,
                    (i & 2) == 0 ? caja.min.y : caja.max.y,
                    (i & 4) == 0 ? caja.min.z : caja.max.z)));
            return resultado;
        }

        static Bounds CajaLocal(UnityEngine.Object asset)
        {
            if (asset is Mesh malla) return malla.bounds;
            var objeto = (GameObject)asset;
            var filtros = objeto.GetComponentsInChildren<MeshFilter>(true).Where(f => f.sharedMesh != null).ToArray();
            if (filtros.Length == 0) throw new ArgumentException("El asset no contiene mallas: " + objeto.name);
            Bounds? caja = null;
            foreach (var filtro in filtros)
            {
                var parte = TransformarCaja(filtro.sharedMesh.bounds,
                    objeto.transform.worldToLocalMatrix * filtro.transform.localToWorldMatrix);
                if (caja == null) caja = parte;
                else { var union = caja.Value; union.Encapsulate(parte); caja = union; }
            }
            return caja.Value;
        }

        static Respuesta ResolverAsset(Pedido p)
        {
            if (string.IsNullOrWhiteSpace(p.nombre)) throw new ArgumentException("Falta el nombre del asset.");
            string ruta = p.nombre;
            if (!ruta.StartsWith("Assets/", StringComparison.OrdinalIgnoreCase))
            {
                var candidatas = AssetDatabase.FindAssets("t:Mesh").Concat(AssetDatabase.FindAssets("t:GameObject"))
                    .Select(AssetDatabase.GUIDToAssetPath).Distinct()
                    .Where(r => string.Equals(Path.GetFileNameWithoutExtension(r), p.nombre, StringComparison.OrdinalIgnoreCase))
                    .Where(r => { var a = AssetDatabase.LoadMainAssetAtPath(r); return a is Mesh || a is GameObject; })
                    .OrderBy(r => r, StringComparer.Ordinal).ToArray();
                if (candidatas.Length == 0) throw new ArgumentException("No hay assets con nombre " + p.nombre);
                if (candidatas.Length != 1)
                    throw new ArgumentException("Hay varios assets con nombre " + p.nombre + ": " + string.Join(", ", candidatas));
                ruta = candidatas[0];
            }
            var asset = CargarAsset(ruta);
            var caja = CajaLocal(asset);
            return new Respuesta { ruta = AssetDatabase.GetAssetPath(asset), min = ANucleo(caja.min), max = ANucleo(caja.max) };
        }

        static Respuesta Colocar(Pedido p)
        {
            if (string.IsNullOrWhiteSpace(p.nombre)) throw new ArgumentException("Falta el nombre del grupo.");
            if (p.instancias == null) throw new ArgumentException("Faltan las instancias.");
            foreach (var instancia in p.instancias)
            {
                if (instancia == null) throw new ArgumentException("Instancia inválida.");
                Validar(new[] { instancia.pos, instancia.escala }, 3, "pos/escala");
                if (float.IsNaN(instancia.yaw) || float.IsInfinity(instancia.yaw))
                    throw new ArgumentException("Yaw inválido.");
            }
            var asset = CargarAsset(p.ruta);
            var local = CajaLocal(asset);
            var raiz = Raiz(true);
            var grupo = new GameObject(p.nombre) { hideFlags = HideFlags.DontSaveInEditor };
            grupo.transform.SetParent(raiz, false);
            var cajas = new List<Caja>();
            try
            {
                foreach (var instancia in p.instancias)
                {
                    GameObject hijo;
                    if (asset is Mesh malla)
                    {
                        hijo = new GameObject("Instancia " + cajas.Count);
                        hijo.transform.SetParent(grupo.transform, false);
                        hijo.AddComponent<MeshFilter>().sharedMesh = malla;
                        hijo.AddComponent<MeshRenderer>().sharedMaterial =
                            AssetDatabase.GetBuiltinExtraResource<Material>("Default-Material.mat");
                    }
                    else hijo = (GameObject)PrefabUtility.InstantiatePrefab(asset, grupo.transform);
                    foreach (var t in hijo.GetComponentsInChildren<Transform>(true))
                        t.gameObject.hideFlags |= HideFlags.DontSaveInEditor;
                    hijo.transform.localPosition = AUnity(instancia.pos);
                    hijo.transform.localRotation = Quaternion.Euler(0, -instancia.yaw, 0);
                    hijo.transform.localScale = new Vector3(instancia.escala[0], instancia.escala[2], instancia.escala[1]);
                    var mundo = TransformarCaja(local, hijo.transform.localToWorldMatrix);
                    cajas.Add(new Caja { min = ANucleo(mundo.min), max = ANucleo(mundo.max) });
                }
                var viejo = raiz.Cast<Transform>().FirstOrDefault(t => t != grupo.transform && t.name == p.nombre);
                if (viejo != null) Borrar(viejo.gameObject);
            }
            catch { Borrar(grupo); throw; }
            SceneView.RepaintAll();
            return new Respuesta { nodo = grupo.name, instancias = cajas.ToArray() };
        }

        static bool EsPreview(Transform objeto)
        {
            for (var t = objeto; t != null; t = t.parent)
                if ((t.gameObject.hideFlags & HideFlags.DontSaveInEditor) != 0) return true;
            return false;
        }

        // Contra TODAS las mallas de la escena, incluido lo que la corrida en curso ya colocó (un
        // piso y los muebles encima, en un mismo grafo). El Preview de la corrida anterior no está:
        // el núcleo lo descarta al empezar cada Run (docs/contrato-motor.md).
        // En double: Vector3 es float32 y un rayo de ±10 km (el de `place surface`) pierde ahí un
        // milímetro (medido en Godot: el piso en -5 cm daba -4,98).
        // ponytail: O(triángulos) por rayo; una BVH si la escena pesa.
        static Respuesta Raycast(Pedido p)
        {
            if (p.rayos == null) throw new ArgumentException("Faltan los rayos.");
            var filtros = SceneManager.GetActiveScene().GetRootGameObjects()
                .SelectMany(g => g.GetComponentsInChildren<MeshFilter>(true))
                .Where(f => f.sharedMesh != null && f.GetComponent<Renderer>() != null).ToArray();
            var geometria = filtros.Select(f => (
                vertices: f.sharedMesh.vertices.Select(v => D(f.transform.localToWorldMatrix, v)).ToArray(),
                indices: f.sharedMesh.triangles)).ToArray();
            var golpes = new List<Golpe>();
            foreach (var rayo in p.rayos)
            {
                if (rayo == null) throw new ArgumentException("Rayo inválido.");
                Validar(new[] { rayo.desde, rayo.hacia }, 3, "desde/hacia");
                // Núcleo (cm, Z arriba) → Unity (m, Y arriba), en double.
                var o = new[] { rayo.desde[0] * 0.01, rayo.desde[2] * 0.01, rayo.desde[1] * 0.01 };
                var d = new[] { rayo.hacia[0] * 0.01 - o[0], rayo.hacia[2] * 0.01 - o[1], rayo.hacia[1] * 0.01 - o[2] };
                double mejor = double.MaxValue;
                var golpe = new Golpe();
                foreach (var malla in geometria)
                for (int i = 0; i < malla.indices.Length; i += 3)
                {
                    var a = malla.vertices[malla.indices[i]];
                    var e1 = Resta(malla.vertices[malla.indices[i + 1]], a);
                    var e2 = Resta(malla.vertices[malla.indices[i + 2]], a);
                    var q = Cruz(d, e2);
                    double det = Punto(e1, q);
                    if (Math.Abs(det) < 1e-18) continue;
                    var t = Resta(o, a);
                    double u = Punto(t, q) / det;
                    if (u < 0 || u > 1) continue;
                    var r = Cruz(t, e1);
                    double v = Punto(d, r) / det;
                    if (v < 0 || u + v > 1) continue;
                    double f = Punto(e2, r) / det;   // fracción del segmento desde→hacia
                    if (f < 0 || f > 1 || f >= mejor) continue;
                    mejor = f;
                    var n = Cruz(e1, e2);
                    double largo = Math.Sqrt(Punto(n, n));
                    if (Punto(n, d) > 0) largo = -largo;   // del lado de `desde`
                    golpe = new Golpe { golpe = true,
                        punto = new[] { Math.Round((o[0] + d[0] * f) * 100.0, 3), Math.Round((o[2] + d[2] * f) * 100.0, 3),
                                        Math.Round((o[1] + d[1] * f) * 100.0, 3) },
                        normal = new[] { Math.Round(n[0] / largo, 4), Math.Round(n[2] / largo, 4), Math.Round(n[1] / largo, 4) } };
                }
                golpes.Add(golpe);
            }
            return new Respuesta { golpes = golpes.ToArray() };
        }

        static double[] D(Matrix4x4 m, Vector3 v)
        {
            return new[] { (double)m.m00 * v.x + (double)m.m01 * v.y + (double)m.m02 * v.z + m.m03,
                           (double)m.m10 * v.x + (double)m.m11 * v.y + (double)m.m12 * v.z + m.m13,
                           (double)m.m20 * v.x + (double)m.m21 * v.y + (double)m.m22 * v.z + m.m23 };
        }
        static double[] Resta(double[] a, double[] b) { return new[] { a[0] - b[0], a[1] - b[1], a[2] - b[2] }; }
        static double[] Cruz(double[] a, double[] b)
        { return new[] { a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0] }; }
        static double Punto(double[] a, double[] b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }

        static void Borrar(GameObject objeto)
        {
            var mallas = objeto.GetComponentsInChildren<MeshFilter>(true)
                .Select(f => f.sharedMesh).Where(m => m != null && !AssetDatabase.Contains(m)).Distinct().ToArray();
            UnityEngine.Object.DestroyImmediate(objeto);
            foreach (var malla in mallas) UnityEngine.Object.DestroyImmediate(malla);
        }

        static Respuesta Fijar()
        {
            var raiz = Raiz(false);
            if (raiz == null) return new Respuesta { fijados = 0 };
            if (!AssetDatabase.IsValidFolder("Assets/Scenes")) AssetDatabase.CreateFolder("Assets", "Scenes");
            if (!AssetDatabase.IsValidFolder(CarpetaMallas)) AssetDatabase.CreateFolder("Assets", "JamGenerado");
            foreach (var filtro in raiz.GetComponentsInChildren<MeshFilter>(true))
            {
                // Una escena no conserva un Mesh transitorio: se guarda como asset primero.
                if (filtro.sharedMesh != null && !AssetDatabase.Contains(filtro.sharedMesh))
                    AssetDatabase.CreateAsset(filtro.sharedMesh,
                        AssetDatabase.GenerateUniqueAssetPath(CarpetaMallas + "/Malla.asset"));
            }
            foreach (var t in raiz.GetComponentsInChildren<Transform>(true))
                t.gameObject.hideFlags &= ~HideFlags.DontSaveInEditor;
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
