"""Recursos y mecanismos de sincronizacion *modelados*.

Estos objetos se usan tanto en planificacion (buzon de listos) como en los
simuladores de concurrencia. No usan ``threading``: representan de forma
explicita el contador y las colas de espera para poder mostrar, paso a paso,
como evoluciona cada mecanismo.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional


class Semaforo:
    """Semaforo contador con cola de espera observable (semantica clasica).

    ``P()`` (wait): si el contador es > 0 lo decrementa y continua; si no, el
    actor queda bloqueado en la cola. ``V()`` (signal): si hay bloqueados
    despierta exactamente a uno (sin tocar el contador); si no, incrementa.
    """

    def __init__(self, nombre: str, valor_inicial: int = 0) -> None:
        if valor_inicial < 0:
            raise ValueError("El valor inicial no puede ser negativo")
        self.nombre = nombre
        self.valor_inicial = valor_inicial
        self.valor = valor_inicial
        self.esperando: deque[str] = deque()
        self.operaciones_p = 0
        self.operaciones_v = 0

    def intentar_p(self, actor: str) -> bool:
        """Operacion ``P()``. ``True`` si adquiere, ``False`` si se bloquea."""
        self.operaciones_p += 1
        if self.valor > 0:
            self.valor -= 1
            return True
        self.esperando.append(actor)
        return False

    def v(self) -> Optional[str]:
        """Operacion ``V()``. Devuelve el actor despertado o ``None``."""
        self.operaciones_v += 1
        if self.esperando:
            return self.esperando.popleft()
        self.valor += 1
        return None

    def retirar(self, actor: str) -> bool:
        """Quita a un actor de la cola de espera (desbloqueo forzado).

        Se usa cuando el motor decide reanudar a un actor bloqueado por otro
        motivo (p. ej. el cierre de jornada). Mantiene la cola de espera
        coherente con el estado real de los actores.
        """
        try:
            self.esperando.remove(actor)
            return True
        except ValueError:
            return False

    def reiniciar(self) -> None:
        self.valor = self.valor_inicial
        self.esperando.clear()
        self.operaciones_p = 0
        self.operaciones_v = 0

    @property
    def bloqueados(self) -> tuple[str, ...]:
        return tuple(self.esperando)

    def instantanea(self) -> dict:
        return {
            "nombre": self.nombre,
            "valor": self.valor,
            "bloqueados": list(self.esperando),
        }


@dataclass
class Buffer:
    """Buzon compartido acotado (productor-consumidor, mesa, sala de espera)."""

    nombre: str
    capacidad: int
    elementos: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.capacidad < 1:
            raise ValueError("La capacidad debe ser >= 1")

    @property
    def ocupados(self) -> int:
        return len(self.elementos)

    @property
    def libres(self) -> int:
        return self.capacidad - len(self.elementos)

    @property
    def lleno(self) -> bool:
        return self.ocupados >= self.capacidad

    @property
    def vacio(self) -> bool:
        return not self.elementos

    def insertar(self, elemento) -> None:
        if self.lleno:
            raise ValueError(f"El buffer {self.nombre} esta lleno")
        self.elementos.append(elemento)

    def extraer(self):
        if self.vacio:
            raise ValueError(f"El buffer {self.nombre} esta vacio")
        return self.elementos.pop(0)

    def reiniciar(self) -> None:
        self.elementos.clear()

    def casillas(self) -> list:
        """Vista de la capacidad: valor real o ``None`` (hueco libre)."""
        return self.elementos + [None] * self.libres
