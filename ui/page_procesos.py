"""Módulo 1 · Gestión de procesos.

Pantalla de carga, configuración, simulación paso a paso, diagrama
cartesiano, panel de estados, métricas y exportación. Todo el estado vive en
``st.session_state`` y el motor es ajeno a Streamlit.
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from core.archivos import GestorArchivos, ResultadoCarga
from core.metricas import calcular_metricas, consumo_cpu_por_proceso
from models.proceso import Proceso
from schedulers import NOMBRES, SimuladorProcesos
from schedulers import claves as claves_algoritmos
from schedulers import crear

from . import components as cmp
from .chart_procesos import (
    figura_cartesiana,
    figura_consumo_cpu,
    tabla_intervalos,
)
from .theme import RUTA_EJEMPLO

# Ventana de filas dibujadas en el diagrama: etiqueta -> limite (None = todas).
# Con cientos o miles de procesos, limitar las filas mantiene fluido el paso.
VENTANAS = {"80": 80, "40": 40, "160": 160, "Todas": None}
VENTANA_POR_DEFECTO = "80"

# Filas que se envian al navegador en las tablas de registros. Las exportaciones
# CSV conservan siempre el historial completo; solo se acota lo que se dibuja.
MAX_FILAS_TABLA = 400

# Con mas de este numero de procesos, la ejecucion automatica agrupa varios
# eventos por fotograma para terminar en un numero de actualizaciones razonable.
UMBRAL_EVENTOS_POR_FOTOGRAMA = 80


def eventos_por_fotograma(n_procesos: int) -> int:
    """Eventos que avanza la ejecucion automatica en cada actualizacion.

    Con pocos procesos se avanza de uno en uno (paso a paso real, como en la
    demostracion). Con cargas grandes se agrupan para que la simulacion
    termine en un numero acotado de fotogramas en vez de miles.
    """
    if n_procesos <= UMBRAL_EVENTOS_POR_FOTOGRAMA:
        return 1
    return max(1, n_procesos // 8)



def _cargar_ejemplo() -> list[Proceso]:
    return GestorArchivos.cargar(RUTA_EJEMPLO).procesos


def _obtener_simulador(procesos, algoritmo, quantum) -> SimuladorProcesos:
    """Devuelve el simulador vigente; lo (re)construye si cambio la entrada."""
    ss = st.session_state
    firma = (tuple(p.pid for p in procesos), algoritmo, quantum)
    if ss.get("proc_sim") is None or ss.get("proc_firma") != firma:
        ss["proc_sim"] = SimuladorProcesos(procesos, crear(algoritmo, quantum))
        ss["proc_firma"] = firma
        ss["proc_auto"] = False
        ss["proc_auto_toggle"] = False
    return ss["proc_sim"]


def _inicializar(ss: st.session_state) -> None:
    if "proc_procesos" not in ss:
        ss["proc_procesos"] = _cargar_ejemplo()
    ss.setdefault("proc_algoritmo", "fcfs")
    ss.setdefault("proc_quantum", 4)
    ss.setdefault("proc_auto", False)
    ss.setdefault("proc_auto_toggle", False)
    ss.setdefault("proc_velocidad", 0.6)
    ss.setdefault("proc_unidades", 5)
    ss.setdefault("proc_manual", "")
    ss.setdefault("proc_ventana", VENTANA_POR_DEFECTO)


def _sincronizar_auto(sim: SimuladorProcesos, ss: st.session_state) -> None:
    """Sincroniza la bandera de automatismo con el estado real del simulador.

    Se ejecuta **antes** de instanciar el widget toggle: Streamlit prohíbe
    modificar la clave de un widget despues de crearlo.
    """
    if sim.terminado():
        ss["proc_auto"] = False
        ss["proc_auto_toggle"] = False


def _poner_auto(ss: st.session_state, activo: bool) -> None:
    """Cambia la bandera de automatismo en la bandera y en su widget toggle."""
    ss["proc_auto"] = activo
    ss["proc_auto_toggle"] = activo


def _aplicar_carga(
    ss: st.session_state, res: ResultadoCarga
) -> None:
    """Vuelca un ResultadoCarga en el estado, mostrando errores si los hay."""
    if res.errores:
        st.error("Validación de los procesos:")
        for e in res.errores:
            st.markdown(f"- {e}")
        for adv in res.advertencias:
            st.warning(adv)
        return
    ss["proc_procesos"] = res.procesos
    ss["proc_sim"] = None
    ss["proc_auto"] = False
    st.success(f"{len(res.procesos)} procesos cargados.")
    for adv in res.advertencias:
        st.warning(adv)


def _configuracion(ss: st.session_state) -> None:
    """Carga del TXT y configuración del algoritmo (panel superior)."""
    st.markdown('<div class="oslab-seccion">Entrada de procesos</div>',
                unsafe_allow_html=True)
    subido = st.file_uploader(
        "Archivo TXT · PID,Llegada,Rafaga,Prioridad",
        type=["txt"],
        key="proc_uploader",
        help="Formato: PID,Llegada,Rafaga,Prioridad[,RafagaES]",
    )
    if subido is not None:
        _aplicar_carga(ss, GestorArchivos.desde_bytes(subido.getvalue()))

    if st.button("Cargar archivo de ejemplo", width="stretch"):
        ss["proc_procesos"] = _cargar_ejemplo()
        ss["proc_sim"] = None
        ss["proc_auto"] = False

    st.text_area(
        "Entrada manual · una línea por proceso",
        key="proc_manual",
        height=120,
        placeholder="1,0,8,2\n2,1,4,1\n3,2,9,3",
        help="Formato: PID,Llegada,Rafaga,Prioridad[,RafagaES]",
    )
    if st.button("Cargar procesos escritos", width="stretch"):
        _aplicar_carga(ss, GestorArchivos.parsear(ss.get("proc_manual", "")))

    st.markdown('<div class="oslab-seccion">Configuración</div>',
                unsafe_allow_html=True)
    st.selectbox(
        "Algoritmo de planificación",
        claves_algoritmos(),
        format_func=lambda k: NOMBRES[k],
        key="proc_algoritmo",
    )
    if ss["proc_algoritmo"] == "rr":
        st.number_input(
            "Quantum (Round Robin)",
            min_value=1,
            max_value=50,
            step=1,
            key="proc_quantum",
        )
    st.slider(
        "Velocidad de ejecución automática (s)",
        0.1,
        2.0,
        step=0.1,
        key="proc_velocidad",
    )
    st.number_input(
        "Unidades por «Avanzar intervalo»",
        min_value=1,
        max_value=100,
        step=1,
        key="proc_unidades",
    )
    st.selectbox(
        "Filas visibles en el diagrama",
        list(VENTANAS),
        key="proc_ventana",
        help="Con muchos procesos se dibujan solo las filas más relevantes "
        "(activos primero) para que el paso a paso siga siendo fluido. La "
        "franja de espera siempre cuenta a todos los procesos.",
    )


def _controles(sim: SimuladorProcesos, ss: st.session_state) -> None:
    """Botones de control de la simulación paso a paso."""
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Iniciar", width="stretch", type="primary"):
            sim.reiniciar()
            _poner_auto(ss, True)
    with c2:
        if st.button("Pausar", width="stretch"):
            _poner_auto(ss, False)
    with c3:
        if st.button("Avanzar evento", width="stretch"):
            _poner_auto(ss, False)
            sim.avanzar_evento()
    with c4:
        if st.button("Reiniciar", width="stretch"):
            sim.reiniciar()
            _poner_auto(ss, False)

    d1, d2, d3 = st.columns([1.2, 1, 1])
    with d1:
        if st.button(
            f"Avanzar intervalo · {ss['proc_unidades']} unidades",
            width="stretch",
        ):
            _poner_auto(ss, False)
            sim.avanzar_intervalo(int(ss["proc_unidades"]))
    with d2:
        # El widget es la unica fuente de verdad de su propia clave.
        ss["proc_auto"] = st.toggle(
            "Ejecución automática", key="proc_auto_toggle"
        )
    with d3:
        estado = "corriendo" if ss["proc_auto"] else "detenido"
        cmp.franja_indicadores([(estado, "Estado")])


def _indicadores(sim: SimuladorProcesos) -> None:
    ss = st.session_state
    resumen = calcular_metricas(sim.procesos, sim.intervalos)
    total_rafaga = sum(p.rafaga for p in sim.procesos)
    items = [
        (str(len(sim.procesos)), "Procesos"),
        (str(total_rafaga), "Ráfaga total (u)"),
        (str(sim.reloj), "Tiempo simulado"),
        (f"{resumen.completados}/{resumen.total}", "Terminados"),
        (sim.nombre_algoritmo, "Algoritmo"),
    ]
    if sim.nombre_algoritmo == "Round Robin":
        items.append((str(ss.get("proc_quantum", 4)), "Quantum"))
    cmp.franja_indicadores(items)
    consumos = consumo_cpu_por_proceso(sim.procesos, sim.intervalos)
    st.markdown(
        '<div class="oslab-seccion">Consumo de CPU por proceso</div>',
        unsafe_allow_html=True,
    )
    muchos = len(sim.procesos) > 80
    st.plotly_chart(
        figura_consumo_cpu(
            consumos,
            mostrar_cero=not muchos,
            max_barras=40 if muchos else None,
        ),
        width="stretch",
        config={"displayModeBar": False},
    )
    st.caption(
        "Porcentaje sobre la CPU **ocupada** (no sobre el tiempo total). "
        "La suma de las barras equivale al trabajo de CPU realizado."
        + (
            " Con muchos procesos se muestran solo las 40 barras con más CPU."
            if len(sim.procesos) > 80
            else ""
        )
    )


def _metricas(sim: SimuladorProcesos) -> None:
    resumen = calcular_metricas(sim.procesos, sim.intervalos)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        cmp.tarjeta(f"{resumen.espera_prom}", "Espera promedio")
    with c2:
        cmp.tarjeta(f"{resumen.retorno_prom}", "Retorno promedio")
    with c3:
        cmp.tarjeta(f"{resumen.respuesta_prom}", "Respuesta promedio")
    with c4:
        cmp.tarjeta(f"{resumen.max_espera}", "Espera máxima")


def _tabla_eventos(sim: SimuladorProcesos) -> pd.DataFrame:
    if not sim.eventos:
        return pd.DataFrame(
            columns=["Instante", "Actor", "Acción", "Recurso", "Resultado"]
        )
    return pd.DataFrame(
        [
            {
                "Instante": e.instante,
                "Actor": e.actor,
                "Acción": e.accion,
                "Recurso": e.recurso,
                "Resultado": e.resultado,
            }
            for e in sim.eventos
        ]
    )


def _registros(sim: SimuladorProcesos) -> None:
    filas_proc = [p.to_dict() for p in sim.procesos]
    df_proc = pd.DataFrame(filas_proc)
    df_intervalos = tabla_intervalos(sim.intervalos)
    df_eventos = _tabla_eventos(sim)

    t1, t2, t3 = st.tabs(
        ["Tabla de procesos", "Intervalos de CPU", "Registro de eventos"]
    )
    with t1:
        cmp.resumen_procesos(filas_proc[:MAX_FILAS_TABLA])
        _aviso_tabla(len(filas_proc), "procesos")
        if not df_proc.empty:
            st.dataframe(
                df_proc[
                    [
                        c
                        for c in [
                            "pid",
                            "llegada",
                            "rafaga",
                            "prioridad",
                            "tiempo_cpu",
                            "estado",
                        ]
                        if c in df_proc.columns
                    ]
                ].head(MAX_FILAS_TABLA),
                width="stretch",
                hide_index=True,
            )
    with t2:
        st.dataframe(
            df_intervalos.head(MAX_FILAS_TABLA),
            width="stretch",
            hide_index=True,
        )
        _aviso_tabla(len(df_intervalos), "intervalos")
        csv = GestorArchivos.filas_a_csv(
            [i.to_dict() for i in sim.intervalos]
        )
        st.download_button(
            "Exportar intervalos a CSV",
            data=csv,
            file_name="intervalos_cpu.csv",
            mime="text/csv",
            disabled=not sim.intervalos,
        )
    with t3:
        st.dataframe(
            df_eventos.head(MAX_FILAS_TABLA),
            width="stretch",
            hide_index=True,
        )
        _aviso_tabla(len(df_eventos), "eventos")
        csv = GestorArchivos.filas_a_csv([e.to_dict() for e in sim.eventos])
        st.download_button(
            "Exportar eventos a CSV",
            data=csv,
            file_name="eventos_simulacion.csv",
            mime="text/csv",
            disabled=not sim.eventos,
        )


def _aviso_tabla(total: int, etiqueta: str) -> None:
    """Indica que la tabla visible esta recortada; el CSV exporta todo."""
    if total > MAX_FILAS_TABLA:
        st.caption(
            f"Mostrando las primeras {MAX_FILAS_TABLA} de {total} filas "
            f"({etiqueta}); la exportación CSV incluye todas."
        )


def render() -> None:
    ss = st.session_state
    _inicializar(ss)

    st.title("Módulo 1 · Gestión de procesos")
    st.caption(
        "Simulación paso a paso con FCFS, SPN, SRT y Round Robin, y su "
        "diagrama cartesiano derivado de los intervalos reales ejecutados."
    )

    with st.expander("Entrada y configuración", expanded=True):
        _configuracion(ss)

    procesos = ss["proc_procesos"]
    if not procesos:
        cmp.nota_explicacion(
            "No hay procesos cargados. Sube un TXT o carga el ejemplo."
        )
        return

    sim = _obtener_simulador(procesos, ss["proc_algoritmo"], ss["proc_quantum"])
    _sincronizar_auto(sim, ss)
    _controles(sim, ss)
    _indicadores(sim)

    # ---------------- escenario + estados ---------------- #
    escenario, estados = st.columns([1.65, 1])
    with escenario:
        max_filas = VENTANAS.get(ss.get("proc_ventana", VENTANA_POR_DEFECTO))
        if len(sim.procesos) > 80:
            if max_filas is None:
                cmp.nota_explicacion(
                    f"{len(sim.procesos)} procesos · se dibujan todas las "
                    "filas; el paso a paso puede ir lento."
                )
            else:
                cmp.nota_explicacion(
                    f"{len(sim.procesos)} procesos · se dibujan hasta "
                    f"{max_filas} filas (activos primero) para mantener "
                    "fluido el paso a paso; la franja de espera cuenta a todos."
                )
        fig = figura_cartesiana(
            sim.intervalos,
            sim.reloj,
            sim.procesos,
            algoritmo=sim.nombre_algoritmo,
            esperas=sim.esperas,
            max_filas=max_filas,
        )
        st.plotly_chart(
            fig, width="stretch", config={"displayModeBar": False}
        )
        st.caption(
            f"Intervalos registrados: **{len(sim.intervalos)}** · "
            f"CPU ocupada: **{sum(i.duracion for i in sim.intervalos if not i.inactivo)}** "
            "unidades."
        )
        cmp.nota_explicacion(
            "Espera: cola de listos + E/S. En cada fila aparecen sus tramos "
            "de espera (apagados) y, abajo, el recuento por unidad de tiempo "
            "(cola de listos y bloqueado en E/S); su suma por proceso "
            "equivale a la métrica de espera."
        )
    with estados:
        cmp.cpu_actual(sim.actual)
        cmp.cola_de_listos(sim.listos, sim.nombre_algoritmo)
        cmp.paneles_de_estado(
            sim.listos, sim.bloqueados, sim.terminados
        )
        cmp.nota_explicacion(
            "<b>Un solo núcleo.</b> Solo puede haber un proceso en ejecución; "
            "los tramos sin proceso aparecen en la fila <i>CPU inactiva</i> "
            "y nunca se cuentan como ejecución."
        )

    _metricas(sim)

    _registros(sim)

    cmp.nota_explicacion(
        "<b>Cómo leer los tiempos.</b> <i>Espera</i> = retorno − ráfaga de "
        "CPU. <i>Retorno</i> = fin − llegada. <i>Respuesta</i> = primera "
        "ejecución − llegada. La <i>utilización acumulada</i> es CPU ocupada "
        "sobre el tiempo total; la <i>instantánea</i> corresponde al último "
        "instante simulado."
    )

    # ---------------- lazo de ejecución automática ---------------- #
    if ss.get("proc_auto"):
        if sim.terminado():
            ss["proc_auto"] = False
        else:
            time.sleep(float(ss.get("proc_velocidad", 0.6)))
            for _ in range(eventos_por_fotograma(len(sim.procesos))):
                if sim.terminado():
                    break
                sim.avanzar_evento()
            if sim.terminado():
                ss["proc_auto"] = False
            st.rerun()
