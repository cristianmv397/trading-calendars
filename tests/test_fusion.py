"""Tests de `fusion`: normalización de trimestre y fusión de fuentes."""

from __future__ import annotations

from datetime import date

import pytest

import fusion
from fuentes.alphavantage import EventoAlphaVantage
from fuentes.nasdaq_earnings import EventoNasdaq
from fuentes.nasdaq_screener import ValorScreener


def _av(ticker, fecha, trimestre, franja=None):
    return EventoAlphaVantage(ticker, f"{ticker} Inc", fecha, trimestre, "1.00", "USD", franja)


def _nq(ticker, fecha, trimestre, franja="time-pre-market"):
    return EventoNasdaq(ticker, f"{ticker} Inc", fecha, franja, trimestre, "1.05", "$1,000,000")


# ---------------------------------------------------------------------------
# Normalización de trimestre
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("2026-06-30", "2026-Q2"),
        ("2026-01-05", "2026-Q1"),
        ("2026-12-31", "2026-Q4"),
        ("Jul/2026", "2026-Q3"),
        ("jan/2027", "2027-Q1"),  # minúsculas también
    ],
)
def test_normalizar_trimestre(texto, esperado):
    assert fusion.normalizar_trimestre(texto) == esperado


def test_normalizar_trimestre_formato_desconocido():
    with pytest.raises(fusion.TrimestreInvalidoError):
        fusion.normalizar_trimestre("no es una fecha")


# ---------------------------------------------------------------------------
# Fusión: Nasdaq gana sobre Alpha Vantage
# ---------------------------------------------------------------------------


def test_nasdaq_gana_sobre_alphavantage_en_el_mismo_trimestre():
    av = [_av("AAPL", "2026-10-25", "2026-09-30")]  # estimado, AV
    nq = [_nq("AAPL", "2026-10-29", "Sep/2026")]  # confirmado, Nasdaq: misma Q3

    fundidos = fusion.fusionar(av, nq)
    assert len(fundidos) == 1
    ev = fundidos[0]
    assert ev.confirmado is True
    assert ev.fuente == "nasdaq"
    assert ev.fecha == date(2026, 10, 29)  # la fecha de Nasdaq, no la de AV


def test_alphavantage_se_conserva_si_nasdaq_no_lo_cubre():
    av = [_av("JPM", "2026-10-14", "2026-09-30")]
    fundidos = fusion.fusionar(av, [])
    assert len(fundidos) == 1
    assert fundidos[0].confirmado is False
    assert fundidos[0].fuente == "alphavantage"


def test_nasdaq_sin_equivalente_en_alphavantage_tambien_se_incluye():
    nq = [_nq("MU", "2026-09-23", "Aug/2026")]
    fundidos = fusion.fusionar([], nq)
    assert len(fundidos) == 1
    assert fundidos[0].confirmado is True


def test_franjas_se_normalizan_en_la_fusion():
    nq = [_nq("WMT", "2026-08-20", "Jul/2026", franja="time-after-hours")]
    fundidos = fusion.fusionar([], nq)
    assert fundidos[0].franja == "tras_cierre"


# ---------------------------------------------------------------------------
# Filtro por capitalización
# ---------------------------------------------------------------------------


def test_filtrar_por_capitalizacion():
    eventos = fusion.fusionar(
        [_av("BIG", "2026-10-01", "2026-09-30"), _av("SMALL", "2026-10-01", "2026-09-30")],
        [],
    )
    universo = [
        ValorScreener("BIG", "Big Co", 50_000_000_000.0),
        ValorScreener("SMALL", "Small Co", 500_000_000.0),
    ]
    filtrados = fusion.filtrar_por_capitalizacion(eventos, universo, minimo_usd=2_000_000_000)
    assert [e.ticker for e in filtrados] == ["BIG"]


def test_ticker_sin_capitalizacion_conocida_se_excluye():
    eventos = fusion.fusionar([_av("GHOST", "2026-10-01", "2026-09-30")], [])
    filtrados = fusion.filtrar_por_capitalizacion(eventos, universo=[], minimo_usd=0)
    assert filtrados == []


# ---------------------------------------------------------------------------
# Normalización de ticker: acciones de doble clase, cada fuente con su
# separador. Caso real detectado el 19/08/2026: BF.B (Brown-Forman) se
# perdía en el filtro de capitalización porque Alpha Vantage lo da como
# "BF.B" y el screener de Nasdaq como "BF/B" -- nunca coincidían.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ticker,esperado",
    [
        ("BF.B", "BF-B"),
        ("BF/B", "BF-B"),
        ("BF-B", "BF-B"),
        ("BRK.A", "BRK-A"),
        ("BRK/A", "BRK-A"),
        ("aapl", "AAPL"),  # sigue pasando a mayúsculas
        (" MU ", "MU"),  # sigue quitando espacios
    ],
)
def test_normalizar_ticker(ticker, esperado):
    assert fusion.normalizar_ticker(ticker) == esperado


def test_filtrar_por_capitalizacion_bf_b_alphavantage_punto_screener_barra():
    """El caso real: BF.B en Alpha Vantage, BF/B en el screener -- debe coincidir."""
    eventos = fusion.fusionar([_av("BF.B", "2026-09-02", "2026-07-31")], [])
    universo = [ValorScreener("BF/B", "Brown-Forman Corporation", 15_000_000_000.0)]
    filtrados = fusion.filtrar_por_capitalizacion(eventos, universo, minimo_usd=2_000_000_000)
    assert [e.ticker for e in filtrados] == ["BF.B"]  # el ticker publicado no cambia, solo la comparación


def test_filtrar_por_capitalizacion_brk_b_alphavantage_guion_screener_barra():
    eventos = fusion.fusionar([_av("BRK-B", "2026-08-02", "2026-06-30")], [])
    universo = [ValorScreener("BRK/B", "Berkshire Hathaway Inc.", 1_100_000_000_000.0)]
    filtrados = fusion.filtrar_por_capitalizacion(eventos, universo, minimo_usd=2_000_000_000)
    assert [e.ticker for e in filtrados] == ["BRK-B"]


def test_filtrar_por_capitalizacion_no_confunde_clases_distintas():
    """BRK/A y BRK/B no deben mezclarse entre sí al normalizar -- solo cambia el separador."""
    eventos = fusion.fusionar(
        [_av("BRK.A", "2026-08-02", "2026-06-30"), _av("BRK.B", "2026-08-02", "2026-06-30")], []
    )
    universo = [
        ValorScreener("BRK/A", "Berkshire Hathaway Inc.", 1_200_000_000_000.0),
        ValorScreener("BRK/B", "Berkshire Hathaway Inc.", 1_100_000_000_000.0),
    ]
    filtrados = fusion.filtrar_por_capitalizacion(eventos, universo, minimo_usd=2_000_000_000)
    assert {e.ticker for e in filtrados} == {"BRK.A", "BRK.B"}
