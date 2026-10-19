"""SRT (Shortest Remaining Time): version expropiativa de SPN.

Cuando llega un proceso con tiempo restante menor que el del proceso en CPU,
se produce una expropiacion. El proceso en ejecucion no vive en el monticulo,
por lo que sus tiempos restantes en la cola permanecen estables.
"""

from __future__ import annotations

import heapq

from models.proceso import Proceso
from .planificador import Planificador


class SRT(Planificador):
    nombre = "SRT"
    descripcion = "Shortest Remaining Time: expropia si un proceso nuevo tiene menos tiempo restante."
    preemptivo = True

    def reiniciar(self) -> None:
        self._heap: list[tuple[int, int, int]] = []
        self._activos: dict[int, Proceso] = {}

    def _clave(self, proceso: Proceso) -> int:
        return proceso.restante

    def encolar(self, proceso: Proceso) -> None:
        self._activos[proceso.pid] = proceso
        heapq.heappush(
            self._heap, (self._clave(proceso), proceso.llegada, proceso.pid)
        )

    def retirar(self, proceso: Proceso) -> None:
        self._activos.pop(proceso.pid, None)

    def _depurar(self) -> None:
        while self._heap and self._heap[0][2] not in self._activos:
            heapq.heappop(self._heap)

    def vacio(self) -> bool:
        self._depurar()
        return not self._heap

    def siguiente(self) -> Proceso | None:
        self._depurar()
        if not self._heap:
            return None
        return self._activos[self._heap[0][2]]

    def listos(self) -> list[Proceso]:
        self._depurar()
        return [self._activos[pid] for _, _, pid in sorted(self._heap)]

    def debe_preemptar(
        self, actual: Proceso | None, siguiente: Proceso | None
    ) -> bool:
        return (
            actual is not None
            and siguiente is not None
            and siguiente.restante < actual.restante
        )
