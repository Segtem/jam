"""Los casos de colocación de la base común: el MISMO texto en Unreal, Godot y Unity. Datos puros.

Cada caso es una lista de pasos; un paso es un texto a correr o `FIJAR` (fijar el Preview). Se mide
lo que colocó el ÚLTIMO paso: la caja de mundo de cada instancia, ordenada. La caja de prueba es
asimétrica y con el pivote corrido para que un yaw con el signo al revés, una escala con los ejes
cruzados o un ancla mal medida den cajas distintas. El asset viaja por el cable y no por nombre: el
nombre con que cada motor guarda un asset es suyo (Unreal lo llama `SM_<name>` y, al fijar, nunca
pisa: crea `_2`, `_3`…). La lee `verifica_colocar_58.py` (Unreal) y
`verifica_colocar.py` (Godot, Unity).
"""

FIJAR = "FIJAR"

CAJA = ("caja = mesh_box size_x=100 size_y=50 size_z=30\n"
        "corrida = mesh_transform @caja x=40 y=10\n"
        "a = mesh_to_static @corrida name=JamPruebaCaja\n")
PISO = ("piso = mesh_box size_x=2000 size_y=2000 size_z=20\n"
        "ap = mesh_to_static @piso name=JamPruebaPiso\n"
        "p = place @ap z=-5 surface=false anchor=top\n")

CASOS = [
    ("en_puntos", [CAJA + "linea = pts_line ax=-400 bx=400 count=6 seed=3\n"
                          "c = place @a points=@linea scale_min=0.5 scale_max=1.5\n"]),
    ("en_rejilla_por_la_esquina", [CAJA + "r = pts_rect size_x=600 size_y=400 cols=3 rows=2 seed=5\n"
                                          "c = place @a points=@r anchor=corner scale_min=0.8 "
                                          "scale_max=1.2 sink=5\n"]),
    ("girada_y_escalada", [CAJA + "c = place @a x=300 y=-200 z=50 yaw=30 scale=2 surface=false "
                                  "anchor=center\n"]),
    # Lo que la MISMA corrida ya colocó es suelo: un piso y la caja encima, en un solo grafo.
    ("sobre_un_piso_del_mismo_run", [PISO + CAJA + "c = place @a x=100 y=150 z=500\n"]),
    # El Preview de la corrida ANTERIOR no: sin fijar, el piso desaparece y la caja cae a z=500 (no
    # hay nada abajo). Va antes que el caso del piso fijado, que deja su piso en la escena.
    ("no_se_apoya_en_el_run_anterior", [PISO, CAJA + "c = place @a x=100 y=150 z=500\n"]),
    # Fijado, sí es suelo.
    ("sobre_un_piso_fijado", [PISO, FIJAR, CAJA + "c = place @a x=100 y=150 z=500 yaw=-45\n"]),
]
