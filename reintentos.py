"""Reintentos con espera creciente para llamadas HTTP a las tres fuentes."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def con_reintentos(
    funcion: Callable[[], T],
    intentos: int = 3,
    espera_base_segundos: float = 1.5,
    excepciones: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Llama a `funcion()` reintentando con espera creciente (1x, 2x, 4x...).

    Relanza la última excepción si se agotan los intentos. No reintenta
    errores que no sean de las `excepciones` indicadas (p. ej. un
    `ValueError` de programación no debería reintentarse como si fuera un
    fallo de red transitorio).
    """
    ultimo_error: Exception | None = None
    for intento in range(intentos):
        try:
            return funcion()
        except excepciones as exc:  # noqa: PERF203 — la excepcion es la señal, no el coste
            ultimo_error = exc
            if intento < intentos - 1:
                time.sleep(espera_base_segundos * (2**intento))
    assert ultimo_error is not None
    raise ultimo_error


__all__ = ["con_reintentos"]
