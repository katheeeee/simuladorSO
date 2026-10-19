"""Planificadores y el simulador de procesos (patron Strategy)."""

from __future__ import annotations

from .fcfs import FCFS
from .planificador import Planificador
from .round_robin import RoundRobin
from .simulador_procesos import SimuladorProcesos
from .spn import SPN
from .srt import SRT

REGISTRO: dict[str, type[Planificador]] = {
    "fcfs": FCFS,
    "spn": SPN,
    "srt": SRT,
    "rr": RoundRobin,
}

NOMBRES: dict[str, str] = {
    "fcfs": "FCFS",
    "spn": "SPN",
    "srt": "SRT",
    "rr": "Round Robin",
}


def crear(clave: str, quantum: int = 4) -> Planificador:
    """Fabrica un planificador a partir de su clave."""
    if clave not in REGISTRO:
        raise KeyError(f"Algoritmo desconocido: {clave}")
    if clave == "rr":
        return RoundRobin(quantum=quantum)
    return REGISTRO[clave]()


def claves() -> list[str]:
    return list(REGISTRO.keys())


__all__ = [
    "Planificador",
    "FCFS",
    "SPN",
    "SRT",
    "RoundRobin",
    "SimuladorProcesos",
    "REGISTRO",
    "NOMBRES",
    "crear",
    "claves",
]
