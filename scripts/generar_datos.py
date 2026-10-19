"""Generador de datos TXT de prueba para OS LAB.

Crea dos archivos con el formato que consume ``core.archivos.GestorArchivos``::

    PID,Llegada,Rafaga,Prioridad[,RafagaES]

* El archivo *limpio* contiene exactamente ``n`` procesos validos (1000 por
  defecto) y se lee sin errores ni advertencias.
* El archivo *sucio* contiene los mismos ``n`` procesos validos mas un bloque
  de lineas invalidas, comentarios, lineas en blanco, cabeceras repetidas y
  separadores mezclados (``,``, ``;`` y espacios) para ejercitar el parser.

Uso::

    python scripts/generar_datos.py
    python scripts/generar_datos.py --n 500 --semilla 7
    python scripts/generar_datos.py --limpio salida.txt --sin-sucio
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

N_PROCESOS = 1000
SEMILLA = 42
RUTA_LIMPIO = BASE / "data" / "procesos_1000.txt"
RUTA_SUCIO = BASE / "data" / "procesos_sucios.txt"


def procesos_limpios(n: int, semilla: int) -> list[tuple[int, int, int, int, int | None]]:
    """Devuelve ``n`` procesos deterministas y validos.

    Cada tupla es ``(pid, llegada, rafaga, prioridad, rafaga_io)``; la rafaga
    de E/S es ``None`` cuando el proceso no lleva la quinta columna.
    """
    rng = random.Random(semilla)
    rafaga_inicial = min(100, max(1, n // 10))
    filas = []
    for pid in range(1, n + 1):
        llegada = 0 if pid <= rafaga_inicial else pid - rafaga_inicial
        rafaga = rng.randint(1, 20)
        prioridad = rng.randint(0, 4)
        rafaga_io = rng.randint(1, 6) if pid % 5 == 0 else None
        filas.append((pid, llegada, rafaga, prioridad, rafaga_io))
    return filas


def _llegada(pid: int, burst: int) -> int:
    return 0 if pid <= burst else pid - burst


def _tupla_a_linea(
    fila: tuple[int, int, int, int, int | None], separador: str = ","
) -> str:
    pid, llegada, rafaga, prioridad, rafaga_io = fila
    campos = [str(pid), str(llegada), str(rafaga), str(prioridad)]
    if rafaga_io is not None:
        campos.append(str(rafaga_io))
    return separador.join(campos)


def _encabezado(n: int, semilla: int) -> list[str]:
    return [
        f"# OS LAB - {n} procesos de prueba",
        "# Formato: PID,Llegada,Rafaga,Prioridad[,RafagaES]",
        f"# Generado por scripts/generar_datos.py (semilla={semilla}, n={n})",
        "PID,Llegada,Rafaga,Prioridad,RafagaES",
    ]


def texto_limpio(n: int = N_PROCESOS, semilla: int = SEMILLA) -> str:
    """Texto completo del archivo limpio (determinista para ``n`` y ``semilla``)."""
    filas = procesos_limpios(n, semilla)
    lineas = _encabezado(n, semilla)
    lineas += [_proceso_a_linea(pid, llegada, rafaga, prioridad, io)
               for pid, llegada, rafaga, prioridad, io in filas]
    return "\n".join(lineas) + "\n"


def _proceso_a_linea(pid, llegada, rafaga, prioridad, rafaga_io) -> str:
    campos = [str(pid), str(llegada), str(rafaga), str(prioridad)]
    if rafaga_io is not None:
        campos.append(str(rafaga_io))
    return ",".join(campos)


_LINEAS_INVALIDAS = [
    "999,0,5,2",       # PID duplicado (999 ya existe)
    "1001,5,0,1",      # rafaga fuera de rango (0)
    "1002,5,abc,1",    # valor no numerico
    "1003,5,3",        # faltan columnas (3)
    "1004,5,3,1,2,3",  # columnas de mas (6)
    "1005,5,3,-1",     # prioridad negativa
    "1006,5,3,1,-2",   # rafaga de E/S negativa
    "1007,200000,3,1", # llegada fuera de rango
    "1008,5,1001,1",   # rafaga fuera de rango (1001)
]


def texto_sucio(n: int = N_PROCESOS, semilla: int = SEMILLA) -> str:
    """Texto con ``n`` procesos validos mas casos de error para el parser.

    Incluye comentarios, lineas en blanco, una cabecera repetida y
    separadores mezclados (``,``, ``;`` y espacios), ademas de 9 lineas
    invalidas que deben reportarse con su numero de linea.
    """
    filas = procesos_limpios(n, semilla)
    lineas = _encabezado(n, semilla)
    lineas.append("# A continuacion se mezclan separadores para probar el parser")
    for indice, (pid, llegada, rafaga, prioridad, rafaga_io) in enumerate(filas):
        if indice and indice % 40 == 0:
            lineas.append("")
        if indice and indice % 60 == 0:
            lineas.append("# marca intermedia")
        if indice % 7 == 0:
            separador = ";"
        elif indice % 11 == 0:
            separador = " "
        else:
            separador = ","
        lineas.append(
            _proceso_a_linea(pid, llegada, rafaga, prioridad, rafaga_io)
            .replace(",", separador)
        )
    lineas.append("")
    lineas.append("# --- bloque de casos invalidos (deben reportarse) ---")
    lineas.append("PID,Llegada,Rafaga,Prioridad")  # cabecera repetida: se ignora
    lineas += _LINEAS_INVALIDAS
    return "\n".join(lineas) + "\n"


def escribir(ruta: Path, contenido: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=N_PROCESOS,
                        help="cantidad de procesos validos (por defecto 1000)")
    parser.add_argument("--semilla", type=int, default=SEMILLA,
                        help="semilla del generador (por defecto 42)")
    parser.add_argument("--limpio", type=Path, default=RUTA_LIMPIO,
                        help="ruta del archivo limpio")
    parser.add_argument("--sucio", type=Path, default=RUTA_SUCIO,
                        help="ruta del archivo con errores")
    parser.add_argument("--sin-sucio", action="store_true",
                        help="no generar el archivo con errores")
    args = parser.parse_args(argv)

    escribir(args.limpio, texto_limpio(args.n, args.semilla))
    print(f"Escrito {args.limpio} ({args.n} procesos)")
    if not args.sin_sucio:
        escribir(args.sucio, texto_sucio(args.n, args.semilla))
        print(f"Escrito {args.sucio} ({args.n} validos + errores de prueba)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
