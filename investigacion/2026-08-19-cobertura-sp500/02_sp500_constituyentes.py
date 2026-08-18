"""Paso 2: parsea la tabla de componentes del S&P 500 desde Wikipedia.

Fuente: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
Consultada: 19/08/2026 (descarga cruda guardada en
wikipedia_sp500_raw.html, en este mismo directorio, para que el paso sea
reproducible sin depender de que la página no cambie después).

Por qué Wikipedia y no una API de pago: el plan de EODHD contratado por
trading-stack devuelve 403 en `fundamentals` (no cubre listas de índices),
y no hay ninguna otra fuente ya integrada en el proyecto que dé la
composición del S&P 500. Wikipedia mantiene esta tabla activamente
(cambios de composición del índice se reflejan en días), está citada como
la referencia de facto para este dato en el uso común, y es trivialmente
verificable por cualquiera sin clave de API. Limitación aceptada: es una
fuente editada por voluntarios, no el proveedor oficial (S&P Dow Jones
Indices, de pago) — para el propósito de esta investigación (medir un
hueco de cobertura, no operar con el dato) es proporcionada.
"""
import csv
import re
from pathlib import Path

from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent
RUTA_HTML = RAIZ / "wikipedia_sp500_raw.html"
RUTA_SALIDA = RAIZ / "sp500_constituyentes.csv"


def parsear(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tabla = soup.find("table", {"id": "constituents"})
    if tabla is None:
        raise RuntimeError("No se encontro la tabla con id='constituents' en la pagina.")

    filas = tabla.find("tbody").find_all("tr")
    cabecera = [th.get_text(" ", strip=True) for th in filas[0].find_all("th")]

    idx_symbol = cabecera.index("Symbol")
    idx_security = cabecera.index("Security")
    idx_sector = cabecera.index("GICS Sector")
    idx_subindustria = cabecera.index("GICS Sub-Industry")

    componentes = []
    for tr in filas[1:]:
        celdas = tr.find_all(["td", "th"])
        if len(celdas) <= max(idx_symbol, idx_security, idx_sector, idx_subindustria):
            continue
        symbol = celdas[idx_symbol].get_text(" ", strip=True).replace(".", "-")  # BRK.B -> BRK-B, forma habitual de ticker
        nombre = celdas[idx_security].get_text(" ", strip=True)
        sector = celdas[idx_sector].get_text(" ", strip=True)
        subindustria = celdas[idx_subindustria].get_text(" ", strip=True)

        # El exchange no viene como texto de celda: viene en el href del
        # enlace del symbol (nyse.com/quote/XNYS:... o nasdaq.com/...).
        enlace = celdas[idx_symbol].find("a")
        exchange = "SIN DATO"
        if enlace and enlace.get("href"):
            href = enlace["href"]
            if "nyse.com" in href:
                exchange = "NYSE"
            elif "nasdaq.com" in href:
                exchange = "NASDAQ"

        componentes.append({
            "ticker": symbol,
            "nombre": nombre,
            "sector_gics": sector,
            "subindustria_gics": subindustria,
            "exchange": exchange,
        })
    return componentes


def main() -> None:
    html = RUTA_HTML.read_text(encoding="utf-8")
    componentes = parsear(html)
    print(f"Componentes parseados: {len(componentes)}")

    sin_exchange = [c for c in componentes if c["exchange"] == "SIN DATO"]
    print(f"Sin exchange detectado por el link del symbol: {len(sin_exchange)} -> {[c['ticker'] for c in sin_exchange]}")

    with RUTA_SALIDA.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "nombre", "sector_gics", "subindustria_gics", "exchange"])
        writer.writeheader()
        writer.writerows(componentes)
    print(f"Guardado {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
