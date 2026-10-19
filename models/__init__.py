"""Modelos de dominio de OS LAB (independientes de la interfaz)."""

from .evento import Evento, Intervalo
from .proceso import EstadoProceso, Proceso
from .recurso import Buffer, Semaforo

__all__ = [
    "Evento",
    "Intervalo",
    "EstadoProceso",
    "Proceso",
    "Buffer",
    "Semaforo",
]
