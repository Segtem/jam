"""Contrato 1 con Unity en 127.0.0.1:8793; reutiliza el núcleo y transporte de Godot.

El cálculo y el Compile son los mismos. Sólo cambian el motor, el puerto y los textos de
presentación heredados. No necesita paquetes de Unity ni importar Unreal.
"""

from . import adaptador_godot as _godot
from .adaptador_godot import CONTRATO, ErrorAdaptador, correr_texto  # noqa: F401

PUERTO = 8793


class Cliente(_godot.Cliente):
    def __init__(self, host="127.0.0.1", puerto=PUERTO, plazo=60.0):
        try:
            super().__init__(host=host, puerto=puerto, plazo=plazo)
        except ErrorAdaptador as e:
            raise ErrorAdaptador(str(e).replace("Godot", "Unity")) from None

    def pedir(self, op, **datos):
        try:
            return super().pedir(op, **datos)
        except ErrorAdaptador as e:
            raise ErrorAdaptador(str(e).replace("Godot", "Unity")) from None


class AdaptadorUnity(_godot.AdaptadorGodot):
    MOTOR = "unity"

    def __init__(self, cliente):
        try:
            super().__init__(cliente)
        except ErrorAdaptador as e:
            raise ErrorAdaptador(str(e).replace("Godot", "Unity")) from None
        self.version_unity = self.version_godot

    def implementacion(self, verbo):
        try:
            fn = super().implementacion(verbo)
        except RuntimeError as e:
            raise RuntimeError(str(e).replace("Godot", "Unity")) from None
        if verbo != "mesh_preview":
            return fn

        def mostrar(*args, **kwargs):
            return fn(*args, **kwargs).replace("en Godot:", "en Unity:", 1)
        return mostrar
