"""Tests de `fuentes.nasdaq_earnings`. Solo parseo: sin red."""

from __future__ import annotations

import json

import pytest

from fuentes import nasdaq_earnings as ne
from tests.conftest import FIXTURES


def _leer_json(nombre: str) -> dict:
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))


def test_parsea_dia_con_datos():
    cuerpo = _leer_json("nasdaq_earnings_dia_con_datos.json")
    eventos = ne.parsear_respuesta("2026-08-20", cuerpo)
    assert len(eventos) == 5
    wmt = next(e for e in eventos if e.ticker == "WMT")
    assert wmt.fecha == "2026-08-20"  # viene de la petición, no de la fila
    assert wmt.franja == "time-pre-market"
    assert wmt.trimestre_fiscal == "Jul/2026"
    assert wmt.capitalizacion == "$917,327,784,197"


def test_franja_no_suministrada_se_conserva_tal_cual():
    cuerpo = _leer_json("nasdaq_earnings_dia_con_datos.json")
    eventos = ne.parsear_respuesta("2026-08-20", cuerpo)
    hubg = next(e for e in eventos if e.ticker == "HUBG")
    assert hubg.franja == "time-not-supplied"


def test_data_null_entero_no_es_un_error():
    """Fin de semana real (sábado, verificado contra la API): 'data' es null entero."""
    cuerpo = _leer_json("nasdaq_earnings_dia_sin_datos.json")
    eventos = ne.parsear_respuesta("2026-10-10", cuerpo)
    assert eventos == []


def test_rows_null_dentro_de_data_no_es_un_error():
    """Festivo dentro de una semana con datos: 'data' presente, 'rows' es null."""
    cuerpo = _leer_json("nasdaq_earnings_dia_rows_null.json")
    eventos = ne.parsear_respuesta("2026-08-22", cuerpo)
    assert eventos == []


def test_respuesta_con_forma_no_reconocida_lanza_error():
    with pytest.raises(ne.NasdaqError, match="no reconocida"):
        ne.parsear_respuesta("2026-08-20", {"algo": "completamente distinto"})
