"""FCFS (First Come, First Served): el primero en llegar, el primero en ser
atendido. No expropiativo; usa una cola FIFO."""

from __future__ import annotations

from collections import deque

from models.proceso import Proceso
from .planificador import Planificador


class FCFS(Planificador):
    nombre = "FCFS"
    descripcion = "First Come, First Served: atiende en orden de llegada (FIFO, no expropiativo)."
    preemptivo = False

    def reiniciar(self) -> None:
        self._cola: deque[Proceso] = deque()

    def encolar(self, proceso: Proceso) -> None:
        self._cola.append(proceso)

    def retirar(self, proceso: Proceso) -> None:
        for i, p in enumerate(self._cola):
            if p.pid == proceso.pid:
                del self._cola[i]
                return

    def vacio(self) -> bool:
        return not self._cola

    def siguiente(self) -> Proceso | None:
        return self._cola[0] if self._cola else None

    def listos(self) -> list[Proceso]:
        return list(self._cola)
