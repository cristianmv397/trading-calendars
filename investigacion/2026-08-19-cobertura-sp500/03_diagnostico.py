"""Paso 3 y 4: forma del hueco de cobertura (exchange, sector, capitalizacion,
mes) y diagnostico de por que falta cada componente del S&P 500 ausente --
en el origen (Alpha Vantage / Nasdaq earnings / Nasdaq screener) o en el
pipeline de fusion/filtrado.

Reutiliza los clientes YA EXISTENTES del propio proyecto
(fuentes/alphavantage.py, fuentes/nasdaq_screener.py,
fuentes/nasdaq_earnings.py): no se reimplementa nada de la logica de
peticion HTTP ni del saneado de errores -- esos modulos ya construyen la
URL, meten la clave y sanean cualquier excepcion (nunca str(exc) a pelo).
Este script NO modifica generate.py, fusion.py ni ningun fichero del
generador: solo llama a las funciones de lectura que ya existen.

Llamadas de red que hace:
- Alpha Vantage EARNINGS_CALENDAR: UNA sola peticion (horizon=12month,
  igual que el generador real) -- el plan gratuito es de 25/dia y no hay
  motivo para gastarlo por ticker.
- Screener de Nasdaq: UNA sola peticion (mismo endpoint y parametros que
  usa el generador).
- Nasdaq earnings dia a dia: CERO peticiones nuevas -- se reutiliza el
  cache real de 90 dias en cache/nasdaq_earnings/, generado por la propia
  ejecucion del 17/08/2026 que produjo el ICS publicado que se esta
  auditando. Es el dataset correcto para esta pregunta: no "que dice
  Nasdaq hoy", sino "que dijo Nasdaq cuando se genero el feed publicado".
"""
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import tomllib
from fuentes import alphavantage as av
from fuentes import nasdaq_screener as ns
from fuentes import nasdaq_earnings as ne


def cargar_dotenv(ruta: Path) -> None:
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def cargar_sp500() -> list[dict]:
    with (SALIDA / "sp500_constituyentes.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cargar_tickers_mid() -> set[str]:
    with (SALIDA / "tickers_mid.csv").open(encoding="utf-8") as f:
        return {r["ticker"] for r in csv.DictReader(f)}


def cargar_cache_nasdaq_earnings() -> dict[str, list[dict]]:
    """ticker -> lista de eventos {fecha, trimestre_fiscal, franja} vistos en el cache de 90 dias."""
    directorio = RAIZ / "cache" / "nasdaq_earnings"
    por_ticker: dict[str, list[dict]] = {}
    for ruta in sorted(directorio.glob("*.json")):
        fecha = ruta.stem
        cuerpo = json.loads(ruta.read_text(encoding="utf-8"))
        for ev in ne.parsear_respuesta(fecha, cuerpo):
            por_ticker.setdefault(ev.ticker, []).append(
                {"fecha": ev.fecha, "trimestre_fiscal": ev.trimestre_fiscal, "franja": ev.franja}
            )
    return por_ticker


def decil_capitalizacion(cap: float | None, todos_los_caps: list[float]) -> str:
    if cap is None:
        return "SIN DATO"
    ordenados = sorted(todos_los_caps)
    n = len(ordenados)
    for decil in range(1, 11):
        limite = ordenados[min(int(n * decil / 10), n - 1)]
        if cap <= limite:
            return f"D{decil}"
    return "D10"


def main() -> None:
    cargar_dotenv(RAIZ / ".env")
    api_key = os.environ.get("ALPHAVANTAGE_API_KEY")
    if not api_key:
        print("Falta ALPHAVANTAGE_API_KEY en el entorno o en .env.", file=sys.stderr)
        raise SystemExit(1)

    with (RAIZ / "config.toml").open("rb") as f:
        config = tomllib.load(f)

    sp500 = cargar_sp500()
    tickers_mid = cargar_tickers_mid()
    faltan = [c for c in sp500 if c["ticker"] not in tickers_mid]
    presentes = [c for c in sp500 if c["ticker"] in tickers_mid]

    print(f"S&P 500 (Wikipedia, 503 filas): {len(sp500)}")
    print(f"Presentes en earnings-mid.ics: {len(presentes)}")
    print(f"AUSENTES de earnings-mid.ics: {len(faltan)}")

    # --- Screener de Nasdaq: universo y capitalizacion (una peticion) ---
    print("\nPidiendo el screener de Nasdaq (universo + capitalizacion)...")
    universo = ns.obtener_universo(
        config["nasdaq"]["user_agent"], config["nasdaq"]["origin"], config["nasdaq"]["referer"]
    )
    cap_por_ticker = {v.ticker: v.capitalizacion_usd for v in universo if v.capitalizacion_usd}
    tickers_en_screener = {v.ticker for v in universo}
    print(f"Universo del screener: {len(universo)} valores, {len(cap_por_ticker)} con capitalizacion")

    # --- Alpha Vantage: calendario completo (una peticion) ---
    print("Pidiendo Alpha Vantage EARNINGS_CALENDAR (horizon=12month)...")
    eventos_av = av.obtener_calendario(api_key, horizon=config["alphavantage"]["horizon"])
    av_por_ticker: dict[str, list] = {}
    for e in eventos_av:
        av_por_ticker.setdefault(e.ticker, []).append(e)
    print(f"Alpha Vantage: {len(eventos_av)} filas, {len(av_por_ticker)} tickers distintos")

    # --- Cache real de Nasdaq earnings (90 dias, sin red nueva) ---
    ne_por_ticker = cargar_cache_nasdaq_earnings()
    print(f"Cache de Nasdaq earnings (90 dias, del 17/08/2026): {len(ne_por_ticker)} tickers distintos")

    # -------------------------------------------------------------------
    # Diagnostico por componente ausente: en que paso se pierde.
    # -------------------------------------------------------------------
    filas_diagnostico = []
    for c in faltan:
        t = c["ticker"]
        en_screener = t in tickers_en_screener
        cap = cap_por_ticker.get(t)
        en_av = t in av_por_ticker
        en_ne = t in ne_por_ticker
        mes_av = av_por_ticker[t][0].fecha[:7] if en_av else None  # AAAA-MM

        if not en_screener:
            diagnostico = "AUSENTE del screener de Nasdaq (sin universo/capitalizacion)"
        elif cap is not None and cap <= config["capitalizacion"]["mid_cap_usd"]:
            diagnostico = f"En screener pero cap. {cap:,.0f} USD <= umbral mid ({config['capitalizacion']['mid_cap_usd']:,.0f})"
        elif not en_av and not en_ne:
            diagnostico = "En screener con cap. suficiente, pero AUSENTE de Alpha Vantage Y de Nasdaq earnings (fuente)"
        elif not en_av and en_ne:
            diagnostico = "En screener y en Nasdaq earnings, pero AUSENTE de Alpha Vantage (fuente)"
        elif en_av and not en_ne:
            diagnostico = "En Alpha Vantage pero fuera del horizonte de 90 dias de Nasdaq earnings (o Nasdaq no lo cubrio esos dias) -- deberia haber pasado el filtro de capitalizacion, revisar trimestre"
        else:
            diagnostico = "En screener, en Alpha Vantage Y en Nasdaq earnings -- deberia estar en el ICS, posible fallo del pipeline (fusion/normalizar_trimestre)"

        filas_diagnostico.append({
            "ticker": t,
            "nombre": c["nombre"],
            "sector_gics": c["sector_gics"],
            "exchange": c["exchange"],
            "en_screener_nasdaq": en_screener,
            "capitalizacion_usd": cap,
            "en_alphavantage": en_av,
            "mes_alphavantage": mes_av,
            "en_nasdaq_earnings_cache90d": en_ne,
            "diagnostico": diagnostico,
        })

    with (SALIDA / "ausentes_diagnostico.csv").open("w", newline="", encoding="utf-8") as f:
        campos = list(filas_diagnostico[0].keys())
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas_diagnostico)
    print(f"\nGuardado {SALIDA / 'ausentes_diagnostico.csv'} ({len(filas_diagnostico)} filas)")

    print("\nResumen de diagnostico (cuantos ausentes caen en cada motivo):")
    for motivo, n in Counter(f["diagnostico"].split(" -- ")[0].split(",")[0].split(" (")[0] for f in filas_diagnostico).most_common():
        print(f"  {n:4d}  {motivo}")

    # -------------------------------------------------------------------
    # Forma del hueco: exchange, sector, capitalizacion, mes.
    # -------------------------------------------------------------------
    print("\n--- Exchange ---")
    exch_faltan = Counter(c["exchange"] for c in faltan)
    exch_presentes = Counter(c["exchange"] for c in presentes)
    for ex in ("NYSE", "NASDAQ", "SIN DATO"):
        f_, p_ = exch_faltan.get(ex, 0), exch_presentes.get(ex, 0)
        total = f_ + p_
        pct = 100 * f_ / total if total else 0
        print(f"  {ex:10s}  ausentes={f_:3d}  presentes={p_:3d}  total={total:3d}  %ausentes={pct:.1f}%")

    print("\n--- Sector GICS ---")
    sec_faltan = Counter(c["sector_gics"] for c in faltan)
    sec_presentes = Counter(c["sector_gics"] for c in presentes)
    for sec in sorted(set(sec_faltan) | set(sec_presentes)):
        f_, p_ = sec_faltan.get(sec, 0), sec_presentes.get(sec, 0)
        total = f_ + p_
        pct = 100 * f_ / total if total else 0
        print(f"  {sec:25s}  ausentes={f_:3d}  presentes={p_:3d}  total={total:3d}  %ausentes={pct:.1f}%")

    print("\n--- Capitalizacion por decil (deciles calculados sobre el universo completo del screener) ---")
    todos_los_caps = [v.capitalizacion_usd for v in universo if v.capitalizacion_usd]
    decil_por_ticker_faltan = Counter(
        decil_capitalizacion(cap_por_ticker.get(c["ticker"]), todos_los_caps) for c in faltan
    )
    for decil in [f"D{i}" for i in range(1, 11)] + ["SIN DATO"]:
        print(f"  {decil:8s}  ausentes={decil_por_ticker_faltan.get(decil, 0)}")

    print("\n--- Mes de publicacion previsto (segun Alpha Vantage), solo de los ausentes que SI aparecen alli ---")
    meses_faltan = Counter(f["mes_alphavantage"] for f in filas_diagnostico if f["mes_alphavantage"])
    for mes, n in sorted(meses_faltan.items()):
        print(f"  {mes}  {n}")


if __name__ == "__main__":
    main()
