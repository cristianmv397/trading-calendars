"""Tests de `ics`: UID estable, SEQUENCE, franjas horarias, día completo."""

from __future__ import annotations

from datetime import date, time, timedelta
from zoneinfo import ZoneInfo

import pytest

import ics
from fusion import EventoResultado

HORA_ANTES_APERTURA = time(8, 0)
HORA_TRAS_CIERRE = time(16, 15)


def _evento(ticker="AAPL", fecha=date(2026, 10, 29), franja="tras_cierre", trimestre="2026-Q3"):
    return EventoResultado(ticker, f"{ticker} Inc", fecha, franja, True, "nasdaq", trimestre, "1.50")


# ---------------------------------------------------------------------------
# UID
# ---------------------------------------------------------------------------


def test_uid_es_estable_entre_dos_llamadas():
    e1 = _evento(fecha=date(2026, 10, 29))
    e2 = _evento(fecha=date(2026, 11, 5))  # misma clave ticker+trimestre, fecha distinta
    assert ics.construir_uid(e1.ticker, e1.trimestre_normalizado) == ics.construir_uid(
        e2.ticker, e2.trimestre_normalizado
    )


def test_uid_distinto_para_trimestre_distinto():
    a = ics.construir_uid("AAPL", "2026-Q3")
    b = ics.construir_uid("AAPL", "2026-Q4")
    assert a != b


# ---------------------------------------------------------------------------
# SEQUENCE
# ---------------------------------------------------------------------------


def test_sequence_cero_para_evento_nuevo():
    ev = _evento()
    uid = ics.construir_uid(ev.ticker, ev.trimestre_normalizado)
    assert ics.calcular_sequence(uid, ev, estado_previo={}) == 0


def test_sequence_no_sube_si_no_cambia_nada():
    ev = _evento(fecha=date(2026, 10, 29), franja="tras_cierre")
    uid = ics.construir_uid(ev.ticker, ev.trimestre_normalizado)
    estado_previo = {uid: {"fecha": "2026-10-29", "franja": "tras_cierre", "sequence": 2}}
    assert ics.calcular_sequence(uid, ev, estado_previo) == 2


def test_sequence_sube_si_cambia_la_fecha():
    ev = _evento(fecha=date(2026, 11, 5), franja="tras_cierre")
    uid = ics.construir_uid(ev.ticker, ev.trimestre_normalizado)
    estado_previo = {uid: {"fecha": "2026-10-29", "franja": "tras_cierre", "sequence": 0}}
    assert ics.calcular_sequence(uid, ev, estado_previo) == 1


def test_sequence_sube_si_cambia_solo_la_franja():
    ev = _evento(fecha=date(2026, 10, 29), franja="antes_apertura")
    uid = ics.construir_uid(ev.ticker, ev.trimestre_normalizado)
    estado_previo = {uid: {"fecha": "2026-10-29", "franja": "tras_cierre", "sequence": 0}}
    assert ics.calcular_sequence(uid, ev, estado_previo) == 1


def test_guardar_y_cargar_estado_ida_y_vuelta(tmp_path):
    ev = _evento()
    uid = ics.construir_uid(ev.ticker, ev.trimestre_normalizado)
    ruta = tmp_path / "estado" / "publicado.json"
    ics.guardar_estado(ruta, [(uid, ev, 3)])

    releido = ics.cargar_estado(ruta)
    assert releido[uid] == {"fecha": "2026-10-29", "franja": "tras_cierre", "sequence": 3}


def test_cargar_estado_vacio_si_no_existe_el_fichero(tmp_path):
    assert ics.cargar_estado(tmp_path / "no-existe.json") == {}


# ---------------------------------------------------------------------------
# Franjas horarias: invierno (EST) y verano (EDT)
# ---------------------------------------------------------------------------


def test_antes_apertura_en_invierno_da_hora_local_08_00():
    ev = _evento(fecha=date(2026, 1, 15), franja="antes_apertura")  # EST, UTC-5
    evento_ical = ics.construir_evento(ev, 0, date(2026, 1, 1), HORA_ANTES_APERTURA, 15, HORA_TRAS_CIERRE, 15)
    dtstart = evento_ical["dtstart"].dt
    assert dtstart.hour == 8 and dtstart.minute == 0
    assert dtstart.tzinfo == ZoneInfo("America/New_York")
    # En enero, Nueva York está en EST: UTC-5.
    assert dtstart.utcoffset() == timedelta(hours=-5)


def test_tras_cierre_en_verano_da_hora_local_16_15():
    ev = _evento(fecha=date(2026, 7, 15), franja="tras_cierre")  # EDT, UTC-4
    evento_ical = ics.construir_evento(ev, 0, date(2026, 7, 1), HORA_ANTES_APERTURA, 15, HORA_TRAS_CIERRE, 15)
    dtstart = evento_ical["dtstart"].dt
    assert dtstart.hour == 16 and dtstart.minute == 15
    # En julio, Nueva York está en EDT: UTC-4 (una hora distinta que en invierno).
    assert dtstart.utcoffset() == timedelta(hours=-4)


def test_duracion_del_evento_con_hora():
    ev = _evento(fecha=date(2026, 10, 29), franja="tras_cierre")
    evento_ical = ics.construir_evento(ev, 0, date(2026, 10, 1), HORA_ANTES_APERTURA, 15, HORA_TRAS_CIERRE, 15)
    dtstart, dtend = evento_ical["dtstart"].dt, evento_ical["dtend"].dt
    assert dtend - dtstart == timedelta(minutes=15)


# ---------------------------------------------------------------------------
# Franja desconocida -> día completo
# ---------------------------------------------------------------------------


def test_franja_desconocida_es_evento_de_dia_completo():
    ev = _evento(fecha=date(2026, 8, 22), franja="desconocida")
    evento_ical = ics.construir_evento(ev, 0, date(2026, 8, 1), HORA_ANTES_APERTURA, 15, HORA_TRAS_CIERRE, 15)
    dtstart_prop = evento_ical["dtstart"]
    assert dtstart_prop.dt == date(2026, 8, 22)
    assert dtstart_prop.params.get("VALUE") == "DATE"


# ---------------------------------------------------------------------------
# SUMMARY: la fiabilidad se ve de un vistazo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "confirmado,franja,esperado",
    [
        (True, "tras_cierre", "AAPL — resultados (confirmado, tras el cierre)"),
        (True, "antes_apertura", "AAPL — resultados (confirmado, antes de apertura)"),
        (False, "antes_apertura", "AAPL — resultados (ESTIMADO, antes de apertura)"),
        (True, "desconocida", "AAPL — resultados (confirmado)"),
        (False, "desconocida", "AAPL — resultados (ESTIMADO)"),
    ],
)
def test_summary(confirmado, franja, esperado):
    assert ics.construir_summary("AAPL", confirmado, franja) == esperado


# ---------------------------------------------------------------------------
# Calendario completo: ICS válido, VTIMEZONE presente, cabeceras correctas
# ---------------------------------------------------------------------------


def test_construir_calendario_incluye_vtimezone_y_cabeceras():
    cal, _ = ics.construir_calendario(
        [_evento()], "Test", {}, date(2026, 8, 17), HORA_ANTES_APERTURA, 15, HORA_TRAS_CIERRE, 15
    )
    salida = cal.to_ical().decode("utf-8")
    assert "BEGIN:VTIMEZONE" in salida
    assert "TZID:America/New_York" in salida
    assert "X-WR-CALNAME:Test" in salida
    assert "X-WR-TIMEZONE:America/New_York" in salida
    assert "REFRESH-INTERVAL;VALUE=DURATION:P1D" in salida
    assert "VERSION:2.0" in salida


def test_construir_calendario_sin_eventos_no_falla():
    cal, registro = ics.construir_calendario(
        [], "Vacio", {}, date(2026, 8, 17), HORA_ANTES_APERTURA, 15, HORA_TRAS_CIERRE, 15
    )
    assert registro == []
    assert "BEGIN:VCALENDAR" in cal.to_ical().decode("utf-8")
