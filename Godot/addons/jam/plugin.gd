@tool
extends EditorPlugin
## Adaptador de Jam para Godot (tarea `base-comun`, paso 2).
##
## El núcleo de Jam corre FUERA de Godot (Python) y le pide a este plugin sólo las PRIMITIVAS del
## contrato, por TCP en 127.0.0.1:8792: una línea de JSON por pedido, otra por respuesta. No hay
## evaluación arbitraria de código: la lista de operaciones es cerrada (`_atender`).
##
## El contrato habla en el marco del núcleo —el de Unreal: centímetros, Z arriba, mano izquierda—.
## Godot usa metros, Y arriba, mano derecha. La traducción intercambia Y y Z y divide por 100; como
## ese intercambio es una REFLEXIÓN, da vuelta el orden de los triángulos, y por eso cada triángulo se
## invierte. Medido, no deducido: en el BoxMesh del propio Godot, (c-a)×(b-a) apunta afuera en los
## 12 triángulos, la misma fórmula que Unreal en SU marco.

const PUERTO := 8792
const CONTRATO := 1
const PREVIEW := "JamPreview"

var _srv := TCPServer.new()
var _clientes: Array = []


func _enter_tree() -> void:
	var err := _srv.listen(PUERTO, "127.0.0.1")
	if err == OK:
		print("JAM_GODOT escuchando en 127.0.0.1:%d (contrato %d)" % [PUERTO, CONTRATO])
	else:
		push_warning("JAM_GODOT no pude abrir el puerto %d (%s)" % [PUERTO, error_string(err)])


func _exit_tree() -> void:
	for c in _clientes:
		c.peer.disconnect_from_host()
	_clientes.clear()
	_srv.stop()


func _process(_delta: float) -> void:
	while _srv.is_connection_available():
		_clientes.append({"peer": _srv.take_connection(), "buf": ""})
	for c in _clientes.duplicate():
		var p: StreamPeerTCP = c.peer
		p.poll()
		if p.get_status() != StreamPeerTCP.STATUS_CONNECTED:
			_clientes.erase(c)
			continue
		var n := p.get_available_bytes()
		if n <= 0:
			continue
		var r: Array = p.get_data(n)
		c.buf += (r[1] as PackedByteArray).get_string_from_utf8()
		while c.buf.find("\n") >= 0:
			var corte: int = c.buf.find("\n")
			var linea: String = c.buf.substr(0, corte)
			c.buf = c.buf.substr(corte + 1)
			var respuesta := _atender(JSON.parse_string(linea))
			p.put_data((JSON.stringify(respuesta) + "\n").to_utf8_buffer())


func _atender(pedido) -> Dictionary:
	if typeof(pedido) != TYPE_DICTIONARY or not pedido.has("op"):
		return {"ok": false, "error": "pedido inválido: se esperaba {\"op\": …}"}
	match pedido.op:
		"hola":
			return {"ok": true, "motor": "godot", "contrato": CONTRATO,
				"version": Engine.get_version_info().string,
				"primitivas": ["mostrar_malla", "descartar", "fijar", "hechos"]}
		"mostrar_malla":
			return _mostrar_malla(pedido)
		"descartar":
			var raiz := _raiz_preview(false)
			var cuantos := 0
			if raiz:
				for hijo in raiz.get_children():
					hijo.free()
					cuantos += 1
			return {"ok": true, "descartados": cuantos}
		"fijar":
			return _fijar()
		"hechos":
			var lista: Array = []
			var raiz := _raiz_preview(false)
			if raiz:
				for hijo in raiz.get_children():
					if hijo is MeshInstance3D:
						lista.append({"nodo": str(hijo.name), "hechos": _hechos(hijo)})
			return {"ok": true, "mallas": lista}
	return {"ok": false, "error": "operación desconocida: %s" % str(pedido.op)}


# ---- marco del núcleo (cm, Z arriba) ↔ Godot (m, Y arriba) ----

func _a_godot(p: Array) -> Vector3:
	return Vector3(p[0], p[2], p[1]) * 0.01


func _a_nucleo(v: Vector3) -> Array:
	return [v.x * 100.0, v.z * 100.0, v.y * 100.0]


func _escena() -> Node:
	var raiz := EditorInterface.get_edited_scene_root()
	if raiz == null and ResourceLoader.exists("res://main.tscn"):
		EditorInterface.open_scene_from_path("res://main.tscn")
		raiz = EditorInterface.get_edited_scene_root()
	return raiz


func _raiz_preview(crear: bool) -> Node3D:
	var escena := _escena()
	if escena == null:
		return null
	var raiz := escena.get_node_or_null(PREVIEW) as Node3D
	if raiz == null and crear:
		raiz = Node3D.new()
		raiz.name = PREVIEW
		escena.add_child(raiz)   # sin owner: el Preview no se guarda hasta «fijar»
	return raiz


func _mostrar_malla(pedido: Dictionary) -> Dictionary:
	var m: Dictionary = pedido.get("malla", {})
	var raiz := _raiz_preview(true)
	if raiz == null:
		return {"ok": false, "error": "no hay una escena abierta en el editor (ni res://main.tscn)"}
	var verts := PackedVector3Array()
	for p in m.get("vertices", []):
		verts.append(_a_godot(p))
	var norms := PackedVector3Array()
	for p in m.get("normales", []):
		norms.append(Vector3(p[0], p[2], p[1]))
	var uvs := PackedVector2Array()
	for p in m.get("uv0", []):
		uvs.append(Vector2(p[0], p[1]))
	var idx := PackedInt32Array()
	for t in m.get("triangulos", []):
		idx.append(int(t[0]))
		idx.append(int(t[2]))   # invertido: la traducción de marco es una reflexión
		idx.append(int(t[1]))
	if verts.is_empty() or idx.is_empty():
		return {"ok": false, "error": "la malla llegó vacía"}
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_INDEX] = idx
	if norms.size() == verts.size():
		arrays[Mesh.ARRAY_NORMAL] = norms
	if uvs.size() == verts.size():
		arrays[Mesh.ARRAY_TEX_UV] = uvs
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var nombre := str(pedido.get("nombre", "JamPreview"))
	var viejo := raiz.get_node_or_null(nombre)
	if viejo:
		viejo.free()   # mismo nombre = mismo nodo: correr dos veces no apila copias
	var mi := MeshInstance3D.new()
	mi.name = nombre
	mi.mesh = mesh
	raiz.add_child(mi)
	return {"ok": true, "nodo": str(mi.name), "hechos": _hechos(mi)}


func _fijar() -> Dictionary:
	var escena := _escena()
	var raiz := _raiz_preview(false)
	if escena == null or raiz == null:
		return {"ok": true, "fijados": 0}
	raiz.owner = escena
	for hijo in raiz.get_children():
		hijo.owner = escena
	var err := EditorInterface.save_scene()
	return {"ok": err == OK, "fijados": raiz.get_child_count(), "error": error_string(err)}


## Los hechos de una malla, MEDIDOS sobre lo que Godot guardó (no sobre lo que se le mandó) y
## traducidos al marco del núcleo, para compararlos tal cual con los que mide Unreal.
func _hechos(mi: MeshInstance3D) -> Dictionary:
	var arrays: Array = mi.mesh.surface_get_arrays(0)
	var v: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
	var posiciones := {}
	for p in v:
		var n := _a_nucleo(p)
		posiciones["%.3f,%.3f,%.3f" % [n[0], n[1], n[2]]] = true
	var aabb := mi.mesh.get_aabb()
	var a := _a_nucleo(aabb.position)
	var b := _a_nucleo(aabb.end)
	var centro := aabb.get_center()
	var area := 0.0
	var afuera := 0
	for t in range(idx.size() / 3):
		var p0 := v[idx[3 * t]]
		var p1 := v[idx[3 * t + 1]]
		var p2 := v[idx[3 * t + 2]]
		var cara := (p2 - p0).cross(p1 - p0)   # la cara que Godot dibuja (medido en su BoxMesh)
		area += cara.length() / 2.0
		if cara.dot((p0 + p1 + p2) / 3.0 - centro) > 0.0:
			afuera += 1
	return {"triangulos": idx.size() / 3, "posiciones": posiciones.size(),
		"min": [snappedf(minf(a[0], b[0]), 0.001), snappedf(minf(a[1], b[1]), 0.001), snappedf(minf(a[2], b[2]), 0.001)],
		"max": [snappedf(maxf(a[0], b[0]), 0.001), snappedf(maxf(a[1], b[1]), 0.001), snappedf(maxf(a[2], b[2]), 0.001)],
		"area": snappedf(area * 10000.0, 0.001), "caras_hacia_afuera": afuera}
