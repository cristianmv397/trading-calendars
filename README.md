# trading-calendars

Genera y publica dos feeds de calendario (ICS) con las fechas de resultados
trimestrales de empresas cotizadas en EE. UU., para suscribirlos desde Google
Calendar. Proyecto hermano de [`trading-stack`](https://github.com/cristianmv397/trading-stack)
(privado): este repositorio es **público**, porque GitHub Pages lo exige y
porque Google Calendar necesita leer el ICS sin autenticación. No hay nada
sensible aquí — ninguna clave, ninguna posición, ningún dato de cuenta.

## Por qué existe

Sirve para **evitar** operar valores que publican resultados dentro de la
ventana de una operación swing, no para operar el evento. Por eso: **una
fecha estimada presentada como confirmada es peor que no tener el dato.**
Todo evento del calendario deja claro de dónde sale (`nasdaq` o
`alphavantage`) y si está confirmado o es una estimación — visible en el
propio título del evento, no solo en la descripción.

## URLs de suscripción

*(Se rellenan aquí en cuanto el operador active GitHub Pages — ver
"Lo que queda por hacer" más abajo. Formato esperado:)*

```
https://cristianmv397.github.io/trading-calendars/earnings-large.ics
https://cristianmv397.github.io/trading-calendars/earnings-mid.ics
```

- **`earnings-large.ics`** — capitalización > 10.000 M USD.
- **`earnings-mid.ics`** — capitalización > 2.000 M USD (incluye a los
  anteriores).

En Google Calendar: **Otros calendarios → Desde URL**, pegar la URL. Se
actualiza sola (cabecera `REFRESH-INTERVAL`), aunque Google Calendar en la
práctica la relee cada 12-24 h, no al instante.

## Validación realizada (17/08/2026)

Ejecución real, sin datos simulados, contra las tres APIs, ya con el
diagnóstico corregido de Alpha Vantage (`horizon=12month`):

| | Large (>10.000M$) | Mid (>2.000M$) |
|---|---|---|
| Eventos | 316 | 567 |
| Rango de fechas | 2026-08-17 → 2027-02-11 | 2026-08-17 → 2027-02-11 |
| Confirmados (Nasdaq) | 116 | 225 |
| Estimados (Alpha Vantage) | 200 | 342 |
| Día completo (franja desconocida) | 237 | 435 |

Universo del screener: 7.176 valores. Alpha Vantage: **2.036 filas** (antes
1.814, con el `horizon` corregido). Nasdaq (90 días consultados): 635 filas,
muy concentradas en las primeras semanas — ver el hallazgo de cobertura de
Nasdaq más abajo.

**Por qué el recuento de eventos casi no cambió aunque Alpha Vantage pasó de
1.814 a 2.036 filas:** de esas 2.036, solo 1.233 tickers están en el
universo del screener (nasdaq+nyse+amex); el resto (803) son valores OTC o
fuera de ese universo, y quedan excluidos por diseño (sin capitalización
conocida, no se puede aplicar el filtro — ver `fusion.filtrar_por_capitalizacion`).
De los 1.233 que sí están, la mayoría no supera los umbrales de large/mid
cap. El número de empresas grandes y medianas de EE. UU. es finito
independientemente de cuánto se alargue el horizonte de consulta: alargarlo
amplía sobre todo el **rango de fechas** cubierto (ahora hasta febrero de
2027, antes hasta noviembre de 2026), no tanto el recuento total de
eventos relevantes.

**ICS validado con un parser independiente** (`vobject`, sin relación con
`icalendar`, que es lo que lo construye): confirma el mismo número de
`VEVENT` en los dos ficheros, la presencia de `VTIMEZONE`, y resuelve
correctamente el desplazamiento horario de verano (`-04:00`, EDT) para un
evento de agosto.

**Contraste manual de tres tickers conocidos** (búsqueda externa, no la
misma fuente que generó el dato):

| Ticker | Generado | Contrastado |
|---|---|---|
| AAPL | 2026-10-29, ESTIMADO, día completo | Coincide con la previsión pública basada en el patrón histórico de Apple |
| NVDA | 2026-08-26, confirmado, tras el cierre | Coincide exactamente con el anuncio real (fecha y franja) |
| JPM | 2026-10-13, **ESTIMADO** (no confirmado), día completo | La fecha coincide con el comunicado oficial de JPMorgan, pero Nasdaq no tenía ese día en su calendario (ver hallazgo siguiente), así que el sistema no pudo marcarlo como confirmado aunque la estimación acertara |

## De dónde salen los datos, y por qué tres fuentes

Ninguna fuente cubre sola lo que hace falta:

1. **Alpha Vantage `EARNINGS_CALENDAR`** — el esqueleto. Una sola petición
   cubre el mercado entero. **Todas sus fechas se tratan como estimadas.**
   Plan gratuito: 25 peticiones/día, así que se llama una única vez por
   ejecución.

   **Diagnóstico corregido el 17/08/2026** (ver `fuentes/alphavantage.py`):
   una primera prueba de `horizon=6month` y `horizon=12month` devolvió un
   cuerpo de 87 bytes con pinta de CSV corrupto (un mensaje de error
   troceado carácter a carácter). Repetido más tarde el mismo día,
   `horizon=12month` devolvió un CSV real y completo: **2.036 filas, ~7
   meses de cobertura** (agosto 2026 a marzo 2027). No era corrupción, era
   un fallo transitorio de la API — probablemente el límite de 25
   peticiones/día agotado durante las pruebas previas de ese mismo día. El
   parser (`parsear_csv`) ya no confunde un mensaje de error corto con un
   CSV: si el cuerpo no empieza por la cabecera esperada, el error muestra
   el texto real devuelto por el servidor. `config.toml` usa `horizon =
   "12month"`.

2. **API pública de Nasdaq (`/api/calendar/earnings`)** — precisión a corto
   plazo, confirmada. Una petición por día natural, acepta hasta ~90 días
   vista. Sus fechas **sustituyen** a las de Alpha Vantage cuando coinciden
   ticker y trimestre fiscal. No es una API oficial ni documentada: exige
   cabeceras de navegador (`User-Agent`, `Origin`, `Referer`) o devuelve
   vacío.

   **Hallazgo importante, verificado el 17/08/2026 con una ejecución real:**
   la API acepta consultar cualquier fecha dentro de esos ~90 días, pero
   **la cobertura real cae en picado con la distancia**, no solo por fines
   de semana y festivos. En la ejecución de referencia (horizonte
   17/08–14/11/2026): agosto tuvo 324 filas, septiembre 253, **octubre solo
   58, y noviembre 0 filas en el mes entero**. Esto no es un patrón de días
   no laborables: el 13/10/2026, por ejemplo, la API devolvió "No record
   found" para el día completo — ni JPM ni ninguna otra empresa —, pese a
   que JPMorgan ya había anunciado esa fecha en un comunicado de prensa
   oficial meses antes (verificado por separado, ver sección de validación
   más abajo). La conclusión práctica: el papel de Nasdaq como fuente
   "confirmada y precisa" solo es fiable de verdad en las primeras ~6
   semanas del horizonte; más allá, casi todo depende de la estimación de
   Alpha Vantage aunque la fecha ya esté confirmada en otro sitio. No hay
   forma de arreglar esto desde el cliente: es una limitación de cobertura
   de los datos que expone la propia API.

3. **Screener público de Nasdaq (`/api/screener/stocks`)** — universo y
   capitalización, para el filtro de tamaño. No se usa para fechas.

   **Hallazgo, verificado el 17/08/2026:** el parámetro multi-exchange
   documentado como `exchange=nasdaq|nyse|amex` **no funciona** (devuelve 0
   registros). Omitir el parámetro `exchange` por completo sí da el
   universo combinado real (~7.176 valores, consistente con nasdaq + nyse +
   amex por separado). El código omite el parámetro a propósito.

   La API tampoco expone campos para distinguir SPAC, fondos cerrados o ADR
   sin volumen: no se fuerza ese filtro con heurísticas sobre el nombre.

### Cómo se fusionan

Clave de fusión: `(ticker, trimestre fiscal normalizado)`. El trimestre se
normaliza a partir del **mes de cierre** (`fiscalDateEnding` de Alpha
Vantage, `fiscalQuarterEnding` de Nasdaq) porque las dos fuentes no usan el
mismo formato — es una aproximación por mes, no el calendario fiscal oficial
de cada empresa (ver docstring de `fusion.normalizar_trimestre`).

## Formato del ICS

- iCalendar 2.0 válido, con `VTIMEZONE` completo para `America/New_York`
  (generado con `icalendar.Timezone.from_tzid`, con las reglas reales de
  cambio de hora de EE. UU.). Nunca horas en UTC fijas.
- Antes de apertura → 08:00 hora de Nueva York, 15 min. Tras cierre → 16:15,
  15 min. Franja desconocida → evento de **día completo**: la ausencia de
  dato es información, no se inventa una hora.
- `UID` estable a partir de ticker + trimestre fiscal normalizado (no de la
  fecha): al regenerar, Google Calendar actualiza el evento existente en
  vez de duplicarlo.
- `SEQUENCE` sube cuando cambia la fecha o la franja de un evento ya
  publicado, comparando contra `estado/publicado.json`.

## Estructura

```
trading-calendars/
├── README.md
├── config.toml               umbrales de capitalización, horas, horizonte
├── generate.py                punto de entrada
├── fusion.py                  normalización de trimestre y fusión de fuentes
├── ics.py                     construcción del VCALENDAR (UID, SEQUENCE, VTIMEZONE)
├── reintentos.py               espera creciente en llamadas HTTP
├── fuentes/
│   ├── alphavantage.py
│   ├── nasdaq_earnings.py
│   └── nasdaq_screener.py
├── estado/publicado.json      UID -> fecha/franja/sequence, para el SEQUENCE
├── tests/                     pytest, sin red, con fixtures reales recortadas
└── docs/                      salida servida por GitHub Pages
    ├── earnings-large.ics
    ├── earnings-mid.ics
    └── index.html
```

## Desarrollo local

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; source .venv/bin/activate en Linux/Mac
pip install -r requirements.txt
cp .env.example .env          # rellenar ALPHAVANTAGE_API_KEY
python -m pytest -q           # 50 tests, sin red
python generate.py            # ejecución real: sí toca la red
```

`ALPHAVANTAGE_API_KEY` se lee de la variable de entorno, nunca hardcodeada.
`.env` está en `.gitignore` — nunca se sube.

## Automatización (GitHub Actions)

`.github/workflows/generar.yml`: cron **semanal** (lunes, 05:00 UTC ≈ 06:00
CET / 07:00 CEST de Europa/Madrid — GitHub Actions no soporta zonas
horarias en cron, así que la hora local real oscila una hora según la
época del año) + `workflow_dispatch` para lanzarlo a mano.

Semanal, no mensual: el horizonte real de Nasdaq como fuente confirmada son
~6 semanas (ver hallazgo más abajo), así que un ciclo mensual tardaría
demasiado en convertir un evento ESTIMADO en confirmado justo en el tramo
que más importa. Con cadencia semanal, cualquier evento dentro de esas 6
semanas tiene varias oportunidades de pasar de estimado a confirmado antes
de que se acerque la fecha.

Cada ejecución escribe un sello de actividad (`.last-run`) además de
`docs/` y `estado/`, para que GitHub no desactive el cron por inactividad
del repositorio — es el motivo concreto por el que un proyecto de terceros
equivalente dejó de funcionar en abril de 2026, no una precaución
hipotética.

GitHub Pages se sirve directamente desde la rama `main`, carpeta `/docs` —
no hay un job de despliegue de Pages separado: el commit del workflow ya dej
a `docs/` actualizado en `main`, y Pages sirve lo que haya ahí.

### Secretos que hay que configurar en GitHub

| Secreto | Qué es | Dónde se configura |
|---|---|---|
| `ALPHAVANTAGE_API_KEY` | Clave de Alpha Vantage | `Settings → Secrets and variables → Actions → New repository secret` |

## Lo que queda por hacer (fuera de este repositorio local)

1. **Crear el repositorio remoto** en GitHub, público, llamado
   `trading-calendars`.
2. **Añadir el remoto y subir** esta rama (`git remote add origin ...` y
   `git push -u origin main`) — no lo hace Claude, es una regla del
   proyecto.
3. **Crear el secreto** `ALPHAVANTAGE_API_KEY` en
   `Settings → Secrets and variables → Actions`.
4. **Activar GitHub Pages**: `Settings → Pages → Source: Deploy from a
   branch → Branch: main, carpeta /docs → Save`.
5. **Lanzar el workflow una vez a mano** (`Actions → Generar calendario de
   resultados → Run workflow`) para que `docs/` tenga contenido real antes
   de que Pages lo sirva por primera vez.
6. **Suscribir las dos URLs** en Google Calendar (sección de arriba).
