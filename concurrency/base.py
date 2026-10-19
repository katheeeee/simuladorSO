"""Motor deterministico de concurrencia (sin hilos reales).

Todos los problemas de sincronizacion se modelan sobre una misma maquina de
estados didactica:

* Cada participante (``Actor``) ejecuta un **micro-programa** escrito como un
  generador de Python que va produciendo operaciones (``Micro``).
* Una operacion puede ser una accion cualquiera, una ``P()`` o una ``V()``
  sobre un semaforo, o el fin del actor.
* El motor elige en cada paso, de forma **circular (Round Robin)**, al
  siguiente actor listo y ejecuta exactamente una operacion. Cuando una ``P()``
  no puede continuar, el actor queda bloqueado; una ``V()`` posterior lo
  despierta y el motor lo reanuda automaticamente (la ``P()`` ya satisfecha no
  se repite).

El resultado es reproducible: la misma configuracion produce siempre la misma
secuencia de eventos. No se usa ``threading``: todo es observable paso a paso.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterator, Optional

from models.evento import Evento
from models.recurso import Semaforo

LIMITE_PASOS = 5000


class EstadoActor(Enum):
    """Estados de un participante simulado."""

    LISTO = "Listo"
    EJECUTANDO = "Ejecutando"
    BLOQUEADO = "Bloqueado"
    TERMINADO = "Terminado"


@dataclass
class Micro:
    """Una operacion atomica del micro-programa de un actor."""

    tipo: str  # "accion" | "P" | "V" | "fin"
    accion: str
    sem: Optional[str] = None
    fn: Optional[Callable[["Actor"], str]] = None
    recurso: str = ""


class Actor:
    """Participante con micro-programa, estado observable y contadores."""

    def __init__(
        self,
        nombre: str,
        rol: str,
        programa: Callable[[], Iterator[Micro]],
    ) -> None:
        self.nombre = nombre
        self.rol = rol
        self.estado = EstadoActor.LISTO
        self.accion = "Pendiente de iniciar"
        self.datos: dict = {}
        self._programa = programa
        self._gen: Optional[Iterator[Micro]] = None
        self.micro: Optional[Micro] = None

    def iniciar(self) -> None:
        self._gen = self._programa()
        self._siguiente_micro()
        if self.micro is not None:
            self.accion = "Listo"

    def _siguiente_micro(self) -> None:
        try:
            self.micro = next(self._gen)  # type: ignore[arg-type]
        except StopIteration:
            self.micro = None
            self.estado = EstadoActor.TERMINADO
            self.accion = "Terminado"

    @property
    def terminado(self) -> bool:
        return self.estado is EstadoActor.TERMINADO

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "rol": self.rol,
            "estado": self.estado.value,
            "accion": self.accion,
            **self.datos,
        }


@dataclass
class InstantaneaConcurrencia:
    """Vista inmutable del estado del simulador para la interfaz."""

    paso: int
    terminado: bool
    interbloqueo: bool
    actores: list[dict]
    semaforos: list[dict]
    variables: dict
    recurso: object
    total_eventos: int
    ultimo_actor: Optional[str]
    violaciones: list[str] = field(default_factory=list)


class SimuladorConcurrencia:
    """Base comun de los cinco simuladores de concurrencia."""

    titulo = "Simulacion de concurrencia"
    mensaje_inicial = "Pulse «Avanzar paso» o «Ejecutar» para comenzar."
    pasos_por_intervalo = 5

    def __init__(self) -> None:
        self.eventos: list[Evento] = []
        self._paso = 0
        self._finalizado = False
        self.interbloqueo = False
        self.violaciones: list[str] = []
        self._ronda = 0
        self.ultimo_actor: Optional[Actor] = None
        self._por_nombre: dict[str, Actor] = {}
        self._construir()
        self._arrancar()

    # ---------------------------------------------------------- construccion
    def _construir(self) -> None:
        """Define semaforos, actores, variables y recurso (subclases)."""
        raise NotImplementedError

    def _arrancar(self) -> None:
        self._por_nombre = {a.nombre: a for a in self.actores}
        for actor in self.actores:
            actor.iniciar()
        self._fijar_estado_inicial()
        self.eventos.append(
            Evento(0, "sistema", "Simulacion lista", "", self.mensaje_inicial,
                   "concurrencia")
        )

    def _fijar_estado_inicial(self) -> None:
        """Gancho opcional tras reiniciar (subclases)."""

    # ---------------------------------------------------------------- utilidades
    def _sem(self, clave: str, inicial: int) -> Semaforo:
        sem = Semaforo(clave, inicial)
        self.semaforos[clave] = sem
        return sem

    def _buscar(self, nombre: str) -> Actor:
        return self._por_nombre[nombre]

    def _desbloquear_forzado(self, actor: Actor, motivo: str = "Fin de la jornada") -> None:
        """Reanuda a un actor bloqueado y lo saca de la cola del semáforo.

        Se usa en los ganchos ``_post_paso`` cuando la simulación decide cerrar
        un ciclo (p. ej. ya no habrá más señalizaciones) sin dejar actores
        bloqueados colgados ni entradas fantasma en los semáforos.
        """
        micro = actor.micro
        if micro is not None and micro.sem is not None:
            sem = self.semaforos.get(micro.sem)
            if sem is not None:
                sem.retirar(actor.nombre)
        actor.estado = EstadoActor.LISTO
        actor.accion = motivo
        actor._siguiente_micro()

    # --------------------------------------------------------------- consultas
    @property
    def terminado(self) -> bool:
        return self._finalizado or self.interbloqueo

    @property
    def paso_actual(self) -> int:
        return self._paso

    def instantanea(self) -> InstantaneaConcurrencia:
        return InstantaneaConcurrencia(
            paso=self._paso,
            terminado=self.terminado,
            interbloqueo=self.interbloqueo,
            actores=[a.to_dict() for a in self.actores],
            semaforos=[s.instantanea() for s in self.semaforos.values()],
            variables=dict(self.variables),
            recurso=self.recurso_instantanea(),
            total_eventos=len(self.eventos),
            ultimo_actor=self.ultimo_actor.nombre if self.ultimo_actor else None,
            violaciones=list(self.violaciones),
        )

    def recurso_instantanea(self) -> object:
        """Vista del recurso compartido (subclases)."""
        return None

    def _invariantes(self) -> list[str]:
        """Invariantes del problema; se comprueban tras cada paso."""
        return []

    def _post_paso(self) -> None:
        """Gancho tras cada paso (p. ej. fin de jornada)."""

    # ------------------------------------------------------------------- avance
    def paso(self) -> Optional[Evento]:
        """Ejecuta exactamente una operacion. ``None`` si ya no hay avance."""
        if self.terminado:
            return None
        if self._paso >= LIMITE_PASOS:
            self._finalizar(f"limite de seguridad ({LIMITE_PASOS}) alcanzado")
            return self.eventos[-1]

        actor = self._siguiente_actor()
        if actor is None:
            self._cerrar()
            return self.eventos[-1]

        self._paso += 1
        micro = actor.micro
        assert micro is not None
        actor.estado = EstadoActor.EJECUTANDO
        resultado = self._ejecutar(actor, micro)
        if actor.estado is EstadoActor.EJECUTANDO:
            actor.estado = EstadoActor.LISTO

        ev = Evento(
            self._paso,
            actor.nombre,
            micro.accion,
            micro.recurso,
            resultado,
            "concurrencia",
        )
        self.eventos.append(ev)
        self.ultimo_actor = actor
        self.violaciones.extend(self._invariantes())
        self._post_paso()
        return ev

    def _ejecutar(self, actor: Actor, micro: Micro) -> str:
        if micro.tipo == "P":
            return self._ejecutar_p(actor, micro)
        if micro.tipo == "V":
            return self._ejecutar_v(actor, micro)
        if micro.tipo == "fin":
            actor.estado = EstadoActor.TERMINADO
            actor.accion = "Terminado"
            actor.micro = None
            return "finaliza su ejecucion"
        # accion generica
        resultado = micro.fn(actor) if micro.fn else ""
        actor.accion = micro.accion
        actor._siguiente_micro()
        return resultado

    def _ejecutar_p(self, actor: Actor, micro: Micro) -> str:
        sem = self.semaforos[micro.sem]  # type: ignore[index]
        if sem.intentar_p(actor.nombre):
            actor.accion = micro.accion
            actor._siguiente_micro()
            return f"adquiere {sem.nombre} (valor={sem.valor})"
        actor.estado = EstadoActor.BLOQUEADO
        actor.accion = f"Bloqueado en {sem.nombre}"
        return f"se bloquea en {sem.nombre}"

    def _ejecutar_v(self, actor: Actor, micro: Micro) -> str:
        sem = self.semaforos[micro.sem]  # type: ignore[index]
        despertado = sem.v()
        actor.accion = micro.accion
        if despertado is not None:
            otro = self._buscar(despertado)
            otro.estado = EstadoActor.LISTO
            otro.accion = "Reanudado por un V()"
            otro._siguiente_micro()
            resultado = f"V({sem.nombre}) despierta a {despertado}"
        else:
            resultado = f"V({sem.nombre}) incrementa (valor={sem.valor})"
        actor._siguiente_micro()
        return resultado

    def _siguiente_actor(self) -> Optional[Actor]:
        total = len(self.actores)
        for salto in range(total):
            indice = (self._ronda + salto) % total
            candidato = self.actores[indice]
            if candidato.estado is EstadoActor.LISTO and candidato.micro:
                self._ronda = (indice + 1) % total
                return candidato
        return None

    def _cerrar(self) -> None:
        """Se invoca cuando ningun actor esta listo."""
        if all(a.terminado for a in self.actores):
            self._finalizar("todos los actores terminaron")
            return
        bloqueados = [a.nombre for a in self.actores if a.estado is EstadoActor.BLOQUEADO]
        self.interbloqueo = True
        detalle = ", ".join(bloqueados) if bloqueados else "sin actores listos"
        self.eventos.append(
            Evento(
                self._paso,
                "sistema",
                "Interbloqueo detectado",
                "",
                f"ningun actor puede avanzar: {detalle}",
                "concurrencia",
            )
        )

    def _finalizar(self, razon: str) -> None:
        if self._finalizado or self.interbloqueo:
            return
        self._finalizado = True
        self.eventos.append(
            Evento(self._paso, "sistema", "Simulacion finalizada", "", razon,
                   "concurrencia")
        )

    def avanzar(self, n: int) -> list[Evento]:
        salida: list[Evento] = []
        for _ in range(max(0, n)):
            ev = self.paso()
            if ev is None:
                break
            salida.append(ev)
        return salida

    def ejecutar_completo(self, maximo: int = LIMITE_PASOS) -> list[Evento]:
        salida: list[Evento] = []
        for _ in range(maximo):
            ev = self.paso()
            if ev is None:
                break
            salida.append(ev)
        return salida

    def reiniciar(self) -> None:
        self.eventos = []
        self._paso = 0
        self._finalizado = False
        self.interbloqueo = False
        self.violaciones = []
        self._ronda = 0
        self.ultimo_actor = None
        self._construir()
        self._arrancar()

    # --------------------------------------------------------------- estadisticas
    def estadisticas(self) -> dict:
        return {
            "paso": self._paso,
            "eventos": len(self.eventos),
            "terminado": self.terminado,
            "interbloqueo": self.interbloqueo,
        }

    def resumen(self) -> str:
        estado = "interbloqueo" if self.interbloqueo else (
            "terminada" if self._finalizado else "en curso"
        )
        return f"Simulacion {estado} en el paso {self._paso}"
