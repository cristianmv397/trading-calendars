"""Cliente de Alpha Vantage `EARNINGS_CALENDAR`: el esqueleto del calendario.

Cubre un horizonte amplio en una sola petición, pero sus fechas son SIEMPRE
estimadas — Alpha Vantage no distingue una fecha confirmada por la empresa de
una proyección. Sí trae una columna `timeOfTheDay` (pre-market / post-market
/ vacía), así que se usa franja horaria cuando la trae, aunque el dato en sí
siga marcado como estimado (no confirmado) en el `SUMMARY` del evento.

LIMITACIÓN CONOCIDA (verificada el 17/08/2026, ver `config.toml`):
`horizon=6month` y `horizon=12month` devuelven una respuesta corrupta con la
clave probada — Content-Type `application/x-download`, 87 bytes, un mensaje
de error troceado carácter a carácter en las 7 columnas del CSV
(`E,r,r,o,r, ,M`). No se ha podido confirmar si es un bug del servidor o una
restricción de plan no documentada. Solo `horizon=3month` (el valor por
defecto de la propia API) devolvió datos reales en la prueba.

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

    No intenta adivinar formas raras: si la cabecera o el número de columnas
    no coincide con lo esperado, es un error (puede ser la respuesta
    corrupta conocida de horizon=6/12month, o un mensaje de error real de la
    API), no una fila con datos atípicos.
    """
    contenido = contenido.strip()
    if not contenido:
        raise AlphaVantageError("Respuesta vacía de Alpha Vantage.")

    filas = list(csv.reader(io.StringIO(contenido)))
    if not filas:
        raise AlphaVantageError("CSV sin filas.")

    cabecera = filas[0]
    if cabecera != COLUMNAS_ESPERADAS:
        raise AlphaVantageError(
            f"Cabecera de columnas inesperada: {cabecera!r}. "
            "Puede ser un mensaje de error de la API en vez de datos "
            "(ver LIMITACIÓN CONOCIDA en el docstring del módulo)."
        )

    eventos = []
    for fila in filas[1:]:
        if len(fila) != len(COLUMNAS_ESPERADAS):
            raise AlphaVantageError(
                f"Fila con {len(fila)} columnas, se esperaban {len(COLUMNAS_ESPERADAS)}: "
                f"{fila!r}. Es la firma de la respuesta corrupta conocida de horizon=6/12month: "
                "revisar el valor de `horizon` usado."
            )
        symbol, name, report_date, fiscal_date, estimate, currency, franja = fila
        if not symbol.strip() or not report_date.strip():
            continue
        report_date, fiscal_date = report_date.strip(), fiscal_date.strip()
        if not _PATRON_FECHA.match(report_date) or (fiscal_date and not _PATRON_FECHA.match(fiscal_date)):
            raise AlphaVantageError(
                f"Fecha con formato inesperado en la fila {fila!r} (se esperaba AAAA-MM-DD). "
                "Es la firma de la respuesta corrupta conocida de horizon=6/12month: "
                "revisar el valor de `horizon` usado."
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
