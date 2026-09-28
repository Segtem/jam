using System;
using System.Runtime.Serialization;
using UnityEditor;
using UnityEngine;

namespace Jam
{
    [Serializable, DataContract]
    public sealed class MedicionCubo
    {
        [DataMember] public int triangulos;
        [DataMember] public int cruz_ba_ca_afuera;
        [DataMember] public int cruz_ca_ba_afuera;
    }

    public static class JamMedicion
    {
        // Control independiente: índices del cubo NATIVO, sin usar normales de sombreado
        // ni los buffers que llegan de Python. Se repite al iniciar cada servidor.
        public static MedicionCubo MedirCubo()
        {
            var cubo = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cubo.hideFlags = HideFlags.HideAndDontSave;
            try
            {
                var m = cubo.GetComponent<MeshFilter>().sharedMesh;
                var v = m.vertices;
                var t = m.triangles;
                var r = new MedicionCubo { triangulos = t.Length / 3 };
                for (int i = 0; i < t.Length; i += 3)
                {
                    var a = v[t[i]];
                    var b = v[t[i + 1]];
                    var c = v[t[i + 2]];
                    var radial = (a + b + c) / 3f - m.bounds.center;
                    if (Vector3.Dot(Vector3.Cross(b - a, c - a), radial) > 0)
                        r.cruz_ba_ca_afuera++;
                    if (Vector3.Dot(Vector3.Cross(c - a, b - a), radial) > 0)
                        r.cruz_ca_ba_afuera++;
                }
                return r;
            }
            finally { UnityEngine.Object.DestroyImmediate(cubo); }
        }

        public static void Ejecutar()
        {
            Debug.Log("JAM_UNITY_CUBO " + JsonUtility.ToJson(MedirCubo()));
            EditorApplication.Exit(0);
        }
    }
}
