"""Cliente de Alpha Vantage `EARNINGS_CALENDAR`: el esqueleto del calendario.

Cubre un horizonte amplio en una sola petición, pero sus fechas son SIEMPRE
estimadas — Alpha Vantage no distingue una fecha confirmada por la empresa de
una proyección. Sí trae una columna `timeOfTheDay` (pre-market / post-market
/ vacía), así que se usa franja horaria cuando la trae, aunque el dato en sí
siga marcado como estimado (no confirmado) en el `SUMMARY` del evento.

DIAGNÓSTICO CORREGIDO (17/08/2026): en una primera prueba, `horizon=6month`
y `horizon=12month` devolvieron un cuerpo de 87 bytes (`E,r,r,o,r, ,M` tras
la cabecera) que parecía CSV corrupto. Repetido más tarde el mismo día,
`horizon=12month` devolvió un CSV real y completo (2.036 filas, cobertura de
~7 meses vista). **No era corrupción del CSV: era un fallo transitorio de la
API** (probablemente relacionado con el límite de 25 peticiones/día del plan
gratuito, agotado durante las pruebas previas de ese mismo día) — el cuerpo
de 87 bytes no era un CSV mal formado, sino un mensaje de error corto que el
`csv.reader` trituraba carácter a carácter porque no se comprobaba antes si
el cuerpo tenía la forma de un CSV real. `parsear_csv` ya no asume eso: si
la respuesta no empieza por la cabecera esperada, falla mostrando el
contenido real devuelto por el servidor, en vez de intentar trocearlo como
si fueran datos.

Plan gratuito: 25 peticiones/día. `obtener_calendario` debe llamarse una
única vez por ejecución del generador, nunca por ticker.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

import requests

_PATRON_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")

COLUMNAS_ESPERADAS = [
    "symbol",
    "name",
    "reportDate",
    "fiscalDateEnding",
    "estimate",
    "currency",
    "timeOfTheDay",
]

URL = "https://www.alphavantage.co/query"


class AlphaVantageError(RuntimeError):
    """La API devolvió un error, o una respuesta que no tiene la forma esperada."""


@dataclass(frozen=True)
class EventoAlphaVantage:
    ticker: str
    nombre: str
    fecha: str  # AAAA-MM-DD (reportDate)
    trimestre_fiscal: str  # AAAA-MM-DD (fiscalDateEnding) — clave del UID
    estimacion_eps: str | None
    moneda: str
    franja: str | None  # 'pre-market' / 'post-market' / None


def parsear_csv(contenido: str) -> list[EventoAlphaVantage]:
    """Parsea el CSV crudo de `EARNINGS_CALENDAR`.

    Comprueba primero que el cuerpo tiene pinta de ser el CSV esperado
    (empieza por la cabecera correcta) antes de intentar trocearlo por
    comas: un mensaje de error corto de la API (límite de peticiones, plan,
    lo que sea) no es un CSV, y pasarlo por `csv.reader` de todas formas
    produce filas de un carácter sin avisar de nada — es exactamente lo que
    pasó en la prueba del 17/08/2026 (ver docstring del módulo). Si el
    cuerpo no tiene la forma de un CSV, el error muestra el texto real que
    devolvió el servidor, no un diagnóstico inventado.
    """
    contenido = contenido.strip()
    if not contenido:
        raise AlphaVantageError("Respuesta vacía de Alpha Vantage.")

    primera_linea = contenido.splitlines()[0]
    if not primera_linea.startswith("symbol,"):
        extracto = contenido[:300]
        raise AlphaVantageError(
            f"La respuesta no tiene forma de CSV (no empieza por 'symbol,'). "
            f"Contenido devuelto por el servidor: {extracto!r}"
        )

    filas = list(csv.reader(io.StringIO(contenido)))
    cabecera = filas[0]
    if cabecera != COLUMNAS_ESPERADAS:
        raise AlphaVantageError(f"Cabecera de columnas inesperada: {cabecera!r}.")

    eventos = []
    for fila in filas[1:]:
        if len(fila) != len(COLUMNAS_ESPERADAS):
            raise AlphaVantageError(
                f"Fila con {len(fila)} columnas, se esperaban {len(COLUMNAS_ESPERADAS)}: {fila!r}."
            )
        symbol, name, report_date, fiscal_date, estimate, currency, franja = fila
        if not symbol.strip() or not report_date.strip():
            continue
        report_date, fiscal_date = report_date.strip(), fiscal_date.strip()
        if not _PATRON_FECHA.match(report_date) or (fiscal_date and not _PATRON_FECHA.match(fiscal_date)):
            raise AlphaVantageError(
                f"Fecha con formato inesperado en la fila {fila!r} (se esperaba AAAA-MM-DD)."
            )
        eventos.append(
            EventoAlphaVantage(
                ticker=symbol.strip().upper(),
                nombre=name.strip(),
                fecha=report_date,
                trimestre_fiscal=fiscal_date,
                estimacion_eps=estimate.strip() or None,
                moneda=currency.strip(),
                franja=franja.strip() or None,
            )
        )
    return eventos


def obtener_calendario(
    api_key: str, horizon: str = "3month", timeout: float = 30.0
) -> list[EventoAlphaVantage]:
    """Descarga y parsea `EARNINGS_CALENDAR`. Única función del módulo que toca la red."""
    params = {"function": "EARNINGS_CALENDAR", "horizon": horizon, "apikey": api_key}
    try:
        respuesta = requests.get(URL, params=params, timeout=timeout)
        respuesta.raise_for_status()
    except requests.RequestException as exc:
        # Nunca str(exc): la URL de la petición lleva `apikey` en la query.
        respuesta_http = getattr(exc, "response", None)
        detalle = (
            f"HTTP {respuesta_http.status_code} ({respuesta_http.reason})"
            if respuesta_http is not None
            else type(exc).__name__
        )
        raise AlphaVantageError(f"Fallo en la petición a Alpha Vantage: {detalle}") from exc
    return parsear_csv(respuesta.text)


__all__ = ["EventoAlphaVantage", "AlphaVantageError", "parsear_csv", "obtener_calendario"]
