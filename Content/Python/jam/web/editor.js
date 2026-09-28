// El editor de nodos de Jam en la web (etapa 3 de `fuera-del-motor`).
//
// Un solo editor para los tres motores: habla `POST /api/<función>` con `{args: [...]}` y recibe
// `{resultado: "<json>"}`. Detrás está Unreal (`jam.web`, la puerta dentro del editor) o el núcleo de
// Jam con Godot/Unity del otro lado (`jam.servidor`); el editor no sabe cuál.
//
// El canvas es LiteGraph.js (MIT, el de ComfyUI). El grafo de Jam es el MISMO JSON que guarda el Graph
// de Slate: `{nodes: {nombre: {verb, params, x, y, bypass, debug}}, edges: [[origen, pin, destino, pin]]}`.
// El nombre de cada nodo es su id, el que el texto escribe a la izquierda del «=».
"use strict";

const $ = (s) => document.querySelector(s);
const ESTADOS = { ok: "#3aa45a", aviso: "#d8b820", warn: "#e08a2a", error: "#d4453c",
                  cancelado: "#8c4a44", omitido: "#6f6d68", bypass: "#4a78d4", info: "#5a7fa0" };
// Los nodos de valor que OPERAN (sumar, descomponer una matriz…) reciben sus operandos por cable.
const VALORES_SIMPLES = new Set(["number", "text", "boolean", "math"]);
const IDENT = /^[A-Za-z_][A-Za-z0-9_]*$/;

let SPEC = null, POR_VERBO = {}, grafo, lienzo;
let ultimoJson = "", textoEditado = false, pausa = false;

// ---------------------------------------------------------------- API

async function api(fn, ...args) {
  const r = await fetch(`/api/${fn}`, { method: "POST", body: JSON.stringify({ args }) });
  if (!r.ok) throw new Error(`${fn}: HTTP ${r.status}`);
  const cuerpo = await r.json();
  return typeof cuerpo.resultado === "string" ? JSON.parse(cuerpo.resultado) : cuerpo.resultado;
}

function reportar(texto, clase) {
  const el = $("#reporte");
  el.innerHTML = "";
  for (const linea of String(texto || "").split("\n")) {
    const div = document.createElement("div");
    div.textContent = linea;
    if (clase) div.className = clase;
    else if (/\[error\]|✗|no disponible/.test(linea)) div.className = "error";
    else if (/✓/.test(linea)) div.className = "ok";
    el.appendChild(div);
  }
}

// ---------------------------------------------------------------- tipos de nodo desde el spec

function tipoDeSlot(tipo) {
  if (!tipo || tipo === "*") return 0;           // comodín: LiteGraph acepta cualquiera
  return tipo;
}

function registrarNodos() {
  LiteGraph.clearRegisteredTypes && LiteGraph.clearRegisteredTypes();
  for (const t of SPEC.tools) {
    POR_VERBO[t.verbo] = t;
    // Los nodos de DATOS que operan (sumar, armar un vector, descomponer una matriz…) reciben sus
    // operandos por cable: cada parámetro es además un pin. Los demás, sólo si se lo pide el menú.
    const operador = t.seccion === "Datos" && !VALORES_SIMPLES.has(t.verbo);
    function Nodo() {
      this.properties = { verbo: t.verbo, nombre: "" };
      const esEntradaAsset = t.in_name === "A" && t.asset_row;
      if (!t.source && !esEntradaAsset) {
        const tipos = [t.in_name, ...(t.in_accepts || [])].filter(Boolean).join(",");
        this.addInput("in", tipoDeSlot(tipos));
        // Variádico (mesh_merge…): en LiteGraph una entrada lleva UN cable, en Jam el pin «in» lleva
        // varios en orden. Se muestran varias entradas «in» y siempre queda una libre al final.
        if (t.aridad === -1) this.addInput("in", tipoDeSlot(tipos));
      }
      if (t.asset_row) this.addInput(esEntradaAsset ? "in" : "asset", "A");
      for (const p of t.params || []) {
        if (p.data_type) { this.addInput(p.nombre, tipoDeSlot(p.data_type)); continue; }
        if (operador && p.nombre !== "name") this.addInput(p.nombre, 0);
        this.agregarControl(p);
      }
      this.addOutput("out", tipoDeSlot(t.out_name));
      for (const o of t.outs || []) this.addOutput(o.name, tipoDeSlot(o.tipo));
      this.size = this.computeSize();
      this.size[0] = Math.max(this.size[0], 200);
      if (t.disponible === false) {
        this.color = "#3a3030"; this.bgcolor = "#2a2525";
      }
    }
    Nodo.title = t.label || t.verbo;
    Nodo.desc = t.doc;
    Nodo.prototype.agregarControl = function (p) {
      const cambio = () => cambioEnElGrafo();
      if (p.opciones && p.opciones.length) {
        this.addWidget("combo", p.nombre, p.default, cambio, { values: p.opciones.map(String) });
      } else if (p.tipo === "bool") {
        this.addWidget("toggle", p.nombre, String(p.default).toLowerCase() === "true", cambio);
      } else if (p.tipo === "int") {
        this.addWidget("number", p.nombre, Number(p.default), cambio, { precision: 0, step: 10 });
      } else if (p.tipo === "float") {
        this.addWidget("number", p.nombre, Number(p.default), cambio, { precision: 3, step: 10 });
      } else {
        this.addWidget("text", p.nombre, p.default, cambio);
      }
    };
    Nodo.prototype.onConnectionsChange = function () {
      if (t.aridad !== -1) return;
      const ins = this.inputs.filter((i) => i.name === "in");
      if (ins.every((i) => i.link != null)) this.addInput("in", ins[0].type);
    };
    Nodo.prototype.onAdded = function () {
      if (!this.properties.nombre) this.properties.nombre = nombreNuevo(t.verbo);
      this.actualizarTitulo();
    };
    Nodo.prototype.actualizarTitulo = function () {
      const etiqueta = t.label || t.verbo;
      this.title = this.properties.nombre === etiqueta ? etiqueta : `${this.properties.nombre} · ${etiqueta}`;
    };
    Nodo.prototype.onDrawForeground = function (ctx) {
      const r = this.resultado;
      if (!r && t.disponible !== false) return;
      ctx.font = "11px sans-serif";
      ctx.fillStyle = r ? (ESTADOS[r.estado] || "#aaa") : "#d4453c";
      const texto = r ? r.texto : `no disponible en este motor: ${t.porque}`;
      ctx.fillText(String(texto).split("\n")[0].slice(0, 70), 4, this.size[1] + 14);
    };
    Nodo.prototype.getExtraMenuOptions = function () {
      const nodo = this;
      const opciones = [
        { content: "Renombrar…", callback: () => renombrar(nodo) },
        { content: nodo.properties.bypass ? "Quitar bypass" : "Bypass",
          callback: () => { nodo.properties.bypass = !nodo.properties.bypass; nodo.mode = nodo.properties.bypass ? 4 : 0; cambioEnElGrafo(); } },
      ];
      const libres = (t.params || []).filter((p) => !p.data_type && nodo.findInputSlot(p.nombre) < 0);
      if (libres.length) {
        opciones.push(null, { content: "Cablear un parámetro", has_submenu: true,
          submenu: { options: libres.map((p) => ({ content: p.nombre,
            callback: () => { nodo.addInput(p.nombre, 0); nodo.setDirtyCanvas(true, true); } })) } });
      }
      return opciones;
    };
    LiteGraph.registerNodeType(`${t.cat || "Otros"}/${t.verbo}`, Nodo);
  }
}

// ---------------------------------------------------------------- nombres

function nombresUsados() {
  return new Set((grafo._nodes || []).map((n) => n.properties && n.properties.nombre).filter(Boolean));
}

// La misma regla que `jam.texto.nombre_nuevo`: el verbo, y `_2`, `_3`… si ya existe; nunca renombra.
function nombreNuevo(verbo) {
  const usados = nombresUsados();
  let base = String(verbo).startsWith("fn:") ? "funcion" : String(verbo).replace(/\W/g, "_");
  if (!IDENT.test(base)) base = "nodo_" + base;
  if (!usados.has(base)) return base;
  let i = 2;
  while (usados.has(`${base}_${i}`)) i++;
  return `${base}_${i}`;
}

function renombrar(nodo) {
  const nuevo = prompt("Nombre del nodo (letras, dígitos y «_»):", nodo.properties.nombre);
  if (!nuevo || nuevo === nodo.properties.nombre) return;
  if (!IDENT.test(nuevo)) return reportar(`«${nuevo}» no es un nombre: letras, dígitos y «_», sin empezar por dígito`, "error");
  if (nombresUsados().has(nuevo)) return reportar(`ya hay un nodo «${nuevo}»`, "error");
  nodo.properties.nombre = nuevo;
  nodo.actualizarTitulo();
  cambioEnElGrafo();
}

// ---------------------------------------------------------------- JamGraph ↔ LiteGraph

function aJam() {
  const nodes = {}, edges = [];
  for (const n of grafo._nodes || []) {
    const t = POR_VERBO[n.properties.verbo];
    const params = {};
    for (const w of n.widgets || []) {
      params[w.name] = typeof w.value === "boolean" ? String(w.value) : String(w.value);
    }
    nodes[n.properties.nombre] = { verb: n.properties.verbo, params, x: Math.round(n.pos[0]),
                                   y: Math.round(n.pos[1]) };
    if (n.properties.bypass) nodes[n.properties.nombre].bypass = true;
    if (n.properties.asset) nodes[n.properties.nombre].asset = n.properties.asset;
  }
  // Por destino y slot: el orden de los cables de un variádico es el de sus entradas, no el de
  // creación de los links.
  const links = Object.values(grafo.links).filter(Boolean)
    .sort((x, y) => (x.target_id - y.target_id) || (x.target_slot - y.target_slot));
  for (const l of links) {
    const a = grafo.getNodeById(l.origin_id), b = grafo.getNodeById(l.target_id);
    if (!a || !b) continue;
    edges.push([a.properties.nombre, a.outputs[l.origin_slot].name, b.properties.nombre, b.inputs[l.target_slot].name]);
  }
  return { schema_version: 1, nodes, edges };
}

function desdeJam(doc) {
  pausa = true;
  grafo.clear();
  const porNombre = {};
  for (const [nombre, nd] of Object.entries(doc.nodes || {})) {
    const t = POR_VERBO[nd.verb];
    const nodo = t ? LiteGraph.createNode(`${t.cat || "Otros"}/${nd.verb}`) : null;
    if (!nodo) { reportar(`verbo desconocido en el archivo: «${nd.verb}» (nodo ${nombre})`, "error"); continue; }
    nodo.properties.nombre = nombre;
    nodo.pos = [Number(nd.x) || 0, Number(nd.y) || 0];
    for (const w of nodo.widgets || []) {
      if (!(w.name in (nd.params || {}))) continue;
      const v = nd.params[w.name];
      w.value = w.type === "toggle" ? String(v).toLowerCase() === "true"
              : w.type === "number" ? Number(v) : String(v);
    }
    if (nd.bypass) { nodo.properties.bypass = true; nodo.mode = 4; }
    if (nd.asset) nodo.properties.asset = nd.asset;
    grafo.add(nodo);
    porNombre[nombre] = nodo;
  }
  separarEncimados(Object.values(porNombre));
  for (const [a, ap, b, bp] of doc.edges || []) {
    const na = porNombre[a], nb = porNombre[b];
    if (!na || !nb) continue;
    let si = na.findOutputSlot(ap);
    // El primer slot con ese nombre que esté LIBRE: en un variádico hay varios «in».
    let di = nb.inputs.findIndex((i) => i.name === bp && i.link == null);
    if (di < 0 && bp === "in" && POR_VERBO[nb.properties.verbo].aridad === -1) {
      nb.addInput("in", nb.inputs.find((i) => i.name === "in").type); di = nb.inputs.length - 1;
    }
    if (di < 0) { nb.addInput(bp, 0); di = nb.inputs.length - 1; }   // un parámetro cableado
    if (si >= 0 && di >= 0) na.connect(si, nb, di);
  }
  pausa = false;
  lienzo.setDirty(true, true);
  cambioEnElGrafo(true);
}

// Un nodo que llega del texto sin posición (o de un .jamgraph de Slate, cuyos nodos miden distinto)
// puede caer encima de otro: se corre hacia abajo hasta que no se pise con ninguno ya ubicado.
function separarEncimados(nodos) {
  const ubicados = [];
  const pisa = (a, b) => a.pos[0] < b.pos[0] + b.size[0] && b.pos[0] < a.pos[0] + a.size[0] &&
                         a.pos[1] < b.pos[1] + b.size[1] + 40 && b.pos[1] < a.pos[1] + a.size[1] + 40;
  for (const n of nodos) {
    let vueltas = 0;
    while (ubicados.some((u) => pisa(n, u)) && vueltas++ < 200) n.pos[1] += 30;
    ubicados.push(n);
  }
}

// ---------------------------------------------------------------- compilar, correr, texto

let temporizador = null;
function cambioEnElGrafo(inmediato) {
  if (pausa) return;
  clearTimeout(temporizador);
  temporizador = setTimeout(sincronizar, inmediato ? 0 : 350);
}

async function sincronizar() {
  const doc = aJam();
  const json = JSON.stringify(doc);
  if (json === ultimoJson) return;
  ultimoJson = json;
  try {
    pintar(await api("compilar_grafo", json), false);
    if (!textoEditado) {
      const t = await api("texto_de_grafo", json);
      $("#fuente").value = t.ok ? t.texto : `# ${t.error}`;
    }
  } catch (e) { reportar(String(e), "error"); }
}

function pintar(envelope, desdeRun) {
  for (const n of grafo._nodes || []) {
    const r = (envelope.nodes || {})[n.properties.nombre];
    n.resultado = r || null;
    if (r) n.boxcolor = ESTADOS[r.estado] || null;
  }
  lienzo.setDirty(true, true);
  if (desdeRun || !envelope.ok) reportar(envelope.report || envelope.error || "");
}

async function correr() {
  reportar("corriendo…");
  const r = await api("correr_grafo", JSON.stringify(aJam()));
  pintar(r, true);
}

async function aplicarTexto() {
  const r = await api("grafo_de_texto", $("#fuente").value, JSON.stringify(aJam()));
  $("#errores-texto").textContent = (r.errores || []).map((e) =>
    `línea ${e.linea}${e.nodo ? ` (${e.nodo})` : ""}: ${e.mensaje}`).join("\n");
  if (r.graph) {
    textoEditado = false; $("#sin-aplicar").textContent = "";
    desdeJam(r.graph);
  }
}

// ---------------------------------------------------------------- arranque

function ajustarLienzo() {
  const c = $("#canvas"), caja = $("#lienzo").getBoundingClientRect();
  c.width = caja.width; c.height = caja.height;
  lienzo && lienzo.resize();
}

async function iniciar() {
  const estado = await api("estado");
  $("#motor").textContent = `· ${estado.motor}`;
  const con = $("#conexion");
  con.className = estado.conectado ? "on" : "off";
  con.textContent = estado.conectado ? `${estado.motor} conectado` : `sin ${estado.motor}: ${estado.error || ""}`;
  document.title = `Jam · ${estado.motor}`;
  SPEC = await api("spec_editor");
  registrarNodos();
  grafo = new LGraph();
  ajustarLienzo();
  lienzo = new LGraphCanvas("#canvas", grafo);
  lienzo.background_image = null;
  lienzo.render_canvas_border = false;
  lienzo.show_info = false;   // el contador de FPS de LiteGraph
  grafo.onNodeAdded = () => cambioEnElGrafo();
  grafo.onNodeRemoved = () => cambioEnElGrafo();
  grafo.onConnectionChange = () => cambioEnElGrafo();
  lienzo.onNodeMoved = () => cambioEnElGrafo();
  grafo.start();
  window.addEventListener("resize", ajustarLienzo);
  const disponibles = SPEC.tools.filter((t) => t.disponible !== false).length;
  reportar(`${SPEC.tools.length} nodos, ${disponibles} disponibles en ${estado.motor}. ` +
           "Doble clic en el fondo busca un nodo; clic derecho, el menú por categoría.");
}

$("#b-compilar").onclick = () => { ultimoJson = ""; sincronizar().then(() => reportar("Compile listo: mirá el color de cada nodo")); };
$("#b-correr").onclick = correr;
$("#b-fijar").onclick = async () => reportar(JSON.stringify(await api("preview", "bake")));
$("#b-descartar").onclick = async () => reportar(JSON.stringify(await api("preview", "discard")));
$("#b-nuevo").onclick = () => { grafo.clear(); cambioEnElGrafo(true); };
$("#b-guardar").onclick = () => {
  const blob = new Blob([JSON.stringify(aJam(), null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "grafo.jamgraph"; a.click();
};
$("#archivo").onchange = async (e) => {
  const f = e.target.files[0];
  if (f) desdeJam(JSON.parse(await f.text()));
  e.target.value = "";
};
$("#b-texto").onclick = () => {
  $("#texto").classList.toggle("oculto");
  $("#b-texto").classList.toggle("activo");
  setTimeout(ajustarLienzo, 0);
};
$("#b-aplicar").onclick = aplicarTexto;
$("#b-refrescar").onclick = () => { textoEditado = false; $("#sin-aplicar").textContent = ""; ultimoJson = ""; sincronizar(); };
$("#fuente").addEventListener("input", () => { textoEditado = true; $("#sin-aplicar").textContent = "● sin aplicar"; });

iniciar().catch((e) => reportar(`no pude arrancar el editor: ${e}`, "error"));
