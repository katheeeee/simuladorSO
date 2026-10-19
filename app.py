"""OS LAB · Simulador de Sistemas Operativos.

Punto de entrada de la aplicación Streamlit. La barra superior (un control
segmentado) decide qué módulo se renderiza; cada módulo mantiene su propio
estado en ``st.session_state`` y delega toda la lógica en los paquetes
``core``, ``schedulers`` y ``concurrency`` (independientes de Streamlit).
"""

from __future__ import annotations

import streamlit as st

from ui import page_concurrencia, page_procesos
from ui.theme import cargar_css

st.set_page_config(
    page_title="OS LAB · Simulador de Sistemas Operativos",
    layout="wide",
)

cargar_css()

OPCIONES = ["Planificación de procesos", "Concurrencia"]

st.markdown(
    '<div class="oslab-encabezado">'
    '<div class="oslab-logo">OS LAB</div>'
    '<div class="oslab-sublogo">Simulador de Sistemas Operativos</div>'
    "</div>",
    unsafe_allow_html=True,
)

pagina = st.segmented_control(
    "Sección",
    OPCIONES,
    default=OPCIONES[0],
    key="nav",
    label_visibility="collapsed",
)
if not pagina:
    pagina = OPCIONES[0]

st.markdown('<div class="oslab-separador"></div>', unsafe_allow_html=True)

if pagina == "Concurrencia":
    page_concurrencia.render()
else:
    page_procesos.render()
