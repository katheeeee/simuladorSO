"""Escenas visuales de los problemas de concurrencia.

Cada funcion recibe la instantanea del simulador y devuelve HTML que representa
el recurso compartido (buzon, sala, mesa, barberia o mesa de fumadores). Se
mantienen deliberadamente sencillas: son apoyos visuales coherentes con el
resto de la interfaz.
"""

from __future__ import annotations

import html

from concurrency.base import InstantaneaConcurrencia


def _esc(texto: object) -> str:
    return html.escape(str(texto))


def _bloque_recurso(titulo: str, cuerpo: str) -> str:
    return (
        f'<div class="oslab-recurso">'
        f'<div class="oslab-recurso-titulo">{_esc(titulo)}</div>'
        f"{cuerpo}</div>"
    )


def escena(problema: str, ins: InstantaneaConcurrencia) -> str:
    """Devuelve el HTML del recurso del problema indicado."""
    constructor = {
        "productor_consumidor": _buzon,
        "lectores_escritores": _sala,
        "filosofos": _mesa_filosofos,
        "barbero": _barberia,
        "fumadores": _mesa_fumadores,
    }.get(problema)
    if constructor is None:
        return ""
    return constructor(ins.recurso)


def _buzon(recurso: dict) -> str:
    casillas = []
    for valor in recurso.get("casillas", []):
        lleno = "1" if valor is not None else "0"
        casillas.append(
            f'<span class="oslab-celda" data-lleno="{lleno}">'
            f"{_esc(valor) if valor is not None else '·'}</span>"
        )
    cuerpo = (
        f'<div class="oslab-celdas">{"".join(casillas)}</div>'
        f'<div class="oslab-recurso-fila">'
        f"Ocupados: <b>{recurso.get('ocupados', 0)}</b> / "
        f"{recurso.get('capacidad', 0)}</div>"
    )
    return _bloque_recurso(
        f"Buzón · {recurso.get('nombre', 'Buzon')}", cuerpo
    )


def _sala(recurso: dict) -> str:
    lectores = int(recurso.get("lectores", 0))
    escritor = bool(recurso.get("escritor", False))
    if escritor:
        estado = (
            '<span class="oslab-badge-estado" data-estado="bloqueo">'
            "Escritor en acceso exclusivo</span>"
        )
    elif lectores:
        estado = (
            '<span class="oslab-badge-estado" data-estado="fin">'
            f"Lectura compartida · {lectores} lector(es)</span>"
        )
    else:
        estado = (
            '<span class="oslab-badge-estado" data-estado="curso">'
            "Recurso libre</span>"
        )
    cuerpo = f'<div class="oslab-recurso-fila">{estado}</div>'
    return _bloque_recurso("Sala (recurso compartido)", cuerpo)


def _mesa_filosofos(recurso: dict) -> str:
    tenedores = recurso.get("tenedores", [])
    parte = []
    for t in tenedores:
        libre = "1" if t.get("libre") else "0"
        etiqueta = f"{t.get('nombre', '?')}: " + ("libre" if t.get("libre") else "en uso")
        parte.append(
            f'<span class="oslab-tenedor" data-libre="{libre}">{_esc(etiqueta)}</span>'
        )
    cuerpo = (
        f'<div class="oslab-celdas">{"".join(parte)}</div>'
        f'<div class="oslab-recurso-fila">Comiendo ahora: '
        f"<b>{recurso.get('comiendo', 0)}</b></div>"
    )
    return _bloque_recurso("Mesa · tenedores", cuerpo)


def _barberia(recurso: dict) -> str:
    sillas = int(recurso.get("sillas", 0))
    esperando = int(recurso.get("esperando", 0))
    casillas = []
    for i in range(sillas):
        ocupada = "1" if i < esperando else "0"
        casillas.append(
            f'<span class="oslab-celda" data-lleno="{ocupada}">'
            f"{'Cliente' if ocupada == '1' else '·'}</span>"
        )
    barbero = (
        "trabajando"
        if recurso.get("barbero_activo")
        else "dormido o esperando"
    )
    cuerpo = (
        f'<div class="oslab-recurso-fila">Barbero: <b>{_esc(barbero)}</b></div>'
        f'<div class="oslab-celdas">{ "".join(casillas) }</div>'
        f'<div class="oslab-recurso-fila">Sillas ocupadas: '
        f"<b>{esperando}</b> / {sillas}</div>"
    )
    return _bloque_recurso("Barbería · sala de espera", cuerpo)


def _mesa_fumadores(recurso: dict) -> str:
    mesa = recurso.get("mesa", [])
    cuerpo_mesa = []
    for i in range(2):
        valor = mesa[i] if i < len(mesa) else None
        lleno = "1" if valor is not None else "0"
        cuerpo_mesa.append(
            f'<span class="oslab-celda" data-lleno="{lleno}">'
            f"{_esc(valor) if valor is not None else '·'}</span>"
        )
    fumadores = []
    for f in recurso.get("fumadores", []):
        fumadores.append(
            '<div class="oslab-comensal">'
            f'<div class="oslab-actor-rol">Propio</div>'
            f"{_esc(f.get('propio', ''))}"
            f"<div class=\"oslab-actor-accion\">"
            f"cigarrillos: {f.get('cigarros', 0)}</div></div>"
        )
    cuerpo = (
        f'<div class="oslab-recurso-titulo">Mesa del agente</div>'
        f'<div class="oslab-celdas">{"".join(cuerpo_mesa)}</div>'
        f'<div class="oslab-recurso-titulo" style="margin-top:12px">'
        f"Fumadores</div>"
        f'<div class="oslab-mesa">{"".join(fumadores)}</div>'
    )
    return _bloque_recurso("Fumadores", cuerpo)
