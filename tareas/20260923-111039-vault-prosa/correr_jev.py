"""Corrida congelada: no abre el juicio ni la clave del operador. Sin reintentos."""
import hashlib, json, math, os, time
from datetime import datetime, timezone
from pathlib import Path
import requests
D=Path(__file__).resolve().parent
S=D/'corrida-jev'; S.mkdir(exist_ok=False)
def ahora(): return datetime.now(timezone.utc).isoformat()
def guardar(nombre,x): (S/nombre).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
criterio=(D/'ciego/CRITERIO.md').read_text()
assert criterio==(D/'CRITERIO.md').read_text()
registros=json.loads((D/'ciego/registros.json').read_text())
preguntas={}
for seccion in criterio.split('## P')[1:]:
    cabecera, cuerpo=seccion.split('\n',1)
    q=cabecera.split('`')[1]
    preguntas[q]=cuerpo.split('¿',1)[1].split('?',1)[0]
    preguntas[q]='¿'+preguntas[q]+'?'
assert len(registros)==20 and len(preguntas)==3
protocolo=dict(inicio_utc=ahora(),modelo='typesafe/jev-1.13',corte_si=0.5,zona_descriptiva=[0.4,0.6],lote=4,reintentos=0,sha256_criterio=sha(D/'ciego/CRITERIO.md'),sha256_registros=sha(D/'ciego/registros.json'),exposicion='Se leyó oracle tarea ver: nota agregada adelanta P1 de Claude y debilidad de controles. No se abrió juicio-ciego-claude.json ni clave-operador.json antes de sellar respuestas. Modelo sin esa nota.',fuente_api='https://openrouter.ai/blog/insights/what-is-jev/',adaptacion='CRITERIO íntegro; mismos registros sin modificaciones en cinco lotes consecutivos de cuatro. Noul devuelve P(sí), sin justificaciones/citas generativas. P(no)=1-P(sí).')
guardar('protocolo-corrida.json',protocolo)
(D/'RESULTADO.md').write_text('# Piloto de prosa del vault\n\nCorrida iniciada. Si se interrumpe, las respuestas crudas y el consumo informado quedan en `corrida-jev/`. Comparación todavía no realizada; no adoptar medida con una corrida incompleta.\n')
clave=os.environ.get('OPENROUTER_API_KEY'); resumen=[]; respuestas={}; fallo=None
for n,i in enumerate(range(0,len(registros),4),1):
    lote=registros[i:i+4]
    pedido=dict(model=protocolo['modelo'],state=dict(description=criterio,records=lote),questions={f"{r['id']}__{q}":dict(type='noul',instructions=f"Para el registro {r['id']}, aplicando exclusivamente CRITERIO: {texto}") for r in lote for q,texto in preguntas.items()})
    guardar(f'solicitud-{n:02}.json',pedido)
    info=dict(lote=n,inicio_utc=ahora()); inicio=time.monotonic()
    try:
        if not clave: raise ValueError('Sin credencial')
        resp=requests.post('https://openrouter.ai/api/alpha/decisions',headers={'Authorization':'Bearer '+clave,'Content-Type':'application/json'},json=pedido,timeout=55,allow_redirects=False)
        cruda=resp.content
        if clave.encode() in cruda: raise ValueError('Respuesta refleja credencial')
        (S/f'respuesta-cruda-{n:02}.json').write_bytes(cruda)
        info.update(http=resp.status_code,sha256_cruda=hashlib.sha256(cruda).hexdigest())
        resp.raise_for_status(); datos=json.loads(cruda)
        info.update(modelo=datos.get('model'),usage=datos.get('usage'),id=datos.get('id'))
        assert set(datos['answers'])==set(pedido['questions'])
        for k,a in datos['answers'].items():
            p=a['noul']; assert a['type']=='noul' and type(p) in (int,float) and math.isfinite(p) and 0<=p<=1
            respuestas[k]=p
    except Exception as e:
        fallo=type(e).__name__; info['fallo']=fallo
    info.update(fin_utc=ahora(),segundos=time.monotonic()-inicio);resumen.append(info);guardar('consumo.json',resumen)
    print('Lote',n,'HTTP',info.get('http'),'respuestas acumuladas',len(respuestas),'fallo',fallo,flush=True)
    if fallo: break
guardar('respuestas-probabilidades.json',respuestas)
guardar('sello-respuestas.json',dict(fin_utc=ahora(),completa=not fallo and len(respuestas)==60,respuestas=len(respuestas),fallo=fallo,archivos={p.name:sha(p) for p in sorted(S.glob('respuesta-cruda-*'))}))
