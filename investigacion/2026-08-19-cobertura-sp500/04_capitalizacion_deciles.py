"""Paso 3 (complemento): decil de capitalizacion DENTRO del S&P 500 (no del
universo completo del screener, donde el S&P 500 entero cae trivialmente en
los deciles mas altos). Reutiliza el cliente del screener; una peticion mas.
"""
import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import tomllib
from fuentes import nasdaq_screener as ns


def main() -> None:
    with (RAIZ / "config.toml").open("rb") as f:
        config = tomllib.load(f)
    universo = ns.obtener_universo(
        config["nasdaq"]["user_agent"], config["nasdaq"]["origin"], config["nasdaq"]["referer"]
    )
    cap_por_ticker = {v.ticker: v.capitalizacion_usd for v in universo if v.capitalizacion_usd}

    sp500 = list(csv.DictReader((SALIDA / "sp500_constituyentes.csv").open(encoding="utf-8")))
    mid = {r["ticker"] for r in csv.DictReader((SALIDA / "tickers_mid.csv").open(encoding="utf-8"))}

    con_cap = [(c["ticker"], cap_por_ticker.get(c["ticker"])) for c in sp500]
    con_cap = [(t, cap) for t, cap in con_cap if cap is not None]
    caps_ordenadas = sorted(cap for _, cap in con_cap)
    n = len(caps_ordenadas)
    print(f"Componentes del S&P 500 con capitalizacion conocida: {n} de {len(sp500)}")

    def decil_sp500(cap: float) -> int:
        for d in range(1, 11):
            limite = caps_ordenadas[min(int(n * d / 10), n - 1)]
            if cap <= limite:
                return d
        return 10

    filas = []
    for ticker, cap in con_cap:
        ausente = ticker not in mid
        filas.append({"ticker": ticker, "capitalizacion_usd": cap, "decil_sp500": decil_sp500(cap), "ausente": ausente})

    with (SALIDA / "capitalizacion_deciles_sp500.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "capitalizacion_usd", "decil_sp500", "ausente"])
        w.writeheader()
        w.writerows(filas)

    print("\nDecil (1=mas pequeno del S&P 500, 10=mas grande) -> % ausente:")
    for d in range(1, 11):
        del_decil = [f for f in filas if f["decil_sp500"] == d]
        ausentes_decil = [f for f in del_decil if f["ausente"]]
        pct = 100 * len(ausentes_decil) / len(del_decil) if del_decil else 0
        print(f"  D{d:2d}  n={len(del_decil):3d}  ausentes={len(ausentes_decil):3d}  %ausentes={pct:.1f}%")

    print(f"\nGuardado {SALIDA / 'capitalizacion_deciles_sp500.csv'}")


if __name__ == "__main__":
    main()
