"""Tests de `fuentes.nasdaq_screener`. Solo parseo: sin red."""

from __future__ import annotations

import json

import pytest

from fuentes import nasdaq_screener as ns
from tests.conftest import FIXTURES


def _leer_json(nombre: str) -> dict:
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))


def test_parsea_screener_real():
    cuerpo = _leer_json("nasdaq_screener.json")
    valores = ns.parsear_respuesta(cuerpo)
    assert len(valores) == 5
    nvda = next(v for v in valores if v.ticker == "NVDA")
    assert nvda.capitalizacion_usd == pytest.approx(5_445_242_000_000.0)


def test_capitalizacion_con_simbolo_dolar_tambien_se_parsea():
    """El screener normalmente no lleva '$', pero el parser no debe depender de eso."""
    assert ns._parsear_capitalizacion("$917,327,784,197") == pytest.approx(917_327_784_197.0)


def test_capitalizacion_vacia_es_none():
    cuerpo = _leer_json("nasdaq_screener.json")
    valores = ns.parsear_respuesta(cuerpo)
    nocap = next(v for v in valores if v.ticker == "NOCAP")
    assert nocap.capitalizacion_usd is None


def test_respuesta_sin_table_lanza_error():
    with pytest.raises(ns.NasdaqScreenerError, match="'data.table'"):
        ns.parsear_respuesta({"data": {"filters": None}})
