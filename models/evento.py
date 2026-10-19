"""Registro cronologico de eventos.

Cada transicion relevante de una simulacion (llegada, despacho, preempcion,
fin de CPU, bloqueo, operacion ``P``/``V`` de un semaforo, etc.) se anota como
un :class:`Evento`. El historial es la fuente de verdad para los paneles y
para la exportacion a CSV.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Evento:
    """Evento atomico y auditable de la simulacion.

    instante   : tiempo (logico) en que ocurre.
    actor      : quien lo provoca ("CPU", "P1", "Productor", "Agente", ...).
    accion     : que ocurre ("Despacho", "Llegada", "P(empty)", ...).
    recurso    : recurso o proceso afectado ("" si no aplica).
    resultado  : efecto observable ("ejecutando", "bloqueado", "ok", ...).
    categoria  : "planificacion" o "concurrencia" (para filtrar).
    """

    instante: int
    actor: str
    accion: str
    recurso: str = ""
    resultado: str = ""
    categoria: str = "planificacion"

    def to_dict(self) -> dict:
        return {
            "instante": self.instante,
            "actor": self.actor,
            "accion": self.accion,
            "recurso": self.recurso,
            "resultado": self.resultado,
            "categoria": self.categoria,
        }

    @property
    def texto(self) -> str:
        partes = [f"t={self.instante}", self.actor, self.accion]
        if self.recurso:
            partes.append(f"[{self.recurso}]")
        if self.resultado:
            partes.append(f"-> {self.resultado}")
        return " ".join(partes)


@dataclass(frozen=True)
class Intervalo:
    """Tramo de CPU ocupada (o inactiva) registrado por la simulacion.

    Es la materia prima del diagrama cartesiano: cada intervalo se dibuja como
    un segmento horizontal sobre la fila del proceso, entre ``inicio`` y
    ``fin``. Un ``pid`` igual a ``None`` representa CPU inactiva (IDLE).
    """

    pid: int | None
    inicio: int
    fin: int
    algoritmo: str
    nombre: str = field(default="CPU inactiva")

    @property
    def duracion(self) -> int:
        return self.fin - self.inicio

    @property
    def inactivo(self) -> bool:
        return self.pid is None

    def to_dict(self) -> dict:
        return {
            "PID": self.pid if self.pid is not None else "IDLE",
            "Proceso": self.nombre,
            "Inicio": self.inicio,
            "Fin": self.fin,
            "Duracion": self.duracion,
            "Algoritmo": self.algoritmo,
        }


MOTIVO_LISTO = "listo"
MOTIVO_BLOQUEADO = "bloqueado"


@dataclass(frozen=True)
class TramoEspera:
    """Tramo en que un proceso esta fuera de la CPU.

    motivo  : "listo" (esperando en la cola de listos) o "bloqueado"
              (suspended en E/S). Los tramos son semiabiertos ``[inicio, fin)``
              y nunca se solapan con la CPU ni entre si del mismo proceso.
    """

    pid: int
    inicio: int
    fin: int
    motivo: str = MOTIVO_LISTO

    def __post_init__(self) -> None:
        if self.motivo not in (MOTIVO_LISTO, MOTIVO_BLOQUEADO):
            raise ValueError(f"Motivo de espera desconocido: {self.motivo!r}")

    @property
    def duracion(self) -> int:
        return self.fin - self.inicio

    def to_dict(self) -> dict:
        return {
            "PID": self.pid,
            "Inicio": self.inicio,
            "Fin": self.fin,
            "Duracion": self.duracion,
            "Motivo": self.motivo,
        }
