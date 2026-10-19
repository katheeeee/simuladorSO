"""Paleta, tipografia y carga del CSS personalizado de OS LAB.

Estilo *retro pastel* (finales de los 70 / principios de los 80): fondo crema,
colores calidos suaves y bordes redondeados con sombras duras tipo pegatina.
Se usan solo fuentes del sistema para no depender de la red.
"""

from __future__ import annotations

import colorsys
from pathlib import Path

import streamlit as st

BASE = Path(__file__).resolve().parent.parent
RUTA_CSS = BASE / "assets" / "style.css"
RUTA_EJEMPLO = BASE / "data" / "procesos_ejemplo.txt"

# Paleta retro pastel, consistente por proceso (se reutiliza en el diagrama
# cartesiano, los chips de estado, las barras de consumo y las tablas).
PALETA = [
    "#E38B66",  # terracota
    "#F6B48C",  # melocoton
    "#E8A0A0",  # rosa viejo
    "#EAC4D5",  # rosa palo
    "#F5DFA4",  # mantequilla
    "#B6D7A8",  # salvia
    "#9EC5E0",  # celeste
    "#C3AED6",  # lavanda
    "#F2C7A0",  # arena
    "#A9D6CB",  # aguamarina
    "#D8B4C8",  # orquidea
    "#AEC6CF",  # gris azulado
]

COL_INACTIVA = "#D8CBB6"
COL_CURSOR = "#D9683B"

# Franja inferior del diagrama: recuento de procesos fuera de la CPU.
COL_ESPERA_LISTO = "#9EC5E0"  # celeste (cola de listos)
COL_ESPERA_BLOQUEADO = "#C3AED6"  # lavanda (bloqueo por E/S)

# Colores del grafico (fondo crema, grilla tenue, texto tinta).
COL_PAPEL = "#FBF3E4"
COL_FONDO_GRAFICO = "#FFFDF8"
COL_GRILLA = "#EFE3CE"
COL_TEXTO_EJE = "#6B584C"

# Tipografia del sistema: cuerpo redondeado y valores en monoespaciada.
FUENTE = "'Trebuchet MS', 'Avenir Next', 'Segoe UI', system-ui, sans-serif"
FUENTE_MONO = "'IBM Plex Mono', 'DejaVu Sans Mono', 'Courier New', monospace"


def cargar_css() -> None:
    """Inyecta ``assets/style.css`` en la app (solo una vez por ejecucion)."""
    if not RUTA_CSS.exists():
        return
    css = RUTA_CSS.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _tono_pastel(indice: int) -> str:
    """Genera un color pastel estable para indices fuera de ``PALETA``.

    Usa el angulo aureo para repartir los matices y fija saturacion y brillo
    en un rango pastel, de modo que aun con muchos procesos los colores siguen
    siendo distinguibles y coherentes con el estilo.
    """
    proporcion = 0.618033988749895
    matiz = (indice * proporcion) % 1.0
    r, g, b = colorsys.hsv_to_rgb(matiz, 0.42, 0.9)
    return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"


def color_pid(pid: int | None, pids: list[int] | None = None) -> str:
    """Color estable de un proceso segun su posicion en la lista de PIDs."""
    if pid is None:
        return COL_INACTIVA
    if not pids:
        return PALETA[0]
    idx = pids.index(pid) if pid in pids else 0
    if idx < len(PALETA):
        return PALETA[idx]
    return _tono_pastel(idx)
