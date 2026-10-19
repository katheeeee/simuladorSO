"""Filósofos comensales.

Cinco (o n) filosofos se sientan alrededor de una mesa. Entre cada par hay un
tenedor (semaforo binario). Para comer hay que tomar los dos tenedores
contiguos.

Estrategias seleccionables:

* ``ingenuo``: todos toman primero el tenedor izquierdo y despues el derecho.
  Con todos hambrientos a la vez, cada uno retiene un tenedor y espera el del
  vecino: **interbloqueo** real que la simulacion detecta.
* ``jerarquico``: el ultimo filosofo invierte el orden de sus tenedores
  (rompe la espera circular). Correcto, sin interbloqueo.
* ``camarero``: un semaforo ``camarero`` (valor ``n-1``) limita el numero de
  filosofos que intentan tomar cubiertos a la vez. Correcto.
"""

from __future__ import annotations

from typing import Callable, Iterator

from .base import Actor, Micro, SimuladorConcurrencia

ESTRATEGIAS = ("ingenuo", "jerarquico", "camarero")


class Filosofos(SimuladorConcurrencia):
    titulo = "Filósofos comensales"

    def __init__(
        self,
        n_filosofos: int = 5,
        rondas: int = 1,
        estrategia: str = "ingenuo",
    ) -> None:
        if n_filosofos < 2:
            raise ValueError("Se necesitan al menos 2 filosofos")
        if rondas < 1:
            raise ValueError("Las rondas deben ser >= 1")
        if estrategia not in ESTRATEGIAS:
            raise ValueError(f"Estrategia desconocida: {estrategia}")
        self.n = n_filosofos
        self.rondas = rondas
        self.estrategia = estrategia
        super().__init__()

    # ---------------------------------------------------------- construccion
    def _construir(self) -> None:
        self.semaforos = {}
        for i in range(self.n):
            self._sem(f"tenedor_{i}", 1)
        if self.estrategia == "camarero":
            self._sem("camarero", self.n - 1)
        self.variables = {"comidas": 0, "comiendo_ahora": 0}
        self.actores = []
        for i in range(self.n):
            actor = Actor(f"Filósofo {i + 1}", "Filósofo", _vacio)
            actor.datos["comidas"] = 0
            actor._programa = self._programa_filosofo(i)
            self.actores.append(actor)

    def _tenedores(self, i: int) -> tuple[int, int]:
        izquierdo = i
        derecho = (i + 1) % self.n
        if self.estrategia == "jerarquico" and i == self.n - 1:
            return derecho, izquierdo
        return izquierdo, derecho

    def _programa_filosofo(self, i: int) -> Callable[[], Iterator[Micro]]:
        primero, segundo = self._tenedores(i)

        def gen() -> Iterator[Micro]:
            for _ in range(self.rondas):
                yield Micro("accion", "Pensar", fn=self._pensar)
                if self.estrategia == "camarero":
                    yield Micro("P", "P(camarero)", sem="camarero")
                yield Micro(
                    "P", f"P(tenedor_{primero})", sem=f"tenedor_{primero}",
                    recurso=f"Tenedor {primero}",
                )
                yield Micro(
                    "P", f"P(tenedor_{segundo})", sem=f"tenedor_{segundo}",
                    recurso=f"Tenedor {segundo}",
                )
                yield Micro("accion", "Comer", fn=self._comer)
                yield Micro(
                    "V", f"V(tenedor_{primero})", sem=f"tenedor_{primero}",
                    recurso=f"Tenedor {primero}",
                )
                yield Micro(
                    "V", f"V(tenedor_{segundo})", sem=f"tenedor_{segundo}",
                    recurso=f"Tenedor {segundo}",
                )
                if self.estrategia == "camarero":
                    yield Micro("V", "V(camarero)", sem="camarero")
                yield Micro("accion", "Dejar de comer", fn=self._dejar_de_comer)
            yield Micro("fin", "Terminar")

        return gen

    # --------------------------------------------------------------- acciones
    def _pensar(self, actor: Actor) -> str:
        return "piensa un momento"

    def _comer(self, actor: Actor) -> str:
        actor.datos["comidas"] += 1
        self.variables["comidas"] += 1
        self.variables["comiendo_ahora"] += 1
        return f"come con los tenedores {self._tenedores_nombre(actor)}"

    def _dejar_de_comer(self, actor: Actor) -> str:
        self.variables["comiendo_ahora"] = max(
            0, self.variables["comiendo_ahora"] - 1
        )
        return "termina de comer"

    def _tenedores_nombre(self, actor: Actor) -> str:
        i = self.actores.index(actor)
        a, b = self._tenedores(i)
        return f"{a} y {b}"

    # ------------------------------------------------------------- instantanea
    def recurso_instantanea(self) -> dict:
        tenedores = []
        for i in range(self.n):
            sem = self.semaforos[f"tenedor_{i}"]
            tenedores.append(
                {"nombre": f"Tenedor {i}", "libre": sem.valor > 0}
            )
        return {
            "tipo": "mesa",
            "n": self.n,
            "tenedores": tenedores,
            "comiendo": self.variables["comiendo_ahora"],
        }

    def _invariantes(self) -> list[str]:
        fallos = []
        if self.variables["comiendo_ahora"] < 0:
            fallos.append("comiendo_ahora negativo")
        limite = self.n if self.estrategia != "camarero" else self.n - 1
        if self.variables["comiendo_ahora"] > limite:
            fallos.append(
                f"comen {self.variables['comiendo_ahora']} filosofos "
                f"(maximo esperado {limite})"
            )
        for i in range(self.n):
            sem = self.semaforos[f"tenedor_{i}"]
            if sem.valor not in (0, 1):
                fallos.append(f"tenedor_{i} no binario: {sem.valor}")
        return fallos


def _vacio() -> Iterator[Micro]:
    return iter(())
