"""Punto de entrada: genera `docs/earnings-large.ics` y `docs/earnings-mid.ics`.

Orden de ejecución:

1. Universo y capitalización (screener de Nasdaq, 1 petición).
2. Esqueleto del año (Alpha Vantage `EARNINGS_CALENDAR`, 1 petición).
3. Calendario de resultados de Nasdaq, día a día, para el horizonte
   configurado (con caché en disco para no repetir peticiones al depurar).
4. Fusión: Nasdaq sobrescribe a Alpha Vantage en el mismo ticker+trimestre
   y se marca `confirmado`.
5. Filtrado por capitalización: dos listas, large y mid (mid incluye a
   large — ver config.toml).
6. Construcción de los dos `VCALENDAR`, con `SEQUENCE` calculado contra el
   estado publicado la última vez.
7. Solo si TODO lo anterior tuvo éxito se escriben los ficheros de salida.
   Si algo falla, no se toca nada de lo ya publicado y se sale con código
   distinto de cero (regla explícita del proyecto: mejor no publicar que
   publicar un ICS a medias encima del bueno).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib

import fusion
import ics
from fuentes import alphavantage as av
from fuentes import nasdaq_earnings as ne
from fuentes import nasdaq_screener as ns
from reintentos import con_reintentos

RAIZ = Path(__file__).resolve().parent


class GenerateError(RuntimeError):
    """Fallo irrecuperable de la generación: no se debe escribir nada."""


# ---------------------------------------------------------------------------
# Configuración y .env
# ---------------------------------------------------------------------------


def cargar_dotenv(ruta: Path, entorno: dict | None = None) -> None:
    """`.env` opcional para no reintroducir ALPHAVANTAGE_API_KEY cada sesión.

    No sobrescribe variables ya presentes en el entorno, no falla si el
    fichero no existe. Mismo patrón que `trading-stack/motor/escaner.py`.
    """
    entorno = os.environ if entorno is None else entorno
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave:
            entorno.setdefault(clave, valor)


def cargar_config(ruta: Path) -> dict:
    with ruta.open("rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# Descarga de Nasdaq earnings, día a día, con caché en disco
# ---------------------------------------------------------------------------


def obtener_earnings_nasdaq_horizonte(
    fecha_inicio: date,
    dias_horizonte: int,
    config_nasdaq: dict,
    directorio_cache: Path | None,
) -> list[ne.EventoNasdaq]:
    """Descarga el calendario de resultados de Nasdaq para cada día del horizonte.

    Si `directorio_cache` no es None, cachea el JSON crudo de cada día ahí:
    relanzar el script el mismo día no repite las peticiones. El caché no
    tiene fecha de caducidad propia porque solo sirve para depurar en local
    — en CI el directorio parte vacío en cada ejecución.
    """
    eventos: list[ne.EventoNasdaq] = []
    for offset in range(dias_horizonte):
        fecha = (fecha_inicio + timedelta(days=offset)).isoformat()
        cuerpo = None
        ruta_cache = directorio_cache / f"{fecha}.json" if directorio_cache else None

        if ruta_cache is not None and ruta_cache.exists():
            cuerpo = json.loads(ruta_cache.read_text(encoding="utf-8"))
        else:
            cuerpo = con_reintentos(
                lambda f=fecha: ne.descargar_dia_crudo(
                    f, config_nasdaq["user_agent"], config_nasdaq["origin"], config_nasdaq["referer"]
                ),
                excepciones=(ne.NasdaqError,),
            )
            if ruta_cache is not None:
                ruta_cache.parent.mkdir(parents=True, exist_ok=True)
                ruta_cache.write_text(json.dumps(cuerpo), encoding="utf-8")

        eventos.extend(ne.parsear_respuesta(fecha, cuerpo))
    return eventos


# ---------------------------------------------------------------------------
# index.html
# ---------------------------------------------------------------------------


REPO_GITHUB = "cristianmv397/trading-calendars"


def construir_index_html(fecha_generacion: date, url_base: str) -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>trading-calendars — calendario de resultados</title>
</head>
<body>
<h1>Calendario de resultados trimestrales (EE. UU.)</h1>
<p>Generado el {fecha_generacion.isoformat()}. Fuentes: Nasdaq (confirmado) y
Alpha Vantage (estimado) — ver <a href="https://github.com/{REPO_GITHUB}">README</a>
para el detalle de cómo se combinan y con qué fiabilidad.</p>
<ul>
<li><a href="{url_base}/earnings-large.ics">earnings-large.ics</a> — capitalización &gt; 10.000 M USD</li>
<li><a href="{url_base}/earnings-mid.ics">earnings-mid.ics</a> — capitalización &gt; 2.000 M USD (incluye large)</li>
</ul>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------


def generar(config: dict, api_key: str, fecha_referencia: date, directorio_cache: Path | None) -> dict:
    """Ejecuta todo el pipeline EN MEMORIA y devuelve lo que hay que escribir.

    No toca disco de salida (`docs/`, `estado/`): eso lo hace `escribir()`,
    y solo si esta función termina sin excepción. Lanza `GenerateError` (o
    deja propagar el error original de la fuente) si algo falla.
    """
    universo = con_reintentos(
        lambda: ns.obtener_universo(
            config["nasdaq"]["user_agent"], config["nasdaq"]["origin"], config["nasdaq"]["referer"]
        ),
        excepciones=(ns.NasdaqScreenerError,),
    )
    if not universo:
        raise GenerateError("El screener de Nasdaq devolvió un universo vacío.")

    eventos_av = con_reintentos(
        lambda: av.obtener_calendario(api_key, horizon=config["alphavantage"]["horizon"]),
        excepciones=(av.AlphaVantageError,),
    )
    if not eventos_av:
        raise GenerateError("Alpha Vantage devolvió un calendario de resultados vacío.")

    eventos_nasdaq = obtener_earnings_nasdaq_horizonte(
        fecha_referencia, config["nasdaq"]["dias_horizonte"], config["nasdaq"], directorio_cache
    )

    fundidos = fusion.fusionar(eventos_av, eventos_nasdaq)
    if not fundidos:
        raise GenerateError("La fusión de fuentes no produjo ningún evento.")

    eventos_large = fusion.filtrar_por_capitalizacion(
        fundidos, universo, config["capitalizacion"]["large_cap_usd"]
    )
    eventos_mid = fusion.filtrar_por_capitalizacion(
        fundidos, universo, config["capitalizacion"]["mid_cap_usd"]
    )

    ruta_estado = RAIZ / config["salida"]["directorio_estado"] / "publicado.json"
    estado_previo = ics.cargar_estado(ruta_estado)

    hora_antes = time.fromisoformat(config["horas"]["antes_apertura_hora"])
    hora_tras = time.fromisoformat(config["horas"]["tras_cierre_hora"])

    cal_large, _ = ics.construir_calendario(
        eventos_large,
        "Resultados trimestrales — Large Cap (>10.000M$)",
        estado_previo,
        fecha_referencia,
        hora_antes,
        config["horas"]["antes_apertura_duracion_minutos"],
        hora_tras,
        config["horas"]["tras_cierre_duracion_minutos"],
    )
    # eventos_mid ⊇ eventos_large (ver config.toml): su registro de estado ya
    # cubre todo lo publicado, así que es el único que hace falta persistir.
    cal_mid, registro_estado_mid = ics.construir_calendario(
        eventos_mid,
        "Resultados trimestrales — Mid Cap (>2.000M$)",
        estado_previo,
        fecha_referencia,
        hora_antes,
        config["horas"]["antes_apertura_duracion_minutos"],
        hora_tras,
        config["horas"]["tras_cierre_duracion_minutos"],
    )

    return {
        "cal_large": cal_large,
        "cal_mid": cal_mid,
        "registro_estado": registro_estado_mid,
        "ruta_estado": ruta_estado,
        "n_universo": len(universo),
        "n_av": len(eventos_av),
        "n_nasdaq": len(eventos_nasdaq),
        "n_large": len(eventos_large),
        "n_mid": len(eventos_mid),
        "eventos_large": eventos_large,
        "eventos_mid": eventos_mid,
    }


def escribir(resultado: dict, config: dict, fecha_generacion: date, url_base: str) -> None:
    """Escribe los ficheros de salida. Solo se llama si `generar()` no lanzó nada."""
    directorio_salida = RAIZ / config["salida"]["directorio_salida"]
    directorio_salida.mkdir(parents=True, exist_ok=True)

    (directorio_salida / config["salida"]["calendario_nombre_large"]).write_bytes(
        resultado["cal_large"].to_ical()
    )
    (directorio_salida / config["salida"]["calendario_nombre_mid"]).write_bytes(
        resultado["cal_mid"].to_ical()
    )
    (directorio_salida / "index.html").write_text(
        construir_index_html(fecha_generacion, url_base), encoding="utf-8"
    )
    ics.guardar_estado(resultado["ruta_estado"], resultado["registro_estado"])


def main(argv: list[str] | None = None) -> int:
    cargar_dotenv(RAIZ / ".env")
    api_key = os.environ.get("ALPHAVANTAGE_API_KEY")
    if not api_key:
        print("Falta la variable de entorno ALPHAVANTAGE_API_KEY (o un .env; ver .env.example).", file=sys.stderr)
        return 1

    config = cargar_config(RAIZ / "config.toml")
    fecha_referencia = date.today()
    directorio_cache = RAIZ / "cache" / "nasdaq_earnings"

    try:
        resultado = generar(config, api_key, fecha_referencia, directorio_cache)
    except (GenerateError, av.AlphaVantageError, ne.NasdaqError, ns.NasdaqScreenerError) as exc:
        print(f"Fallo en la generación, no se ha escrito nada: {exc}", file=sys.stderr)
        return 1

    url_base = os.environ.get("TRADING_CALENDARS_URL_BASE", ".")
    escribir(resultado, config, fecha_referencia, url_base)

    print(
        f"Universo: {resultado['n_universo']}. Alpha Vantage: {resultado['n_av']} filas. "
        f"Nasdaq (horizonte): {resultado['n_nasdaq']} filas. "
        f"Large: {resultado['n_large']} eventos. Mid: {resultado['n_mid']} eventos."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
