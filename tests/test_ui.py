"""Prueba de humo de la interfaz con ``streamlit.testing.v1.AppTest``.

Cada prueba parte de una aplicación nueva y navega al Módulo 1 para no
depender del orden de ejecución.
"""

from __future__ import annotations

import logging
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")

# AppTest corre la aplicación fuera de un servidor ("bare mode") y Streamlit
# emite un aviso inocuo por cada ejecución del script. Lo filtramos para que
# la salida de la suite quede limpia; no afecta a la lógica probada.
_AVISO = "missing ScriptRunContext"
_filtro_original = logging.Logger.filter


def _filtrar_aviso_de_streamlit(self: logging.Logger, record: logging.LogRecord):
    try:
        if _AVISO in record.getMessage():
            return False
    except Exception:  # pragma: no cover - nunca debe romper un test
        pass
    return _filtro_original(self, record)


logging.Logger.filter = _filtrar_aviso_de_streamlit


class TestInterfaz(unittest.TestCase):
    def setUp(self):
        self.at = AppTest.from_file(APP, default_timeout=60)
        self.at.run()
        self.assertFalse(self.at.exception, "la pantalla inicial fallo")
        self.at.segmented_control[0].set_value("Planificación de procesos")
        self.at.run()

    def _boton(self, etiqueta):
        return [b for b in self.at.button if b.label == etiqueta][0]

    def _sim(self):
        return self.at.session_state.get("proc_sim")

    def test_navegacion_a_procesos(self):
        self.assertFalse(self.at.exception)
        etiquetas = [b.label for b in self.at.button]
        for esperado in ("Iniciar", "Pausar", "Avanzar evento", "Reiniciar"):
            self.assertIn(esperado, etiquetas)

    def test_avanzar_evento_produce_estado(self):
        sim = self._sim()
        inicial = sim.reloj
        self._boton("Avanzar evento").click()
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertGreater(sim.reloj, inicial)
        self.assertGreater(len(sim.intervalos), 0)

    def test_avanzar_intervalo(self):
        sim = self._sim()
        antes = sim.reloj
        [
            b
            for b in self.at.button
            if b.label.startswith("Avanzar intervalo")
        ][0].click()
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertGreater(sim.reloj, antes)

    def test_reiniciar_borra_todo(self):
        self._boton("Avanzar evento").click()
        self.at.run()
        self._boton("Reiniciar").click()
        self.at.run()
        self.assertFalse(self.at.exception)
        sim = self._sim()
        self.assertEqual(sim.reloj, 0)
        self.assertEqual(sim.intervalos, [])
        self.assertEqual(sim.eventos, [])

    def test_grafico_y_registros_presentes(self):
        self.assertGreaterEqual(len(self.at.get("plotly_chart")), 1)
        self.assertEqual(len(self.at.tabs), 3)
        self.assertGreaterEqual(len(self.at.dataframe), 3)

    def test_pausar_desactiva_auto(self):
        self._boton("Pausar").click()
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertFalse(self.at.session_state.get("proc_auto"))

    def test_cambio_de_algoritmo_reconstruye(self):
        self.at.selectbox[0].set_value("rr")
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self._sim().nombre_algoritmo, "Round Robin")

    def test_carga_ejemplo(self):
        self._boton("Cargar archivo de ejemplo").click()
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertGreaterEqual(len(self.at.session_state["proc_procesos"]), 4)

    def test_entrada_manual_carga_procesos(self):
        self.at.text_area[0].set_value("1,0,4,2\n2,1,3,1")
        self._boton("Cargar procesos escritos").click()
        self.at.run()
        self.assertFalse(self.at.exception)
        pids = [p.pid for p in self.at.session_state["proc_procesos"]]
        self.assertEqual(pids, [1, 2])
        self.assertFalse(self.at.exception)

    def test_entrada_manual_rechaza_linea_invalida(self):
        antes = len(self.at.session_state["proc_procesos"])
        self.at.text_area[0].set_value("1,0,0,2\n")
        self._boton("Cargar procesos escritos").click()
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertEqual(len(self.at.session_state["proc_procesos"]), antes)

    def test_diagrama_muestra_rafaga_y_conteo(self):
        self.assertGreaterEqual(len(self.at.get("plotly_chart")), 1)
        markdowns = [str(m.value) for m in self.at.markdown]
        self.assertTrue(any("Procesos" in m for m in markdowns))
        self.assertTrue(any("Ráfaga total" in m for m in markdowns))

    def test_navegacion_superior_entre_modulos(self):
        self.at.segmented_control[0].set_value("Concurrencia")
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertIn("Módulo 2", self.at.title[0].value)
        self.at.segmented_control[0].set_value("Planificación de procesos")
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertIn("Módulo 1", self.at.title[0].value)


class TestEventosPorFotograma(unittest.TestCase):
    """La ejecución automática agrupa eventos solo con cargas grandes."""

    def test_pocos_procesos_paso_a_paso(self):
        from ui.page_procesos import eventos_por_fotograma

        self.assertEqual(eventos_por_fotograma(5), 1)
        self.assertEqual(eventos_por_fotograma(80), 1)

    def test_carga_grande_agrupa_eventos(self):
        from ui.page_procesos import eventos_por_fotograma

        self.assertGreater(eventos_por_fotograma(1000), 1)


class TestInterfazConcurrencia(unittest.TestCase):
    def setUp(self):
        self.at = AppTest.from_file(APP, default_timeout=90)
        # velocidad 0 -> el bucle automatico termina en la misma ejecucion
        self.at.session_state["conc_velocidad"] = 0.0
        self.at.run()
        self.at.segmented_control[0].set_value("Concurrencia")
        self.at.run()

    def _selector(self):
        return [
            s
            for s in self.at.selectbox
            if s.label == "Simulador de concurrencia"
        ][0]

    def _boton(self, etiqueta):
        return [b for b in self.at.button if b.label == etiqueta][0]

    def test_pagina_sin_excepciones(self):
        self.assertFalse(self.at.exception)
        self.assertIn("Módulo 2", self.at.title[0].value)

    def test_arranca_en_automatico_sin_presionar_botones(self):
        self.assertFalse(self.at.exception)
        sim = self.at.session_state["conc_sim"]
        self.assertGreater(sim.paso_actual, 0)

    def test_configuracion_nueva_enciende_automatizacion(self):
        from ui.page_concurrencia import _obtener_simulador

        ss: dict = {}
        sim = _obtener_simulador("barbero", {}, ss)
        self.assertIsNotNone(sim)
        self.assertTrue(ss["conc_auto"])
        self.assertTrue(ss["conc_auto_toggle"])

    def test_solo_avanza_un_paso_a_la_vez(self):
        etiquetas = [b.label for b in self.at.button]
        self.assertIn("Avanzar paso", etiquetas)
        self.assertFalse(
            any(e.startswith("Avanzar ") and e.endswith("pasos") for e in etiquetas),
            etiquetas,
        )
        self.assertNotIn("conc_unidades", self.at.session_state)

    def test_leyenda_compacta_de_hilos_y_recursos(self):
        textos = [str(c.value) for c in self.at.caption]
        leyenda = [t for t in textos if "Hilos:" in t]
        self.assertTrue(leyenda, textos)
        self.assertIn("Semáforos:", leyenda[0])
        self.assertIn("empty", leyenda[0])
        self.assertIn("Recurso:", leyenda[0])

    def test_ejecutar_completo_productor_consumidor(self):
        self._boton("Ejecutar completo").click()
        self.at.run()
        self.assertFalse(self.at.exception)
        sim = self.at.session_state["conc_sim"]
        self.assertTrue(sim.terminado)
        self.assertEqual(sim.variables["consumidos"], sim.variables["producidos"])

    def test_reiniciar(self):
        self._boton("Avanzar paso").click()
        self.at.run()
        self._boton("Reiniciar").click()
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state["conc_sim"].paso_actual, 0)

    def test_recorrer_los_cinco_problemas(self):
        from concurrency import claves

        for clave in claves():
            self._selector().set_value(clave)
            self.at.run()
            self.assertFalse(self.at.exception, f"fallo en {clave}")
            self._boton("Ejecutar completo").click()
            self.at.run()
            self.assertFalse(self.at.exception, f"fallo al ejecutar {clave}")
            self.assertTrue(self.at.session_state["conc_sim"].terminado)

    def test_filosofos_ingenuo_muestra_interbloqueo(self):
        self._selector().set_value("filosofos")
        self.at.run()
        self._boton("Ejecutar completo").click()
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertTrue(self.at.session_state["conc_sim"].interbloqueo)


if __name__ == "__main__":
    unittest.main()