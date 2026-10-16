// El editor web de verdad, en node: LiteGraph, renombrar.js y editor.js reales, con un DOM mínimo de
// prueba y el núcleo (jam.servidor.Nucleo) detrás. Lo usa tests/test_renombrar_nodo.py.
//
//   node editor_en_node.js <carpeta web> <python> <escenario>
//
// El núcleo corre en un proceso hijo (puente_nucleo.py) que contesta por la entrada y la salida estándar:
// sin sockets, para que las pruebas corran también donde no se pueden abrir (el sandbox de un revisor).
// Imprime un JSON con lo que el escenario observó. El lienzo es un doble (no hay <canvas> en node): sólo
// guarda la selección, que es lo que F2 lee.
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm"), { spawn } = require("child_process");
const [web, python, escenario] = process.argv.slice(2);

// El núcleo, de a un pedido por vez: el editor llama `fetch("/api/<fn>", {body: {args}})`.
const nucleo = spawn(python, [path.join(__dirname, "puente_nucleo.py"), "godot"], { stdio: ["pipe", "pipe", "inherit"] });
let pendiente = Promise.resolve(), resto = "";
const esperando = [];
nucleo.stdout.on("data", (trozo) => {
  resto += trozo;
  let i;
  while ((i = resto.indexOf("\n")) >= 0) { const linea = resto.slice(0, i); resto = resto.slice(i + 1); esperando.shift()(JSON.parse(linea)); }
});
function alNucleo(url, opciones) {
  const fn = url.replace(/^\/api\//, ""), args = JSON.parse((opciones && opciones.body) || "{}").args || [];
  const respuesta = (pendiente = pendiente.then(() => new Promise((r) => { esperando.push(r); nucleo.stdin.write(JSON.stringify({ fn, args }) + "\n"); })));
  return respuesta.then((r) => ({ ok: !r.error, status: r.error ? 500 : 200, json: async () => r }));
}

function elemento() {
  const e = { textContent: "", value: "", className: "", style: {}, children: [],
              addEventListener() {}, appendChild(c) { this.children.push(c); return c; }, remove() {}, focus() {},
              setAttribute() {}, click() {}, getBoundingClientRect() { return { width: 800, height: 600 }; },
              querySelector() { return elemento(); }, querySelectorAll() { return []; } };
  Object.defineProperty(e, "innerHTML", { get: () => "", set() { e.children = []; } });  // reportar lo vacía así
  return e;
}
const porSelector = {}, escuchas = {}, respuestas = [], pedidos = [];
const ctx = {
  console, setTimeout, clearTimeout, setInterval, clearInterval, Blob: class {}, URL: { createObjectURL: () => "" },
  navigator: {}, location: { search: "" },
  document: { title: "", body: elemento(), createElement: () => elemento(),
              querySelector: (s) => (porSelector[s] = porSelector[s] || elemento()),
              addEventListener: (tipo, f) => (escuchas[tipo] = escuchas[tipo] || []).push(f) },
  fetch: alNucleo,
  prompt: (mensaje, porDefecto) => { pedidos.push(porDefecto); return respuestas.shift(); },
};
ctx.window = ctx; ctx.self = ctx;
ctx.addEventListener = () => {};  // window.addEventListener("resize", …)
vm.createContext(ctx);
const cargar = (archivo) => vm.runInContext(fs.readFileSync(path.join(web, archivo), "utf8"), ctx, { filename: archivo });
cargar("vendor/litegraph.js");
ctx.LGraphCanvas = class {
  constructor(_sel, grafo) { this.graph = grafo; this.selected_nodes = {}; this.ds = { scale: 1, offset: [0, 0] };
                             this.canvas = { width: 800, height: 600 }; }
  convertOffsetToCanvas(p) { return p; }
  selectNode(n) { this.selected_nodes = { [n.id]: n }; }
  deselectAllNodes() { this.selected_nodes = {}; }
  resize() {} setDirty() {} draw() {} centerOnNode() {}
};
cargar("renombrar.js");
cargar("editor.js");
const en = (codigo) => vm.runInContext(codigo, ctx);
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

async function listo() {
  // El editor terminó de arrancar cuando informa los nodos disponibles: antes puede llegar la vitrina inicial
  // y pisar el grafo del escenario.
  for (let i = 0; i < 400 && !/disponibles en/.test(reporte()); i++) await dormir(25);
  if (!/disponibles en/.test(reporte())) throw new Error(`el editor no terminó de arrancar: ${reporte()}`);
  en("grafo.clear()");
}
function nodo(nombre) { return en(`grafo._nodes.find((n) => n.properties.nombre === ${JSON.stringify(nombre)})`); }
function reporte() { return (porSelector["#reporte"] || elemento()).children.map((c) => c.textContent).join("\n"); }
async function f2(nombres, respuesta, etiqueta = "CANVAS") {
  const seleccion = {};
  for (const n of nombres) seleccion[nodo(n).id] = nodo(n);
  en("lienzo").selected_nodes = seleccion;
  if (respuesta !== undefined) respuestas.push(respuesta);
  let evitado = false;
  for (const f of escuchas.keydown || []) f({ key: "F2", target: { tagName: etiqueta }, preventDefault: () => (evitado = true) });
  await en("renombrando");  // renombrar puede esperar al Compile del núcleo
  return evitado;
}
const cargarGrafo = (g) => en(`desdeJam(${JSON.stringify(g)})`);
const compilar = () => en("api")("compilar_grafo", JSON.stringify(en("aJam()")));

const ESCENARIOS = {
  async f2() {
    cargarGrafo({ nodes: { caja: { verb: "mesh_box", params: {} }, ver: { verb: "mesh_preview", params: { name: "c" } } },
                  edges: [["caja", "out", "ver", "in"]] });
    const evitado = await f2(["caja"], "cubo");
    return { evitado, pedidos, grafo: en("aJam()"), compilado: await compilar() };
  },
  async f2_sin_disparar() {
    cargarGrafo({ nodes: { caja: { verb: "mesh_box", params: {} }, ver: { verb: "mesh_preview", params: { name: "c" } } }, edges: [] });
    await f2(["caja"], "cubo", "INPUT");            // escribiendo en un campo
    await f2(["caja", "ver"], "cubo");              // dos seleccionados
    return { pedidos, nombres: Object.keys(en("aJam()").nodes).sort() };
  },
  async invalido_o_repetido() {
    cargarGrafo({ nodes: { caja: { verb: "mesh_box", params: {} }, ver: { verb: "mesh_preview", params: { name: "c" } } },
                  edges: [["caja", "out", "ver", "in"]] });
    const salida = {};
    for (const nombre of ["1cubo", "ver"]) {
      await f2(["caja"], nombre);
      salida[nombre] = { grafo: en("aJam()"), reporte: reporte() };
    }
    return salida;
  },
  async valor_sin_name() {
    cargarGrafo({ nodes: { ancho: { verb: "number", params: { value: "3" } },
                           calc: { verb: "math", params: { name: "doble", expr: "ancho * 2" } } }, edges: [] });
    const cargado = en("aJam()");
    await f2(["ancho"], "ancho_total");
    const salida = { cargado, grafo: en("aJam()"), compilado: await compilar() };
    cargarGrafo({ nodes: { alto: { verb: "number", params: { name: "", value: "2" } } }, edges: [] });  // name vacío
    salida.vacio = en("aJam()");
    return salida;
  },
  async valores_nuevos() {
    en("grafo.clear()");
    en("agregarNodo(POR_VERBO.number)"); en("agregarNodo(POR_VERBO.number)");
    return { grafo: en("aJam()"), compilado: await compilar() };
  },
  async valor_con_name() {
    cargarGrafo({ nodes: { ancho: { verb: "number", params: { name: "medida", value: "3" } } }, edges: [] });
    await f2(["ancho"], "ancho_total");
    return { grafo: en("aJam()") };
  },
  async operacion() {
    cargarGrafo({ nodes: { s: { verb: "math_add", params: { a: "1", b: "2" } }, libre: { verb: "math_add", params: { a: "1", b: "1" } },
                           c: { verb: "math", params: { name: "x", expr: "s * 2" } } }, edges: [] });
    await f2(["s"], "t");
    const usada = { grafo: en("aJam()"), reporte: reporte() };
    // Una expresión que ya tenía otra variable faltante: el Compile nombra las dos, en plural.
    cargarGrafo({ nodes: { s: { verb: "math_add", params: { a: "1", b: "2" } },
                           c2: { verb: "math", params: { name: "y", expr: "s + falta" } } }, edges: [] });
    await f2(["s"], "t");
    const plural = { grafo: en("aJam()"), reporte: reporte() };
    cargarGrafo({ nodes: { s: { verb: "math_add", params: { a: "1", b: "2" } }, libre: { verb: "math_add", params: { a: "1", b: "1" } },
                           c: { verb: "math", params: { name: "x", expr: "s * 2" } } }, edges: [] });
    await f2(["libre"], "otra");
    return { usada, plural, libre: { grafo: en("aJam()") }, compilado: await compilar() };
  },
};

(async () => {
  await listo();
  const salida = await ESCENARIOS[escenario]();
  en("grafo.stop()");
  nucleo.stdin.end();
  process.stdout.write(JSON.stringify(salida));
  process.exit(0);
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
