"""Componentes visuales reutilizables (tarjetas, chips de estado, paneles).

Todo se genera como HTML embebido para mantener un estilo coherente y no
dependan del CSS por defecto de Streamlit.
"""

from __future__ import annotations

import streamlit as st

from models.proceso import Proceso

from .theme import color_pid


def tarjeta(valor: str | int | float, etiqueta: str, ayuda: str = "") -> None:
    """KPI compacto con valor grande y etiqueta debajo."""
    st.markdown(
        f'<div class="oslab-kpi" title="{ayuda}">'
        f'<div class="oslab-kpi-valor">{valor}</div>'
        f'<div class="oslab-kpi-etiqueta">{etiqueta}</div></div>',
        unsafe_allow_html=True,
    )


def franja_indicadores(items: list[tuple[str, str]]) -> None:
    """Franja compacta de indicadores (valor + etiqueta) en una sola línea."""
    piezas = "".join(
        f'<span class="oslab-franja-item">'
        f'<span class="oslab-franja-valor">{valor}</span>'
        f'<span class="oslab-franja-etiqueta">{etiqueta}</span></span>'
        for valor, etiqueta in items
    )
    st.markdown(f'<div class="oslab-franja">{piezas}</div>',
                unsafe_allow_html=True)


def _chips(procesos: list[Proceso], vacio: str) -> str:
    if not procesos:
        return f'<span class="oslab-chip oslab-chip-vacio">{vacio}</span>'
    pids = sorted(p.pid for p in procesos)
    salida = []
    for p in procesos:
        color = color_pid(p.pid, pids)
        extra = ""
        if p.restante is not None and not p.terminado:
            extra = f'<span class="oslab-chip-restante">{p.restante}</span>'
        salida.append(
            f'<span class="oslab-chip" style="border-left-color:{color}">'
            f"{p.nombre}{extra}</span>"
        )
    return "".join(salida)


def panel_estado(
    titulo: str, procesos: list[Proceso], vacio: str, acento: str
) -> None:
    """Panel de un estado concreto (Listos / Bloqueados / Terminados)."""
    st.markdown(
        f'<div class="oslab-panel" data-acento="{acento}">'
        f'<div class="oslab-panel-titulo">{titulo}'
        f'<span class="oslab-panel-contador">{len(procesos)}</span></div>'
        f'<div class="oslab-chips">{_chips(procesos, vacio)}</div></div>',
        unsafe_allow_html=True,
    )


def paneles_de_estado(listos, bloqueados, terminados) -> None:
    """Los tres grupos de estados en columnas independientes."""
    c1, c2, c3 = st.columns(3)
    with c1:
        panel_estado("Listos", listos, "ninguno", "listo")
    with c2:
        panel_estado("Bloqueados", bloqueados, "ninguno", "bloqueado")
    with c3:
        panel_estado("Terminados", terminados, "ninguno", "terminado")


def cpu_actual(actual: Proceso | None) -> None:
    """Aviso destacado de quien ocupa la CPU ahora mismo."""
    if actual is None:
        st.markdown(
            '<div class="oslab-cpu oslab-cpu-idle">'
            "<b>CPU:</b> inactiva (sin proceso en ejecución)</div>",
            unsafe_allow_html=True,
        )
    else:
        color = color_pid(actual.pid, [actual.pid])
        st.markdown(
            f'<div class="oslab-cpu" style="background:{color}22;'
            f'border-left:5px solid {color}">'
            f"<b>CPU:</b> {actual.nombre} en ejecución · "
            f"restan {actual.restante} de {actual.rafaga} unidades</div>",
            unsafe_allow_html=True,
        )


def cola_de_listos(procesos: list[Proceso], algoritmo: str) -> None:
    """Cola de listos en el orden exacto en que seran atendidos."""
    if not procesos:
        texto = "<span class='oslab-chip oslab-chip-vacio'>cola vacía</span>"
    else:
        texto = " ".join(
            f"<span class='oslab-flecha'>{i + 1}</span>"
            f"<span class='oslab-chip'>{p.nombre}</span>"
            for i, p in enumerate(procesos)
        )
    st.markdown(
        f'<div class="oslab-panel" data-acento="cola">'
        f'<div class="oslab-panel-titulo">Cola de listos · {algoritmo}'
        f'<span class="oslab-panel-contador">{len(procesos)}</span></div>'
        f'<div class="oslab-chips">{texto}</div></div>',
        unsafe_allow_html=True,
    )


def nota_explicacion(texto: str) -> None:
    """Bloque de explicación conceptual."""
    st.markdown(f'<div class="oslab-nota">{texto}</div>', unsafe_allow_html=True)


def resumen_procesos(filas: list[dict]) -> None:
    """Tabla de procesos con columnas de tiempos calculados."""
    import pandas as pd

    if not filas:
        st.caption("No hay procesos cargados.")
        return
    columnas = [
        "pid",
        "nombre",
        "llegada",
        "rafaga",
        "restante",
        "prioridad",
        "estado",
        "espera",
        "retorno",
        "respuesta",
    ]
    df = pd.DataFrame(filas)
    df = df[[c for c in columnas if c in df.columns]]
    df.columns = [
        {
            "pid": "PID",
            "nombre": "Nombre",
            "llegada": "Llegada",
            "rafaga": "Ráfaga",
            "restante": "Restante",
            "prioridad": "Prioridad",
            "estado": "Estado",
            "espera": "Espera",
            "retorno": "Retorno",
            "respuesta": "Respuesta",
        }.get(c, c)
        for c in df.columns
    ]
    st.dataframe(df, width="stretch", hide_index=True)
