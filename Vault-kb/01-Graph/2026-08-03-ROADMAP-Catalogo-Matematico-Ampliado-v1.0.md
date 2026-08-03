---
title: "Catálogo matemático ampliado de Jam"
tipo: ROADMAP
version: "1.0"
date: 2026-08-03
updated: 2026-08-03
status: en-progreso
area: 01-Graph
tags:
  - jam
  - graph
  - math
  - roadmap
  - procedural
  - vectores
  - matrices
aliases:
  - Catálogo completo de Math
  - Roadmap matemático de Jam
  - Biblioteca matemática
---

# Catálogo matemático ampliado de Jam

Este documento convierte en tarea durable la ambición matemática de Jam. No es una promesa de
poner cientos de fichas sin criterio: es el catálogo objetivo del que salen lotes verificables. El
orden de entrega favorece modelado procedural, PCG, materiales, animación y herramientas técnicas.

El plan operativo inicial y sus criterios viven en
[[2026-08-02-PLAN-Verbos-Math-Numeros-Vectores-Matrices-v1.0]]. Este roadmap amplía su horizonte.

## Reglas del catálogo

- Identidad por dominio: `math_add`, `vector_add`, `matrix_add`; no existe un comodín ambiguo.
- Los pines dicen semántica y tipo: `base (Número)`, `exponente (Número)`, no `A/B` si importa orden.
- Radianes internamente; grados y vueltas se convierten con nodos explícitos.
- Toda aleatoriedad recibe `seed` y `stream/id`; el orden accidental de ejecución no cambia datos.
- NaN, infinito, división por cero, dominio real inválido y matriz singular son errores explícitos.
- Las operaciones con varias salidas publican pines reales: seno/coseno, mínimo/máximo, cociente/resto.
- El registro puro es fuente única para Graph, Flow, Compile, Inspector y spec. Slate sólo presenta.
- Los tipos objetivo son `N`, `I`, `B`, `V2/V3/V4`, `Q`, `M3/M4`, `C`, series, `Rango`,
  `Transform` y `Color`.

## Estado actual

Verdes en tests, intérprete embebido y primera verificación manual: **Sumar, Restar, Multiplicar y
Dividir**. El lote 2026-08-03 agrega **Negar, Absoluto, Módulo, Potencia y Raíz cuadrada**; queda
pendiente su gesto visual antes de declararlo cerrado.

## 1. Fuentes y constantes

- Número, Entero, Booleano, Índice, Frame, Tiempo, Delta de tiempo y Seed.
- Pi, Tau, Euler, proporción áurea, raíz de dos, épsilon, cero, uno y menos uno.
- Parámetro nombrado, contador, valor previo y aleatorio determinista.
- Infinito sólo como límite/diagnóstico, nunca como salida silenciosa de una cuenta.

## 2. Aritmética escalar

- Sumar, suma variádica, Restar, Multiplicar, producto variádico y Dividir.
- División entera, cociente/resto, Módulo y resto IEEE.
- Negar, Absoluto, Signo, Copiar signo y Recíproco.
- Cuadrado, Cubo, Multiplicar-y-sumar —FMA—, Incrementar y Decrementar.
- Diferencia absoluta, promedio de dos valores y distancia escalar.

## 3. Potencias, raíces y logaritmos

- Potencia real, potencia entera, raíz cuadrada, cúbica y n-ésima; Hipotenusa.
- Exponencial, base dos, `expm1`; logaritmo natural, base dos, base diez y base arbitraria.
- `log1p`, escala logarítmica, amplitud a decibelios y decibelios a amplitud.

## 4. Rango, normalización y remapeo

- Mínimo, Máximo, Mínimo-y-máximo, Limitar y Saturar.
- Limitar inferior/superior, Envolver, Repetir y Ping-pong.
- Normalizar, Desnormalizar, Remapear y Remapear limitado/logarítmico.
- Invertir, expandir y contraer rango; centro y tamaño de rango.
- Pertenencia, intersección y unión de rangos; cuantizar y ajustar a múltiplo.

## 5. Redondeo y escalones

- Piso, Techo, Truncar, Redondear, redondeo bancario y alejándose de cero.
- Parte fraccionaria, separar entero/fracción y mantisa/exponente.
- Redondear a decimales o múltiplo, Snap escalar, Step, Smoothstep y Smootherstep.

## 6. Comparación, clasificación y lógica

- Menor, menor o igual, mayor, mayor o igual, Igual y Distinto.
- Igual aproximado, casi cero, Entre, fuera de rango, mismo signo y signos opuestos.
- Es positivo/negativo/cero/entero/par/impar/finito/infinito/NaN.
- Comparación de tres vías y Elegir por condición.
- Y, O, XOR, No, NAND, NOR, equivalencia, Todos, Alguno, Ninguno y contar verdaderos.
- Máscaras, Toggle y flancos ascendente/descendente para grafos dependientes del tiempo.

## 7. Trigonometría y ángulos

- Seno, Coseno, Tangente y salida conjunta Seno/Coseno.
- Arcoseno, Arcocoseno, Arcotangente y `atan2`.
- Secante, cosecante, cotangente e hiperbólicas con sus inversas.
- Grados/radianes/vueltas, normalizar/envolver ángulo y diferencia angular mínima.
- Interpolar ángulos, dirección 2D a ángulo, elevación/azimut y sentido horario.

## 8. Interpolación y easing

- Lerp, lerp limitado e inverso; bilineal y trilineal.
- Cúbica, Hermite, Catmull–Rom, Bézier cuadrática/cúbica y racional.
- Aproximación constante/exponencial, amortiguación suave y resorte.
- Ease In/Out/InOut lineal, cuadrático, cúbico, cuártico, quíntico, seno, exponencial,
  circular, Back, Bounce y Elastic.
- Curva de respuesta configurable.

## 9. Enteros, bits y combinatoria

- Conversiones real/entero, MCD, MCM, factorial, combinaciones y permutaciones.
- Primos, siguiente primo, factorización, potencias de dos y logaritmo entero.
- Dígitos, bases decimal/binaria/hexadecimal.
- AND/OR/XOR/NOT, shifts, rotaciones y conteo de bits.
- Morton 2D/3D, hash de entero y hash de coordenadas.

## 10. Vectores 2D, 3D y 4D

- Construir/descomponer, sumar/restar, negar y escalar.
- Multiplicar/dividir componentes, absoluto, mínimo, máximo, clamp y redondeo por componente.
- Largo, largo al cuadrado, distancia, normalizar, establecer/limitar largo.
- Producto punto, cruz 3D y cruz 2D escalar; ángulo y ángulo firmado.
- Proyección, rechazo, reflexión, refracción y dirección entre puntos.
- Interpolar, orientar, ortogonal, base ortonormal y Gram–Schmidt.
- Componentes paralela/perpendicular, dominante, permutaciones y swizzle.
- Conversiones dimensionales y coordenadas homogéneas.
- Casi igual/paralelo/perpendicular, colineal y coplanar.

## 11. Coordenadas y proyecciones

- Cartesiano/polar, cartesiano/cilíndrico y cartesiano/esférico.
- UV centrado, local/mundo/padre, tangente/mundo y baricéntricas.
- Dirección a latitud/longitud y vuelta.
- Proyección plana, cilíndrica, esférica, cúbica, octaédrica y triplanar.

## 12. Cuaterniones y rotaciones

- Identidad, construir/descomponer y normalizar.
- Eje/ángulo, Euler, matriz y rotación entre dos direcciones.
- Look-at, multiplicar, inversa, conjugado, diferencia y ángulo.
- Rotar vector, Nlerp, Slerp, Slerp completo y Squad.
- Swing/twist, limitar giro, rotación mínima y orientación normal/tangente.

## 13. Matrices y sistemas lineales

- Identidad y cero 2×2, 3×3 y 4×4.
- Construir/descomponer filas y columnas; obtener/establecer elemento.
- Sumar, restar, escalar, multiplicar matrices y transformar vector.
- Transponer, determinante, inversa, adjunta, traza, menor/cofactor y norma.
- Singularidad, identidad, ortogonalidad, simetría y ortonormalización.
- Resolver sistema lineal; descomposición LU/QR y valores/vectores propios.
- Traslación, rotación, escala, shear, perspectiva, ortográfica, look-at y cambio de base.

## 14. Transformaciones 3D

- Construir/descomponer `Transform`, identidad, combinar e invertir.
- Transformar punto, vector, dirección, normal, caja y volumen.
- Local/mundo, trasladar, rotar, escalar, mirror y shear.
- Pivote, alinear ejes/normal, mirar objetivo y diferencia relativa.
- Interpolar, detectar escala negativa, extraer rotación/escala y matriz 4×4.

## 15. Series y colecciones numéricas

- Range, Linspace, Logspace, secuencia, repetir, ciclar e índices.
- Obtener/establecer/insertar/eliminar, concatenar, slice, invertir y rotar.
- Ordenar, únicos, filtrar, mapear, reducir, agrupar, particionar, zip e intercalar.
- Acumuladas, diferencias, ventanas móviles, muestrear/remuestrear/diezmar.
- Rellenar ausentes, vecino más cercano, búsqueda de intervalo, histograma y CDF.

## 16. Estadística

- Cantidad, suma, producto, promedio simple/ponderado, mediana y moda.
- Mínimo/máximo, percentiles, cuantiles y cuartiles.
- Varianza, desviación estándar, error estándar y desviación absoluta mediana.
- Asimetría, curtosis, covarianza, correlación y RMS.
- Medias geométrica, armónica y recortada; centroide ponderado.
- Z-score, normalización robusta y outliers por IQR/desviación.
- Regresión lineal/polinómica, R², matriz de covarianza y PCA.

## 17. Probabilidad y aleatoriedad determinista

- Uniforme, normal, normal truncada, exponencial, Poisson y binomial.
- Bernoulli, beta, gamma, log-normal, triangular, Weibull y Cauchy.
- Distribución discreta ponderada; PDF, CDF y cuantil.
- Elegir con pesos, barajar, muestrear sin reemplazo, reservoir y alias sampling.

## 18. Ruido y patrones procedurales

- Value, Perlin, Simplex/OpenSimplex, Worley/Voronoi, Cellular y white/blue noise.
- Curl, periódico y variantes 1D/2D/3D/4D.
- FBM, turbulencia, ridged multifractal, billow, híbrido y domain warp.
- Octavas, seed, derivada y gradiente.
- Checker, rayas, anillos, ondas, espiral, hexágonos, ladrillos y Truchet.
- Distancias Manhattan, Chebyshev y Minkowski.

## 19. Curvas y splines

- Evaluar, derivadas, tangente, normal, binormal, curvatura y longitud.
- Parámetro por distancia, punto más cercano y distancia a curva.
- Dividir/remuestrear por cantidad o distancia.
- Bézier, Hermite, Catmull–Rom, B-spline y NURBS.
- Interpolar, suavizar, simplificar, offset, cerrar, revertir, unir, recortar y extender.
- Frenet frame y parallel-transport frame.

## 20. Geometría analítica

- Distancias y puntos más cercanos para línea, segmento, plano y triángulo.
- Intersecciones línea/rayo/segmento con plano, triángulo, esfera y caja.
- Área, volumen, centroide, normal, baricéntricas y orientación robusta.
- Circuncentro, incentro, caja/esfera envolvente y ángulo sólido.
- Dentro de polígono/volumen, SAT básico y distancias firmadas.

## 21. SDF y modelado implícito

- Esfera, caja, caja redondeada, cápsula, cilindro, cono, toro, plano y segmento.
- Unión, intersección, diferencia y sus variantes suaves.
- Dilatar, erosionar, redondear, shell/onion y desplazamiento.
- Repetición cartesiana/polar, twist, bend y taper.
- Gradiente y normal de SDF.

## 22. Color

- RGB/RGBA, HSV/HSL, lineal/sRGB y temperatura/color.
- Luminancia, saturación, contraste, gamma, exposición e inversión.
- Mezcla, multiplicación, alpha compose y pre/despremultiplicar.
- Interpolar RGB/HSV, gradiente, ramp, posterizar y cuantizar.
- Distancia de color, complementario, paleta procedural y accesibilidad cromática.

## 23. Señales y tiempo

- Seno, cuadrada, triangular, sierra y pulso.
- Oscilador, fase, frecuencia, período y duty cycle.
- ADSR, pasa-bajos/altos/banda, media móvil y suavizado exponencial.
- Derivada/integral temporal, FFT/inversa, magnitud/fase, convolución y correlación.

## 24. Cálculo y análisis numérico

- Derivada, gradiente, Jacobiano, Hessiano, divergencia, curl y Laplaciano.
- Integración por trapecios/Simpson y longitud de arco.
- Raíces por bisección, Newton y secante.
- Descenso de gradiente, mínimos/máximos y ajuste de curva.
- Euler, Runge–Kutta y relajación de restricciones con tolerancia explícita.

## 25. Complejos y funciones especiales

- Complejo rectangular/polar, real/imaginario, módulo, argumento y conjugado.
- Aritmética, potencia, raíz, exponencial, logaritmo y trigonometría compleja.
- Mandelbrot y Julia como iteradores deterministas.
- Gamma, log-gamma, beta, `erf`, logística, sigmoid, softplus y sinc.
- Bessel, Fresnel, Gaussiana, campana, impulso aproximado y Lambert W.

## Orden de implementación

1. Completar escalares: aritmética, rango, redondeo, trigonometría y comparación.
2. Vectores, coordenadas, cuaterniones, matrices y `Transform`.
3. Series, estadística y aleatoriedad determinista.
4. Ruido, patrones, curvas y geometría analítica.
5. Color, SDF y señales.
6. Cálculo numérico, complejos y funciones especiales.

Cada lote necesita tablas de verdad, errores de dominio, paridad Graph/Flow, mutación deliberada,
round-trip de grafo, Inspector y una sonda dentro de UE. La GUI se declara verde recién cuando una
persona encuentre, conecte y ejecute los nodos desde el ribbon real.
