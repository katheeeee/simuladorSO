"""Módulo 2 · Problemas de concurrencia.

Una única pantalla presenta los cinco simuladores (Productor-Consumidor,
Lectores-Escritores, Filósofos, Barbero dormilón y Fumadores). El problema y su
configuración se eligen en un panel superior; el motor vive en ``concurrency`` y
es ajeno a Streamlit. Toda la interacción (avanzar paso, ejecutar, reiniciar)
reconstruye la vista a partir de la instantánea del motor.
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from concurrency import DESCRIPCIONES, NOMBRES, claves, crear
from concurrency.base import SimuladorConcurrencia

from . import components as cmp
from . import concurrencia_escenas as esc

NOTAS = {
    "productor_consumidor": (
        "<b>Sección crítica y semáforos.</b> El buzón se protege con el "
        "mutex; <code>empty</code> y <code>full</code> cuentan huecos y "
        "elementos. Con el protocolo «incorrecto» (tomar el mutex antes de "
        "<code>empty</code>/<code>full</code>) puede aparecer un "
        "interbloqueo real cuando el buzón se llena."
    ),
    "lectores_escritores": (
        "<b>Lectores concurrentes, escritor exclusivo.</b> El primer lector "
        "toma la sala y el último la libera; el escritor necesita la sala en "
        "exclusiva. Con prioridad de escritores se evita que los lectores los "
        "dejen esperando indefinidamente."
    ),
    "filosofos": (
        "<b>Espera circular.</b> En la estrategia «ingenua» cada filósofo "
        "retiene un tenedor y espera el del vecino: interbloqueo. La "
        "«jerárquica» invierte el orden en un filósofo y la del «camarero» "
        "limita a n-1 los comensales que compiten, rompiendo el ciclo."
    ),
    "barbero": (
        "<b>Productor-consumidor con espera.</b> El barbero duerme "
        "(bloqueado en <code>clientes</code>) hasta que llega alguien. Si las "
        "sillas de espera están llenas, el cliente se marcha."
    ),
    "fumadores": (
        "<b>Un despertar específico.</b> El agente pone dos ingredientes y "
        "señala únicamente al fumador al que le falta el tercero; cada "
        "fumador espera en su propio semáforo, por eso el protocolo está "
        "libre de interbloqueo."
    ),
}


# ---------------------------------------------------------------- configuracion
def _configuracion(ss: st.session_state) -> tuple[str, dict]:
    """Dibuja los controles de configuración y devuelve (problema, config)."""
    st.markdown(
        '<div class="oslab-seccion">Problema</div>', unsafe_allow_html=True
    )
    problema = st.selectbox(
        "Simulador de concurrencia",
        claves(),
        format_func=lambda k: NOMBRES[k],
        key="conc_problema",
        label_visibility="collapsed",
    )
    st.markdown(
        '<div class="oslab-seccion">Configuración</div>',
        unsafe_allow_html=True,
    )
    constructor = _CONFIG.get(problema)
    config = constructor(ss) if constructor else {}
    ss.setdefault("conc_velocidad", 0.3)
    st.slider(
        "Velocidad automática (s)",
        0.0,
        1.5,
        step=0.05,
        key="conc_velocidad",
    )
    return problema, config


def _num(ss, clave: str, defecto: int, minimo: int, maximo: int, etiqueta: str):
    ss.setdefault(clave, defecto)
    return st.number_input(
        etiqueta, min_value=minimo, max_value=maximo, step=1, key=clave
    )


def _sel(ss, clave: str, opciones, etiqueta: str):
    ss.setdefault(clave, opciones[0])
    return st.selectbox(etiqueta, opciones, key=clave)


def _config_pc(ss) -> dict:
    return {
        "productores": _num(ss, "conc_pc_prod", 2, 1, 4, "Productores"),
        "consumidores": _num(ss, "conc_pc_cons", 2, 1, 4, "Consumidores"),
        "capacidad": _num(ss, "conc_pc_cap", 3, 1, 6, "Capacidad del buzón"),
        "items_por_productor": _num(
            ss, "conc_pc_items", 3, 1, 5, "Elementos por productor"
        ),
        "protocolo": _sel(
            ss, "conc_pc_proto", ["correcto", "incorrecto"], "Protocolo"
        ),
    }


def _config_le(ss) -> dict:
    return {
        "lectores": _num(ss, "conc_le_lect", 3, 1, 5, "Lectores"),
        "escritores": _num(ss, "conc_le_esc", 2, 1, 4, "Escritores"),
        "lecturas": _num(ss, "conc_le_lecturas", 2, 1, 4, "Lecturas por lector"),
        "escrituras": _num(
            ss, "conc_le_escrituras", 2, 1, 4, "Escrituras por escritor"
        ),
        "prioridad": _sel(
            ss, "conc_le_prio", ["lectores", "escritores"], "Prioridad"
        ),
    }


def _config_fil(ss) -> dict:
    return {
        "n_filosofos": _num(ss, "conc_fil_n", 5, 2, 7, "Filósofos"),
        "rondas": _num(ss, "conc_fil_rondas", 1, 1, 4, "Rondas"),
        "estrategia": _sel(
            ss,
            "conc_fil_estrategia",
            ["ingenuo", "jerarquico", "camarero"],
            "Estrategia",
        ),
    }


def _config_bar(ss) -> dict:
    return {
        "clientes": _num(ss, "conc_bar_clientes", 6, 1, 10, "Clientes"),
        "sillas": _num(ss, "conc_bar_sillas", 2, 1, 5, "Sillas de espera"),
    }


def _config_fum(ss) -> dict:
    return {
        "rondas": _num(ss, "conc_fum_rondas", 6, 1, 12, "Rondas"),
        "desfase": _num(ss, "conc_fum_desfase", 0, 0, 2, "Desfase de rotación"),
    }


_CONFIG = {
    "productor_consumidor": _config_pc,
    "lectores_escritores": _config_le,
    "filosofos": _config_fil,
    "barbero": _config_bar,
    "fumadores": _config_fum,
}


RECURSOS = {
    "productor_consumidor": "Buzón",
    "lectores_escritores": "Sala de lectura",
    "filosofos": "Tenedores",
    "barbero": "Sillón y sillas de espera",
    "fumadores": "Mesa de ingredientes",
}


def _leyenda(sim: SimuladorConcurrencia, problema: str) -> None:
    """Resumen compacto de hilos, semáforos y recurso compartido."""
    conteo: dict[str, int] = {}
    for actor in sim.actores:
        conteo[actor.rol] = conteo.get(actor.rol, 0) + 1
    hilos = ", ".join(f"{n}×{rol}" for rol, n in conteo.items())
    nombres = [sem.nombre for sem in sim.semaforos.values()]
    semaforos = ", ".join(nombres) if nombres else "ninguno"
    st.caption(
        f"Hilos: {hilos} · Semáforos: {semaforos} · "
        f"Recurso: {RECURSOS[problema]}"
    )


# ------------------------------------------------------------------- simulador
def _obtener_simulador(
    problema: str, config: dict, ss: st.session_state
) -> SimuladorConcurrencia:
    firma = (problema, tuple(sorted(config.items())))
    if ss.get("conc_sim") is None or ss.get("conc_firma") != firma:
        ss["conc_sim"] = crear(problema, **config)
        ss["conc_firma"] = firma
        # Cada configuración nueva arranca en automático (valor por defecto);
        # el usuario puede pausar con el interruptor.
        _poner_auto(ss, True)
    return ss["conc_sim"]


def _sincronizar_auto(sim: SimuladorConcurrencia, ss: st.session_state) -> None:
    if sim.terminado:
        ss["conc_auto"] = False
        ss["conc_auto_toggle"] = False


def _poner_auto(ss: st.session_state, activo: bool) -> None:
    ss["conc_auto"] = activo
    ss["conc_auto_toggle"] = activo


# -------------------------------------------------------------------- controles
def _controles(sim: SimuladorConcurrencia, ss: st.session_state) -> None:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Ejecutar completo", width="stretch", type="primary"):
            _poner_auto(ss, False)
            sim.ejecutar_completo()
    with c2:
        if st.button("Avanzar paso", width="stretch"):
            _poner_auto(ss, False)
            sim.paso()
    with c3:
        if st.button("Reiniciar", width="stretch"):
            _poner_auto(ss, False)
            sim.reiniciar()
    with c4:
        ss["conc_auto"] = st.toggle(
            "Ejecución automática", key="conc_auto_toggle"
        )

    st.caption(
        f"Paso: **{sim.paso_actual}** · "
        + ("corriendo" if ss["conc_auto"] else "detenido")
    )


# ------------------------------------------------------------------ indicadores
def _estado_texto(sim: SimuladorConcurrencia) -> tuple[str, str]:
    if sim.interbloqueo:
        return "Interbloqueo", "bloqueo"
    if sim.terminado:
        return "Terminada", "fin"
    return "En curso", "curso"


def _indicadores(sim: SimuladorConcurrencia) -> None:
    etiqueta, clase = _estado_texto(sim)
    activos = [a for a in sim.actores if not a.terminado]
    cmp.franja_indicadores(
        [
            (str(sim.paso_actual), "Paso actual"),
            (str(len(activos)), "Actores activos"),
            (str(len(sim.eventos)), "Eventos"),
            (str(len(sim.semaforos)), "Semáforos"),
            (
                f'<span class="oslab-badge-estado" data-estado="{clase}">'
                f"{etiqueta}</span>",
                "Estado",
            ),
        ]
    )


def _actores(sim: SimuladorConcurrencia) -> None:
    st.markdown(
        '<div class="oslab-seccion">Actores</div>', unsafe_allow_html=True
    )
    orden = {"Ejecutando": 0, "Listo": 1, "Bloqueado": 2, "Terminado": 3}
    actores = sorted(
        sim.actores, key=lambda a: (orden.get(a.estado.value, 9), a.nombre)
    )
    tarjetas = []
    for a in actores:
        tarjetas.append(
            f'<div class="oslab-actor" data-estado="{a.estado.value}">'
            f'<span class="oslab-actor-rol">{a.rol} · {a.estado.value}</span>'
            f"<span>{a.nombre}</span>"
            f'<span class="oslab-actor-accion">{a.accion}</span></div>'
        )
    st.markdown(
        f'<div class="oslab-actores">{"".join(tarjetas)}</div>',
        unsafe_allow_html=True,
    )


def _semaforos(sim: SimuladorConcurrencia) -> None:
    filas = [
        {
            "Semáforo": s["nombre"],
            "Valor": s["valor"],
            "Bloqueados": ", ".join(s["bloqueados"]) or "—",
        }
        for s in (sem.instantanea() for sem in sim.semaforos.values())
    ]
    df = pd.DataFrame(filas)
    st.markdown(
        '<div class="oslab-seccion">Semáforos</div>', unsafe_allow_html=True
    )
    st.dataframe(df, width="stretch", hide_index=True)


def _variables(sim: SimuladorConcurrencia) -> None:
    if not sim.variables:
        return
    chips = "".join(
        f'<span class="oslab-chip">{clave}: {valor}</span>'
        for clave, valor in sim.variables.items()
    )
    st.markdown(
        '<div class="oslab-seccion">Variables compartidas</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="oslab-chips">{chips}</div>', unsafe_allow_html=True)


def _eventos(sim: SimuladorConcurrencia) -> None:
    if not sim.eventos:
        st.caption("Todavía no hay eventos.")
        return
    df = pd.DataFrame(
        [
            {
                "Paso": e.instante,
                "Actor": e.actor,
                "Acción": e.accion,
                "Recurso": e.recurso or "—",
                "Resultado": e.resultado,
            }
            for e in sim.eventos
        ]
    )
    st.dataframe(df, width="stretch", hide_index=True)
    from core.archivos import GestorArchivos

    csv = GestorArchivos.filas_a_csv([e.to_dict() for e in sim.eventos])
    st.download_button(
        "Exportar eventos a CSV",
        data=csv,
        file_name="eventos_concurrencia.csv",
        mime="text/csv",
    )


# ------------------------------------------------------------------------ render
def render() -> None:
    ss = st.session_state

    st.title("Módulo 2 · Concurrencia")
    st.caption(
        "Cinco problemas clásicos de sincronización resueltos con semáforos, "
        "paso a paso y con detección de interbloqueos."
    )

    with st.expander("Problema y configuración", expanded=True):
        problema, config = _configuracion(ss)

    st.subheader(NOMBRES[problema])
    st.caption(DESCRIPCIONES[problema])

    sim = _obtener_simulador(problema, config, ss)
    _sincronizar_auto(sim, ss)
    _leyenda(sim, problema)
    _controles(sim, ss)
    _indicadores(sim)
    _actores(sim)

    escenario, panel = st.columns([1.55, 1])
    with escenario:
        st.markdown(
            '<div class="oslab-seccion">Recurso compartido</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            esc.escena(problema, sim.instantanea()), unsafe_allow_html=True
        )
    with panel:
        _semaforos(sim)
        _variables(sim)

    if sim.violaciones:
        st.error("Se detectaron inconsistencias: " + "; ".join(sim.violaciones))
    if sim.interbloqueo:
        st.error(
            "Interbloqueo detectado: ningún actor puede avanzar. "
            "Revisa el protocolo o la estrategia elegida."
        )
    elif sim.terminado:
        st.success("La simulación terminó sin interbloqueos.")

    cmp.nota_explicacion(NOTAS[problema])

    st.markdown(
        '<div class="oslab-seccion">Registro de eventos</div>',
        unsafe_allow_html=True,
    )
    _eventos(sim)

    if ss.get("conc_auto"):
        if sim.terminado:
            ss["conc_auto"] = False
        else:
            time.sleep(float(ss.get("conc_velocidad", 0.4)))
            sim.paso()
            if sim.terminado:
                ss["conc_auto"] = False
            st.rerun()
