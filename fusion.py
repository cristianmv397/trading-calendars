"""Fusión de las tres fuentes: normaliza el trimestre fiscal, funde Alpha
Vantage con Nasdaq (Nasdaq gana y marca `confirmado`), y filtra por
capitalización usando el screener.

SUPUESTO: el trimestre fiscal se normaliza a partir del **mes de cierre**
(Q1 ene-mar, Q2 abr-jun, Q3 jul-sep, Q4 oct-dic), no del calendario fiscal
"oficial" de cada empresa (que puede no coincidir con el año natural). Es la
mejor clave común disponible entre `fiscalDateEnding` (Alpha Vantage,
AAAA-MM-DD) y `fiscalQuarterEnding` (Nasdaq, "Mon/AAAA" tipo "Jul/2026") sin
datos adicionales por compañía. Dos eventos del mismo ticker en trimestres
reales distintos pero que caigan en el mismo Q normalizado se tratarían como
el mismo evento — un riesgo aceptado, no un caso ausente: no hay forma de
distinguirlo con lo que exponen las dos APIs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from fuentes.alphavantage import EventoAlphaVantage
from fuentes.nasdaq_earnings import EventoNasdaq
from fuentes.nasdaq_screener import ValorScreener

_MESES = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
_PATRON_FECHA_ISO = re.compile(r"^(\d{4})-(\d{2})-\d{2}$")
_PATRON_MES_ANIO = re.compile(r"^([A-Za-z]{3})/(\d{4})$")

_FRANJA_NASDAQ_A_INTERNA = {
    "time-pre-market": "antes_apertura",
    "time-after-hours": "tras_cierre",
    "time-not-supplied": "desconocida",
}


class TrimestreInvalidoError(ValueError):
    """El texto de trimestre fiscal no tiene ninguna de las dos formas conocidas."""


def normalizar_trimestre(texto: str) -> str:
    """'2026-06-30' o 'Jul/2026' -> 'AAAA-Qn'. Ver SUPUESTO en el docstring del módulo."""
    m_iso = _PATRON_FECHA_ISO.match(texto)
    if m_iso:
        anio, mes = int(m_iso.group(1)), int(m_iso.group(2))
        return f"{anio}-Q{(mes - 1) // 3 + 1}"
    m_mes_anio = _PATRON_MES_ANIO.match(texto)
    if m_mes_anio:
        mes_txt, anio_txt = m_mes_anio.groups()
        mes = _MESES.get(mes_txt.title())
        if mes is None:
            raise TrimestreInvalidoError(f"Mes no reconocido en {texto!r}")
        return f"{int(anio_txt)}-Q{(mes - 1) // 3 + 1}"
    raise TrimestreInvalidoError(f"Formato de trimestre no reconocido: {texto!r}")


def normalizar_franja_nasdaq(franja: str) -> str:
    return _FRANJA_NASDAQ_A_INTERNA.get(franja, "desconocida")


def normalizar_franja_alphavantage(franja: str | None) -> str:
    if franja == "pre-market":
        return "antes_apertura"
    if franja == "post-market":
        return "tras_cierre"
    return "desconocida"


@dataclass(frozen=True)
class EventoResultado:
    """Evento ya fusionado, listo para `ics.construir_evento`."""

    ticker: str
    nombre: str
    fecha: date
    franja: str  # 'antes_apertura' | 'tras_cierre' | 'desconocida'
    confirmado: bool
    fuente: str  # 'nasdaq' | 'alphavantage'
    trimestre_normalizado: str  # 'AAAA-Qn', clave del UID
    eps_estimado: str | None


def _fecha_desde_iso(texto: str) -> date:
    anio, mes, dia = (int(x) for x in texto.split("-"))
    return date(anio, mes, dia)


def fusionar(
    eventos_av: list[EventoAlphaVantage],
    eventos_nasdaq: list[EventoNasdaq],
) -> list[EventoResultado]:
    """Funde Alpha Vantage (estimado) con Nasdaq (confirmado, gana en empate).

    Clave de fusión: (ticker, trimestre normalizado). Si un evento de Alpha
    Vantage no tiene fila de Nasdaq con la misma clave, se conserva como
    estimado. Eventos de Nasdaq sin equivalente en Alpha Vantage también se
    incluyen (Nasdaq es más preciso a corto plazo, no hay motivo para
    descartarlos). Filas con trimestre fiscal no parseable se descartan
    (no se puede construir un UID estable sin esa clave).
    """
    por_clave: dict[tuple[str, str], EventoResultado] = {}

    for e in eventos_av:
        try:
            trimestre = normalizar_trimestre(e.trimestre_fiscal)
        except TrimestreInvalidoError:
            continue
        clave = (e.ticker, trimestre)
        por_clave[clave] = EventoResultado(
            ticker=e.ticker,
            nombre=e.nombre,
            fecha=_fecha_desde_iso(e.fecha),
            franja=normalizar_franja_alphavantage(e.franja),
            confirmado=False,
            fuente="alphavantage",
            trimestre_normalizado=trimestre,
            eps_estimado=e.estimacion_eps,
        )

    for e in eventos_nasdaq:
        if not e.trimestre_fiscal:
            continue
        try:
            trimestre = normalizar_trimestre(e.trimestre_fiscal)
        except TrimestreInvalidoError:
            continue
        clave = (e.ticker, trimestre)
        por_clave[clave] = EventoResultado(  # Nasdaq gana: sobrescribe si ya existía
            ticker=e.ticker,
            nombre=e.nombre,
            fecha=date.fromisoformat(e.fecha),
            franja=normalizar_franja_nasdaq(e.franja),
            confirmado=True,
            fuente="nasdaq",
            trimestre_normalizado=trimestre,
            eps_estimado=e.eps_estimado,
        )

    return sorted(por_clave.values(), key=lambda ev: (ev.fecha, ev.ticker))


_SEPARADORES_CLASE_ACCION = str.maketrans({".": "-", "/": "-"})


def normalizar_ticker(ticker: str) -> str:
    """Normaliza el separador de una acción de doble clase para comparar.

    Cada fuente representa una acción de doble clase con un separador
    distinto para el mismo ticker: Alpha Vantage usa punto (`BF.B`), el
    screener de Nasdaq usa barra (`BF/B`). Un cruce por cadena exacta entre
    las dos nunca coincide, y el evento se pierde en
    `filtrar_por_capitalizacion` aunque la fuente de fechas sí lo cubra —
    confirmado el 19/08/2026 con `BF.B` (Brown-Forman): tenía fecha real en
    Alpha Vantage y se descartaba igualmente por "sin capitalización
    conocida". Este es el único sitio del código donde se compara un ticker
    de una fuente contra el de otra; normalizar aquí basta.

    Solo unifica el separador (`.`, `/` → `-`) tras pasar a mayúsculas y
    quitar espacios — no toca nada más: no es una normalización general de
    símbolos, es la que hace falta para este cruce concreto.
    """
    return ticker.strip().upper().translate(_SEPARADORES_CLASE_ACCION)


def filtrar_por_capitalizacion(
    eventos: list[EventoResultado],
    universo: list[ValorScreener],
    minimo_usd: float,
) -> list[EventoResultado]:
    """Conserva solo los eventos de tickers con capitalización > `minimo_usd`.

    Un ticker que no aparece en el universo del screener (p. ej. deslistado
    entre la descarga del universo y la de earnings) se excluye: sin
    capitalización conocida no se puede aplicar el filtro, y la opción
    conservadora es no publicarlo, no asumir que cumple el mínimo. La
    comparación se hace sobre el ticker normalizado (ver
    `normalizar_ticker`); el evento publicado conserva su ticker original,
    tal cual lo dio su fuente — la normalización es solo para encontrar la
    capitalización correcta, no cambia lo que se publica.
    """
    capitalizacion_por_ticker = {
        normalizar_ticker(v.ticker): v.capitalizacion_usd
        for v in universo
        if v.capitalizacion_usd is not None
    }
    return [
        ev
        for ev in eventos
        if (cap := capitalizacion_por_ticker.get(normalizar_ticker(ev.ticker))) is not None
        and cap > minimo_usd
    ]


__all__ = [
    "EventoResultado",
    "TrimestreInvalidoError",
    "normalizar_trimestre",
    "normalizar_franja_nasdaq",
    "normalizar_franja_alphavantage",
    "normalizar_ticker",
    "fusionar",
    "filtrar_por_capitalizacion",
]
