"""Carga y validacion de procesos desde archivos TXT.

Formato esperado (una linea por proceso)::

    PID,Llegada,Rafaga,Prioridad[,RafagaES]

* La cabecera (p. ej. ``PID,Llegada,Rafaga,Prioridad``) es opcional.
* Se permiten lineas en blanco y comentarios que empiecen con ``#``.
* Los errores se acumulan con el numero de linea para poder mostrarlos.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from models.proceso import Proceso

MAX_PROCESOS = 1000
MAX_RAFAGA = 1000
MAX_LLEGADA = 100000

_CABECERAS = {"pid", "llegada", "rafaga", "prioridad", "rafagaes", "rafaga_es"}


@dataclass
class ResultadoCarga:
    """Resultado de interpretar un archivo de procesos."""

    procesos: list[Proceso] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errores and bool(self.procesos)


class GestorArchivos:
    """Responsable unico de leer/validar/exportar datos de entrada."""

    @staticmethod
    def _separar(linea: str) -> list[str]:
        if "," in linea:
            return [c.strip() for c in linea.split(",")]
        if ";" in linea:
            return [c.strip() for c in linea.split(";")]
        return linea.split()

    @staticmethod
    def parsear(texto: str) -> ResultadoCarga:
        resultado = ResultadoCarga()
        vistos: set[int] = set()

        for numero, cruda in enumerate(texto.splitlines(), start=1):
            linea = cruda.strip()
            if not linea or linea.startswith("#"):
                continue

            campos = GestorArchivos._separar(linea)
            # Cabecera opcional.
            if all(c.lower().replace(" ", "") in _CABECERAS for c in campos):
                continue

            if len(campos) not in (4, 5):
                resultado.errores.append(
                    f"Linea {numero}: se esperaban 4 o 5 columnas "
                    f"(PID,Llegada,Rafaga,Prioridad[,RafagaES]); hay {len(campos)}."
                )
                continue

            try:
                pid = int(float(campos[0]))
                llegada = int(float(campos[1]))
                rafaga = int(float(campos[2]))
                prioridad = int(float(campos[3]))
                rafaga_io = int(float(campos[4])) if len(campos) == 5 else 0
            except ValueError:
                resultado.errores.append(
                    f"Linea {numero}: valor no numerico en '{campos}'."
                )
                continue

            if pid in vistos:
                resultado.errores.append(f"Linea {numero}: PID {pid} duplicado.")
                continue
            if not (0 <= rafaga <= MAX_RAFAGA):
                resultado.errores.append(
                    f"Linea {numero}: rafaga invalida ({rafaga}); debe estar entre 1 y {MAX_RAFAGA}."
                )
                continue
            if rafaga < 1:
                resultado.errores.append(f"Linea {numero}: la rafaga debe ser >= 1.")
                continue
            if not (0 <= llegada <= MAX_LLEGADA):
                resultado.errores.append(
                    f"Linea {numero}: llegada invalida ({llegada})."
                )
                continue
            if prioridad < 0:
                resultado.errores.append(
                    f"Linea {numero}: la prioridad no puede ser negativa."
                )
                continue
            if rafaga_io < 0:
                resultado.errores.append(
                    f"Linea {numero}: la rafaga de E/S no puede ser negativa."
                )
                continue

            vistos.add(pid)
            resultado.procesos.append(
                Proceso(pid, llegada, rafaga, prioridad, rafaga_io)
            )

        if len(resultado.procesos) > MAX_PROCESOS:
            resultado.advertencias.append(
                f"Se cargaron {len(resultado.procesos)} procesos; el maximo "
                f"recomendado es {MAX_PROCESOS}."
            )
        if not resultado.procesos and not resultado.errores:
            resultado.errores.append("El archivo no contiene procesos validos.")
        return resultado

    @staticmethod
    def cargar(ruta: str | Path) -> ResultadoCarga:
        texto = Path(ruta).read_text(encoding="utf-8")
        return GestorArchivos.parsear(texto)

    @staticmethod
    def desde_bytes(datos: bytes) -> ResultadoCarga:
        return GestorArchivos.parsear(datos.decode("utf-8", errors="replace"))

    @staticmethod
    def filas_a_csv(filas: list[dict]) -> str:
        """Serializa una lista de diccionarios a texto CSV."""
        if not filas:
            return ""
        buffer = io.StringIO()
        escritor = csv.DictWriter(buffer, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)
        return buffer.getvalue()
