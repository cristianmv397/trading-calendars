"""Cliente del screener público (no oficial) de Nasdaq: universo y capitalización.

Se usa solo para filtrar por capitalización, no para fechas de resultados.

HALLAZGO (verificado el 17/08/2026): el parámetro multi-exchange separado
por `|` (`exchange=nasdaq|nyse|amex`) NO funciona — devuelve `totalrecords: 0`
con `rows: null`. **Omitir el parámetro `exchange` por completo** sí
devuelve el universo combinado real: se comprobó que da ~7.176 valores,
consistente con nasdaq (4.169) + nyse (2.713) + amex (293) por separado.

La API tampoco expone campos para distinguir SPAC, fondos cerrados o ADR sin
volumen en esta respuesta. No se fuerza ese filtro con heurísticas sobre el
nombre: si algún día la API añade esos campos, se aplica aquí.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

URL = "https://api.nasdaq.com/api/screener/stocks"


class NasdaqScreenerError(RuntimeError):
    """El screener devolvió un error, o una forma inesperada."""


@dataclass(frozen=True)
class ValorScreener:
    ticker: str
    nombre: str
    capitalizacion_usd: float | None


def _parsear_capitalizacion(valor: str | None) -> float | None:
    """'5,445,242,000,000' o '$917,327,784,197' o '' -> float o None."""
    if not valor:
        return None
    limpio = valor.replace("$", "").replace(",", "").strip()
    if not limpio:
        return None
    try:
        return float(limpio)
    except ValueError:
        return None


def parsear_respuesta(cuerpo: dict) -> list[ValorScreener]:
    datos = cuerpo.get("data")
    if datos is None:
        raise NasdaqScreenerError(f"Respuesta sin 'data': claves {list(cuerpo.keys())}")
    tabla = datos.get("table")
    if tabla is None:
        raise NasdaqScreenerError(f"Respuesta sin 'data.table': claves {list(datos.keys())}")
    filas = tabla.get("rows") or []

    valores = []
    for fila in filas:
        symbol = (fila.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        valores.append(
            ValorScreener(
                ticker=symbol,
                nombre=(fila.get("name") or "").strip(),
                capitalizacion_usd=_parsear_capitalizacion(fila.get("marketCap")),
            )
        )
    return valores


def obtener_universo(
    user_agent: str,
    origin: str,
    referer: str,
    limite: int = 25_000,
    timeout: float = 30.0,
) -> list[ValorScreener]:
    """Descarga y parsea el universo combinado (nasdaq+nyse+amex). Una única petición.

    No se pasa `exchange`: ver HALLAZGO en el docstring del módulo.
    """
    cabeceras = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": user_agent,
        "Origin": origin,
        "Referer": referer,
    }
    try:
        respuesta = requests.get(
            URL,
            params={"tableonly": "true", "limit": limite},
            headers=cabeceras,
            timeout=timeout,
        )
        respuesta.raise_for_status()
    except requests.RequestException as exc:
        respuesta_http = getattr(exc, "response", None)
        detalle = (
            f"HTTP {respuesta_http.status_code} ({respuesta_http.reason})"
            if respuesta_http is not None
            else type(exc).__name__
        )
        raise NasdaqScreenerError(f"Fallo en la petición al screener de Nasdaq: {detalle}") from exc
    try:
        cuerpo = respuesta.json()
    except ValueError as exc:
        raise NasdaqScreenerError(f"Respuesta no JSON del screener de Nasdaq: {type(exc).__name__}") from exc
    return parsear_respuesta(cuerpo)


__all__ = ["ValorScreener", "NasdaqScreenerError", "parsear_respuesta", "obtener_universo"]
