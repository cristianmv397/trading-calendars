"""Construcción del calendario ICS a partir de eventos ya fusionados.

Requisitos de formato (repetidos aquí porque son los que más se suelen
saltar):

- VTIMEZONE completo para `America/New_York`, nunca horas en UTC fijas: el
  horario de verano de EE. UU. y el de Europa no cambian el mismo día.
- Antes de apertura -> 08:00 hora de Nueva York, 15 min. Tras cierre -> 16:15,
  15 min. Franja desconocida -> evento de día completo (`VALUE=DATE`): la
  ausencia de dato es información, no se inventa una hora por defecto.
- `UID` estable a partir de ticker + trimestre fiscal normalizado — no de la
  fecha ni de nada aleatorio.
- `SEQUENCE` que sube solo cuando cambia fecha o franja de un evento ya
  publicado (comparado contra `estado/publicado.json`).
- Plegado de líneas y escapado: los hace `icalendar` (`Calendar.to_ical()`),
  no se construye el texto a mano.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, Timezone, vText

from fusion import EventoResultado

ZONA_NY = ZoneInfo("America/New_York")
ZONA_UTC = ZoneInfo("UTC")

_TEXTO_FRANJA = {
    "antes_apertura": "antes de apertura",
    "tras_cierre": "tras el cierre",
}


# ---------------------------------------------------------------------------
# UID, SUMMARY, DESCRIPTION
# ---------------------------------------------------------------------------


def construir_uid(ticker: str, trimestre_normalizado: str) -> str:
    """UID determinista: mismo ticker+trimestre -> mismo UID siempre.

    Legible a propósito (no un hash): facilita depurar el ICS a mano.
    """
    return f"{ticker.strip().upper()}-{trimestre_normalizado}@trading-calendars"


def construir_summary(ticker: str, confirmado: bool, franja: str) -> str:
    estado = "confirmado" if confirmado else "ESTIMADO"
    texto_franja = _TEXTO_FRANJA.get(franja)
    if texto_franja:
        return f"{ticker} — resultados ({estado}, {texto_franja})"
    return f"{ticker} — resultados ({estado})"


def construir_description(evento: EventoResultado, fecha_generacion: date) -> str:
    lineas = [
        f"Ticker: {evento.ticker}",
        f"Nombre: {evento.nombre}",
        f"Fuente: {evento.fuente}",
        f"Estado: {'confirmado' if evento.confirmado else 'estimado'}",
    ]
    if evento.eps_estimado:
        lineas.append(f"EPS estimado: {evento.eps_estimado}")
    lineas.append(f"Generado: {fecha_generacion.isoformat()}")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Estado publicado (para SEQUENCE)
# ---------------------------------------------------------------------------


def cargar_estado(ruta: Path) -> dict[str, dict]:
    """Carga `estado/publicado.json`. Vacío si no existe (primera ejecución)."""
    if not ruta.exists():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def calcular_sequence(uid: str, evento: EventoResultado, estado_previo: dict[str, dict]) -> int:
    """Sequence de un evento: 0 si es nuevo, +1 si cambió fecha o franja, igual si no.

    No muta `estado_previo`: es responsabilidad de `guardar_estado` escribir
    el estado nuevo, para que esta función se pueda probar sin efectos
    secundarios.
    """
    anterior = estado_previo.get(uid)
    if anterior is None:
        return 0
    if anterior["fecha"] != evento.fecha.isoformat() or anterior["franja"] != evento.franja:
        return anterior["sequence"] + 1
    return anterior["sequence"]


def guardar_estado(ruta: Path, eventos_con_uid_y_sequence: list[tuple[str, EventoResultado, int]]) -> None:
    """Escribe el estado nuevo, para que la próxima ejecución calcule el SEQUENCE correcto."""
    nuevo_estado = {
        uid: {"fecha": evento.fecha.isoformat(), "franja": evento.franja, "sequence": sequence}
        for uid, evento, sequence in eventos_con_uid_y_sequence
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(nuevo_estado, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# VEVENT y VCALENDAR
# ---------------------------------------------------------------------------


def construir_evento(
    evento: EventoResultado,
    sequence: int,
    fecha_generacion: date,
    hora_antes_apertura: time,
    duracion_antes_apertura_min: int,
    hora_tras_cierre: time,
    duracion_tras_cierre_min: int,
) -> Event:
    ev = Event()
    uid = construir_uid(evento.ticker, evento.trimestre_normalizado)
    ev.add("uid", uid)
    ev.add("summary", vText(construir_summary(evento.ticker, evento.confirmado, evento.franja)))
    ev.add("description", vText(construir_description(evento, fecha_generacion)))
    ev.add("sequence", sequence)
    ev.add("dtstamp", datetime.now(tz=ZONA_UTC))

    if evento.franja == "antes_apertura":
        inicio = datetime.combine(evento.fecha, hora_antes_apertura, tzinfo=ZONA_NY)
        ev.add("dtstart", inicio)
        ev.add("dtend", inicio + timedelta(minutes=duracion_antes_apertura_min))
    elif evento.franja == "tras_cierre":
        inicio = datetime.combine(evento.fecha, hora_tras_cierre, tzinfo=ZONA_NY)
        ev.add("dtstart", inicio)
        ev.add("dtend", inicio + timedelta(minutes=duracion_tras_cierre_min))
    else:  # desconocida -> dia completo, sin inventar una hora
        ev.add("dtstart", evento.fecha)
        ev.add("dtend", evento.fecha + timedelta(days=1))
    return ev


def construir_calendario(
    eventos: list[EventoResultado],
    nombre_calendario: str,
    estado_previo: dict[str, dict],
    fecha_generacion: date,
    hora_antes_apertura: time,
    duracion_antes_apertura_min: int,
    hora_tras_cierre: time,
    duracion_tras_cierre_min: int,
) -> tuple[Calendar, list[tuple[str, EventoResultado, int]]]:
    """Construye el VCALENDAR completo y devuelve también el estado a persistir.

    Se devuelve el estado en vez de escribirlo aquí: esta función no toca
    disco, para poder probarla sin ficheros temporales.
    """
    cal = Calendar()
    cal.add("prodid", "-//trading-calendars//earnings//ES")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", nombre_calendario)
    cal.add("x-wr-timezone", "America/New_York")
    cal.add("refresh-interval;value=duration", "P1D")

    if eventos:
        primera = min(ev.fecha for ev in eventos) - timedelta(days=1)
        ultima = max(ev.fecha for ev in eventos) + timedelta(days=1)
    else:
        primera, ultima = fecha_generacion, fecha_generacion
    cal.add_component(Timezone.from_tzid("America/New_York", first_date=primera, last_date=ultima))

    registro_estado: list[tuple[str, EventoResultado, int]] = []
    for evento in eventos:
        uid = construir_uid(evento.ticker, evento.trimestre_normalizado)
        sequence = calcular_sequence(uid, evento, estado_previo)
        cal.add_component(
            construir_evento(
                evento,
                sequence,
                fecha_generacion,
                hora_antes_apertura,
                duracion_antes_apertura_min,
                hora_tras_cierre,
                duracion_tras_cierre_min,
            )
        )
        registro_estado.append((uid, evento, sequence))

    return cal, registro_estado


__all__ = [
    "ZONA_NY",
    "construir_uid",
    "construir_summary",
    "construir_description",
    "cargar_estado",
    "calcular_sequence",
    "guardar_estado",
    "construir_evento",
    "construir_calendario",
]
