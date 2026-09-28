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


const PUERTO_EDITOR := 8795
var _pid_editor := -1


func _enter_tree() -> void:
	add_tool_menu_item("Jam: editor de nodos", _abrir_editor)
	var err := _srv.listen(PUERTO, "127.0.0.1")
	if err == OK:
		print("JAM_GODOT escuchando en 127.0.0.1:%d (contrato %d)" % [PUERTO, CONTRATO])
	else:
		push_warning("JAM_GODOT no pude abrir el puerto %d (%s)" % [PUERTO, error_string(err)])


## El editor de nodos de Jam (la web): lo sirve el núcleo en un proceso aparte, que habla con este
## plugin por el contrato. Si ya está corriendo, sólo se abre otra ventana.
func _abrir_editor() -> void:
	# Dónde está el núcleo y con qué Python: los escribe `tools/instalar.py` en project.godot
	# ([jam] nucleo_python / python). Sin instalar, el lugar de la máquina de desarrollo.
	var casa := OS.get_environment("USERPROFILE") if OS.get_name() == "Windows" else OS.get_environment("HOME")
	var ruta := str(ProjectSettings.get_setting("jam/nucleo_python", casa + "/Dev/jam/Content/Python"))
	var python := str(ProjectSettings.get_setting("jam/python",
		"python" if OS.get_name() == "Windows" else "python3"))
	var codigo := "import sys; sys.path.insert(0, %s); from jam import servidor; " % JSON.stringify(ruta)
	if _pid_editor > 0 and OS.is_process_running(_pid_editor):
		codigo += "servidor.abrir_ventana('http://127.0.0.1:%d/')" % PUERTO_EDITOR
		OS.create_process(python, ["-c", codigo])
		return
	codigo += "servidor.main(['--motor', 'godot', '--abrir'])"
	_pid_editor = OS.create_process(python, ["-c", codigo])
	if _pid_editor <= 0:
		push_error("JAM_GODOT no pude lanzar «%s»: instalá Python 3.11+ o fijá jam/python en Configuración del proyecto" % python)
		return
	print("JAM_GODOT editor de nodos en http://127.0.0.1:%d/ (pid %d)" % [PUERTO_EDITOR, _pid_editor])


func _exit_tree() -> void:
	remove_tool_menu_item("Jam: editor de nodos")
	if _pid_editor > 0 and OS.is_process_running(_pid_editor):
		OS.kill(_pid_editor)
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
				"primitivas": ["mostrar_malla", "descartar", "fijar", "hechos",
					"guardar_malla", "resolver_asset", "colocar", "raycast"]}
		"mostrar_malla":
			return _mostrar_malla(pedido)
		"descartar":
			# Sólo lo que no se fijó: lo fijado ya es escena (tiene dueño) y descartar no lo toca.
			var raiz := _raiz_preview(false)
			var cuantos := 0
			if raiz:
				for hijo in raiz.get_children():
					if hijo.owner == null:
						hijo.free()
						cuantos += 1
			return {"ok": true, "descartados": cuantos}
		"fijar":
			return _fijar()
		"guardar_malla":
			return _guardar_malla(pedido)
		"resolver_asset":
			return _resolver_asset(str(pedido.get("nombre", "")))
		"colocar":
			return _colocar(pedido)
		"raycast":
			var golpes: Array = []
			for rayo in pedido.get("rayos", []):
				golpes.append(_raycast(_a_godot(rayo.desde), _a_godot(rayo.hacia)))
			return {"ok": true, "golpes": golpes}
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
	var raiz := _raiz_preview(true)
	if raiz == null:
		return {"ok": false, "error": "no hay una escena abierta en el editor (ni res://main.tscn)"}
	var mesh := _armar_malla(pedido.get("malla", {}))
	if mesh == null:
		return {"ok": false, "error": "la malla llegó vacía"}
	var nombre := str(pedido.get("nombre", "JamPreview"))
	var viejo := raiz.get_node_or_null(nombre)
	if viejo:
		viejo.free()   # mismo nombre = mismo nodo: correr dos veces no apila copias
	var mi := MeshInstance3D.new()
	mi.name = nombre
	mi.mesh = mesh
	raiz.add_child(mi)
	return {"ok": true, "nodo": str(mi.name), "hechos": _hechos(mi)}


func _armar_malla(m: Dictionary) -> ArrayMesh:
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
		return null
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
	return mesh


func _fijar() -> Dictionary:
	var escena := _escena()
	var raiz := _raiz_preview(false)
	if escena == null or raiz == null:
		return {"ok": true, "fijados": 0}
	raiz.owner = escena
	_poseer(raiz, escena)
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
		# `+ 0.0` convierte -0 en +0: un vértice en el eje (ápice, polo) sale como -0.0000001 y
		# «%.3f» lo escribiría «-0.000», partiendo un mismo punto en dos.
		posiciones["%.3f,%.3f,%.3f" % [snappedf(n[0], 0.001) + 0.0, snappedf(n[1], 0.001) + 0.0,
			snappedf(n[2], 0.001) + 0.0]] = true
	var aabb := mi.mesh.get_aabb()
	var a := _a_nucleo(aabb.position)
	var b := _a_nucleo(aabb.end)
	var centro := aabb.get_center()
	var area := 0.0
	var volumen := 0.0   # con signo: positivo sólo si las caras que Godot dibuja miran afuera
	var afuera := 0
	for t in range(idx.size() / 3):
		var p0 := v[idx[3 * t]]
		var p1 := v[idx[3 * t + 1]]
		var p2 := v[idx[3 * t + 2]]
		var cara := (p2 - p0).cross(p1 - p0)   # la cara que Godot dibuja (medido en su BoxMesh)
		area += cara.length() / 2.0
		volumen += p0.dot(cara) / 6.0
		if cara.dot((p0 + p1 + p2) / 3.0 - centro) > 0.0:
			afuera += 1
	return {"triangulos": idx.size() / 3, "posiciones": posiciones.size(),
		"min": [snappedf(minf(a[0], b[0]), 0.001), snappedf(minf(a[1], b[1]), 0.001), snappedf(minf(a[2], b[2]), 0.001)],
		"max": [snappedf(maxf(a[0], b[0]), 0.001), snappedf(maxf(a[1], b[1]), 0.001), snappedf(maxf(a[2], b[2]), 0.001)],
		"area": snappedf(area * 10000.0, 0.001), "volumen": snappedf(volumen * 1000000.0, 0.001),
		"caras_hacia_afuera": afuera}


## Todo lo que cuelga de `nodo` pasa a ser de la escena (se guarda). Dentro de una escena instanciada
## no se entra: sus nodos son de SU escena, y poseerlos los volvería «hijos editables».
func _poseer(nodo: Node, escena: Node) -> void:
	for hijo in nodo.get_children():
		hijo.owner = escena
		if hijo.scene_file_path.is_empty():
			_poseer(hijo, escena)


# ---- colocar (docs/contrato-motor.md) ----

const CARPETA_MALLAS := "res://Jam/Mallas"
const EXTENSIONES := ["tres", "res", "mesh", "obj", "glb", "gltf", "tscn", "scn", "fbx", "blend"]


func _guardar_malla(pedido: Dictionary) -> Dictionary:
	var mesh := _armar_malla(pedido.get("malla", {}))
	if mesh == null:
		return {"ok": false, "error": "la malla llegó vacía"}
	var nombre := str(pedido.get("nombre", "GeneratedMesh")).validate_filename()
	DirAccess.make_dir_recursive_absolute(CARPETA_MALLAS)
	var ruta := "%s/%s.tres" % [CARPETA_MALLAS, nombre]
	var err := ResourceSaver.save(mesh, ruta)
	if err != OK:
		return {"ok": false, "error": "no pude guardar %s (%s)" % [ruta, error_string(err)]}
	mesh.take_over_path(ruta)   # que un load() posterior no devuelva la versión vieja del caché
	EditorInterface.get_resource_filesystem().update_file(ruta)
	return {"ok": true, "ruta": ruta}


func _buscar(carpeta: String, nombre: String, hallados: Array) -> void:
	var dir := DirAccess.open(carpeta)
	if dir == null:
		return
	for sub in dir.get_directories():
		if not sub.begins_with(".") and not (carpeta == "res://" and sub == "addons"):
			_buscar(carpeta.path_join(sub), nombre, hallados)
	for f in dir.get_files():
		if f.get_extension().to_lower() in EXTENSIONES and f.get_basename().to_lower() == nombre:
			hallados.append(carpeta.path_join(f))


## La caja local de lo que se puede colocar: una malla, o las mallas de una escena en el espacio de
## su raíz. Vacía si no hay mallas.
func _caja_local(recurso: Resource) -> AABB:
	if recurso is Mesh:
		return (recurso as Mesh).get_aabb()
	var caja := AABB()
	var hay := false
	if recurso is PackedScene:
		var raiz := (recurso as PackedScene).instantiate()
		var pila := [[raiz, Transform3D.IDENTITY]]
		while not pila.is_empty():
			var par: Array = pila.pop_back()
			var n: Node = par[0]
			var t: Transform3D = par[1]
			if n is Node3D and n != raiz:
				t = t * (n as Node3D).transform
			if n is MeshInstance3D and (n as MeshInstance3D).mesh:
				var c := t * (n as MeshInstance3D).mesh.get_aabb()
				caja = c if not hay else caja.merge(c)
				hay = true
			for h in n.get_children():
				pila.append([h, t])
		raiz.free()
	return caja


func _caja_a_nucleo(c: AABB) -> Dictionary:
	var a := _a_nucleo(c.position)
	var b := _a_nucleo(c.end)
	return {"min": [snappedf(minf(a[0], b[0]), 0.001), snappedf(minf(a[1], b[1]), 0.001), snappedf(minf(a[2], b[2]), 0.001)],
		"max": [snappedf(maxf(a[0], b[0]), 0.001), snappedf(maxf(a[1], b[1]), 0.001), snappedf(maxf(a[2], b[2]), 0.001)]}


func _resolver_asset(nombre: String) -> Dictionary:
	var ruta := nombre
	if not nombre.begins_with("res://"):
		var hallados: Array = []
		_buscar("res://", nombre.to_lower(), hallados)
		if hallados.is_empty():
			return {"ok": false, "error": "no hay ningún asset «%s» en el proyecto" % nombre}
		if hallados.size() > 1:
			return {"ok": false, "error": "«%s» es ambiguo: %s" % [nombre, ", ".join(hallados)]}
		ruta = hallados[0]
	if not ResourceLoader.exists(ruta):
		return {"ok": false, "error": "no existe %s" % ruta}
	var recurso := load(ruta)
	if not (recurso is Mesh or recurso is PackedScene):
		return {"ok": false, "error": "%s no es una malla ni una escena" % ruta}
	return {"ok": true, "ruta": ruta}.merged(_caja_a_nucleo(_caja_local(recurso)))


func _colocar(pedido: Dictionary) -> Dictionary:
	var raiz := _raiz_preview(true)
	if raiz == null:
		return {"ok": false, "error": "no hay una escena abierta en el editor (ni res://main.tscn)"}
	var ruta := str(pedido.get("ruta", ""))
	var recurso: Resource = load(ruta) if ResourceLoader.exists(ruta) else null
	if not (recurso is Mesh or recurso is PackedScene):
		return {"ok": false, "error": "no puedo colocar «%s»: no es una malla ni una escena" % ruta}
	var local := _caja_local(recurso)
	var nombre := str(pedido.get("nombre", "Jam_place"))
	var viejo := raiz.get_node_or_null(nombre)
	if viejo:
		viejo.free()
	var grupo := Node3D.new()
	grupo.name = nombre
	raiz.add_child(grupo)
	var medidas: Array = []
	for i in pedido.get("instancias", []):
		var nodo: Node3D
		if recurso is Mesh:
			nodo = MeshInstance3D.new()
			(nodo as MeshInstance3D).mesh = recurso
		else:
			nodo = (recurso as PackedScene).instantiate()
		var e: Array = i.get("escala", [1, 1, 1])
		# yaw del núcleo (alrededor de Z) = -yaw alrededor de Y: la traducción de marco es una reflexión.
		var giro := Basis(Vector3.UP, deg_to_rad(-float(i.get("yaw", 0.0))))
		nodo.transform = Transform3D(giro * Basis.from_scale(Vector3(e[0], e[2], e[1])), _a_godot(i.pos))
		grupo.add_child(nodo)
		medidas.append(_caja_a_nucleo(nodo.global_transform * local))
	return {"ok": true, "nodo": nombre, "instancias": medidas}


## Las mallas que son suelo: todas las de la escena, incluido lo que la corrida en curso ya colocó
## (un piso y después los muebles, en el mismo grafo). El Preview de la corrida ANTERIOR no está:
## el núcleo lo descarta al empezar cada Run.
func _mallas_de(n: Node, escena: Node, salida: Array) -> void:
	if n is MeshInstance3D and (n as MeshInstance3D).mesh and (n as MeshInstance3D).visible:
		salida.append(n)
	for h in n.get_children():
		_mallas_de(h, escena, salida)


func _raycast(desde: Vector3, hacia: Vector3) -> Dictionary:
	var escena := _escena()
	if escena == null:
		return {"golpe": false}
	var mallas: Array = []
	_mallas_de(escena, escena, mallas)
	var mejor := INF
	var punto := Vector3.ZERO
	var normal := Vector3.ZERO
	for mi in mallas:
		var t: Transform3D = (mi as MeshInstance3D).global_transform
		var inv := t.affine_inverse()
		var a0 := _aplicar64(inv, desde)
		var b0 := _aplicar64(inv, hacia)
		var caras: PackedVector3Array = (mi as MeshInstance3D).mesh.get_faces()
		# ponytail: todas las caras de todas las mallas, O(triángulos); una BVH si la escena pesa.
		for k in range(0, caras.size(), 3):
			var u := _cruce(a0, b0, caras[k], caras[k + 1], caras[k + 2])
			if u < 0.0:
				continue
			# `u` es la fracción del segmento, la misma en local y en mundo (transformación afín).
			var d := u * desde.distance_to(hacia)
			if d < mejor:
				mejor = d
				punto = _lerp64(desde, hacia, u)
				var n := (caras[k + 1] - caras[k]).cross(caras[k + 2] - caras[k])
				normal = (t.basis.inverse().transposed() * n).normalized()
	if mejor == INF:
		return {"golpe": false}
	if normal.dot(desde - punto) < 0.0:
		normal = -normal
	var pn := _a_nucleo(punto)
	return {"golpe": true, "punto": [snappedf(pn[0], 0.001), snappedf(pn[1], 0.001), snappedf(pn[2], 0.001)],
		"normal": [snappedf(normal.x, 0.0001), snappedf(normal.z, 0.0001), snappedf(normal.y, 0.0001)]}


## Möller–Trumbore con escalares de 64 bits: `Vector3` es float32 y un rayo de ±10 km (el de
## `place surface`) pierde ahí un milímetro —se midió: el piso en -5 cm daba -4,98—. Devuelve la
## fracción del segmento `a→b` donde cruza el triángulo, o -1.
func _cruce(a: Array, b: Array, p0: Vector3, p1: Vector3, p2: Vector3) -> float:
	var ox: float = a[0]; var oy: float = a[1]; var oz: float = a[2]
	var dx: float = b[0] - ox; var dy: float = b[1] - oy; var dz: float = b[2] - oz
	var e1x: float = p1.x - p0.x; var e1y: float = p1.y - p0.y; var e1z: float = p1.z - p0.z
	var e2x: float = p2.x - p0.x; var e2y: float = p2.y - p0.y; var e2z: float = p2.z - p0.z
	var px: float = dy * e2z - dz * e2y; var py: float = dz * e2x - dx * e2z; var pz: float = dx * e2y - dy * e2x
	var det: float = e1x * px + e1y * py + e1z * pz
	if absf(det) < 1e-18:
		return -1.0
	var tx: float = ox - p0.x; var ty: float = oy - p0.y; var tz: float = oz - p0.z
	var u: float = (tx * px + ty * py + tz * pz) / det
	if u < 0.0 or u > 1.0:
		return -1.0
	var qx: float = ty * e1z - tz * e1y; var qy: float = tz * e1x - tx * e1z; var qz: float = tx * e1y - ty * e1x
	var v: float = (dx * qx + dy * qy + dz * qz) / det
	if v < 0.0 or u + v > 1.0:
		return -1.0
	var f: float = (e2x * qx + e2y * qy + e2z * qz) / det
	return f if f >= 0.0 and f <= 1.0 else -1.0


## `t * p` con la aritmética en 64 bits (las entradas de la matriz siguen siendo float32).
func _aplicar64(t: Transform3D, p: Vector3) -> Array:
	var x: float = p.x; var y: float = p.y; var z: float = p.z
	var c0 := t.basis.x; var c1 := t.basis.y; var c2 := t.basis.z
	return [c0.x * x + c1.x * y + c2.x * z + t.origin.x, c0.y * x + c1.y * y + c2.y * z + t.origin.y,
		c0.z * x + c1.z * y + c2.z * z + t.origin.z]


func _lerp64(a: Vector3, b: Vector3, f: float) -> Vector3:
	# El punto se arma en 64 bits y recién al final vuelve a float32: cerca del golpe sobra precisión.
	return Vector3(float(a.x) + (float(b.x) - float(a.x)) * f, float(a.y) + (float(b.y) - float(a.y)) * f,
		float(a.z) + (float(b.z) - float(a.z)) * f)
