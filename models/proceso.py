"""Modelo de dominio: el proceso y su ciclo de vida.

Un ``Proceso`` representa la unidad de trabajo que compite por la CPU. Sus
datos de definicion (pid, llegada, rafaga, prioridad, rafaga de E/S) son
inmutables en la practica; su estado de ejecucion cambia durante la
simulacion y se reinicia con :meth:`reiniciar`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EstadoProceso(Enum):
    """Estados por los que transita un proceso."""

    NUEVO = "Nuevo"
    LISTO = "Listo"
    EJECUCION = "Ejecucion"
    BLOQUEADO = "Bloqueado"
    TERMINADO = "Terminado"

    @property
    def es_final(self) -> bool:
        return self is EstadoProceso.TERMINADO


@dataclass(eq=False)
class Proceso:
    """Proceso con validacion de datos de entrada y estado de simulacion.

    Attributes de definicion (validados en ``__post_init__``):
        pid, llegada, rafaga, prioridad, rafaga_io

    Attributes de ejecucion (gestionados por el simulador):
        estado, restante, tiempo_cpu, espera_acumulada, primer_inicio, fin,
        despertar_en, hizo_io
    """

    pid: int
    llegada: int
    rafaga: int
    prioridad: int = 1
    rafaga_io: int = 0

    estado: EstadoProceso = field(default=EstadoProceso.NUEVO)
    restante: int = field(default=0)
    tiempo_cpu: int = field(default=0)
    espera_acumulada: int = field(default=0)
    primer_inicio: int | None = field(default=None)
    fin: int | None = field(default=None)
    despertar_en: int | None = field(default=None)
    hizo_io: bool = field(default=False)

    def __post_init__(self) -> None:
        if not isinstance(self.pid, int) or isinstance(self.pid, bool):
            raise ValueError("El PID debe ser un entero")
        if self.pid < 0:
            raise ValueError("El PID no puede ser negativo")
        if not isinstance(self.llegada, int) or self.llegada < 0:
            raise ValueError("El tiempo de llegada debe ser un entero >= 0")
        if not isinstance(self.rafaga, int) or self.rafaga < 1:
            raise ValueError("La rafaga debe ser un entero >= 1")
        if not isinstance(self.prioridad, int):
            raise ValueError("La prioridad debe ser un entero")
        if not isinstance(self.rafaga_io, int) or self.rafaga_io < 0:
            raise ValueError("La rafaga de E/S debe ser un entero >= 0")
        if self.restante == 0:
            self.restante = self.rafaga

    # ------------------------------------------------------------------ #
    # Datos derivados (encapsulamiento: se exponen como propiedades)
    # ------------------------------------------------------------------ #
    @property
    def nombre(self) -> str:
        return f"P{self.pid}"

    @property
    def tiempo_retorno(self) -> int | None:
        if self.fin is None:
            return None
        return self.fin - self.llegada

    @property
    def tiempo_respuesta(self) -> int | None:
        if self.primer_inicio is None:
            return None
        return self.primer_inicio - self.llegada

    @property
    def tiempo_espera(self) -> int | None:
        """Espera = retorno - tiempo de CPU util.

        Incluye el tiempo en cola de listos y el bloqueado en E/S: toda la
        vida del proceso por fuera de la CPU. El simulador la desglosa en
        ``esperas`` (tramos ``listo`` y ``bloqueado``), cuya suma por proceso
        coincide con este valor.
        """
        retorno = self.tiempo_retorno
        if retorno is None:
            return None
        return retorno - self.rafaga

    # ------------------------------------------------------------------ #
    @property
    def terminado(self) -> bool:
        return self.estado is EstadoProceso.TERMINADO

    def reiniciar(self) -> None:
        """Devuelve el proceso a su estado inicial (previo a simular)."""
        self.estado = EstadoProceso.NUEVO
        self.restante = self.rafaga
        self.tiempo_cpu = 0
        self.espera_acumulada = 0
        self.primer_inicio = None
        self.fin = None
        self.despertar_en = None
        self.hizo_io = False

    def clonar(self) -> "Proceso":
        return Proceso(
            pid=self.pid,
            llegada=self.llegada,
            rafaga=self.rafaga,
            prioridad=self.prioridad,
            rafaga_io=self.rafaga_io,
        )

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "llegada": self.llegada,
            "rafaga": self.rafaga,
            "prioridad": self.prioridad,
            "rafaga_io": self.rafaga_io,
            "estado": self.estado.value,
            "restante": self.restante,
            "tiempo_cpu": self.tiempo_cpu,
            "espera": self.tiempo_espera,
            "retorno": self.tiempo_retorno,
            "respuesta": self.tiempo_respuesta,
        }

    # Comparaciones: por clave de planificacion (restante, luego llegada, pid)
    def __lt__(self, otro: "Proceso") -> bool:
        return (self.restante, self.llegada, self.pid) < (
            otro.restante,
            otro.llegada,
            otro.pid,
        )

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Proceso) and self.pid == otro.pid

    def __hash__(self) -> int:
        return hash(self.pid)

    def __repr__(self) -> str:  # pragma: no cover - cosmetico
        return f"Proceso(P{self.pid}, lleg={self.llegada}, raf={self.rafaga}, rest={self.restante})"
