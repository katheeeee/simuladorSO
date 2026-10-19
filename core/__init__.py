"""Nucleo independiente de la interfaz: archivos y metricas."""

from .archivos import GestorArchivos, ResultadoCarga
from .metricas import (
    MetricaProceso,
    ResumenMetricas,
    calcular_metricas,
    utilizacion_instantanea,
)

__all__ = [
    "GestorArchivos",
    "ResultadoCarga",
    "MetricaProceso",
    "ResumenMetricas",
    "calcular_metricas",
    "utilizacion_instantanea",
]
