"""Clase base de planificacion (patron Strategy).

El simulador (``SimuladorProcesos``) posee el reloj y el estado de los
procesos; el planificador solo decide *quien corre*. Gracias a esta
separacion cada algoritmo vive en su propio modulo y se intercambia en
tiempo de ejecucion (polimorfismo).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from models.proceso import Proceso


class Planificador(ABC):
    """Interfaz comun a FCFS, SPN, SRT y Round Robin."""

    nombre: str = "Planificador"
    descripcion: str = ""
    preemptivo: bool = False

    def __init__(self, quantum: int | None = None) -> None:
        if quantum is not None and quantum < 1:
            raise ValueError("El quantum debe ser >= 1")
        self.quantum = quantum
        self.reiniciar()

    # ------------------------------------------------------------------ #
    # Ciclo de vida y gestion del conjunto de listos
    # ------------------------------------------------------------------ #
    @abstractmethod
    def reiniciar(self) -> None:
        """Vacia la cola de listos y los contadores internos."""

    @abstractmethod
    def encolar(self, proceso: Proceso) -> None:
        """Incorpora un proceso al conjunto de listos."""

    @abstractmethod
    def retirar(self, proceso: Proceso) -> None:
        """Saca un proceso del conjunto de listos."""

    @abstractmethod
    def vacio(self) -> bool:
        """¿No hay procesos listos?"""

    @abstractmethod
    def siguiente(self) -> Proceso | None:
        """Devuelve (sin retirar) el proximo candidato segun la politica."""

    @abstractmethod
    def listos(self) -> list[Proceso]:
        """Instantanea ordenada de los procesos listos (para la interfaz)."""

    # ------------------------------------------------------------------ #
    # Ganchos opcionales (por defecto, politicas no expropiativas)
    # ------------------------------------------------------------------ #
    def asignar(self, proceso: Proceso) -> None:
        """Se llama cuando un proceso es despachado a la CPU."""

    def notificar_tick(self, proceso: Proceso) -> None:
        """Se llama tras ejecutar una unidad de tiempo del proceso."""

    def debe_preemptar(
        self, actual: Proceso | None, siguiente: Proceso | None
    ) -> bool:
        """¿Debe quitarse la CPU al proceso en ejecucion?"""
        return False

    def contexto(self) -> dict:
        """Datos extra para la interfaz (p. ej. el cuanto)."""
        return {"quantum": self.quantum}
