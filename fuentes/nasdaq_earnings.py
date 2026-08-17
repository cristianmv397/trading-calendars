"""Cliente de la API pública (no oficial) de calendario de resultados de Nasdaq.

Una petición por día natural; cubre unos ~90 días vista. Sus fechas
SUSTITUYEN a las de Alpha Vantage cuando coinciden ticker y trimestre
fiscal, y se marcan como CONFIRMADAS: es la fuente de mayor precisión a
corto plazo. No es una API documentada ni oficial — sin cabeceras de
navegador devuelve vacío o 403.

`rows` puede venir `null` en festivos y fines de semana: no es un error, es
"no hay resultados programados ese día". La fecha del evento no viene en
cada fila: es la que se pidió en la petición.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

URL = "https://api.nasdaq.com/api/calendar/earnings"


class NasdaqError(RuntimeError):
    """La API de Nasdaq devolvió un error, o una forma inesperada."""


@dataclass(frozen=True)
class EventoNasdaq:
    ticker: str
    nombre: str
    fecha: str  # AAAA-MM-DD, la pedida en la petición
    franja: str  # 'time-pre-market' / 'time-after-hours' / 'time-not-supplied'
    trimestre_fiscal: str | None  # fiscalQuarterEnding, p.ej. "Jul/2026"
    eps_estimado: str | None
    capitalizacion: str | None  # tal cual la devuelve la API (con "$" y comas)


def parsear_respuesta(fecha: str, cuerpo: dict) -> list[EventoNasdaq]:
    """Parsea el JSON de un día. `fecha` es la pedida, en formato AAAA-MM-DD.

    Dos formas confirmadas (17/08/2026) de "no hay resultados ese día", que
    NO son un error:
      1. `data` presente, `data.rows` es `null` (festivo dentro de una
         semana con datos, según la documentación original).
      2. `data` es directamente `null` (fin de semana, verificado contra un
         sábado real: `{"data": null, "status": {"bCodeMessage": [{"code":
         1002, "errorMessage": "Earnings Calendar: No record found."}]}}`).
    Solo se considera un error si ni siquiera están las claves de nivel
    superior esperadas (`data`, `message`, `status`): eso sí es una forma
    de respuesta no reconocida.
    """
    if not {"data", "message", "status"} & cuerpo.keys():
        raise NasdaqError(f"Respuesta con forma no reconocida para {fecha}: claves {list(cuerpo.keys())}")
    datos = cuerpo.get("data")
    if datos is None:
        return []  # fin de semana: 'data' es null entero (forma 2)
    filas = datos.get("rows")
    if filas is None:
        return []  # festivo dentro de semana con datos: 'rows' es null (forma 1)

    eventos = []
    for fila in filas:
        symbol = (fila.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        eventos.append(
            EventoNasdaq(
                ticker=symbol,
                nombre=(fila.get("name") or "").strip(),
                fecha=fecha,
                franja=fila.get("time") or "time-not-supplied",
                trimestre_fiscal=fila.get("fiscalQuarterEnding") or None,
                eps_estimado=fila.get("epsForecast") or None,
                capitalizacion=fila.get("marketCap") or None,
            )
        )
    return eventos


def descargar_dia_crudo(
    fecha: str,
    user_agent: str,
    origin: str,
    referer: str,
    timeout: float = 20.0,
) -> dict:
    """Descarga el JSON crudo de un día (AAAA-MM-DD), sin parsear.

    Separado de `obtener_dia` para que quien orquesta (generate.py) pueda
    cachear en disco la respuesta cruda antes de parsearla.
    """
    cabeceras = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": user_agent,
        "Origin": origin,
        "Referer": referer,
    }
    try:
        respuesta = requests.get(URL, params={"date": fecha}, headers=cabeceras, timeout=timeout)
        respuesta.raise_for_status()
    except requests.RequestException as exc:
        respuesta_http = getattr(exc, "response", None)
        detalle = (
            f"HTTP {respuesta_http.status_code} ({respuesta_http.reason})"
            if respuesta_http is not None
            else type(exc).__name__
        )
        raise NasdaqError(f"Fallo en la petición a Nasdaq earnings ({fecha}): {detalle}") from exc
    try:
        return respuesta.json()
    except ValueError as exc:
        raise NasdaqError(f"Respuesta no JSON de Nasdaq earnings ({fecha}): {type(exc).__name__}") from exc


def obtener_dia(
    fecha: str,
    user_agent: str,
    origin: str,
    referer: str,
    timeout: float = 20.0,
) -> list[EventoNasdaq]:
    """Descarga y parsea el calendario de resultados de un día natural (AAAA-MM-DD)."""
    cuerpo = descargar_dia_crudo(fecha, user_agent, origin, referer, timeout)
    return parsear_respuesta(fecha, cuerpo)


__all__ = ["EventoNasdaq", "NasdaqError", "parsear_respuesta", "descargar_dia_crudo", "obtener_dia"]
