"""Compara artefactos sellados; no llama modelos ni altera juicios."""
import json, hashlib
from decimal import Decimal
from datetime import datetime,timezone
from pathlib import Path
D=Path(__file__).resolve().parent; S=D/'corrida-jev'
def leer(p): return json.loads(p.read_text())
def guardar(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
sello=leer(S/'sello-respuestas.json'); assert sello['completa'] and sello['respuestas']==60
for n,h in sello['archivos'].items(): assert sha(S/n)==h
protocolo=leer(S/'protocolo-corrida.json')
assert sha(D/'ciego/CRITERIO.md')==protocolo['sha256_criterio']
assert sha(D/'ciego/registros.json')==protocolo['sha256_registros']
registros=leer(D/'ciego/registros.json'); juicio=leer(D/'juicio-ciego-claude.json'); clave=leer(D/'clave-operador.json')
assert len(juicio)==len(clave)==len(registros)==20
ids={r['id'] for r in registros}; assert len(ids)==20 and ids=={r['id'] for r in juicio}=={r['id'] for r in clave}
J={r['id']:r for r in juicio}; K={r['id']:r for r in clave}; Q=['tema_desarrollado','referencia_concreta','vigencia_delimitada']
P=leer(S/'respuestas-probabilidades.json'); assert set(P)=={f'{i}__{q}' for i in ids for q in Q}
# Reconstruir probabilidades desde las respuestas HTTP, no confiar sólo en el resumen.
crudas={}
for n in sello['archivos']: crudas.update({k:a['noul'] for k,a in leer(S/n)['answers'].items()})
assert P==crudas
filas=[]
for r in registros:
 for q in Q:
  i=r['id']; j=J[i][q]; assert type(j) is bool
  p=P[f'{i}__{q}']; v=p>=.5
  filas.append(dict(id=i,pregunta=q,ruta=K[i]['ruta'],control=K[i]['control'],esperado=(K[i]['esperado'] or {}).get(q),claude=j,jev=v,p_si=p,p_no=round(1-p,10),acuerdo=v==j,justificacion_claude=J[i]['justificacion_'+q],cita_claude=J[i]['cita_'+q]))
resumen={}
for q in Q:
 resumen[q]={}
 for grupo in ['originales','controles','total']:
  f=[r for r in filas if r['pregunta']==q and (grupo=='total' or r['control']==(grupo=='controles'))]
  resumen[q][grupo]=dict(n=len(f),acuerdos=sum(r['acuerdo'] for r in f),claude_si=sum(r['claude'] for r in f),jev_si=sum(r['jev'] for r in f),si_si=sum(r['claude'] and r['jev'] for r in f),no_no=sum(not r['claude'] and not r['jev'] for r in f),claude_si_jev_no=sum(r['claude'] and not r['jev'] for r in f),claude_no_jev_si=sum(not r['claude'] and r['jev'] for r in f),brier=sum((r['p_si']-r['claude'])**2 for r in f)/len(f),zona_04_06=sum(.4<=r['p_si']<=.6 for r in f))
consumo=leer(S/'consumo.json'); costo=sum(Decimal(str(r['usage']['cost'])) for r in consumo)
guardar(S/'comparaciones.json',filas);guardar(S/'analisis.json',resumen)
guardar(S/'sello-comparacion.json',dict(fecha_utc=datetime.now(timezone.utc).isoformat(),sha256_juicio=sha(D/'juicio-ciego-claude.json'),sha256_clave=sha(D/'clave-operador.json'),sello_respuestas_previo=sello['fin_utc'],validaciones='20 ids únicos idénticos, 60 booleanos, 60 probabilidades coincidentes con HTTP, hashes de criterio/registros/crudas intactos'))
lineas=['# Resultado del piloto de prosa del vault','', 'Corrida completa el 2026-09-23. **Recomendación: revisión a mano antes de adoptar una medida en sombra.**','', 'Se conservaron el CRITERIO íntegro y los 20 registros (15 originales y 5 controles), sin editar título ni cuerpo. Se enviaron cinco lotes consecutivos de cuatro registros, con las tres preguntas independientes. Corte fijado antes de llamar: `p(sí) ≥ 0,5`; zona descriptiva cercana al corte: `[0,4; 0,6]`. No hubo ajustes ni reintentos después de ver el juicio.','', '## Acuerdo por pregunta','', '| Pregunta | Originales | Controles: acuerdo | Total | Claude sí/no (originales) | Jev sí/no (originales) |','|---|---:|---:|---:|---:|---:|']
for n,q in enumerate(Q,1):
 a=resumen[q];o=a['originales'];c=a['controles'];t=a['total']
 lineas.append(f"| P{n} `{q}` | {o['acuerdos']}/15 ({o['acuerdos']/15:.1%}) | {c['acuerdos']}/5 | {t['acuerdos']}/20 | {o['claude_si']}/{15-o['claude_si']} | {o['jev_si']}/{15-o['jev_si']} |")
lineas+=['','## Controles atrapados','', '| Pregunta | Jev contra defecto esperado | Claude contra defecto esperado |','|---|---:|---:|']
for n,q in enumerate(Q,1):
 f=[r for r in filas if r['control'] and r['pregunta']==q]
 lineas.append(f"| P{n} | {sum(r['jev']==r['esperado'] for r in f)}/5 | {sum(r['claude']==r['esperado'] for r in f)}/5 |")
lineas+=['', 'Los cinco controles esperan **no en las tres preguntas**. Son degradaciones gruesas: atraparlos no demuestra sensibilidad a errores plausibles, citas inventadas o desactualización real. P1 y P2 tienen todos los originales positivos según Claude: no hay negativos naturales para estimar esos errores.','', '## Desacuerdos','']
for r in filas:
 if not r['acuerdo']:
  lineas += [f"- **{r['id']} · {r['pregunta']}**: Claude {'sí' if r['claude'] else 'no'}, Jev {'sí' if r['jev'] else 'no'}; p(sí)={r['p_si']:.2f}, p(no)={r['p_no']:.2f}. Documento: `{r['ruta']}`. Justificación de Claude: {r['justificacion_claude']} Cita: {json.dumps(r['cita_claude'],ensure_ascii=False)}."]
lineas+=['','La comparación mide acuerdo con Claude, no exactitud contra una verdad técnica. No se corrige el juicio para mejorar el acuerdo. Las probabilidades pertenecen a Jev; Claude entregó booleanos, no probabilidades. `p(no)` se calcula como complemento de `p(sí)`, no mediante otra llamada.','', '## Probabilidades y calibración descriptiva','', '| Pregunta | Brier originales / total | Originales cerca del corte |','|---|---:|---:|']
for n,q in enumerate(Q,1):
 a=resumen[q];lineas.append(f"| P{n} | {a['originales']['brier']:.4f} / {a['total']['brier']:.4f} | {a['originales']['zona_04_06']}/15 |")
lineas+=['','Brier se calcula contra los booleanos de Claude. Una única muestra pequeña y controles artificiales no certifican calibración ni generalización. La tabla siguiente conserva los dos lados de las 60 respuestas; en cada celda: `Claude; p(sí) / p(no)`.','', '| ID | Tipo | P1 | P2 | P3 |','|---|---|---|---|---|']
for r in registros:
 f=[x for x in filas if x['id']==r['id']]
 lineas.append('| '+r['id']+' | '+('control' if K[r['id']]['control'] else 'original')+' | '+' | '.join(f"{'sí' if x['claude'] else 'no'}; {x['p_si']:.2f} / {x['p_no']:.2f}" for x in f)+' |')
lineas+=['','## Costo real informado por la API','',f"Cinco HTTP 200, 60 respuestas, cero reintentos. Modelo efectivo: `typesafe/jev-1.13-20260917`. Total `usage.cost`: **USD {costo}** ({costo*100} centavos de dólar). No es una estimación por tarifas ni una auditoría de factura.",f"Tokens informados: {sum(r['usage']['input_tokens'] for r in consumo)} de entrada y {sum(r['usage']['output_tokens'] for r in consumo)} de salida. Suma de latencias HTTP: {sum(r['segundos'] for r in consumo):.3f} s.",'', '| Lote | Entrada | Salida | USD | Segundos |','|---|---:|---:|---:|---:|']
for r in consumo: lineas.append(f"| {r['lote']} | {r['usage']['input_tokens']} | {r['usage']['output_tokens']} | {r['usage']['cost']:.9f} | {r['segundos']:.3f} |")
lineas+=['','## Orden, integridad y límites','',f"Respuestas crudas guardadas antes de abrir el juicio y selladas a las `{sello['fin_utc']}`. SHA-256 del juicio usado: `{sha(D/'juicio-ciego-claude.json')}`. El usuario confirmó sesión limpia; el JSON no registra versión exacta ni fecha del juez.",'','Exposición del operador: `oracle tarea ver` mostró una nota previa que adelantaba el resultado P1 y la debilidad de controles. Se declaró antes de las llamadas. Ni esa nota, ni el juicio, ni la clave del operador se enviaron al modelo. No se afirma ceguera total del operador.','', 'Validado: 20 ids únicos idénticos, 60 respuestas booleanas de Claude, 60 probabilidades válidas de Jev; reconstrucción desde HTTP idéntica al resumen; hashes de criterio, registros y respuestas intactos. Jev usa Noul y no devuelve citas ni justificaciones: conserva las preguntas semánticas, pero su formato de salida difiere de la plantilla de Claude. Véase [documentación de OpenRouter](https://openrouter.ai/blog/insights/what-is-jev/).','', '## Decisión y continuación','', 'Recomiendo revisión a mano de los desacuerdos y del borde entre «limitación técnica» y «condición de vigencia» en P3. No basta el acuerdo de P1/P2 sobre controles obvios para promover el sensor. Tampoco descartaría la herramienta: el costo permite repetir un piloto mejor diseñado. Antes de considerar sombra, fijar un criterio aclarado con ejemplos positivos y negativos de P3 y una muestra independiente con defectos plausibles y ambas polaridades naturales por pregunta. No cambiar retroactivamente este criterio ni estas etiquetas.','', 'P2 sólo mide una vía textual de contraste: **no verifica que una ruta exista**. P3 no certifica vigencia actual. Esta corrida no resuelve por sí sola la verdad de la documentación. No se creó medida, se modificó el vault ni se ejecutó el cierre global: el encargo limita toda escritura a esta tarea y prohíbe commits.','', 'Artefactos: [protocolo](corrida-jev/protocolo-corrida.json), [sello previo](corrida-jev/sello-respuestas.json), [consumo](corrida-jev/consumo.json), [60 comparaciones](corrida-jev/comparaciones.json), [métricas](corrida-jev/analisis.json). Solicitudes y respuestas HTTP completas en `corrida-jev/solicitud-*.json` y `respuesta-cruda-*.json`. Recalcular sin red con `python tareas/20260923-111039-vault-prosa/comparar_jev.py`.']
(D/'RESULTADO.md').write_text('\n'.join(lineas)+'\n')
print(json.dumps(resumen,ensure_ascii=False,indent=2));print('USD',costo)
