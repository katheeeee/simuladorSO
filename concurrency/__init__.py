"""Simuladores de concurrencia (patron Strategy sobre un motor comun).

Cada problema implementa su propio protocolo de sincronizacion sobre el motor
deterministico de :mod:`concurrency.base`. La fabrica :func:`crear` construye
el simulador a partir de su clave y una configuracion.
"""

from __future__ import annotations

from .barbero import Barbero
from .base import (
    Actor,
    EstadoActor,
    InstantaneaConcurrencia,
    Micro,
    SimuladorConcurrencia,
)
from .filosofos import Filosofos
from .fumadores import Fumadores
from .lectores_escritores import LectoresEscritores
from .productor_consumidor import ProductorConsumidor

REGISTRO: dict[str, type[SimuladorConcurrencia]] = {
    "productor_consumidor": ProductorConsumidor,
    "lectores_escritores": LectoresEscritores,
    "filosofos": Filosofos,
    "barbero": Barbero,
    "fumadores": Fumadores,
}

NOMBRES: dict[str, str] = {
    "productor_consumidor": "Productor-Consumidor",
    "lectores_escritores": "Lectores-Escritores",
    "filosofos": "Filósofos comensales",
    "barbero": "Barbero dormilón",
    "fumadores": "Fumadores",
}

DESCRIPCIONES: dict[str, str] = {
    "productor_consumidor": (
        "Procesos que producen y consumen elementos de un buzon acotado, "
        "sincronizados con los semaforos empty, full y mutex."
    ),
    "lectores_escritores": (
        "Acceso concurrente a un recurso con lectores simultaneos y "
        "escritores exclusivos; con prioridad configurable."
    ),
    "filosofos": (
        "Cinco filosofos comparten tenedores; se comparan la solucion "
        "ingenua (interbloqueo), la jerarquica y la del camarero."
    ),
    "barbero": (
        "Un barbero que duerme hasta que llega un cliente; los clientes "
        "esperan en sillas limitadas o se marchan."
    ),
    "fumadores": (
        "El agente coloca dos ingredientes y solo el fumador al que le falta "
        "el tercero puede fumar; protocolo libre de interbloqueo."
    ),
}


def crear(clave: str, **config) -> SimuladorConcurrencia:
    """Fabrica el simulador de concurrencia indicado con su configuracion."""
    if clave not in REGISTRO:
        raise KeyError(f"Simulador de concurrencia desconocido: {clave}")
    return REGISTRO[clave](**config)


def claves() -> list[str]:
    return list(REGISTRO.keys())


__all__ = [
    "Actor",
    "EstadoActor",
    "InstantaneaConcurrencia",
    "Micro",
    "SimuladorConcurrencia",
    "ProductorConsumidor",
    "LectoresEscritores",
    "Filosofos",
    "Barbero",
    "Fumadores",
    "REGISTRO",
    "NOMBRES",
    "DESCRIPCIONES",
    "crear",
    "claves",
]
