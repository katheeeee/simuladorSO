"""Simulador de procesos: motor de eventos discretos, reproducible y
separado de la interfaz.

Avanza la simulacion en unidades de tiempo discretas (``avanzar_tick``). Sobre
esa primitiva se ofrecen avances de mayor nivel:

* ``avanzar_evento()``  -> corre hasta que ocurre la siguiente transicion
  relevante (llegada, despacho, expropiacion, fin, bloqueo).
* ``avanzar_intervalo(n)`` -> corre ``n`` unidades de tiempo.
* ``ejecutar_completo()`` -> corre hasta que todos los procesos terminan.

Cada unidad se registra como un :class:`Intervalo` (PID, inicio, fin,
duracion, algoritmo) y cada transicion como un :class:`Evento`. Solo puede
haber **un** proceso en CPU: el motor solo registra un titular por instante.
"""

from __future__ import annotations

from models.evento import MOTIVO_BLOQUEADO, MOTIVO_LISTO, Evento, Intervalo, TramoEspera
from models.proceso import EstadoProceso, Proceso
from .planificador import Planificador

LIMITE_SEGURIDAD = 100_000


class SimuladorProcesos:
    """Motor de simulacion de un solo nucleo controlado por un planificador."""

    def __init__(self, procesos: list[Proceso], planificador: Planificador) -> None:
        if planificador is None:
            raise ValueError("Se requiere un planificador")
        self.planificador = planificador
        self._origen: list[Proceso] = list(procesos)
        self.limite_seguridad = self._calcular_limite(procesos)
        self.reiniciar()

    @staticmethod
    def _calcular_limite(procesos: list[Proceso]) -> int:
        """Cota de tics que garantiza terminar incluso con cargas grandes.

        El peor caso es que todo el trabajo se ejecute en serie (suma de
        rafagas) mas la espera de la ultima llegada. Se toma el maximo entre
        esa cota y el limite base, con un margen para la E/S.
        """
        trabajo = sum(p.rafaga for p in procesos)
        ultima_llegada = max((p.llegada for p in procesos), default=0)
        return max(LIMITE_SEGURIDAD, trabajo + ultima_llegada + 10)

    # ------------------------------------------------------------------ #
    def reiniciar(self) -> None:
        """Restaura los procesos originales y vacia todo el historial."""
        self.procesos: list[Proceso] = list(self._origen)
        for p in self.procesos:
            p.reiniciar()
        self._por_pid: dict[int, Proceso] = {p.pid: p for p in self.procesos}
        self.planificador.reiniciar()
        self.reloj = 0
        self.actual: Proceso | None = None
        self.bloqueados: list[Proceso] = []
        self.intervalos: list[Intervalo] = []
        self.eventos: list[Evento] = []
        self.esperas: dict[int, list[TramoEspera]] = {}
        self._espera_abierta: dict[int, tuple[int, str]] = {}
        self._abierto: int | None = None  # indice de intervalo abierto

    # ------------------------------------------------------------------ #
    # Consultas
    # ------------------------------------------------------------------ #
    @property
    def nombre_algoritmo(self) -> str:
        return self.planificador.nombre

    @property
    def listos(self) -> list[Proceso]:
        return self.planificador.listos()

    @property
    def terminados(self) -> list[Proceso]:
        return [p for p in self.procesos if p.terminado]

    @property
    def pendientes(self) -> list[Proceso]:
        """Procesos aun no terminados (para saber si la simulacion sigue)."""
        return [p for p in self.procesos if not p.terminado]

    def terminado(self) -> bool:
        if not self.procesos:
            return True
        return all(p.terminado for p in self.procesos)

    def ocupacion_cpu(self, instante: int) -> str | None:
        """PID en CPU durante ``instante`` (0-based), o ``None`` si inactiva."""
        for i in self.intervalos:
            if i.inicio <= instante < i.fin:
                return i.pid
        return None

    def validar_un_nucleo(self) -> bool:
        """Verifica que nunca haya dos procesos activos simultaneamente."""
        # Se usan marcas por instante; un solo titular permitido por tic.
        marcas: dict[int, str] = {}
        for i in self.intervalos:
            for t in range(i.inicio, i.fin):
                clave = str(i.pid)
                if t in marcas and marcas[t] != clave:
                    return False
                marcas[t] = clave
        return True

    # ------------------------------------------------------------------ #
    # Primitiva: una unidad de tiempo
    # ------------------------------------------------------------------ #
    def _registrar(self, actor, accion, recurso="", resultado="") -> None:
        self.eventos.append(
            Evento(
                instante=self.reloj,
                actor=actor,
                accion=accion,
                recurso=recurso,
                resultado=resultado,
                categoria="planificacion",
            )
        )

    def _abrir_espera(self, p: Proceso, motivo: str, inicio: int) -> None:
        """Anota el inicio de una espera (cola de listos o bloqueo por E/S).

        Un tramo de duracion cero (por ejemplo, llegada y despacho en el mismo
        tic) se descarta al cerrar; el registro solo tiene sentido si el
        proceso paso al menos una unidad de tiempo fuera de la CPU.
        """
        abierto = self._espera_abierta.get(p.pid)
        if abierto is not None:
            _, previo = abierto
            if previo == motivo:
                return
            self._cerrar_espera(p, inicio)
        self._espera_abierta[p.pid] = (inicio, motivo)

    def _cerrar_espera(self, p: Proceso, fin: int) -> None:
        """Cierra la espera abierta de ``p`` en ``fin`` si tiene duracion."""
        abierto = self._espera_abierta.pop(p.pid, None)
        if abierto is None:
            return
        inicio, motivo = abierto
        if fin > inicio:
            self.esperas.setdefault(p.pid, []).append(
                TramoEspera(pid=p.pid, inicio=inicio, fin=fin, motivo=motivo)
            )

    def _llegadas(self) -> None:
        for p in self.procesos:
            if p.estado is EstadoProceso.NUEVO and p.llegada == self.reloj:
                p.estado = EstadoProceso.LISTO
                self.planificador.encolar(p)
                self._abrir_espera(p, MOTIVO_LISTO, self.reloj)
                self._registrar(
                    "Planificador", "Llegada", p.nombre, "en cola de listos"
                )

    def _despertar(self) -> None:
        """Termina la E/S pendiente. El proceso no vuelve a la CPU: su rafaga
        de CPU ya se agoto, por lo que finaliza al concluir la E/S."""
        despertados = [p for p in self.bloqueados if p.despertar_en == self.reloj]
        for p in despertados:
            self.bloqueados.remove(p)
            p.estado = EstadoProceso.TERMINADO
            p.fin = self.reloj
            p.despertar_en = None
            self._cerrar_espera(p, self.reloj)
            self._registrar(
                "Dispositivo E/S", "Fin de E/S", p.nombre, "terminado tras la E/S"
            )

    def _despachar(self) -> Proceso | None:
        candidato = self.planificador.siguiente()
        if candidato is None:
            return None
        self.planificador.retirar(candidato)
        self.planificador.asignar(candidato)
        candidato.estado = EstadoProceso.EJECUCION
        self._cerrar_espera(candidato, self.reloj)
        if candidato.primer_inicio is None:
            candidato.primer_inicio = self.reloj
        self._registrar(
            "CPU", "Despacho", candidato.nombre, "empieza a ejecutar"
        )
        return candidato

    def _tomar_decision(self) -> None:
        if self.actual is not None and self.actual.terminado:
            self.actual = None

        candidato = self.planificador.siguiente()
        if self.actual is not None and self.planificador.debe_preemptar(
            self.actual, candidato
        ):
            expropiado = self.actual
            self.planificador.encolar(expropiado)
            expropiado.estado = EstadoProceso.LISTO
            self._abrir_espera(expropiado, MOTIVO_LISTO, self.reloj)
            self._registrar(
                "CPU",
                "Expropiacion",
                expropiado.nombre,
                f"vuelve a listos (candidato {candidato.nombre if candidato else '-'})",
            )
            self.actual = None

        if self.actual is None:
            self.actual = self._despachar()

    def _ejecutar(self) -> None:
        p = self.actual
        if p is None:
            return
        p.restante -= 1
        p.tiempo_cpu += 1
        self.planificador.notificar_tick(p)
        if p.restante <= 0:
            if p.rafaga_io > 0 and not p.hizo_io:
                p.hizo_io = True
                p.estado = EstadoProceso.BLOQUEADO
                p.despertar_en = (self.reloj + 1) + p.rafaga_io
                self.bloqueados.append(p)
                self._abrir_espera(p, MOTIVO_BLOQUEADO, self.reloj + 1)
                self._registrar(
                    "CPU", "Fin de CPU", p.nombre, "entra a E/S (bloqueado)"
                )
            else:
                p.fin = self.reloj + 1
                p.estado = EstadoProceso.TERMINADO
                self._registrar("CPU", "Fin de proceso", p.nombre, "terminado")
            self.actual = None

    def _marcar(self) -> None:
        """Abre/extend el intervalo de CPU del instante actual a [reloj, reloj+1).

        La CPU inactiva solo se registra mientras queda trabajo pendiente
        (procesos sin terminar): el instante en que finaliza el ultimo
        proceso no genera una franja de IDLE posterior.
        """
        pid = self.actual.pid if self.actual else None
        nombre = self.actual.nombre if self.actual else "CPU inactiva"

        if pid is None and not self.pendientes:
            # No hay trabajo: cierra el tramo inactivo abierto si lo habia.
            if self._abierto is not None and self.intervalos[self._abierto].inactivo:
                self._abierto = None
            return

        if self._abierto is not None and self.intervalos[self._abierto].pid == pid:
            previo = self.intervalos[self._abierto]
            self.intervalos[self._abierto] = Intervalo(
                pid=previo.pid,
                inicio=previo.inicio,
                fin=self.reloj + 1,
                algoritmo=previo.algoritmo,
                nombre=previo.nombre,
            )
        else:
            self.intervalos.append(
                Intervalo(
                    pid=pid,
                    inicio=self.reloj,
                    fin=self.reloj + 1,
                    algoritmo=self.nombre_algoritmo,
                    nombre=nombre,
                )
            )
            self._abierto = len(self.intervalos) - 1

    def avanzar_tick(self) -> bool:
        """Ejecuta una unidad de tiempo. ``False`` si la simulacion termino."""
        if self.terminado() or self.reloj > self.limite_seguridad:
            return False
        self._llegadas()
        self._despertar()
        self._tomar_decision()
        self._marcar()
        self._ejecutar()
        self.reloj += 1
        return not self.terminado()

    # ------------------------------------------------------------------ #
    # Avances de nivel superior
    # ------------------------------------------------------------------ #
    def avanzar_evento(self) -> bool:
        """Avanza hasta que ocurra la siguiente transicion relevante."""
        if self.terminado():
            return False
        guardado = len(self.eventos)
        vueltas = 0
        while vueltas < self.limite_seguridad:
            if not self.avanzar_tick():
                return False
            vueltas += 1
            if len(self.eventos) > guardado:
                return True
        return False

    def avanzar_intervalo(self, cantidad: int) -> bool:
        """Avanza ``cantidad`` unidades de tiempo."""
        if cantidad < 1:
            raise ValueError("La cantidad debe ser >= 1")
        for _ in range(cantidad):
            if not self.avanzar_tick():
                return False
        return not self.terminado()

    def ejecutar_completo(self) -> None:
        vueltas = 0
        while not self.terminado() and vueltas < self.limite_seguridad:
            self.avanzar_tick()
            vueltas += 1

    # ------------------------------------------------------------------ #
    def instantanea(self) -> dict:
        """Estado completo en un solo diccionario (para la interfaz)."""
        return {
            "reloj": self.reloj,
            "algoritmo": self.nombre_algoritmo,
            "contexto": self.planificador.contexto(),
            "actual": self.actual,
            "listos": self.listos,
            "bloqueados": list(self.bloqueados),
            "terminados": self.terminados,
            "procesos": self.procesos,
            "intervalos": self.intervalos,
            "eventos": self.eventos,
            "esperas": self.esperas,
            "terminado": self.terminado(),
        }
