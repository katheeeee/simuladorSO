"""Pruebas del calculo de metricas de planificacion."""

from __future__ import annotations

import unittest

from core.metricas import (
    calcular_metricas,
    consumo_cpu_por_proceso,
    utilizacion_instantanea,
)
from models.evento import Intervalo
from models.proceso import Proceso
from schedulers import crear, SimuladorProcesos


def preparar():
    procesos = [
        Proceso(1, 0, 4, 2),
        Proceso(2, 2, 3, 1),
        Proceso(3, 5, 2, 3),
    ]
    sim = SimuladorProcesos(procesos, crear("fcfs"))
    sim.ejecutar_completo()
    return sim


class TestMetricasProceso(unittest.TestCase):
    def setUp(self):
        self.sim = preparar()
        self.resumen = calcular_metricas(self.sim.procesos, self.sim.intervalos)

    def test_filas_por_proceso(self):
        self.assertEqual([f.pid for f in self.resumen.procesos], [1, 2, 3])

    def test_retorno(self):
        # P1 fin=4, lleg=0 -> 4 ; P2 fin=7, lleg=2 -> 5 ; P3 fin=9, lleg=5 -> 4
        filas = {f.pid: f for f in self.resumen.procesos}
        self.assertEqual(filas[1].retorno, 4)
        self.assertEqual(filas[2].retorno, 5)
        self.assertEqual(filas[3].retorno, 4)

    def test_espera(self):
        # P1 espera 0 ; P2 espera 3-2=1... (entra a los 4, llego a los 2)
        filas = {f.pid: f for f in self.resumen.procesos}
        self.assertEqual(filas[1].espera, 0)
        self.assertEqual(filas[2].espera, 5 - 3)  # espera = retorno - rafaga
        self.assertEqual(filas[3].espera, 4 - 2)

    def test_respuesta(self):
        filas = {f.pid: f for f in self.resumen.procesos}
        self.assertEqual(filas[1].respuesta, 0)
        self.assertEqual(filas[2].respuesta, 4 - 2)

    def test_promedios(self):
        esperas = [f.espera for f in self.resumen.procesos]
        self.assertEqual(self.resumen.espera_prom, round(sum(esperas) / 3, 2))

    def test_uso_cpu_total(self):
        # FCFS sin inactividad: CPU ocupada todo el tiempo.
        self.assertEqual(self.resumen.uso_cpu, 1.0)
        self.assertEqual(self.resumen.cpu_ocupada, self.resumen.tiempo_total)

    def test_totales(self):
        self.assertEqual(self.resumen.total, 3)
        self.assertEqual(self.resumen.completados, 3)


class TestUtilizacionInstantaneaVsAcumulada(unittest.TestCase):
    def test_instantanea_ocupada_e_inactiva(self):
        intervalos = [
            Intervalo(1, 0, 3, "FCFS", "P1"),
            Intervalo(None, 3, 5, "FCFS", "CPU inactiva"),
        ]
        self.assertEqual(utilizacion_instantanea(intervalos, 3), 1.0)
        self.assertEqual(utilizacion_instantanea(intervalos, 4), 0.0)
        self.assertEqual(utilizacion_instantanea(intervalos, 1), 1.0)

    def test_instantanea_en_tiempos_sin_datos(self):
        self.assertEqual(utilizacion_instantanea([], 5), 0.0)
        self.assertEqual(utilizacion_instantanea([], 0), 0.0)

    def test_acumulada_se_diferencia_de_la_instantanea(self):
        procesos = [Proceso(1, 0, 4, 1), Proceso(2, 10, 4, 1)]
        sim = SimuladorProcesos(procesos, crear("fcfs"))
        sim.ejecutar_completo()
        resumen = calcular_metricas(sim.procesos, sim.intervalos)
        # 8 de CPU ocupada en 14 unidades -> 0.571... acumulada.
        self.assertAlmostEqual(resumen.uso_cpu, 8 / 14, places=3)
        # Instantanea dentro del hueco (t=8, CPU inactiva) es 0.
        self.assertEqual(utilizacion_instantanea(sim.intervalos, 8), 0.0)
        # Instantanea ejecutando P2 (t=11) es 1.
        self.assertEqual(utilizacion_instantanea(sim.intervalos, 11), 1.0)

    def test_resumen_vacio(self):
        r = calcular_metricas([], [])
        self.assertEqual(r.uso_cpu, 0.0)
        self.assertEqual(r.total, 0)
        self.assertEqual(r.espera_prom, 0.0)


class TestConsumoCPU(unittest.TestCase):
    def setUp(self):
        self.sim = preparar()
        self.consumos = consumo_cpu_por_proceso(
            self.sim.procesos, self.sim.intervalos
        )

    def test_un_registro_por_proceso_en_orden(self):
        self.assertEqual([c.pid for c in self.consumos], [1, 2, 3])

    def test_unidades_coinciden_con_cpu_ocupada(self):
        resumen = calcular_metricas(self.sim.procesos, self.sim.intervalos)
        self.assertEqual(
            sum(c.unidades for c in self.consumos), resumen.cpu_ocupada
        )

    def test_porcentajes_suman_cien(self):
        self.assertAlmostEqual(
            sum(c.porcentaje for c in self.consumos), 100.0, delta=0.2
        )

    def test_proceso_sin_ejecutar_queda_en_cero(self):
        procesos = [Proceso(1, 0, 3, 1), Proceso(4, 0, 3, 1)]
        intervalos = [Intervalo(1, 0, 3, "FCFS", "P1")]
        consumos = {c.pid: c for c in consumo_cpu_por_proceso(
            procesos, intervalos)}
        self.assertEqual(consumos[1].unidades, 3)
        self.assertEqual(consumos[4].unidades, 0)
        self.assertEqual(consumos[4].porcentaje, 0.0)

    def test_sin_intervalos(self):
        self.assertEqual(consumo_cpu_por_proceso([], []), [])

    def test_sin_cpu_ocupada_no_divide_por_cero(self):
        procesos = [Proceso(1, 0, 2, 1)]
        consumos = consumo_cpu_por_proceso(
            procesos, [Intervalo(None, 0, 3, "FCFS")]
        )
        self.assertEqual(consumos[0].unidades, 0)
        self.assertEqual(consumos[0].porcentaje, 0.0)


if __name__ == "__main__":
    unittest.main()
