"""Productor-Consumidor con buzon acotado.

Se modela el protocolo clasico con tres semaforos:

* ``empty`` (capacidad inicial): huecos libres en el buzon.
* ``full`` (0 inicial): elementos disponibles para consumir.
* ``mutex`` (1 inicial): protege la seccion critica del buzon.

El productor hace ``P(empty)``, ``P(mutex)``, inserta, ``V(mutex)`` y
``V(full)``; el consumidor hace ``P(full)``, ``P(mutex)``, extrae,
``V(mutex)`` y ``V(empty)``. En ``protocolo="incorrecto"`` se intercambia el
orden de las dos primeras ``P`` (mutex antes de empty/full), lo que produce un
interbloqueo real que la simulacion detecta y muestra.
"""

from __future__ import annotations

from typing import Callable, Iterator

from models.recurso import Buffer

from .base import Actor, Micro, SimuladorConcurrencia

PROTOCOLOS = ("correcto", "incorrecto")


class ProductorConsumidor(SimuladorConcurrencia):
    titulo = "Productor-Consumidor"

    def __init__(
        self,
        productores: int = 2,
        consumidores: int = 2,
        capacidad: int = 3,
        items_por_productor: int = 3,
        protocolo: str = "correcto",
    ) -> None:
        if productores < 1 or consumidores < 1:
            raise ValueError("Se requiere al menos un productor y un consumidor")
        if capacidad < 1:
            raise ValueError("La capacidad debe ser >= 1")
        if items_por_productor < 1:
            raise ValueError("Cada productor debe producir al menos un elemento")
        if protocolo not in PROTOCOLOS:
            raise ValueError(f"Protocolo desconocido: {protocolo}")
        self.n_productores = productores
        self.n_consumidores = consumidores
        self.capacidad = capacidad
        self.items_por_productor = items_por_productor
        self.protocolo = protocolo
        super().__init__()

    # ---------------------------------------------------------- construccion
    @property
    def total_items(self) -> int:
        return self.n_productores * self.items_por_productor

    def _construir(self) -> None:
        self.buffer = Buffer("Buzon", self.capacidad)
        self._contador_items = 0
        self.semaforos = {}
        self._sem("empty", self.capacidad)
        self._sem("full", 0)
        self._sem("mutex", 1)
        self.variables = {
            "producidos": 0,
            "insertados": 0,
            "extraidos": 0,
            "consumidos": 0,
            "en_buffer": 0,
        }
        self.actores = []
        for i in range(self.n_productores):
            self.actores.append(
                Actor(
                    f"Productor {i + 1}",
                    "Productor",
                    self._programa_productor(),
                )
            )
        for i in range(self.n_consumidores):
            self.actores.append(
                Actor(
                    f"Consumidor {i + 1}",
                    "Consumidor",
                    self._programa_consumidor(i),
                )
            )

    # -------------------------------------------------------------- programas
    def _programa_productor(self) -> Callable[[], Iterator[Micro]]:
        def gen() -> Iterator[Micro]:
            for _ in range(self.items_por_productor):
                yield Micro("accion", "Producir", fn=self._producir)
                if self.protocolo == "correcto":
                    yield Micro("P", "P(empty)", sem="empty", recurso="Buzon")
                    yield Micro("P", "P(mutex)", sem="mutex", recurso="Buzon")
                else:
                    yield Micro("P", "P(mutex)", sem="mutex", recurso="Buzon")
                    yield Micro("P", "P(empty)", sem="empty", recurso="Buzon")
                yield Micro("accion", "Insertar", fn=self._insertar, recurso="Buzon")
                yield Micro("V", "V(mutex)", sem="mutex", recurso="Buzon")
                yield Micro("V", "V(full)", sem="full", recurso="Buzon")
            yield Micro("fin", "Terminar")

        return gen

    def _cuota_consumidor(self, indice: int) -> int:
        base, resto = divmod(self.total_items, self.n_consumidores)
        return base + (1 if indice < resto else 0)

    def _programa_consumidor(self, indice: int) -> Callable[[], Iterator[Micro]]:
        cuota = self._cuota_consumidor(indice)

        def gen() -> Iterator[Micro]:
            for _ in range(cuota):
                if self.protocolo == "correcto":
                    yield Micro("P", "P(full)", sem="full", recurso="Buzon")
                    yield Micro("P", "P(mutex)", sem="mutex", recurso="Buzon")
                else:
                    yield Micro("P", "P(mutex)", sem="mutex", recurso="Buzon")
                    yield Micro("P", "P(full)", sem="full", recurso="Buzon")
                yield Micro("accion", "Extraer", fn=self._extraer, recurso="Buzon")
                yield Micro("V", "V(mutex)", sem="mutex", recurso="Buzon")
                yield Micro("V", "V(empty)", sem="empty", recurso="Buzon")
                yield Micro("accion", "Consumir", fn=self._consumir)
            yield Micro("fin", "Terminar")

        return gen

    # --------------------------------------------------------------- acciones
    def _producir(self, actor: Actor) -> str:
        self._contador_items += 1
        item = f"i{self._contador_items}"
        actor.datos["item"] = item
        self.variables["producidos"] += 1
        return f"produce {item}"

    def _insertar(self, actor: Actor) -> str:
        item = actor.datos.get("item", "?")
        self.buffer.insertar(item)
        self.variables["insertados"] += 1
        self.variables["en_buffer"] = self.buffer.ocupados
        return (
            f"inserta {item} en el buzon "
            f"({self.buffer.ocupados}/{self.buffer.capacidad})"
        )

    def _extraer(self, actor: Actor) -> str:
        item = self.buffer.extraer()
        actor.datos["item"] = item
        self.variables["extraidos"] += 1
        self.variables["en_buffer"] = self.buffer.ocupados
        return (
            f"extrae {item} del buzon "
            f"({self.buffer.ocupados}/{self.buffer.capacidad})"
        )

    def _consumir(self, actor: Actor) -> str:
        item = actor.datos.get("item", "?")
        self.variables["consumidos"] += 1
        return f"consume {item}"

    # ------------------------------------------------------------- instantanea
    def recurso_instantanea(self) -> dict:
        return {
            "tipo": "buzon",
            "nombre": self.buffer.nombre,
            "capacidad": self.buffer.capacidad,
            "ocupados": self.buffer.ocupados,
            "casillas": self.buffer.casillas(),
        }

    def _invariantes(self) -> list[str]:
        fallos = []
        ocupados = self.buffer.ocupados
        if not 0 <= ocupados <= self.buffer.capacidad:
            fallos.append(f"Buzon fuera de rango: {ocupados}")
        if self.variables["en_buffer"] != ocupados:
            fallos.append(
                "Contador en_buffer incoherente: "
                f"{self.variables['en_buffer']} != {ocupados}"
            )
        return fallos
