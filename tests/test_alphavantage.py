"""Tests de `fuentes.alphavantage`. Solo parseo: sin red.

`alphavantage_earnings.csv` mezcla filas reales capturadas de la API
(AGPU, AIV) con filas añadidas a mano (JPM, AAPL, NVDA) para poder probar
tickers conocidos sin depender de dónde caigan alfabéticamente en las 1.815
filas reales que devuelve la API de verdad.
"""

from __future__ import annotations

import pytest

from fuentes import alphavantage as av
from tests.conftest import FIXTURES


def _leer(nombre: str) -> str:
    return (FIXTURES / nombre).read_text(encoding="utf-8")


def test_parsea_csv_real():
    eventos = av.parsear_csv(_leer("alphavantage_earnings.csv"))
    assert len(eventos) == 5
    jpm = next(e for e in eventos if e.ticker == "JPM")
    assert jpm.fecha == "2026-10-14"
    assert jpm.trimestre_fiscal == "2026-09-30"
    assert jpm.estimacion_eps == "4.35"
    assert jpm.franja == "pre-market"


def test_franja_vacia_es_none():
    eventos = av.parsear_csv(_leer("alphavantage_earnings.csv"))
    aiv = next(e for e in eventos if e.ticker == "AIV")
    assert aiv.franja is None
    assert aiv.estimacion_eps is None  # estimate vacío en la fila real


def test_csv_vacio_lanza_error():
    with pytest.raises(av.AlphaVantageError, match="vacía"):
        av.parsear_csv("")


def test_respuesta_corrupta_de_horizon_largo_lanza_error():
    """La respuesta real y corrupta de horizon=6/12month: no debe parsearse como datos."""
    with pytest.raises(av.AlphaVantageError, match="[Ff]echa"):
        av.parsear_csv(_leer("alphavantage_error_corrupto.csv"))


def test_fila_con_numero_de_columnas_distinto_lanza_error():
    with pytest.raises(av.AlphaVantageError, match="columnas"):
        av.parsear_csv(
            "symbol,name,reportDate,fiscalDateEnding,estimate,currency,timeOfTheDay\n"
            "AAPL,Apple Inc,2026-10-29,2026-09-30\n"
        )


def test_cabecera_inesperada_lanza_error():
    with pytest.raises(av.AlphaVantageError, match="[Cc]abecera"):
        av.parsear_csv("foo,bar\n1,2\n")
