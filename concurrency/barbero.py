"""Barbero dormilón.

Un barbero atiende a los clientes que encuentran una silla libre en la sala de
espera; si no hay sillas, el cliente se marcha. Cuando no hay clientes, el
barbero **duerme** (queda bloqueado en el semaforo ``clientes``).

Semaforos:

* ``clientes`` (0): el barbero espera aqui a que llegue un cliente.
* ``barbero`` (0): el cliente espera aqui a que el barbero le de paso a la
  silla de trabajo.
* ``mutex`` (1): protege el contador de sillas ocupadas.

Como la simulacion es finita, cuando todos los clientes han terminado y no
queda nadie esperando, el barbero da por concluida la jornada (esto se modela
con el gancho ``_post_paso``, no con hilos).
"""

from __future__ import annotations

from typing import Callable, Iterator

from .base import Actor, EstadoActor, Micro, SimuladorConcurrencia


class Barbero(SimuladorConcurrencia):
    titulo = "Barbero dormilón"

    def __init__(self, clientes: int = 6, sillas: int = 2) -> None:
        if clientes < 1:
            raise ValueError("Se requiere al menos un cliente")
        if sillas < 1:
            raise ValueError("Debe haber al menos una silla de espera")
        self.n_clientes = clientes
        self.sillas = sillas
        super().__init__()

    # ---------------------------------------------------------- construccion
    def _construir(self) -> None:
        self.semaforos = {}
        self._sem("clientes", 0)
        self._sem("barbero", 0)
        self._sem("mutex", 1)
        self.variables = {
            "esperando": 0,
            "atendidos": 0,
            "rechazados": 0,
        }
        self.actores = []
        self._barbero = Actor("Barbero", "Barbero", self._programa_barbero())
        self.actores.append(self._barbero)
        for i in range(self.n_clientes):
            actor = Actor(f"Cliente {i + 1}", "Cliente", _vacio)
            actor.datos["sentado"] = False
            actor._programa = self._programa_cliente(actor)
            self.actores.append(actor)

    def _clientes(self) -> list[Actor]:
        return [a for a in self.actores if a.rol == "Cliente"]

    # -------------------------------------------------------------- programas
    def _programa_cliente(self, actor: Actor) -> Callable[[], Iterator[Micro]]:
        def gen() -> Iterator[Micro]:
            yield Micro("accion", "Llegar", fn=self._llegar)
            yield Micro("P", "P(mutex)", sem="mutex")
            yield Micro("accion", "Buscar silla", fn=self._buscar_silla)
            if actor.datos["sentado"]:
                yield Micro("V", "V(clientes)", sem="clientes")
                yield Micro("V", "V(mutex)", sem="mutex")
                yield Micro("P", "P(barbero)", sem="barbero")
                yield Micro("accion", "Recibir corte", fn=self._recibir)
            else:
                yield Micro("V", "V(mutex)", sem="mutex")
                yield Micro("accion", "Marcharse", fn=self._marcharse)
            yield Micro("fin", "Terminar")

        return gen

    def _programa_barbero(self) -> Callable[[], Iterator[Micro]]:
        def gen() -> Iterator[Micro]:
            while not self._jornada_terminada():
                yield Micro("P", "P(clientes)", sem="clientes", recurso="Sala")
                if self._jornada_terminada() and self.variables["esperando"] == 0:
                    break
                yield Micro("P", "P(mutex)", sem="mutex")
                yield Micro("accion", "Pasar a la silla", fn=self._pasar)
                yield Micro("V", "V(barbero)", sem="barbero")
                yield Micro("V", "V(mutex)", sem="mutex")
                yield Micro("accion", "Cortar el cabello", fn=self._cortar)
            yield Micro("fin", "Terminar")

        return gen

    def _jornada_terminada(self) -> bool:
        clientes = self._clientes()
        return bool(clientes) and all(c.terminado for c in clientes)

    # --------------------------------------------------------------- acciones
    def _llegar(self, actor: Actor) -> str:
        return "llega a la barberia"

    def _buscar_silla(self, actor: Actor) -> str:
        if self.variables["esperando"] < self.sillas:
            self.variables["esperando"] += 1
            actor.datos["sentado"] = True
            return (
                f"ocupa una silla de espera "
                f"({self.variables['esperando']}/{self.sillas})"
            )
        actor.datos["sentado"] = False
        self.variables["rechazados"] += 1
        return "no hay sillas libres: se marcha"

    def _recibir(self, actor: Actor) -> str:
        return "recibe el corte de pelo"

    def _marcharse(self, actor: Actor) -> str:
        return "abandona la barberia"

    def _pasar(self, actor: Actor) -> str:
        self.variables["esperando"] -= 1
        return "pasa al cliente a la silla de trabajo"

    def _cortar(self, actor: Actor) -> str:
        self.variables["atendidos"] += 1
        return f"corta el cabello (atendidos={self.variables['atendidos']})"

    # ------------------------------------------------------------- instantanea
    def recurso_instantanea(self) -> dict:
        return {
            "tipo": "barberia",
            "sillas": self.sillas,
            "esperando": self.variables["esperando"],
            "barbero_activo": (
                self._barbero.estado is EstadoActor.EJECUTANDO
            ),
        }

    # ---------------------------------------------------------------- cierre
    def _post_paso(self) -> None:
        if self.terminado or not self._jornada_terminada():
            return
        if self.variables["esperando"] != 0:
            return
        barbero = self._barbero
        if (
            barbero.estado is EstadoActor.BLOQUEADO
            and barbero.micro is not None
            and barbero.micro.sem == "clientes"
        ):
            self._desbloquear_forzado(barbero)

    def _invariantes(self) -> list[str]:
        fallos = []
        if not 0 <= self.variables["esperando"] <= self.sillas:
            fallos.append(
                f"clientes sentados fuera de rango: {self.variables['esperando']}"
            )
        if self.variables["atendidos"] + self.variables["rechazados"] > self.n_clientes:
            fallos.append("se atendio o rechazo a mas clientes que los existentes")
        return fallos


def _vacio() -> Iterator[Micro]:
    return iter(())
