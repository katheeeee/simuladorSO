"""Diagrama cartesiano de la planificación.

En lugar de un Gantt lineal, la ejecución se dibuja sobre un plano:

* eje X = tiempo de simulación
* eje Y = cada proceso (P1, P2, …) y, al final, la fila de CPU inactiva
* cada intervalo real registrado por el motor es un segmento horizontal
  entre su instante de inicio y el de fin

El gráfico se construye **solo** a partir de los ``Intervalo`` que produce el
motor, de modo que refleja exactamente lo ejecutado y conserva el historial
completo al terminar.
"""

from __future__ import annotations

from itertools import accumulate

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from models.evento import MOTIVO_BLOQUEADO, MOTIVO_LISTO, Intervalo, TramoEspera
from models.proceso import EstadoProceso, Proceso

from .theme import (
    COL_CURSOR,
    COL_ESPERA_BLOQUEADO,
    COL_ESPERA_LISTO,
    COL_FONDO_GRAFICO,
    COL_GRILLA,
    COL_INACTIVA,
    COL_PAPEL,
    COL_TEXTO_EJE,
    FUENTE,
    color_pid,
)

COLUMNA_FILA = [
    "PID",
    "Proceso",
    "Inicio",
    "Fin",
    "Duración",
    "Algoritmo",
]


def tabla_intervalos(intervalos: list[Intervalo]) -> pd.DataFrame:
    """DataFrame de los registros (PID, inicio, fin, duración, algoritmo)."""
    if not intervalos:
        return pd.DataFrame(columns=COLUMNA_FILA)
    filas = []
    for i in intervalos:
        d = i.to_dict()
        d["Duracion"] = d["Duracion"]
        filas.append(
            {
                "PID": d["PID"],
                "Proceso": d["Proceso"],
                "Inicio": d["Inicio"],
                "Fin": d["Fin"],
                "Duración": d["Duracion"],
                "Algoritmo": d["Algoritmo"],
            }
        )
    return pd.DataFrame(filas, columns=COLUMNA_FILA)


def pids_visibles(intervalos: list[Intervalo], procesos: list[Proceso]) -> list[int]:
    """Todos los PIDs que deben aparecer en el eje Y (incluidos los no
    ejecutados todavia)."""
    conjunto = {p.pid for p in procesos}
    conjunto |= {i.pid for i in intervalos if i.pid is not None}
    return sorted(conjunto)


_ORDEN_ESTADO = {
    EstadoProceso.EJECUCION: 0,
    EstadoProceso.LISTO: 1,
    EstadoProceso.BLOQUEADO: 2,
    EstadoProceso.NUEVO: 3,
    EstadoProceso.TERMINADO: 4,
}


def _intervalos_por_pid(intervalos: list[Intervalo]) -> dict[int, list[Intervalo]]:
    """Agrupa los intervalos por PID una sola vez (evita O(PID x intervalos))."""
    por_pid: dict[int, list[Intervalo]] = {}
    for i in intervalos:
        if i.pid is not None:
            por_pid.setdefault(i.pid, []).append(i)
    return por_pid


def seleccionar_pids(
    pids: list[int],
    procesos: list[Proceso],
    max_filas: int | None,
) -> list[int]:
    """Ventana de PIDs a dibujar cuando hay demasiados procesos.

    Con cargas grandes se dibujan solo las filas mas relevantes para que el
    paso a paso siga siendo fluido. Se priorizan los procesos activos
    (en ejecucion, listos y bloqueados) y despues los terminados mas
    recientes y los que llegan antes. El resultado se ordena por PID para que
    el eje Y sea estable entre pasos.
    """
    if max_filas is None or max_filas <= 0 or len(pids) <= max_filas:
        return list(pids)
    datos = {p.pid: p for p in procesos}

    def clave(pid: int) -> tuple[int, int, int]:
        p = datos.get(pid)
        if p is None:
            return (3, 0, pid)
        grupo = _ORDEN_ESTADO.get(p.estado, 3)
        if p.estado is EstadoProceso.TERMINADO:
            return (grupo, -(p.fin if p.fin is not None else 0), pid)
        if p.estado is EstadoProceso.NUEVO:
            return (grupo, p.llegada, pid)
        return (grupo, 0, pid)

    elegidos = sorted(pids, key=clave)[:max_filas]
    return sorted(elegidos)



def _alto_adaptativo(n_filas: int) -> int:
    """Alto del grafico segun el numero de filas (procesos + inactiva).

    Con pocas filas usa un alto comodo; al crecer N reduce el alto de cada
    renglon para no generar un lienzo desproporcionado. El resultado se acota
    para mantener el grafico manejable.
    """
    if n_filas <= 24:
        fila = 46
    else:
        fila = max(12, 1000 // n_filas)
    return int(min(max(360, 120 + fila * n_filas), 4000))


def conteo_espera(
    esperas: dict[int, list[TramoEspera]], limite: int
) -> tuple[list[int], list[int]]:
    """Procesos esperando en cada unidad de tiempo: (cola de listos, E/S).

    Usa un arreglo de diferencias, de modo que el costo es O(tramos) y no
    O(tics x procesos), importante con cargas de 1000 procesos.
    """
    dif_listo = [0] * (limite + 1)
    dif_bloqueado = [0] * (limite + 1)
    for tramos in esperas.values():
        for t in tramos:
            a = min(max(t.inicio, 0), limite)
            b = min(max(t.fin, 0), limite)
            if b <= a:
                continue
            if t.motivo == MOTIVO_LISTO:
                dif_listo[a] += 1
                dif_listo[b] -= 1
            else:
                dif_bloqueado[a] += 1
                dif_bloqueado[b] -= 1
    return list(accumulate(dif_listo))[:limite], list(accumulate(dif_bloqueado))[
        :limite
    ]


def figura_cartesiana(
    intervalos: list[Intervalo],
    reloj: int,
    procesos: list[Proceso] | None = None,
    algoritmo: str = "",
    mostrar_cursor: bool = True,
    esperas: dict[int, list[TramoEspera]] | None = None,
    max_filas: int | None = None,
) -> go.Figure:
    """Construye el grafico cartesiano dinamico con cursor vertical.

    Si ``esperas`` viene informado, cada fila del proceso muestra ademas sus
    tramos de espera (celeste translucido en cola de listos, lavanda rayado
    en bloqueo por E/S) y se agrega abajo una franja con el recuento de
    procesos esperando en cada unidad de tiempo.

    ``max_filas`` limita cuantas filas de proceso se dibujan (util con cientos
    o miles de procesos). La franja de espera siempre es global, es decir,
    cuenta a todos los procesos aunque no se dibujen sus filas.
    """
    procesos = procesos or []
    esperas = esperas or {}
    todos = pids_visibles(intervalos, procesos)
    pids = seleccionar_pids(todos, procesos, max_filas)
    recortado = len(pids) < len(todos)
    rafagas = {p.pid: p.rafaga for p in procesos}
    por_pid = _intervalos_por_pid(intervalos)

    def etiqueta(pid: int) -> str:
        rap = rafagas.get(pid)
        return f"P{pid} · {rap}u" if rap is not None else f"P{pid}"

    etiquetas = [etiqueta(pid) for pid in pids] + ["CPU inactiva"]
    indice = {etiqueta(pid): n for n, pid in enumerate(pids)}
    indice["CPU inactiva"] = len(pids)
    fuente_eje = 13 if len(etiquetas) <= 30 else 9

    maximo = max([i.fin for i in intervalos], default=0)
    limite = max(maximo, reloj, 5) + 1

    con_banda = any(esperas.values())
    alto = _alto_adaptativo(len(etiquetas)) + (110 if con_banda else 0)

    if con_banda:
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.8, 0.2],
            vertical_spacing=0.03,
        )
    else:
        fig = go.Figure()

    def _trazo(trace, fila: int = 1) -> None:
        """Agrega un trazo al Gantt (fila 1) o a la franja inferior (fila 2)."""
        if con_banda:
            fig.add_trace(trace, row=fila, col=1)
        else:
            fig.add_trace(trace)

    if not intervalos:
        fig.add_annotation(
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            text="Pulsa «Iniciar» o «Avanzar evento» para registrar "
            "intervalos de ejecución.",
            showarrow=False,
            font=dict(size=14, color=COL_TEXTO_EJE),
        )
    else:
        # Tramos de espera debajo de la ejecucion (el overlay los cubre).
        for pid in pids:
            tramos_esp = esperas.get(pid) or []
            color = color_pid(pid, pids)
            listos = [t for t in tramos_esp if t.motivo == MOTIVO_LISTO]
            bloqueados = [t for t in tramos_esp if t.motivo == MOTIVO_BLOQUEADO]
            if listos:
                _trazo(
                    go.Bar(
                        orientation="h",
                        y=[indice[etiqueta(pid)]] * len(listos),
                        x=[t.duracion for t in listos],
                        base=[t.inicio for t in listos],
                        marker=dict(
                            color=color,
                            opacity=0.35,
                            line=dict(color="#FFFFFF", width=1),
                        ),
                        legendgroup=f"P{pid}",
                        showlegend=False,
                        customdata=[
                            [t.inicio, t.fin, t.duracion] for t in listos
                        ],
                        hovertemplate=(
                            f"<b>P{pid} · en cola de listos</b><br>"
                            "Inicio: %{customdata[0]}<br>"
                            "Fin: %{customdata[1]}<br>"
                            "Duración: %{customdata[2]}<br>"
                            "<extra></extra>"
                        ),
                    )
                )
            if bloqueados:
                _trazo(
                    go.Bar(
                        orientation="h",
                        y=[indice[etiqueta(pid)]] * len(bloqueados),
                        x=[t.duracion for t in bloqueados],
                        base=[t.inicio for t in bloqueados],
                        marker=dict(
                            color=color,
                            opacity=0.55,
                            pattern=dict(shape="\\", solidity=0.35),
                            line=dict(color="#FFFFFF", width=1),
                        ),
                        legendgroup=f"P{pid}",
                        showlegend=False,
                        customdata=[
                            [t.inicio, t.fin, t.duracion] for t in bloqueados
                        ],
                        hovertemplate=(
                            f"<b>P{pid} · bloqueado en E/S</b><br>"
                            "Inicio: %{customdata[0]}<br>"
                            "Fin: %{customdata[1]}<br>"
                            "Duración: %{customdata[2]}<br>"
                            "<extra></extra>"
                        ),
                    )
                )

        # Un trazo por proceso: todos sus segmentos comparten color y leyenda.
        for pid in pids:
            tramos = por_pid.get(pid, [])
            if not tramos:
                # Proceso aun no ejecutado: entra en la leyenda igualmente.
                _trazo(
                    go.Bar(
                        name=f"P{pid}",
                        orientation="h",
                        x=[],
                        y=[],
                        marker=dict(color=color_pid(pid, pids)),
                    )
                )
                continue
            _trazo(
                go.Bar(
                    name=f"P{pid}",
                    orientation="h",
                    y=[indice[etiqueta(pid)]] * len(tramos),
                    x=[i.duracion for i in tramos],
                    base=[i.inicio for i in tramos],
                    marker=dict(
                        color=color_pid(pid, pids),
                        line=dict(color="#FFFFFF", width=1.2),
                    ),
                    customdata=[
                        [i.inicio, i.fin, i.duracion, i.algoritmo] for i in tramos
                    ],
                    hovertemplate=(
                        f"<b>P{pid}</b><br>"
                        "Inicio: %{customdata[0]}<br>"
                        "Fin: %{customdata[1]}<br>"
                        "Duración: %{customdata[2]}<br>"
                        "Algoritmo: %{customdata[3]}"
                        "<extra></extra>"
                    ),
                )
            )

        inactivos = [i for i in intervalos if i.inactivo]
        if inactivos:
            _trazo(
                go.Bar(
                    name="CPU inactiva",
                    orientation="h",
                    y=[indice["CPU inactiva"]] * len(inactivos),
                    x=[i.duracion for i in inactivos],
                    base=[i.inicio for i in inactivos],
                    marker=dict(
                        color=COL_INACTIVA,
                        line=dict(color="#9AA0A6", width=1.2),
                    ),
                    customdata=[
                        [i.inicio, i.fin, i.duracion, i.algoritmo]
                        for i in inactivos
                    ],
                    hovertemplate=(
                        "<b>CPU inactiva</b><br>"
                        "Inicio: %{customdata[0]}<br>"
                        "Fin: %{customdata[1]}<br>"
                        "Duración: %{customdata[2]}<br>"
                        "Algoritmo: %{customdata[3]}"
                        "<extra></extra>"
                    ),
                )
            )

        # Franja inferior: cuantos procesos esperan en cada unidad de tiempo.
        if con_banda:
            tics = list(range(limite))
            listo, bloqueado = conteo_espera(esperas, limite)
            _trazo(
                go.Bar(
                    x=tics,
                    y=listo,
                    name="En espera (cola de listos)",
                    marker=dict(
                        color=COL_ESPERA_LISTO,
                        line=dict(color="#FFFFFF", width=1),
                    ),
                    legendgroup="espera_listo",
                    hovertemplate=(
                        "<b>t = %{x} u</b><br>"
                        "%{y} proceso(s) esperando la CPU"
                        "<extra></extra>"
                    ),
                ),
                fila=2,
            )
            _trazo(
                go.Bar(
                    x=tics,
                    y=bloqueado,
                    base=listo,
                    name="Bloqueado E/S",
                    marker=dict(
                        color=COL_ESPERA_BLOQUEADO,
                        line=dict(color="#FFFFFF", width=1),
                    ),
                    legendgroup="espera_bloqueado",
                    hovertemplate=(
                        "<b>t = %{x} u</b><br>"
                        "%{y} proceso(s) bloqueado(s) en E/S"
                        "<extra></extra>"
                    ),
                ),
                fila=2,
            )

    if mostrar_cursor:
        vline = dict(
            line_width=2.2,
            line_dash="dash",
            line_color=COL_CURSOR,
        )
        if con_banda:
            fig.add_vline(x=reloj, row="all", **vline)
        else:
            fig.add_vline(x=reloj, **vline)
        fig.add_annotation(
            x=reloj,
            y=1.06,
            yref="paper",
            text=f"t = {reloj}",
            showarrow=False,
            font=dict(size=12, color=COL_CURSOR),
            bgcolor=COL_FONDO_GRAFICO,
            bordercolor=COL_CURSOR,
            borderwidth=1,
        )

    fig.update_layout(
        barmode="overlay",
        height=alto,
        margin=dict(l=10, r=16, t=54, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            title_text="" if con_banda else "Procesos",
        ),
        plot_bgcolor=COL_FONDO_GRAFICO,
        paper_bgcolor=COL_PAPEL,
        font=dict(family=FUENTE, size=13),
        hovermode="closest",
        bargap=0.28,
    )
    ejes_x = dict(
        range=[0, limite],
        dtick=max(1, round(limite / 12)) if limite else 1,
        showgrid=True,
        gridcolor=COL_GRILLA,
        gridwidth=1,
        zeroline=False,
        tickformat="d",
        tickfont=dict(color=COL_TEXTO_EJE),
    )
    ejes_y = dict(
        showgrid=True,
        gridcolor=COL_GRILLA,
        zeroline=False,
        fixedrange=True,
        tickfont=dict(color=COL_TEXTO_EJE, size=fuente_eje),
        title_font=dict(color=COL_TEXTO_EJE),
    )
    if con_banda:
        fig.update_xaxes(row=1, col=1, **ejes_x)
        fig.update_xaxes(
            title="Tiempo de simulación",
            title_font=dict(color=COL_TEXTO_EJE),
            row=2,
            col=1,
            **ejes_x,
        )
        fig.update_yaxes(
            title="Procesos",
            autorange="reversed",
            tickmode="array",
            tickvals=list(range(len(etiquetas))),
            ticktext=etiquetas,
            row=1,
            col=1,
            **ejes_y,
        )
        fig.update_yaxes(
            title="En espera (n)",
            title_font=dict(color=COL_TEXTO_EJE, size=11),
            autorange=True,
            rangemode="tozero",
            tickfont=dict(color=COL_TEXTO_EJE, size=11),
            showgrid=True,
            gridcolor=COL_GRILLA,
            zeroline=False,
            fixedrange=True,
            row=2,
            col=1,
        )
    else:
        fig.update_xaxes(title="Tiempo de simulación", **ejes_x)
        fig.update_yaxes(
            title="Procesos",
            autorange="reversed",
            tickmode="array",
            tickvals=list(range(len(etiquetas))),
            ticktext=etiquetas,
            **ejes_y,
        )
    if algoritmo or recortado:
        partes = []
        if algoritmo:
            partes.append(f"Algoritmo: {algoritmo}")
        if recortado:
            partes.append(f"mostrando {len(pids)} de {len(todos)} procesos")
        fig.update_layout(title=dict(text=" · ".join(partes), x=0))
    return fig


def figura_consumo_cpu(
    consumos: list,
    mostrar_cero: bool = True,
    max_barras: int | None = None,
) -> go.Figure:
    """Barras horizontales del % de CPU *ocupada* que consume cada proceso.

    Recibe la salida de ``core.metricas.consumo_cpu_por_proceso``. El color de
    cada barra se toma de la paleta por posición de PID, de modo que coincide
    con el diagrama cartesiano.

    ``max_barras`` acota la cantidad de barras (las de mayor consumo) para
    mantener el grafico manejable con cargas grandes.
    """
    visibles = [c for c in consumos if mostrar_cero or c.unidades > 0]
    recortado = False
    if max_barras and len(visibles) > max_barras:
        visibles = sorted(visibles, key=lambda c: c.unidades, reverse=True)[
            :max_barras
        ]
        recortado = True
    fig = go.Figure()
    if not visibles:
        fig.add_annotation(
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            text="Sin ejecución registrada todavía.",
            showarrow=False,
            font=dict(size=13, color=COL_TEXTO_EJE),
        )
    else:
        pids_orden = sorted(p.pid for p in consumos)
        etiquetas = [c.nombre for c in visibles]
        valores = [c.porcentaje for c in visibles]
        datos = [f"{c.porcentaje:.1f}% · {c.unidades} u" for c in visibles]
        colores = [color_pid(c.pid, pids_orden) for c in visibles]
        fig.add_trace(
            go.Bar(
                orientation="h",
                x=valores,
                y=etiquetas,
                customdata=datos,
                text=datos,
                textposition="auto",
                marker=dict(
                    color=colores,
                    line=dict(color=COL_TEXTO_EJE, width=1),
                ),
                hovertemplate=(
                    "<b>%{y}</b><br>%{customdata}<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        height=max(140, min(900, 40 + 34 * len(visibles))),
        margin=dict(l=10, r=16, t=10, b=10),
        plot_bgcolor=COL_FONDO_GRAFICO,
        paper_bgcolor=COL_PAPEL,
        font=dict(family=FUENTE, size=13, color=COL_TEXTO_EJE),
        showlegend=False,
        bargap=0.32,
    )
    fig.update_xaxes(
        title="% de CPU ocupada",
        range=[0, max([c.porcentaje for c in consumos], default=0) * 1.15 + 1],
        showgrid=True,
        gridcolor=COL_GRILLA,
        zeroline=False,
        ticksuffix="%",
        tickfont=dict(color=COL_TEXTO_EJE),
        title_font=dict(color=COL_TEXTO_EJE),
    )
    fig.update_yaxes(
        autorange="reversed",
        showgrid=False,
        tickfont=dict(color=COL_TEXTO_EJE),
    )
    if recortado:
        fig.add_annotation(
            x=1.0,
            y=1.08,
            xref="paper",
            yref="paper",
            showarrow=False,
            text=f"top {len(visibles)} de {len(consumos)} procesos",
            font=dict(size=11, color=COL_TEXTO_EJE),
        )
    return fig
