"""Pruebas de los archivos de datos generados para validar la lectura TXT."""

from __future__ import annotations

import unittest
from pathlib import Path

from core.archivos import MAX_PROCESOS, GestorArchivos
from scripts.generar_datos import N_PROCESOS, SEMILLA, texto_limpio

BASE = Path(__file__).resolve().parent.parent
RUTA_LIMPIO = BASE / "data" / "procesos_1000.txt"
RUTA_SUCIO = BASE / "data" / "procesos_sucios.txt"


class TestArchivoLimpio(unittest.TestCase):
    def test_carga_mil_procesos_sin_errores_ni_advertencias(self):
        self.assertTrue(RUTA_LIMPIO.exists(), f"Falta {RUTA_LIMPIO}")
        r = GestorArchivos.cargar(RUTA_LIMPIO)
        self.assertTrue(r.ok)
        self.assertEqual(len(r.procesos), N_PROCESOS)
        self.assertEqual(len(r.procesos), MAX_PROCESOS)
        self.assertEqual(r.errores, [])
        self.assertEqual(r.advertencias, [])

    def test_pids_unicos_y_rangos_validos(self):
        r = GestorArchivos.cargar(RUTA_LIMPIO)
        pids = [p.pid for p in r.procesos]
        self.assertEqual(len(set(pids)), len(pids))
        self.assertEqual(sorted(pids), list(range(1, N_PROCESOS + 1)))
        for p in r.procesos:
            self.assertGreaterEqual(p.rafaga, 1)
            self.assertGreaterEqual(p.rafaga_io, 0)
            self.assertGreaterEqual(p.llegada, 0)
            self.assertGreaterEqual(p.prioridad, 0)

    def test_incluye_procesos_con_y_sin_columna_io(self):
        r = GestorArchivos.cargar(RUTA_LIMPIO)
        con_io = [p for p in r.procesos if p.rafaga_io > 0]
        sin_io = [p for p in r.procesos if p.rafaga_io == 0]
        self.assertTrue(con_io)
        self.assertTrue(sin_io)

    def test_archivo_coincide_con_el_generador(self):
        self.assertEqual(
            RUTA_LIMPIO.read_text(encoding="utf-8"),
            texto_limpio(N_PROCESOS, SEMILLA),
        )

    def test_procesos_limpios_no_superan_el_maximo(self):
        self.assertEqual(N_PROCESOS, MAX_PROCESOS)


class TestArchivoConErrores(unittest.TestCase):
    def test_carga_1000_validos_y_reporta_errores(self):
        r = GestorArchivos.cargar(RUTA_SUCIO)
        self.assertEqual(len(r.procesos), N_PROCESOS)
        self.assertFalse(r.ok)
        self.assertEqual(len(r.errores), 9)

    def test_mensajes_de_error_clasificados(self):
        r = GestorArchivos.cargar(RUTA_SUCIO)
        texto = "\n".join(r.errores)
        self.assertIn("duplicado", texto)
        self.assertIn("no numerico", texto)
        self.assertIn("columnas", texto)
        self.assertIn("prioridad", texto)
        self.assertIn("llegada", texto)
        self.assertIn("rafaga", texto)


if __name__ == "__main__":
    unittest.main()
