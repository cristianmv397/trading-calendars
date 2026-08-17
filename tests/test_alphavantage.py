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


def test_fila_con_fecha_mal_formada_lanza_error():
    """Caso observado el 17/08/2026: un cuerpo con cabecera válida pero una fila
    con datos sin sentido (ver DIAGNÓSTICO CORREGIDO en el docstring del módulo:
    resultó ser un fallo transitorio de la API, no un CSV realmente corrupto,
    pero el parser debe seguir detectando filas con fechas inválidas de todas formas)."""
    with pytest.raises(av.AlphaVantageError, match="[Ff]echa"):
        av.parsear_csv(_leer("alphavantage_error_corrupto.csv"))


def test_respuesta_que_no_es_csv_muestra_el_texto_real_del_servidor():
    """Fixture reconstruida a mano en el estilo típico de un aviso de límite de
    Alpha Vantage (no es una captura literal: nunca vimos el mensaje completo,
    solo una versión truncada a 7 caracteres). Lo que importa es que el error
    muestre el contenido devuelto, no que intente trocearlo como CSV."""
    contenido = _leer("alphavantage_no_es_csv.txt")
    with pytest.raises(av.AlphaVantageError, match="no tiene forma de CSV") as exc_info:
        av.parsear_csv(contenido)
    assert "Alpha Vantage" in str(exc_info.value)  # el texto real es visible en el error


def test_fila_con_numero_de_columnas_distinto_lanza_error():
    with pytest.raises(av.AlphaVantageError, match="columnas"):
        av.parsear_csv(
            "symbol,name,reportDate,fiscalDateEnding,estimate,currency,timeOfTheDay\n"
            "AAPL,Apple Inc,2026-10-29,2026-09-30\n"
        )


def test_cabecera_inesperada_lanza_error():
    with pytest.raises(av.AlphaVantageError, match="[Cc]abecera"):
        av.parsear_csv("symbol,foo\n1,2\n")
