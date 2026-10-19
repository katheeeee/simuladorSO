"""SPN (Shortest Process Next): no expropiativo; elige la rafaga mas corta.

Se apoya en un monticulo (``heapq``) con eliminacion perezosa, ya que un
proceso puede abandonar la cola de listos cuando es despachado.
"""

from __future__ import annotations

import heapq

from models.proceso import Proceso
from .planificador import Planificador


class SPN(Planificador):
    nombre = "SPN"
    descripcion = "Shortest Process Next (SJF no expropiativo): la rafaga mas corta primero."
    preemptivo = False

    def reiniciar(self) -> None:
        self._heap: list[tuple[int, int, int]] = []
        self._activos: dict[int, Proceso] = {}

    def _clave(self, proceso: Proceso) -> int:
        return proceso.rafaga

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
