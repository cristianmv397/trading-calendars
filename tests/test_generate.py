"""Tests de `generate`: solo lo que no toca la red (config, .env, caché, index.html)."""

from __future__ import annotations

import json
from datetime import date

import generate


def test_cargar_dotenv_no_sobrescribe(tmp_path):
    ruta = tmp_path / ".env"
    ruta.write_text("ALPHAVANTAGE_API_KEY=del-fichero\n", encoding="utf-8")
    entorno = {"ALPHAVANTAGE_API_KEY": "de-la-sesion"}
    generate.cargar_dotenv(ruta, entorno)
    assert entorno["ALPHAVANTAGE_API_KEY"] == "de-la-sesion"


def test_cargar_dotenv_rellena_si_falta(tmp_path):
    ruta = tmp_path / ".env"
    ruta.write_text("ALPHAVANTAGE_API_KEY=abc\n", encoding="utf-8")
    entorno = {}
    generate.cargar_dotenv(ruta, entorno)
    assert entorno["ALPHAVANTAGE_API_KEY"] == "abc"


def test_cargar_config_real():
    config = generate.cargar_config(generate.RAIZ / "config.toml")
    assert config["capitalizacion"]["large_cap_usd"] == 10_000_000_000
    assert config["capitalizacion"]["mid_cap_usd"] == 2_000_000_000
    assert config["alphavantage"]["horizon"] == "3month"


def test_index_html_incluye_las_dos_urls():
    html = generate.construir_index_html(date(2026, 8, 17), url_base=".")
    assert "earnings-large.ics" in html
    assert "earnings-mid.ics" in html
    assert "2026-08-17" in html


def test_obtener_earnings_nasdaq_horizonte_usa_cache_sin_tocar_la_red(tmp_path, monkeypatch):
    """Si el JSON del día ya está en caché, no debe llamar a la red en absoluto."""
    directorio_cache = tmp_path / "cache"
    directorio_cache.mkdir()
    (directorio_cache / "2026-08-20.json").write_text(
        json.dumps(
            {
                "data": {
                    "rows": [
                        {
                            "symbol": "AAPL",
                            "name": "Apple Inc.",
                            "time": "time-pre-market",
                            "fiscalQuarterEnding": "Jun/2026",
                            "epsForecast": "1.50",
                            "marketCap": "$3,000,000,000,000",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    def _fallo_si_llama_a_la_red(*a, **kw):
        raise AssertionError("no debería llamar a la red: el día está en caché")

    monkeypatch.setattr("fuentes.nasdaq_earnings.descargar_dia_crudo", _fallo_si_llama_a_la_red)

    eventos = generate.obtener_earnings_nasdaq_horizonte(
        date(2026, 8, 20),
        dias_horizonte=1,
        config_nasdaq={"user_agent": "x", "origin": "x", "referer": "x"},
        directorio_cache=directorio_cache,
    )
    assert len(eventos) == 1
    assert eventos[0].ticker == "AAPL"
