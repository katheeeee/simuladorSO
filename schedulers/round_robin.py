"""Round Robin: alternancia por cuanto con cola circular (FIFO + quantum).

Expropiativo por tiempo. El simulador notifica cada unidad ejecutada; cuando
un proceso agota su cuanto, el planificador pide expropiarlo.
"""

from __future__ import annotations

from collections import deque

from models.proceso import Proceso
from .planificador import Planificador


class RoundRobin(Planificador):
    nombre = "Round Robin"
    descripcion = "Round Robin: reparte la CPU en porciones (quantum) de forma circular."
    preemptivo = True

    def __init__(self, quantum: int = 4) -> None:
        super().__init__(quantum=quantum)

    def reiniciar(self) -> None:
        self._cola: deque[Proceso] = deque()
        self._usado: dict[int, int] = {}

    def encolar(self, proceso: Proceso) -> None:
        if not any(p.pid == proceso.pid for p in self._cola):
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

    # --- contabilidad del cuanto ------------------------------------- #
    def asignar(self, proceso: Proceso) -> None:
        self._usado[proceso.pid] = 0

    def notificar_tick(self, proceso: Proceso) -> None:
        self._usado[proceso.pid] = self._usado.get(proceso.pid, 0) + 1

    def debe_preemptar(
        self, actual: Proceso | None, siguiente: Proceso | None
    ) -> bool:
        if actual is None:
            return False
        return self._usado.get(actual.pid, 0) >= (self.quantum or 1)

    def contexto(self) -> dict:
        return {"quantum": self.quantum}
