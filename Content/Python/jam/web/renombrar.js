// Renombrar un nodo del editor web: una función pura, sin DOM ni LiteGraph, que el editor usa y que
// las pruebas corren con node (tests/test_renombrar_nodo.py). Tarea 20261015-221410-renombrar-nodo.
//
// `nodo` es {nombre, valor, conName, name}: su nombre, si es un nodo de valor (una variable), si su
// verbo tiene el parámetro `name` y el valor de ese parámetro. Devuelve {ok, error, nombre, name,
// variableSinName}: lo que el editor tiene que poner, o por qué no se renombra; con variableSinName,
// el editor comprueba antes que ninguna expresión use el nombre viejo.
(function (raiz) {
  const IDENT = /^[A-Za-z_][A-Za-z0-9_]*$/;

  function renombrar(nodo, nuevo, usados) {
    const viejo = nodo.nombre;
    nuevo = String(nuevo == null ? "" : nuevo);
    if (!nuevo || nuevo === viejo) return { ok: false, error: "" };  // cancelado o sin cambio: nada que decir
    if (!IDENT.test(nuevo)) {
      return { ok: false, error: `«${nuevo}» no es un nombre: letras, dígitos y «_», sin empezar por dígito` };
    }
    if (new Set(usados).has(nuevo)) return { ok: false, error: `ya hay un nodo «${nuevo}»` };
    const r = { ok: true, error: "", nombre: nuevo, name: nodo.name, variableSinName: false };
    if (nodo.valor && nodo.conName && !nodo.name) {
      // Su variable se llamaba como el nodo: se le fija el nombre viejo para que las expresiones que
      // la usan sigan resolviendo la misma variable (decisión de Brian, 2026-10-15).
      r.name = viejo;
    } else if (nodo.valor && !nodo.conName) {
      // Una variable sin parámetro name (una operación math_*) se llama siempre como su nodo: el editor
      // tiene que comprobar con el Compile que ninguna expresión la use antes de renombrarla.
      r.variableSinName = true;
    }
    return r;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { renombrar, IDENT };
  else raiz.JamRenombrar = { renombrar, IDENT };
})(this);
