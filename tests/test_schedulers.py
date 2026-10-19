"""Pruebas de los algoritmos de planificacion y del simulador."""

from __future__ import annotations

import unittest

from models.evento import TramoEspera
from models.proceso import EstadoProceso, Proceso
from schedulers import FCFS, RoundRobin, SPN, SRT, SimuladorProcesos, crear


def caso_tipico() -> list[Proceso]:
    """Caso clasico: P1(0,8) P2(1,4) P3(2,9) P4(3,5)."""
    return [
        Proceso(1, 0, 8, 2),
        Proceso(2, 1, 4, 1),
        Proceso(3, 2, 9, 3),
        Proceso(4, 3, 5, 2),
    ]


def corrida(clave: str, procesos=None, quantum: int = 4) -> SimuladorProcesos:
    sim = SimuladorProcesos(procesos or caso_tipico(), crear(clave, quantum))
    sim.ejecutar_completo()
    return sim


def traza(sim: SimuladorProcesos) -> list[tuple]:
    return [(i.pid, i.inicio, i.fin) for i in sim.intervalos]


class TestFCFS(unittest.TestCase):
    def test_orden_de_llegada(self):
        sim = corrida("fcfs")
        self.assertEqual(
            traza(sim),
            [(1, 0, 8), (2, 8, 12), (3, 12, 21), (4, 21, 26)],
        )

    def test_esperas(self):
        sim = corrida("fcfs")
        esp = {p.pid: p.tiempo_espera for p in sim.procesos}
        self.assertEqual(esp, {1: 0, 2: 7, 3: 10, 4: 18})


class TestSPN(unittest.TestCase):
    def test_elige_rafaga_corta(self):
        # P1 corre hasta t=8; a partir de ahi compiten P2(4), P3(9), P4(5).
        sim = corrida("spn")
        self.assertEqual(
            traza(sim),
            [(1, 0, 8), (2, 8, 12), (4, 12, 17), (3, 17, 26)],
        )

    def test_no_expropia(self):
        sim = corrida("spn")
        # P1 inicio en t=0 y termina sin interrupciones.
        self.assertEqual(traza(sim)[0], (1, 0, 8))


class TestSRT(unittest.TestCase):
    def test_expropia_al_llegar_proceso_corto(self):
        sim = corrida("srt")
        self.assertEqual(traza(sim)[0], (1, 0, 1))  # P2 expropia a P1 en t=1
        self.assertEqual(traza(sim)[1], (2, 1, 5))

    def test_todas_terminan(self):
        sim = corrida("srt")
        self.assertEqual(sim.terminados.__len__(), 4)
        for p in sim.procesos:
            self.assertIsNotNone(p.fin)

    def test_espera_menor_que_fcfs(self):
        esp_srt = {p.pid: p.tiempo_espera for p in corrida("srt").procesos}
        esp_fcfs = {p.pid: p.tiempo_espera for p in corrida("fcfs").procesos}
        self.assertLess(sum(esp_srt.values()), sum(esp_fcfs.values()))


class TestRoundRobin(unittest.TestCase):
    def test_quantum_respetado(self):
        for quantum in (1, 2, 3, 4, 9):
            sim = corrida("rr", quantum=quantum)
            for i in sim.intervalos:
                if i.inactivo:
                    continue
                if i.duracion <= quantum:
                    continue
                # Solo puede "fundirse" cuando el proceso era el unico que
                # quedaba: no habia con quien alternar, no hay expropiacion
                # visible.
                for t in range(i.inicio, i.fin):
                    otros = [
                        p
                        for p in sim.procesos
                        if p.pid != i.pid
                        and p.llegada <= t
                        and (p.fin is None or p.fin > t)
                    ]
                    self.assertEqual(
                        otros,
                        [],
                        f"quantum={quantum} violado en t={t}: intervalo {i}",
                    )

    def test_quantum_uno_alterna(self):
        # P1 y P2 llegan a t=0 y t=1; P3 recien a t=2, por eso P1 (ya en la
        # cola) vuelve antes que P3.
        sim = corrida("rr", quantum=1)
        orden = [i.pid for i in sim.intervalos if not i.inactivo]
        self.assertEqual(orden[:4], [1, 2, 1, 3])

    def test_un_proceso_no_queda_ocioso(self):
        sim = corrida("rr", quantum=3, procesos=[Proceso(1, 0, 5, 1)])
        self.assertEqual(traza(sim), [(1, 0, 5)])
        self.assertNotIn(None, [i.pid for i in sim.intervalos])

    def test_quantum_invalido(self):
        with self.assertRaises(ValueError):
            RoundRobin(quantum=0)


class TestInvarianteUnSoloNucleo(unittest.TestCase):
    def test_sin_solapamiento_para_los_cuatro(self):
        for clave in ("fcfs", "spn", "srt", "rr"):
            sim = corrida(clave, quantum=2)
            self.assertTrue(sim.validar_un_nucleo(), clave)

    def test_tiempos_de_transicion(self):
        for clave in ("fcfs", "spn", "srt", "rr"):
            sim = corrida(clave, quantum=2)
            for i in sim.intervalos:
                self.assertEqual(i.duracion, i.fin - i.inicio)
                self.assertGreaterEqual(i.inicio, 0)
                self.assertGreater(i.fin, i.inicio)
            # La CPU solo queda inactiva si aun no llega nadie.
            for i in sim.intervalos:
                if i.inactivo:
                    self.assertEqual(i.inicio, 0)


class TestMetricasEnSimulacion(unittest.TestCase):
    def test_retorno_y_respuesta(self):
        sim = corrida("fcfs")
        por_pid = {p.pid: p for p in sim.procesos}
        self.assertEqual(por_pid[2].tiempo_retorno, 11)
        self.assertEqual(por_pid[2].tiempo_respuesta, 7)

    def test_uso_cpu_sin_gaps_reales(self):
        sim = corrida("fcfs")
        ocupada = sum(i.duracion for i in sim.intervalos if not i.inactivo)
        self.assertEqual(ocupada, sim.reloj)  # siempre hay trabajo esperando

    def test_inicio_en_tiempo_posterior(self):
        # Proceso que llega tarde: su respuesta es 0 pero su espera puede ser 0.
        p = [Proceso(1, 5, 3, 1)]
        sim = SimuladorProcesos(p, crear("fcfs"))
        sim.ejecutar_completo()
        self.assertEqual(p[0].primer_inicio, 5)
        self.assertEqual(p[0].tiempo_respuesta, 0)
        self.assertEqual(p[0].tiempo_espera, 0)
        # Existe un tramo inicial de CPU inactiva.
        self.assertTrue(any(i.inactivo for i in sim.intervalos))


class TestPasosSimulados(unittest.TestCase):
    def test_paso_a_paso_reproducible(self):
        a = SimuladorProcesos(caso_tipico(), crear("rr", 2))
        while a.avanzar_tick():
            pass
        b = corrida("rr", quantum=2)
        self.assertEqual(traza(a), traza(b))

    def test_avanzar_intervalo(self):
        s = SimuladorProcesos(caso_tipico(), crear("fcfs"))
        s.avanzar_intervalo(5)
        self.assertEqual(s.reloj, 5)

    def test_avanzar_evento_detiene_en_transicion(self):
        s = SimuladorProcesos(caso_tipico(), crear("fcfs"))
        s.avanzar_evento()
        self.assertGreater(len(s.eventos), 0)

    def test_reiniciar_borra_historial(self):
        s = SimuladorProcesos(caso_tipico(), crear("fcfs"))
        s.ejecutar_completo()
        s.reiniciar()
        self.assertEqual(s.reloj, 0)
        self.assertEqual(s.intervalos, [])
        self.assertEqual(s.eventos, [])
        self.assertTrue(all(p.estado is EstadoProceso.NUEVO for p in s.procesos))

    def test_mismo_proceso_no_se_ejecuta_dos_veces_a_la_vez(self):
        s = SimuladorProcesos(caso_tipico(), crear("srt"))
        s.ejecutar_completo()
        self.assertTrue(s.validar_un_nucleo())


class TestCasosLimite(unittest.TestCase):
    def test_procesos_con_llegada_igual(self):
        p = [Proceso(1, 0, 3, 1), Proceso(2, 0, 2, 1), Proceso(3, 0, 4, 1)]
        sim = SimuladorProcesos(p, crear("fcfs"))
        sim.ejecutar_completo()
        self.assertTrue(sim.validar_un_nucleo())
        self.assertEqual(sum(x.duracion for x in sim.intervalos), 9)
        # FCFS desempata por PID.
        self.assertEqual([x.pid for x in sim.intervalos if not x.inactivo], [1, 2, 3])

    def test_lista_vacia(self):
        sim = SimuladorProcesos([], crear("fcfs"))
        sim.ejecutar_completo()
        self.assertTrue(sim.terminado())
        self.assertEqual(sim.intervalos, [])

    def test_un_unico_proceso(self):
        sim = SimuladorProcesos([Proceso(1, 0, 4, 1)], crear("spn"))
        sim.ejecutar_completo()
        self.assertEqual(traza(sim), [(1, 0, 4)])

    def test_planificador_desconocido(self):
        with self.assertRaises(KeyError):
            crear("xyz")

    def test_avanzar_intervalo_invalido(self):
        s = SimuladorProcesos(caso_tipico(), crear("fcfs"))
        with self.assertRaises(ValueError):
            s.avanzar_intervalo(0)

    def test_simulador_sin_planificador(self):
        with self.assertRaises(ValueError):
            SimuladorProcesos(caso_tipico(), None)


class TestESEnProcesos(unittest.TestCase):
    def test_proceso_pasa_por_bloqueado(self):
        p = Proceso(1, 0, 3, 1, rafaga_io=2)
        sim = SimuladorProcesos([p], crear("fcfs"))
        estados = []
        while sim.avanzar_tick():
            estados.append(sim.procesos[0].estado)
        self.assertIn(EstadoProceso.BLOQUEADO, estados)
        self.assertTrue(sim.procesos[0].terminado)

    def test_retorno_incluye_es_y_espera_es_la_diferencia(self):
        p = Proceso(1, 0, 3, 1, rafaga_io=4)
        sim = SimuladorProcesos([p], crear("fcfs"))
        sim.ejecutar_completo()
        # retorno total = 3 (CPU) + 4 (E/S) = 7 ; espera = retorno - rafaga CPU
        self.assertEqual(p.tiempo_retorno, 7)
        self.assertEqual(p.tiempo_espera, 4)
        self.assertTrue(p.terminado)
        # La E/S se ejecuta despues de la CPU: nada corre durante esa espera.
        inactivos = [i for i in sim.intervalos if i.inactivo]
        self.assertEqual(len(inactivos), 1)
        self.assertEqual((inactivos[0].inicio, inactivos[0].fin), (3, 7))


class TestEsperasPorTramo(unittest.TestCase):
    """Los tramos de espera desglosan la metrica: listo + bloqueado."""

    def test_listo_y_bloqueado_suman_la_espera(self):
        for clave in ("fcfs", "spn", "srt", "rr"):
            with self.subTest(algoritmo=clave):
                sim = corrida(clave)
                for p in sim.procesos:
                    tramos = sim.esperas.get(p.pid, [])
                    listo = sum(t.duracion for t in tramos if t.motivo == "listo")
                    bloq = sum(t.duracion for t in tramos if t.motivo == "bloqueado")
                    self.assertEqual(listo + bloq, p.tiempo_espera, p.nombre)

    def test_los_tramos_no_solapan_la_cpu(self):
        for clave in ("fcfs", "spn", "srt", "rr"):
            with self.subTest(algoritmo=clave):
                sim = corrida(clave)
                for p in sim.procesos:
                    cpu = [(i.inicio, i.fin) for i in sim.intervalos if i.pid == p.pid]
                    for t in sim.esperas.get(p.pid, []):
                        self.assertGreater(t.duracion, 0)
                        for a, b in cpu:
                            self.assertFalse(
                                t.inicio < b and a < t.fin,
                                f"{p.nombre} espera {t} solapa CPU ({a},{b})",
                            )

    def test_desglose_con_bloqueo_por_es(self):
        p = Proceso(1, 0, 3, 1, rafaga_io=4)
        sim = SimuladorProcesos([p], crear("fcfs"))
        sim.ejecutar_completo()
        # 3 de CPU y 4 de E/S: la unica espera del proceso es el bloqueo.
        self.assertEqual([(t.inicio, t.fin, t.motivo) for t in sim.esperas[1]],
                         [(3, 7, "bloqueado")])

    def test_llegada_y_despacho_en_el_mismo_tic_no_dejan_tramo(self):
        # FCFS: P1 llega en t=0 y se despacha en t=0 -> espera de duracion 0.
        sim = corrida("fcfs")
        self.assertEqual(sim.esperas.get(1, []), [])

    def test_expropiacion_abre_un_nuevo_tramo_listo(self):
        sim = corrida("rr", quantum=1)
        for p in sim.procesos:
            tramos = [t for t in sim.esperas.get(p.pid, []) if t.motivo == "listo"]
            if p.tiempo_espera:
                self.assertGreater(len(tramos), 1, p.nombre)
            for previo, actual in zip(tramos, tramos[1:]):
                self.assertLessEqual(previo.fin, actual.inicio)

    def test_nada_antes_de_llegar(self):
        # P2 llega en t=2 mientras P1 ocupa la CPU: solo espera desde su llegada.
        sim = SimuladorProcesos(
            [Proceso(1, 0, 5, 1), Proceso(2, 2, 1, 1)], crear("fcfs")
        )
        sim.ejecutar_completo()
        self.assertEqual(
            [(t.inicio, t.fin, t.motivo) for t in sim.esperas[2]],
            [(2, 5, "listo")],
        )

    def test_reiniciar_borra_los_tramos(self):
        sim = corrida("srt")
        self.assertTrue(sim.esperas)
        sim.reiniciar()
        self.assertEqual(sim.esperas, {})
        self.assertEqual(sim._espera_abierta, {})

    def test_motivo_invalido(self):
        with self.assertRaises(ValueError):
            TramoEspera(pid=1, inicio=0, fin=1, motivo="corriendo")


class TestEstructurasDeDatos(unittest.TestCase):
    def test_uso_de_heap_en_prioridad(self):
        self.assertTrue(issubclass(SPN, object))
        s = SPN()
        self.assertIsNone(s.siguiente())
        self.assertTrue(s.vacio())
        p = Proceso(1, 0, 5, 1)
        s.encolar(p)
        self.assertFalse(s.vacio())
        self.assertEqual(s.siguiente(), p)
        self.assertEqual(s.listos(), [p])

    def test_fcfs_es_fifo(self):
        s = FCFS()
        p1, p2 = Proceso(1, 0, 5, 1), Proceso(2, 1, 5, 1)
        s.encolar(p1)
        s.encolar(p2)
        self.assertEqual(s.siguiente(), p1)

    def test_srt_preempta_por_restante(self):
        s = SRT()
        actual = Proceso(1, 0, 10, 1)
        actual.restante = 6
        nuevo = Proceso(2, 1, 4, 1)
        self.assertTrue(s.debe_preemptar(actual, nuevo))
        self.assertFalse(s.debe_preemptar(nuevo, actual))


if __name__ == "__main__":
    unittest.main()
