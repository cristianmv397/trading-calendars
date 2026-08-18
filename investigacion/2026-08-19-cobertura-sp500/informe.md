# Investigación — tamaño y forma del hueco de cobertura del feed de resultados

**Fecha:** 19/08/2026. **Alcance:** solo investigación, no se ha tocado
`generate.py`, `fusion.py`, `ics.py` ni ningún fichero del generador. Los
datos que respaldan este informe están en los ficheros de este mismo
directorio (`investigacion/2026-08-19-cobertura-sp500/`); los scripts que
los produjeron también, numerados en el orden en que se ejecutaron.

## Resumen

**El hueco es grande: 316 de los 503 componentes del S&P 500 (62,8 %) no
aparecen en `earnings-mid.ics`.** No es un problema de capitalización ni de
qué bolsa cotiza cada valor — es casi enteramente un problema de cobertura
de las dos fuentes de fechas (Alpha Vantage y el calendario de resultados de
Nasdaq). El sector sí tiene un efecto real y grande (de 47 % a 90 % de
ausencia según el sector); el mercado de cotización, casi ninguno.

**Actualización tras verificación adversarial (19/08/2026, segunda ronda —
ver sección 4).** La primera versión de este informe daba por buena la
ausencia en Alpha Vantage sin haber mirado la respuesta cruda con los ojos.
Se ha hecho esa comprobación, más consulta por símbolo individual, auditoría
de nuestro propio parseo y un tercer voto independiente. **Veredicto: (c),
mezcla, pero casi enteramente (a).** De los 316 ausentes: **314 (99,4 %)
están genuinamente ausentes de las dos fuentes en origen** — confirmado
sobre el CSV crudo sin parsear, no solo sobre la salida de nuestro cliente.
**1 (`BF.B`, Brown-Forman) es un bug real nuestro**: Alpha Vantage sí tiene
su fecha, pero se pierde en el filtro de capitalización por un desajuste de
formato de ticker entre fuentes. **1 (`BRK.B`, Berkshire Hathaway) tiene el
mismo bug de formato, pero no lo explica**: está ausente de Alpha Vantage en
origen también, así que arreglar el formato no lo recuperaría. **Nuestro
lado explica como mucho el 0,3 % del hueco** (1 de 316); el 99,7 % restante
es de las fuentes. Además, la atribución de la sección 4 original a "MCD"
específicamente para el lado de Nasdaq era imprecisa — corregida ahí mismo:
no es que a MCD le falte cobertura, es que Nasdaq no cubre de forma fiable
ningún ticker más allá de ~6 semanas vista, algo ya documentado en este
README el 17/08/2026.

## 1. Tickers reales en cada ICS, y mid ⊇ large

Script: `01_tickers_ics.py`. Fuente: `docs/earnings-large.ics` y
`docs/earnings-mid.ics` — los ficheros **publicados** (los que sirve GitHub
Pages y los que consume `trading-stack`), no una regeneración nueva.

| | Tickers |
|---|---|
| `earnings-large.ics` | 316 |
| `earnings-mid.ics` | 567 |
| `large` ausentes de `mid` | **0** |

**mid ⊇ large se confirma de nuevo.** Ningún ticker de `large` falta en
`mid`. (Nota: que `large` tenga 316 tickers y el hueco del S&P 500 sea
también de 316 valores es coincidencia de cifras, no relación — son dos
recuentos distintos sobre conjuntos distintos.)

## 2. Componentes del S&P 500 que faltan

Script: `02_sp500_constituyentes.py`. **Fuente: Wikipedia, [List of S&P 500
companies](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies)**,
descargada el 19/08/2026 (snapshot crudo guardado en
`wikipedia_sp500_raw.html` para que el paso sea reproducible sin depender de
que la página cambie). Por qué esta fuente: el plan de EODHD contratado en
`trading-stack` devuelve 403 en `fundamentals` (confirmado el 18/08/2026, no
cubre listas de índice), y no hay ninguna otra fuente ya integrada en
ninguno de los dos proyectos que dé la composición del S&P 500. Wikipedia
mantiene esta tabla activamente y es la referencia de facto de uso común
para este dato sin necesitar clave de API — limitación aceptada: es una
fuente editada por voluntarios, no el proveedor oficial de pago (S&P Dow
Jones Indices), proporcionada para medir un hueco, no para operar con el
dato.

| | Cifra |
|---|---|
| Componentes parseados (incluye AAPL, GOOGL con más de una clase de acción) | 503 |
| Presentes en `earnings-mid.ics` | 187 (37,2 %) |
| **Ausentes de `earnings-mid.ics`** | **316 (62,8 %)** |

Lista completa de los 316, con diagnóstico por fila: `ausentes_diagnostico.csv`.

## 3. Forma del hueco

Script: `03_diagnostico.py` (exchange, sector) y `04_capitalizacion_deciles.py`
(capitalización dentro del S&P 500).

### 3.1 Mercado de cotización — hipótesis del sesgo hacia Nasdaq: **descartada**

| Exchange | Ausentes | Presentes | Total | % ausentes |
|---|---|---|---|---|
| NYSE | 210 | 132 | 342 | 61,4 % |
| NASDAQ | 105 | 55 | 160 | 65,6 % |

La diferencia es de 4 puntos porcentuales, y en el sentido **contrario** al
sospechado: los valores de Nasdaq faltan ligeramente *más*, no menos, que
los de NYSE. No hay sesgo por mercado de cotización que explique el hueco —
MCD (NYSE) no falta por ser NYSE; casi dos tercios de los valores de Nasdaq
del S&P 500 faltan también.

### 3.2 Sector GICS — el patrón real, y es grande

| Sector | Ausentes | Presentes | Total | % ausentes |
|---|---|---|---|---|
| **Utilities** | 28 | 3 | 31 | **90,3 %** |
| **Real Estate** | 25 | 5 | 30 | **83,3 %** |
| **Energy** | 17 | 4 | 21 | **81,0 %** |
| **Materials** | 20 | 5 | 25 | **80,0 %** |
| Health Care | 42 | 17 | 59 | 71,2 % |
| Communication Services | 16 | 8 | 24 | 66,7 % |
| Industrials | 51 | 32 | 83 | 61,4 % |
| Information Technology | 42 | 31 | 73 | 57,5 % |
| Consumer Staples | 17 | 17 | 34 | 50,0 % |
| Financials | 36 | 40 | 76 | 47,4 % |
| **Consumer Discretionary** | 22 | 25 | 47 | **46,8 %** |

Rango de casi 44 puntos entre el sector mejor cubierto (Consumer
Discretionary, 46,8 % ausente) y el peor (Utilities, 90,3 % ausente). Los
sectores "defensivos"/tradicionales (utilities, inmobiliario, energía,
materiales) están sistemáticamente peor cubiertos que tecnología, consumo
discrecional y financieras — consistente con que Alpha Vantage y el
calendario de Nasdaq parecen priorizar (o simplemente cubrir mejor, por lo
que sea en su propia curación de datos) valores más seguidos/negociados,
independientemente de su capitalización.

### 3.3 Capitalización — efecto real pero débil, y no protege ni en el decil más alto

Deciles calculados **dentro del propio S&P 500** (D1 = el 10 % más pequeño
del índice, D10 = el 10 % más grande) — los deciles calculados sobre el
universo completo del screener (~7.190 valores) no sirven aquí: el S&P 500
entero cae trivialmente en los 2-3 deciles más altos de ese universo mucho
más amplio.

| Decil (S&P 500) | n | Ausentes | % ausentes |
|---|---|---|---|
| D1 (más pequeños) | 51 | 40 | 78,4 % |
| D2 | 50 | 39 | 78,0 % |
| D3 | 50 | 34 | 68,0 % |
| D4 | 50 | 31 | 62,0 % |
| D5 | 50 | 32 | 64,0 % |
| D6 | 50 | 33 | 66,0 % |
| D7 | 50 | 31 | 62,0 % |
| D8 | 50 | 32 | 64,0 % |
| D9 | 50 | 22 | 44,0 % |
| D10 (más grandes) | 50 | 20 | **40,0 %** |

Hay un gradiente (78 % → 40 %), así que ser más grande dentro del S&P 500
ayuda algo. Pero **incluso en el decil más alto, 4 de cada 10 valores
faltan** — MCD está en el decil 9 (189.000 M$, cerca del extremo alto) y aun
así falta. El tamaño reduce el riesgo, no lo elimina ni de lejos: no es un
predictor utilizable por sí solo ("por encima de tal capitalización, seguro
que está cubierto" es falso).

### 3.4 Mes de publicación previsto

No se pudo cruzar como se planteaba: de los 316 ausentes, **cero** aparecen
con fecha en la salida de Alpha Vantage (ver sección 4) — no hay ningún mes
que cruzar porque la fuente no les asigna ninguno. Este resultado en sí es
el hallazgo relevante para esta dimensión, y encaja directamente con la
sección 4: el hueco no depende de *cuándo* tocaría publicar, depende de si
la fuente cubre el ticker en absoluto.

### Conclusión de la sección 3

**Hay un patrón claro y es el sector, no el mercado de cotización.** La
capitalización tiene un efecto real pero secundario y no protege ni en el
extremo alto. "El hueco no sigue ningún patrón" habría sido una respuesta
válida si hubiera salido así — no es el caso: el patrón existe, tiene
números, y apunta a la cobertura propia de Alpha Vantage/Nasdaq por sector,
no a un criterio de tamaño o de bolsa.

## 4. Por qué falta MCD (y los otros 315): verificación adversarial

**Primera versión de esta sección (mañana del 19/08/2026):** se basaba en la
salida de nuestro propio cliente (`av.obtener_calendario()`), no en la
respuesta cruda de la API. Correcto metodológicamente pero insuficiente: no
descartaba que el propio cliente, el parseo, o la llamada estuvieran
perdiendo datos antes de que yo los mirara. Lo que sigue es la verificación
que faltaba, hecha por separado (tarde del 19/08/2026), con los 4 pasos
pedidos.

### 4.1 Respuesta cruda de Alpha Vantage, sin parsear, leída a mano

Petición real (`horizon=12month`, la misma que usa el generador), guardada
sin tocar en `av_raw_crudo.csv` antes de pasarla por ningún parser propio.

| Comprobación sobre el CSV crudo | Resultado |
|---|---|
| Líneas totales | 1.995 (1 cabecera + 1.994 filas de datos) |
| `grep MSFT` sobre el fichero crudo | **0 coincidencias** |
| `grep AMZN` sobre el fichero crudo | **0 coincidencias** |
| `grep MCD` sobre el fichero crudo | **0 coincidencias** |
| ¿Cabecera correcta, sin nota de límite de uso? | Sí: `symbol,name,reportDate,fiscalDateEnding,estimate,currency,timeOfTheDay`, cabecera limpia |
| ¿Última línea con pinta de dato real (no corte a mitad)? | Sí: `IFPJF,IFPJF,2027-03-10,2026-12-31,,USD,` — fila bien formada, sin señales de truncamiento |
| Content-Type de la respuesta HTTP | `application/x-download` (descarga de fichero, no un JSON de error envuelto en 200) |

MSFT, AMZN y MCD no están en el texto que llegó del servidor, antes de que
ningún código nuestro lo toque. No hay nota de límite de uso ni de plan: es
un CSV real y completo, del mismo tamaño (1.994 filas) que reportó el
cliente. Esto ya descarta que sea un problema de truncamiento o de
paginación.

### 4.2 Consulta por símbolo individual (`symbol=MSFT`, etc.)

El endpoint sí admite `symbol` (no está documentado que lo haga junto con
`function=EARNINGS_CALENDAR`, pero responde 200 sin error).

| Símbolo | Resultado |
|---|---|
| `MSFT` | Cabecera, **0 filas de datos** |
| `AMZN` | Cabecera, **0 filas de datos** |
| `MCD` | Cabecera, **0 filas de datos** |
| `AAPL` (control, se sabe que está cubierto) | Cabecera + 1 fila real: `AAPL,APPLE INC,2026-10-29,2026-09-30,1.98,USD,` |

Mismo resultado que la consulta masiva, por una vía de código completamente
distinta, con un control positivo (AAPL) funcionando en el mismo lote de
peticiones. (Nota aparte, no determinante: una petición suelta a `AMZN` en
un intento anterior devolvió un cuerpo corto con pinta de mensaje de texto
en vez de CSV — mismo patrón que el fallo transitorio ya documentado el
17/08. No se reprodujo al repetir la petición dos veces más, así que se
trata como ruido transitorio de red/servidor, no como parte del hallazgo;
se deja anotado por transparencia, no como evidencia.)

### 4.3 Auditoría de nuestro parseo (`fuentes/alphavantage.py`)

`parsear_csv` nunca descarta una fila en silencio salvo cuando `symbol` o
`reportDate` vienen vacíos (un `continue` explícito, correcto); cualquier
otra fila con forma inesperada hace que la función **falle con
`AlphaVantageError`**, no que la ignore. Comprobado directamente sobre el
CSV crudo guardado en el paso 4.1:

| | Cifra |
|---|---|
| Filas de datos en el CSV crudo | 1.994 |
| Eventos que devuelve `parsear_csv` sobre ese mismo CSV | **1.994** |
| Tickers distintos en el resultado | **1.994** |
| Filas perdidas por el parseo | **0** |

Uno a uno, sin pérdida. El parseo no es la causa. Tampoco hay normalización
de símbolo alguna en este módulo (`ticker=symbol.strip().upper()`, nada
más) que pudiera transformar "MSFT" en otra cosa.

**Donde sí hay un problema real de normalización, aunque no afecta a MSFT,
AMZN ni MCD:** las acciones de doble clase. Cada fuente usa un separador
distinto para el mismo ticker:

| Empresa | Alpha Vantage | Screener de Nasdaq | Wikipedia (este informe) |
|---|---|---|---|
| Berkshire Hathaway | *(ausente, ver 4.1)* | `BRK/A`, `BRK/B` | `BRK.B` → normalizado a `BRK-B` |
| Brown-Forman | `BF.A`, `BF.B` (con fecha real: `2026-09-02`) | `BF/A`, `BF/B` (sin `marketCap`) | `BF.B` → normalizado a `BF-B` |

`fusion.filtrar_por_capitalizacion` hace un cruce exacto de cadena entre el
ticker del evento (formato de Alpha Vantage o Nasdaq earnings) y el ticker
del screener — `BF.B` nunca coincide con `BF/B`, así que el evento se
descarta por "sin capitalización conocida" **aunque Alpha Vantage sí tenga
una fecha real para Brown-Forman**. Esto **es un bug real de
`trading-calendars`**, confirmado, y afecta a `BF.B`. No afecta a `BRK.B`
porque Berkshire está ausente de Alpha Vantage en origen — arreglar el
formato del ticker no lo recuperaría, ese caso es (a) y (b) a la vez, con
(a) dominando. En todo el S&P 500 **solo 2 tickers tienen este formato**
(`BRK.B` y `BF.B` — comprobado sobre las 503 filas de
`sp500_constituyentes.csv`), así que el bug, siendo real, tiene un alcance
minúsculo: 1 ticker recuperable de 316.

### 4.4 Tercer voto independiente

Finnhub habría sido razonable, pero no hay clave configurada en este
proyecto ni en `trading-stack` y montar una cuenta nueva solo para esta
comprobación puntual no parecía proporcionado — se optó por confirmar con
varias fuentes públicas independientes en su lugar (ninguna es la fuente
del feed):

- **MSFT**: próximo resultado 27-28/10/2026 (fuentes: TipRanks, MarketBeat,
  Investing.com — pequeña discrepancia de un día entre ellas, pero todas de
  acuerdo en la semana).
- **MCD**: próximo resultado 22/10/2026 (fuentes: Investing.com, MarketFairValue,
  y la propia página de Nasdaq nasdaq.com/market-activity/stocks/mcd/earnings —
  distinta del endpoint no oficial `/api/calendar/earnings` que usa este
  proyecto, aunque sea el mismo operador).

Las fechas existen, son públicas y las conocen varios proveedores — **no es
que nadie sepa cuándo publican estas empresas.** Es que ni Alpha Vantage
`EARNINGS_CALENDAR` ni el endpoint no oficial de calendario de Nasdaq las
tienen en sus respectivos datasets en este momento, por el motivo que sea de
su propia curación interna (no observable desde fuera).

### 4.5 Veredicto

**Mezcla — (c) — pero casi enteramente (a).** 314 de 316 (99,4 %) ausentes
son un hueco real de las fuentes, verificado sobre datos crudos sin parsear
y confirmado con una vía de consulta alternativa (por símbolo). 1 de 316
(0,3 %, `BF.B`) es un bug real y gratis de arreglar en `fusion.py`, para una
próxima tarea si se decide. 1 de 316 (0,3 %, `BRK.B`) tiene el mismo bug
pero no lo explica, porque además está ausente en origen. **Nuestro lado
del código explica como máximo el 0,3 % del hueco medido; el 99,7 % restante
es de verdad de las fuentes.**

### 4.6 Corrección: la atribución a "MCD" del lado de Nasdaq era imprecisa

La versión anterior de esta sección decía "por qué falta MCD" enmarcando el
lado de Nasdaq como si fuera un caso de MCD. No lo es, y ya estaba mal
enmarcado con la información que había en el momento de escribirlo: el
README de este mismo repositorio documentó el 17/08/2026 que la cobertura
real de la API de calendario de Nasdaq **se desploma con la distancia
dentro de su propia ventana nominal de 90 días** (agosto 324 filas,
septiembre 253, octubre 58, noviembre 0 — con JPM como ejemplo ya registrado
de una fecha pública y oficial ausente del calendario). MCD no tiene un
problema particular con Nasdaq: **ningún ticker, sea cual sea, tiene fechas
fiables en Nasdaq earnings más allá de ~6 semanas vista**, y el 22/10/2026
cae fuera de esa ventana práctica aunque esté dentro de la ventana nominal
de 90 días. Confirmado de nuevo hoy (19/08/2026, en vivo): la API devuelve
0 filas para el día completo del 22/10/2026 — no un hueco de MCD, un hueco
de fecha, para cualquier empresa. El lado de Nasdaq del hueco de MCD no es
un hallazgo nuevo de esta investigación: es una instancia más de algo que ya
se sabía desde el 17/08. Lo nuevo es que el lado de **Alpha Vantage**
también falla para MCD (y para 315 empresas más) — eso sí es un hallazgo de
esta investigación, y es el que de verdad explica el 63 % de ausencia,
porque Alpha Vantage es el "esqueleto" que en teoría debería cubrir el año
entero.

## 5. Si el hueco se quiere tapar — alternativas y coste aproximado, sin implementar

El hueco es grande (63 % del S&P 500), así que esto aplica — con el matiz de
la sección 4: es un hueco de las fuentes, no del código, salvo un caso.
Ninguna opción está implementada ni evaluada más allá de lo que se puede
razonar desde fuera.

**Aparte de la tabla de abajo, hay una corrección gratuita e independiente
de cuál alternativa se elija (o de no elegir ninguna):** arreglar la
normalización de ticker de doble clase en `fusion.filtrar_por_capitalizacion`
para que compare formatos equivalentes (`.`, `/`, `-`) en vez de cadena
exacta. Recupera como mucho 1 ticker (`BF.B`) de los 316 — no cambia el
tamaño del hueco de forma perceptible, pero es un bug real, ya localizado, y
no cuesta nada arreglarlo la próxima vez que se toque `fusion.py`.

| Alternativa | Qué aporta | Coste aproximado |
|---|---|---|
| **Añadir una tercera fuente de pago** (Finnhub, Polygon.io, IEX Cloud, Zacks, o el propio EODHD si se cambia de plan) | Cobertura probablemente mejor y más uniforme por sector, sin depender de la curación gratuita de Alpha Vantage | Dinero (suscripción mensual) + trabajo de integración (nuevo cliente, nuevo saneado de errores) + otra API que puede fallar o cambiar de forma |
| **Subir de plan en Alpha Vantage** | Más peticiones/día — no está claro que resuelva el hueco: el problema observado es de curación de datos (qué tickers cubren), no de límite de peticiones. Habría que confirmarlo con soporte o documentación de Alpha Vantage antes de pagar por ello | Dinero, con riesgo de que no resuelva nada |
| **Inferir la fecha a partir del histórico de EDGAR** (cadencia de presentación de 10-Q/10-K de cada empresa, proyectando la próxima fecha) | Cobertura casi total (EDGAR es gratuito y cubre toda empresa cotizada en EE. UU.), no depende de que un tercero decida curar el ticker | Trabajo de ingeniería no trivial; el resultado es SIEMPRE una estimación, nunca confirmado — encaja con el estado `proyectado` ya anotado como pendiente en `trading-stack` (más débil que `estimado`), que necesita su propio diseño antes de tocarse |
| **Agregar más fuentes gratuitas no oficiales** (earningswhispers.com, calendarios de MarketBeat/TipRanks/Zacks) | Amplía la red sin coste en dinero | Más fragilidad (APIs no documentadas, como las dos que ya se usan), más mantenimiento, riesgo de términos de servicio, sin garantía de que cubran mejor precisamente los sectores que hoy fallan |
| **No tocar el feed; apoyarse en el diseño ya existente** (`SIN DATO` bloquea el bloque 11 hasta confirmación manual, `trading-stack`) | Coste cero de ingeniería | El coste lo paga el operador: con esta magnitud de hueco, la mayoría de candidatos que lleguen a la watchlist van a necesitar confirmación manual de la fecha de resultados — ya se midió en la validación del 18/08/2026 (6 de 10 candidatos de MCD) y esto explica por qué salió tan alto |

No se recomienda ninguna aquí — es una decisión de coste/beneficio que
corresponde al operador, con estos números delante.

## Ficheros de este directorio

| Fichero | Contenido |
|---|---|
| `01_tickers_ics.py` | Extrae tickers de `docs/earnings-{large,mid}.ics` |
| `tickers_large.csv`, `tickers_mid.csv` | Salida del anterior |
| `02_sp500_constituyentes.py` | Parsea la tabla de Wikipedia |
| `wikipedia_sp500_raw.html` | Snapshot crudo de la página consultada (19/08/2026) |
| `sp500_constituyentes.csv` | 503 componentes: ticker, sector, exchange |
| `03_diagnostico.py` | Cruce exchange/sector + diagnóstico origen vs. pipeline (llama a Alpha Vantage y al screener de Nasdaq en vivo, reutiliza `fuentes/*.py` del propio generador) |
| `ausentes_diagnostico.csv` | Los 316 ausentes, fila a fila, con su diagnóstico |
| `04_capitalizacion_deciles.py` | Deciles de capitalización dentro del S&P 500 |
| `capitalizacion_deciles_sp500.csv` | Salida del anterior |
| `av_raw_crudo.csv` | Respuesta cruda y sin parsear de Alpha Vantage `EARNINGS_CALENDAR` (`horizon=12month`), tal cual llegó del servidor — sección 4.1 |
| `av_raw_symbol_{msft,amzn,mcd,aapl}.csv` | Respuestas crudas de la consulta por símbolo individual — sección 4.2 |
