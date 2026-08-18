"""Paso 1: extrae el conjunto de tickers de los dos ICS PUBLICADOS (docs/) y
confirma que mid es superconjunto de large.

Sin red: lee los ficheros ya generados en docs/, que son los que sirve
GitHub Pages y los que consume trading-stack/motor/calendario_resultados.py.
"""
import csv
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = Path(__file__).resolve().parent

_RE_TICKER = re.compile(r"UID:([A-Z0-9.]+)-\d{4}-Q[1-4]@")


def tickers_de(ruta: Path) -> set[str]:
    return set(_RE_TICKER.findall(ruta.read_text(encoding="utf-8")))


def main() -> None:
    large = tickers_de(RAIZ / "docs" / "earnings-large.ics")
    mid = tickers_de(RAIZ / "docs" / "earnings-mid.ics")

    print(f"large: {len(large)} tickers")
    print(f"mid:   {len(mid)} tickers")
    fuera = large - mid
    print(f"large que NO estan en mid (deberia ser vacio): {len(fuera)} -> {sorted(fuera)}")
    print(f"mid contiene a large: {large <= mid}")

    (SALIDA / "tickers_large.csv").write_text(
        "\n".join(["ticker"] + sorted(large)) + "\n", encoding="utf-8"
    )
    (SALIDA / "tickers_mid.csv").write_text(
        "\n".join(["ticker"] + sorted(mid)) + "\n", encoding="utf-8"
    )
    print(f"Guardados {SALIDA / 'tickers_large.csv'} y tickers_mid.csv")


if __name__ == "__main__":
    main()
