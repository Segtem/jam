"""El almacén de resultados cocinados: qué se guarda, qué se devuelve y qué se tira.

`cache_core` decide la IDENTIDAD de un resultado —la huella— y qué quedó sucio. Acá se guardan los
resultados de verdad, contra esa huella, para que un nodo limpio no se vuelva a cocinar.

Medido en UE 5.8.1: un Run cuesta 167–498 ms y el compile 0,1–0,3 ms. Lo que se guarda son los
resultados del MOTOR, que es donde está el costo.

Dos decisiones que importan más de lo que parece:

  · **Un resultado guardado nunca se devuelve “por las dudas”.** Si la huella no coincide exacto, es
    un fallo de caché y se recocina. Un caché que a veces devuelve algo viejo es un bug silencioso, y
    en geometría se ve como “a veces el muro sale mal” — el peor síntoma posible para depurar.
  · **Hay un tope y un orden de desalojo.** Cada entrada retiene una malla del motor; sin tope, una
    sesión larga de live view se come la memoria y el editor muere por otra causa que nadie va a
    relacionar con esto.
"""

from __future__ import annotations

from collections import OrderedDict

#: Cuántos resultados se retienen. El número sale del uso previsto, no de la nada: una cadena típica
#: de los tutoriales tiene 4–11 nodos, y con 64 entran varios grafos enteros más sus estados
#: intermedios mientras se ajusta un parámetro. Es un tope de SEGURIDAD, no una optimización fina.
CAPACIDAD = 64


class Almacen:
    """Resultados por huella, con desalojo del menos usado recientemente.

    No es un `dict` global a propósito: el caché es estado de una sesión de edición, y poder tener
    uno por Preview —o tirarlo entero— es lo que evita que un Bake arrastre restos del anterior.
    """

    def __init__(self, capacidad: int = CAPACIDAD):
        if capacidad < 1:
            raise ValueError("la capacidad del caché tiene que ser al menos 1")
        self.capacidad = int(capacidad)
        self._items: OrderedDict[str, object] = OrderedDict()
        self.aciertos = 0
        self.fallos = 0

    def obtener(self, huella: str):
        """El resultado guardado para esa huella, o `None`.

        `None` es «no lo tengo», no «el resultado es nulo»: un verbo que legítimamente produce nada
        no se guarda, porque no hay nada que reusar y sí habría un valor que confundir.
        """
        if huella in self._items:
            self._items.move_to_end(huella)
            self.aciertos += 1
            return self._items[huella]
        self.fallos += 1
        return None

    def guardar(self, huella: str, resultado) -> None:
        if resultado is None:
            return
        self._items[huella] = resultado
        self._items.move_to_end(huella)
        while len(self._items) > self.capacidad:
            # El menos usado recientemente: en live view lo que se toca vuelve a tocarse enseguida,
            # y lo que quedó atrás rara vez se pide de nuevo.
            self._items.popitem(last=False)

    def invalidar(self, huellas) -> int:
        """Tira las huellas indicadas. Devuelve cuántas había."""
        tiradas = 0
        for huella in list(huellas or ()):
            if self._items.pop(huella, None) is not None:
                tiradas += 1
        return tiradas

    def limpiar(self) -> None:
        self._items.clear()

    def plan(self, huellas_por_nodo: dict) -> dict:
        """Qué hay que cocinar y qué se reusa, ANTES de tocar el motor.

        Devuelve `{"reusa": [...], "cocina": [...]}` ordenados. Se calcula por adelantado para que el
        ahorro se pueda medir y mostrar —«8 de 11 reusados»— en vez de quedar como una mejora
        invisible que nadie sabe si funciona.
        """
        reusa, cocina = [], []
        for nid, huella in sorted((huellas_por_nodo or {}).items()):
            (reusa if huella in self._items else cocina).append(nid)
        return {"reusa": reusa, "cocina": cocina}

    @property
    def tamano(self) -> int:
        return len(self._items)

    def estadisticas(self) -> dict:
        total = self.aciertos + self.fallos
        return {"entradas": len(self._items), "capacidad": self.capacidad,
                "aciertos": self.aciertos, "fallos": self.fallos,
                "tasa": (self.aciertos / total) if total else 0.0}
