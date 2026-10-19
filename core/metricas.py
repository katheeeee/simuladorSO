"""Calculo de metricas de planificacion.

Las metricas se derivan exclusivamente de los registros reales de la
simulacion (intervalos de CPU e instantes de finalizacion de cada proceso),
nunca de datos precargados.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models.evento import Intervalo
from models.proceso import Proceso


@dataclass(frozen=True)
class MetricaProceso:
    pid: int
    nombre: str
    llegada: int
    rafaga: int
    prioridad: int
    primer_inicio: int | None
    fin: int | None
    espera: int | None
    retorno: int | None
    respuesta: int | None
    estado: str

    @classmethod
    def desde_proceso(cls, proceso: Proceso) -> "MetricaProceso":
        return cls(
            pid=proceso.pid,
            nombre=proceso.nombre,
            llegada=proceso.llegada,
            rafaga=proceso.rafaga,
            prioridad=proceso.prioridad,
            primer_inicio=proceso.primer_inicio,
            fin=proceso.fin,
            espera=proceso.tiempo_espera,
            retorno=proceso.tiempo_retorno,
            respuesta=proceso.tiempo_respuesta,
            estado=proceso.estado.value,
        )


@dataclass(frozen=True)
class ConsumoCPU:
    """Tiempo de CPU y porcentaje que consume cada proceso.

    ``unidades`` es el tiempo de CPU realmente ejecutado por el proceso
    (derivado de los intervalos) y ``porcentaje`` su cuota sobre la CPU
    *ocupada* total, es decir, sobre el tiempo en que la CPU no estuvo
    inactiva.
    """

    pid: int
    nombre: str
    unidades: int
    porcentaje: float


@dataclass(frozen=True)
class ResumenMetricas:
    procesos: list[MetricaProceso] = field(default_factory=list)
    espera_prom: float = 0.0
    retorno_prom: float = 0.0
    respuesta_prom: float = 0.0
    uso_cpu: float = 0.0
    tiempo_total: int = 0
    completados: int = 0
    total: int = 0
    max_espera: int = 0
    cpu_ocupada: int = 0


def _promedio(valores: list[int]) -> float:
    return round(sum(valores) / len(valores), 2) if valores else 0.0


def calcular_metricas(
    procesos: list[Proceso], intervalos: list[Intervalo]
) -> ResumenMetricas:
    """Construye el resumen a partir de los procesos y los intervalos de CPU."""
    filas = [MetricaProceso.desde_proceso(p) for p in procesos]
    terminados = [p for p in procesos if p.fin is not None]

    esperas = [p.tiempo_espera for p in terminados if p.tiempo_espera is not None]
    retornos = [p.tiempo_retorno for p in terminados if p.tiempo_retorno is not None]
    respuestas = [
        p.tiempo_respuesta for p in procesos if p.tiempo_respuesta is not None
    ]

    fin_total = max((i.fin for i in intervalos), default=0)
    cpu_ocupada = sum(i.duracion for i in intervalos if not i.inactivo)
    uso = round(cpu_ocupada / fin_total, 4) if fin_total else 0.0

    return ResumenMetricas(
        procesos=filas,
        espera_prom=_promedio(esperas),
        retorno_prom=_promedio(retornos),
        respuesta_prom=_promedio(respuestas),
        uso_cpu=uso,
        tiempo_total=fin_total,
        completados=len(terminados),
        total=len(procesos),
        max_espera=max(esperas, default=0),
        cpu_ocupada=cpu_ocupada,
    )


def consumo_cpu_por_proceso(
    procesos: list[Proceso], intervalos: list[Intervalo]
) -> list[ConsumoCPU]:
    """Reparte la CPU *ocupada* entre los procesos, en unidades y porcentaje.

    Solo se consideran los intervalos reales no inactivos, de modo que la suma
    de ``unidades`` coincide exactamente con ``cpu_ocupada``. Los procesos que
    aun no han ejecutado nada aparecen con 0 unidades y 0 %.
    """
    total = sum(i.duracion for i in intervalos if not i.inactivo)
    por_pid: dict[int, int] = {}
    for intervalo in intervalos:
        if intervalo.inactivo or intervalo.pid is None:
            continue
        por_pid[intervalo.pid] = por_pid.get(intervalo.pid, 0) + intervalo.duracion

    consumos = []
    for proceso in sorted(procesos, key=lambda p: p.pid):
        unidades = por_pid.get(proceso.pid, 0)
        porcentaje = round(100 * unidades / total, 1) if total else 0.0
        consumos.append(
            ConsumoCPU(
                pid=proceso.pid,
                nombre=proceso.nombre,
                unidades=unidades,
                porcentaje=porcentaje,
            )
        )
    return consumos


def utilizacion_instantanea(intervalos: list[Intervalo], instante: int) -> float:
    """Utilizacion simulada en el intervalo que termina en ``instante``.

    Devuelve 1.0 si la CPU ejecuto un proceso durante ese tramo y 0.0 si
    estuvo inactiva. Es la version *instantanea*, distinta de la acumulada
    que calcula :func:`calcular_metricas`.
    """
    if instante <= 0:
        return 0.0
    for intervalo in intervalos:
        if intervalo.inicio <= instante - 1 and intervalo.fin >= instante:
            return 0.0 if intervalo.inactivo else 1.0
    return 0.0
