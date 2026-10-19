"""Problema de los fumadores.

Tres fumadores poseen, cada uno, un ingrediente permanente (tabaco, papel o
fosforos). El agente coloca **dos** ingredientes distintos en la mesa; solo el
fumador que posee el ingrediente que falta puede fabricar y fumar un
cigarrillo.

Protocolo correcto (libre de interbloqueo):

* ``turno_agente`` (1): el agente lo adquiere al comenzar y espera a que el
  fumador le devuelva el turno al terminar la ronda.
* ``turno_sm<k>`` (0): un semaforo por fumador. El agente despierta **solo**
  al fumador cuyo ingrediente falta; un fumador nunca despierta a otro.
* ``mutex_mesa`` (1): protege la mesa (seccion critica).

La rotacion de combinaciones es determinista, de modo que la simulacion es
reproducible y cada ronda fuma exactamente un fumador.
"""

from __future__ import annotations

from itertools import combinations
from typing import Callable, Iterator, Optional

from .base import Actor, EstadoActor, Micro, SimuladorConcurrencia

INGREDIENTES = ("Tabaco", "Papel", "Fósforos")
_COMBINACIONES = tuple(combinations(range(3), 2))


class Fumadores(SimuladorConcurrencia):
    titulo = "Fumadores"

    def __init__(self, rondas: int = 6, desfase: int = 0) -> None:
        if rondas < 1:
            raise ValueError("Las rondas deben ser >= 1")
        if desfase < 0:
            raise ValueError("El desfase no puede ser negativo")
        self.rondas = rondas
        self.desfase = desfase
        super().__init__()

    # ---------------------------------------------------------- construccion
    def _construir(self) -> None:
        self.semaforos = {}
        self._sem("turno_agente", 1)
        for i in range(3):
            self._sem(f"turno_sm{i}", 0)
        self._sem("mutex_mesa", 1)
        self.mesa: list[str] = []
        self.variables = {"rondas_hechas": 0, "cigarros": 0}
        self.actores = []
        self._agente = Actor("Agente", "Agente", self._programa_agente())
        self.actores.append(self._agente)
        for i in range(3):
            actor = Actor(
                f"Fumador con {INGREDIENTES[i]}", "Fumador", _vacio
            )
            actor.datos["propio"] = INGREDIENTES[i]
            actor.datos["cigarros"] = 0
            actor._programa = self._programa_fumador(i)
            self.actores.append(actor)

    def _fumadores(self) -> list[Actor]:
        return [a for a in self.actores if a.rol == "Fumador"]

    def _combinacion_ronda(self, r: int) -> tuple[str, str, int]:
        """(ingrediente1, ingrediente2, indice del fumador que falta)."""
        indice = (r + self.desfase) % 3
        i1, i2 = _COMBINACIONES[indice]
        faltante = next(k for k in range(3) if k not in (i1, i2))
        return INGREDIENTES[i1], INGREDIENTES[i2], faltante

    # -------------------------------------------------------------- programas
    def _programa_agente(self) -> Callable[[], Iterator[Micro]]:
        def gen() -> Iterator[Micro]:
            for r in range(self.rondas):
                if r == 0:
                    yield Micro("P", "P(turno_agente)", sem="turno_agente")
                i1, i2, f = self._combinacion_ronda(r)
                yield Micro(
                    "P", "P(mutex_mesa)", sem="mutex_mesa", recurso="Mesa"
                )
                yield Micro(
                    "accion", f"Colocar {i1}", fn=self._colocar(i1)
                )
                yield Micro(
                    "accion", f"Colocar {i2}", fn=self._colocar(i2)
                )
                yield Micro(
                    "V", "V(mutex_mesa)", sem="mutex_mesa", recurso="Mesa"
                )
                yield Micro(
                    "V", f"V(turno del fumador {f})", sem=f"turno_sm{f}",
                    recurso="Mesa",
                )
                yield Micro("P", "P(turno_agente)", sem="turno_agente")
            yield Micro("fin", "Terminar")

        return gen

    def _programa_fumador(self, indice: int) -> Callable[[], Iterator[Micro]]:
        def gen() -> Iterator[Micro]:
            while True:
                yield Micro(
                    "P", "P(turno propio)", sem=f"turno_sm{indice}"
                )
                if self.variables["rondas_hechas"] >= self.rondas:
                    break
                yield Micro(
                    "P", "P(mutex_mesa)", sem="mutex_mesa", recurso="Mesa"
                )
                yield Micro("accion", "Tomar ingredientes", fn=self._tomar)
                yield Micro(
                    "V", "V(mutex_mesa)", sem="mutex_mesa", recurso="Mesa"
                )
                yield Micro("accion", "Fumar", fn=self._fumar)
                yield Micro(
                    "V", "V(turno_agente)", sem="turno_agente"
                )
            yield Micro("fin", "Terminar")

        return gen

    # --------------------------------------------------------------- acciones
    def _colocar(self, ingrediente: str) -> Callable[[Actor], str]:
        def accion(actor: Actor) -> str:
            self.mesa.append(ingrediente)
            return f"coloca {ingrediente} en la mesa"

        return accion

    def _tomar(self, actor: Actor) -> str:
        tomados = list(self.mesa)
        self.mesa.clear()
        actor.datos["tomados"] = tomados
        return f"toma {', '.join(tomados)} de la mesa"

    def _fumar(self, actor: Actor) -> str:
        actor.datos["cigarros"] += 1
        self.variables["cigarros"] += 1
        self.variables["rondas_hechas"] += 1
        return (
            f"fuma un cigarrillo con {actor.datos['propio']} "
            f"(ronda {self.variables['rondas_hechas']})"
        )

    # ------------------------------------------------------------- instantanea
    def recurso_instantanea(self) -> dict:
        return {
            "tipo": "mesa_fumadores",
            "mesa": list(self.mesa),
            "fumadores": [
                {
                    "nombre": a.nombre,
                    "propio": a.datos["propio"],
                    "cigarros": a.datos["cigarros"],
                }
                for a in self._fumadores()
            ],
        }

    # ---------------------------------------------------------------- cierre
    def _post_paso(self) -> None:
        if self.terminado or not self._agente.terminado:
            return
        for actor in self._fumadores():
            micro: Optional[Micro] = actor.micro
            if (
                actor.estado is EstadoActor.BLOQUEADO
                and micro is not None
                and micro.sem is not None
                and micro.sem.startswith("turno_sm")
            ):
                self._desbloquear_forzado(actor)

    def _invariantes(self) -> list[str]:
        fallos = []
        if len(self.mesa) > 2:
            fallos.append(f"hay {len(self.mesa)} ingredientes en la mesa (max 2)")
        for f in self._fumadores():
            tomados = f.datos.get("tomados")
            if tomados is not None and len(tomados) != 2:
                fallos.append(
                    f"{f.nombre} tomo {len(tomados)} ingredientes (se esperaban 2)"
                )
            if tomados is not None and f.datos.get("propio") in tomados:
                fallos.append(
                    f"{f.nombre} tomo su propio ingrediente de la mesa"
                )
        if self.variables["cigarros"] > self.rondas:
            fallos.append("se fumaron mas cigarrillos que rondas")
        return fallos


def _vacio() -> Iterator[Micro]:
    return iter(())
