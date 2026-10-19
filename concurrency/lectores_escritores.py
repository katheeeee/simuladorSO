"""Lectores-Escritores.

Varios lectores pueden leer a la vez, pero un escritor necesita acceso
exclusivo. Se modela la solucion clasica con un semaforo ``mutex`` que
protege el contador de lectores y un semaforo ``sala`` que representa el
acceso al recurso.

* ``prioridad="lectores"``: un lector solo espera si hay un escritor ya
  escribiendo (los lectores no se bloquean entre si).
* ``prioridad="escritores"``: se anade un semaforo ``turno`` para que, cuando
  un escritor esta esperando, los lectores nuevos cedan el paso (evita la
  inanicion de los escritores).
"""

from __future__ import annotations

from typing import Callable, Iterator

from .base import Actor, Micro, SimuladorConcurrencia

PRIORIDADES = ("lectores", "escritores")


class LectoresEscritores(SimuladorConcurrencia):
    titulo = "Lectores-Escritores"

    def __init__(
        self,
        lectores: int = 3,
        escritores: int = 2,
        lecturas: int = 2,
        escrituras: int = 2,
        prioridad: str = "lectores",
    ) -> None:
        if lectores < 1 or escritores < 1:
            raise ValueError("Se requiere al menos un lector y un escritor")
        if lecturas < 1 or escrituras < 1:
            raise ValueError("Cada actor debe operar al menos una vez")
        if prioridad not in PRIORIDADES:
            raise ValueError(f"Prioridad desconocida: {prioridad}")
        self.n_lectores = lectores
        self.n_escritores = escritores
        self.lecturas_por_lector = lecturas
        self.escrituras_por_escritor = escrituras
        self.prioridad = prioridad
        super().__init__()

    @property
    def _con_turno(self) -> bool:
        return self.prioridad == "escritores"

    # ---------------------------------------------------------- construccion
    def _construir(self) -> None:
        self.semaforos = {}
        self._sem("mutex", 1)
        self._sem("sala", 1)
        if self._con_turno:
            self._sem("turno", 1)
        self.variables = {
            "lectores_registrados": 0,
            "lectores_en_sala": 0,
            "escritor_en_sala": False,
            "lecturas": 0,
            "escrituras": 0,
        }
        self.actores = []
        for i in range(self.n_lectores):
            actor = Actor(f"Lector {i + 1}", "Lector", _vacio)
            actor._programa = self._programa_lector(actor)
            self.actores.append(actor)
        for i in range(self.n_escritores):
            actor = Actor(f"Escritor {i + 1}", "Escritor", _vacio)
            actor._programa = self._programa_escritor()
            self.actores.append(actor)

    # -------------------------------------------------------------- programas
    def _programa_lector(self, actor: Actor) -> Callable[[], Iterator[Micro]]:
        def gen() -> Iterator[Micro]:
            for _ in range(self.lecturas_por_lector):
                if self._con_turno:
                    yield Micro("P", "P(turno)", sem="turno")
                yield Micro("P", "P(mutex)", sem="mutex")
                yield Micro("accion", "Registrar lector", fn=self._registrar_lector)
                if actor.datos.get("primero"):
                    yield Micro("P", "P(sala)", sem="sala", recurso="Sala")
                yield Micro("V", "V(mutex)", sem="mutex")
                if self._con_turno:
                    yield Micro("V", "V(turno)", sem="turno")
                yield Micro("accion", "Entrar a la sala", fn=self._entrar_sala)
                yield Micro("accion", "Leer", fn=self._leer)
                yield Micro("P", "P(mutex)", sem="mutex")
                yield Micro("accion", "Salir de la sala", fn=self._salir_sala)
                if self.variables["lectores_registrados"] == 0:
                    yield Micro("V", "V(sala)", sem="sala", recurso="Sala")
                yield Micro("V", "V(mutex)", sem="mutex")
            yield Micro("fin", "Terminar")

        return gen

    def _programa_escritor(self) -> Callable[[], Iterator[Micro]]:
        def gen() -> Iterator[Micro]:
            for _ in range(self.escrituras_por_escritor):
                if self._con_turno:
                    yield Micro("P", "P(turno)", sem="turno")
                yield Micro("P", "P(sala)", sem="sala", recurso="Sala")
                if self._con_turno:
                    yield Micro("V", "V(turno)", sem="turno")
                yield Micro("accion", "Entrar a escribir", fn=self._entrar_escritor)
                yield Micro("accion", "Escribir", fn=self._escribir)
                yield Micro("accion", "Salir de escribir", fn=self._salir_escritor)
                yield Micro("V", "V(sala)", sem="sala", recurso="Sala")
            yield Micro("fin", "Terminar")

        return gen

    # --------------------------------------------------------------- acciones
    def _registrar_lector(self, actor: Actor) -> str:
        self.variables["lectores_registrados"] += 1
        actor.datos["primero"] = self.variables["lectores_registrados"] == 1
        return (
            "es el primer lector: solicita la sala"
            if actor.datos["primero"]
            else f"se suma a los lectores activos "
            f"({self.variables['lectores_registrados']})"
        )

    def _entrar_sala(self, actor: Actor) -> str:
        self.variables["lectores_en_sala"] += 1
        return f"lee en la sala ({self.variables['lectores_en_sala']} lectores)"

    def _leer(self, actor: Actor) -> str:
        self.variables["lecturas"] += 1
        actor.datos["operaciones"] = actor.datos.get("operaciones", 0) + 1
        return f"completa una lectura (total {self.variables['lecturas']})"

    def _salir_sala(self, actor: Actor) -> str:
        self.variables["lectores_registrados"] -= 1
        self.variables["lectores_en_sala"] -= 1
        if self.variables["lectores_registrados"] == 0:
            return "es el ultimo lector: libera la sala"
        return f"termina de leer ({self.variables['lectores_en_sala']} lectores)"

    def _entrar_escritor(self, actor: Actor) -> str:
        self.variables["escritor_en_sala"] = True
        return "entra a la seccion critica (acceso exclusivo)"

    def _escribir(self, actor: Actor) -> str:
        self.variables["escrituras"] += 1
        actor.datos["operaciones"] = actor.datos.get("operaciones", 0) + 1
        return f"completa una escritura (total {self.variables['escrituras']})"

    def _salir_escritor(self, actor: Actor) -> str:
        self.variables["escritor_en_sala"] = False
        return "sale de la seccion critica"

    # ------------------------------------------------------------- instantanea
    def recurso_instantanea(self) -> dict:
        return {
            "tipo": "sala",
            "lectores": self.variables["lectores_en_sala"],
            "escritor": self.variables["escritor_en_sala"],
        }

    def _invariantes(self) -> list[str]:
        fallos = []
        if self.variables["lectores_en_sala"] < 0:
            fallos.append("lectores en sala negativo")
        if self.variables["lectores_registrados"] < 0:
            fallos.append("lectores registrados negativo")
        if self.variables["escritor_en_sala"] and self.variables["lectores_en_sala"] > 0:
            fallos.append(
                "escritor y lectores en la sala simultaneamente "
                "(deberia ser acceso exclusivo)"
            )
        return fallos


def _vacio() -> Iterator[Micro]:
    return iter(())
