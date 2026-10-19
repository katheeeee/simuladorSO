"""Pruebas del diagrama cartesiano (deriva de los intervalos reales)."""

from __future__ import annotations

import unittest

from models.evento import Intervalo, TramoEspera
from models.proceso import EstadoProceso, Proceso
from schedulers import crear, SimuladorProcesos
from core.metricas import ConsumoCPU
from ui.chart_procesos import (
    conteo_espera,
    figura_cartesiana,
    figura_consumo_cpu,
    pids_visibles,
    seleccionar_pids,
    tabla_intervalos,
)


def intervalos_ejemplo() -> list[Intervalo]:
    return [
        Intervalo(1, 0, 3, "FCFS", "P1"),
        Intervalo(None, 3, 5, "FCFS", "CPU inactiva"),
        Intervalo(2, 5, 8, "FCFS", "P2"),
        Intervalo(1, 8, 9, "FCFS", "P1"),
    ]


def esperas_ejemplo() -> dict[int, list[TramoEspera]]:
    """Tramos sinteticos: P2 en cola de listos, P3 listo y luego bloqueado."""
    return {
        1: [],
        2: [TramoEspera(2, 1, 3, "listo")],
        3: [TramoEspera(3, 2, 4, "listo"), TramoEspera(3, 5, 7, "bloqueado")],
    }


class TestTablaIntervalos(unittest.TestCase):
    def test_columnas_requeridas(self):
        df = tabla_intervalos(intervalos_ejemplo())
        self.assertEqual(
            list(df.columns),
            ["PID", "Proceso", "Inicio", "Fin", "Duración", "Algoritmo"],
        )

    def test_duracion_calculada(self):
        df = tabla_intervalos(intervalos_ejemplo())
        self.assertEqual(list(df["Duración"]), [3, 2, 3, 1])

    def test_vacia(self):
        df = tabla_intervalos([])
        self.assertTrue(df.empty)


class TestPidsVisibles(unittest.TestCase):
    def test_incluye_no_ejecutados(self):
        procesos = [Proceso(1, 0, 3, 1), Proceso(9, 0, 3, 1)]
        intervalos = [Intervalo(1, 0, 3, "FCFS", "P1")]
        self.assertEqual(pids_visibles(intervalos, procesos), [1, 9])

    def test_sin_procesos_ni_intervalos(self):
        self.assertEqual(pids_visibles([], []), [])


class TestFiguraCartesiana(unittest.TestCase):
    def test_un_trazo_por_proceso_y_leyenda(self):
        fig = figura_cartesiana(intervalos_ejemplo(), reloj=4)
        nombres = [t.name for t in fig.data]
        self.assertIn("P1", nombres)
        self.assertIn("P2", nombres)
        self.assertIn("CPU inactiva", nombres)

    def test_segmentos_derivan_de_los_intervalos(self):
        fig = figura_cartesiana(intervalos_ejemplo(), reloj=4)
        por_nombre = {t.name: t for t in fig.data}
        p1 = por_nombre["P1"]
        # P1 aparece en [0,3) y [8,9)
        self.assertEqual(list(p1.base), [0, 8])
        self.assertEqual(list(p1.x), [3, 1])
        p2 = por_nombre["P2"]
        self.assertEqual(list(p2.base), [5])
        self.assertEqual(list(p2.x), [3])

    def test_inactiva_en_su_fila_propia(self):
        fig = figura_cartesiana(intervalos_ejemplo(), reloj=4)
        inactiva = [t for t in fig.data if t.name == "CPU inactiva"][0]
        self.assertEqual(list(inactiva.base), [3])
        self.assertEqual(list(inactiva.x), [2])

    def test_cursor_presente(self):
        fig = figura_cartesiana(intervalos_ejemplo(), reloj=7)
        lineas = [
            s
            for s in fig.layout.shapes
            if getattr(s, "x0", None) == 7 or getattr(s, "x1", None) == 7
        ]
        self.assertTrue(lineas, "no hay linea vertical del cursor en t=7")

    def test_eje_y_ordenado_con_inactiva_al_final(self):
        fig = figura_cartesiana(intervalos_ejemplo(), reloj=4)
        ticktext = fig.layout.yaxis.ticktext
        self.assertEqual(ticktext[0], "P1")
        self.assertEqual(ticktext[-1], "CPU inactiva")
        self.assertEqual(fig.layout.yaxis.autorange, "reversed")

    def test_vacio_muestra_mensaje(self):
        fig = figura_cartesiana([], reloj=0)
        textos = [a.text for a in fig.layout.annotations]
        self.assertTrue(any("Pulsa" in t for t in textos))

    def test_coherencia_con_un_solo_nucleo(self):
        procesos = [
            Proceso(1, 0, 5, 1),
            Proceso(2, 1, 4, 1),
            Proceso(3, 9, 3, 1),
        ]
        sim = SimuladorProcesos(procesos, crear("srt"))
        sim.ejecutar_completo()
        df = tabla_intervalos(sim.intervalos)
        # Cada instante aparece exactamente una vez (o IDLE o un PID).
        cobertura = {}
        for _, fila in df.iterrows():
            for t in range(int(fila["Inicio"]), int(fila["Fin"])):
                self.assertNotIn(t, cobertura, f"instante {t} duplicado")
                cobertura[t] = fila["PID"]
        self.assertGreater(len(cobertura), 0)


class TestBandaDeEspera(unittest.TestCase):
    """Franja inferior de recuento y segmentos de espera en el Gantt."""

    def test_franja_inferior_con_dos_series(self):
        fig = figura_cartesiana(
            intervalos_ejemplo(),
            reloj=4,
            esperas=esperas_ejemplo(),
        )
        nombres = [t.name for t in fig.data]
        self.assertIn("En espera (cola de listos)", nombres)
        self.assertIn("Bloqueado E/S", nombres)
        banda = [t for t in fig.data if t.name == "Bloqueado E/S"][0]
        self.assertEqual(banda.yaxis, "y2")

    def test_recuento_por_unidad(self):
        listo, bloqueado = conteo_espera(esperas_ejemplo(), limite=9)
        # t=1: solo P2 en cola; t=2: P2 y P3; t=3: solo P3; t=5-6: P3 bloqueado.
        self.assertEqual(listo, [0, 1, 2, 1, 0, 0, 0, 0, 0])
        self.assertEqual(bloqueado, [0, 0, 0, 0, 0, 1, 1, 0, 0])

    def test_cursor_cruza_las_dos_filas(self):
        fig = figura_cartesiana(
            intervalos_ejemplo(),
            reloj=4,
            esperas=esperas_ejemplo(),
        )
        refs = [s.yref for s in fig.layout.shapes if getattr(s, "x0", None) == 4]
        self.assertIn("y domain", refs)
        self.assertIn("y2 domain", refs)

    def test_segmentos_de_espera_en_las_filas_de_proceso(self):
        procesos = [Proceso(1, 0, 3, 1), Proceso(2, 1, 3, 1), Proceso(3, 2, 2, 1)]
        fig = figura_cartesiana(
            intervalos_ejemplo(),
            reloj=4,
            procesos=procesos,
            esperas=esperas_ejemplo(),
        )
        en_fila = [
            t
            for t in fig.data
            if t.showlegend is False and t.yaxis == "y" and len(t.y or []) > 0
        ]
        self.assertTrue(en_fila, "no hay tramos de espera en las filas")
        bases = {b for t in en_fila for b in t.base}
        self.assertEqual(bases, {1, 2, 5})

    def test_eje_y_conserva_los_procesos(self):
        fig = figura_cartesiana(
            intervalos_ejemplo(),
            reloj=4,
            esperas=esperas_ejemplo(),
        )
        self.assertEqual(fig.layout.yaxis.ticktext[0], "P1")
        self.assertEqual(fig.layout.yaxis2.title.text, "En espera (n)")

    def test_sin_esperas_no_crea_segundo_renglon(self):
        fig = figura_cartesiana(intervalos_ejemplo(), reloj=4)
        nombres = [t.name for t in fig.data]
        self.assertNotIn("En espera (cola de listos)", nombres)
        self.assertIsNone(getattr(fig.layout, "yaxis2", None))

    def test_esperas_de_una_corrida_real(self):
        procesos = [Proceso(1, 0, 4, 1, rafaga_io=3), Proceso(2, 0, 2, 1)]
        sim = SimuladorProcesos(procesos, crear("fcfs"))
        sim.ejecutar_completo()
        fig = figura_cartesiana(
            sim.intervalos,
            sim.reloj,
            sim.procesos,
            esperas=sim.esperas,
        )
        # P2 espera la CPU en t=0..3; P1 esta bloqueado en E/S en t=4..6.
        lista = [t for t in fig.data if t.name == "En espera (cola de listos)"]
        bloqueada = [t for t in fig.data if t.name == "Bloqueado E/S"]
        self.assertEqual(list(lista[0].y), [1, 1, 1, 1, 0, 0, 0, 0, 0])
        self.assertEqual(list(bloqueada[0].y), [0, 0, 0, 0, 1, 1, 1, 0, 0])
        # La franja apilada usa base para no solaparse con la cola de listos.
        self.assertEqual(list(bloqueada[0].base), list(lista[0].y))


class TestVentanaDeFilas(unittest.TestCase):
    """Recorte de filas/barras para cargas con cientos de procesos."""

    def test_sin_limite_devuelve_todos(self):
        procesos = [Proceso(i, 0, 4, 1) for i in (1, 2, 3)]
        self.assertEqual(seleccionar_pids([1, 2, 3], procesos, None), [1, 2, 3])

    def test_limite_mayor_que_pids_no_recorta(self):
        procesos = [Proceso(i, 0, 4, 1) for i in (1, 2)]
        self.assertEqual(seleccionar_pids([1, 2], procesos, 5), [1, 2])

    def test_prioriza_activos_y_ordena_por_pid(self):
        activo = Proceso(9, 0, 4, 1, estado=EstadoProceso.EJECUCION)
        listo = Proceso(3, 0, 4, 1, estado=EstadoProceso.LISTO)
        nuevos = [Proceso(pid, 0, 4, 1) for pid in (1, 2, 5, 6)]
        procesos = [activo, listo, *nuevos]
        elegidos = seleccionar_pids([1, 2, 3, 5, 6, 9], procesos, 3)
        self.assertEqual(len(elegidos), 3)
        self.assertIn(9, elegidos)
        self.assertIn(3, elegidos)
        self.assertEqual(elegidos, sorted(elegidos))

    def test_gantt_recorta_y_anota(self):
        ivs = [Intervalo(i, i, i + 1, "FCFS", f"P{i}") for i in range(1, 6)]
        procs = [Proceso(i, 0, 1, 1) for i in range(1, 6)]
        fig = figura_cartesiana(ivs, reloj=6, procesos=procs, max_filas=2)
        filas = [t for t in fig.layout.yaxis.ticktext if t != "CPU inactiva"]
        self.assertEqual(len(filas), 2)
        self.assertIn("de 5 procesos", fig.layout.title.text)

    def test_sin_recorte_no_anota_ventana(self):
        fig = figura_cartesiana(intervalos_ejemplo(), reloj=4, max_filas=10)
        self.assertNotIn("mostrando", fig.layout.title.text or "")


class TestFiguraConsumoCPU(unittest.TestCase):
    def test_barras_por_proceso(self):
        consumos = [
            ConsumoCPU(1, "P1", 5, 41.7),
            ConsumoCPU(2, "P2", 7, 58.3),
        ]
        fig = figura_consumo_cpu(consumos)
        self.assertEqual(len(fig.data), 1)
        self.assertEqual(list(fig.data[0].x), [41.7, 58.3])
        self.assertEqual(list(fig.data[0].y), ["P1", "P2"])

    def test_sin_ejecucion_muestra_mensaje(self):
        fig = figura_consumo_cpu([])
        textos = [a.text for a in fig.layout.annotations]
        self.assertTrue(any("Sin ejecución" in t for t in textos))

    def test_paleta_por_pid(self):
        consumos = [
            ConsumoCPU(1, "P1", 1, 50.0),
            ConsumoCPU(2, "P2", 1, 50.0),
        ]
        fig = figura_consumo_cpu(consumos)
        colores = list(fig.data[0].marker.color)
        self.assertNotEqual(colores[0], colores[1])

    def test_etiquetas_muestran_rafaga_cuando_hay_procesos(self):
        ivs = [Intervalo(1, 0, 2, "SPN", "P1"), Intervalo(2, 2, 4, "SPN", "P2")]
        procs = [Proceso(1, 0, 5, 1), Proceso(2, 1, 3, 2)]
        fig = figura_cartesiana(ivs, reloj=5, procesos=procs)
        ticktext = fig.layout.yaxis.ticktext
        self.assertIn("P1 · 5u", ticktext)
        self.assertIn("P2 · 3u", ticktext)

    def test_max_barras_recorta_y_anota(self):
        consumos = [ConsumoCPU(i, f"P{i}", i, float(i)) for i in range(1, 11)]
        fig = figura_consumo_cpu(consumos, max_barras=3)
        self.assertEqual(len(fig.data[0].x), 3)
        textos = [a.text for a in fig.layout.annotations]
        self.assertTrue(any("top 3 de 10" in t for t in textos))

    def test_mostrar_cero_falso_oculta_inactivos(self):
        consumos = [
            ConsumoCPU(1, "P1", 5, 100.0),
            ConsumoCPU(2, "P2", 0, 0.0),
        ]
        fig = figura_consumo_cpu(consumos, mostrar_cero=False)
        self.assertEqual(list(fig.data[0].y), ["P1"])


if __name__ == "__main__":
    unittest.main()
