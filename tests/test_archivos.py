"""Pruebas de la carga y validacion de archivos TXT."""

from __future__ import annotations

import unittest

from core.archivos import GestorArchivos


class TestCargaValida(unittest.TestCase):
    def test_carga_correcta(self):
        texto = "PID,Llegada,Rafaga,Prioridad\n1,0,5,2\n2,1,3,1\n"
        r = GestorArchivos.parsear(texto)
        self.assertTrue(r.ok)
        self.assertEqual([p.pid for p in r.procesos], [1, 2])
        self.assertEqual([p.rafaga for p in r.procesos], [5, 3])

    def test_sin_cabecera(self):
        r = GestorArchivos.parsear("1,0,5,2\n2,1,3,1\n")
        self.assertTrue(r.ok)
        self.assertEqual(len(r.procesos), 2)

    def test_comentarios_y_blancos_ignorados(self):
        r = GestorArchivos.parsear("# esto es comentario\n\n  \n1,0,5,2\n")
        self.assertTrue(r.ok)
        self.assertEqual(len(r.procesos), 1)

    def test_columna_io_opcional(self):
        r = GestorArchivos.parsear("1,0,5,2,3\n")
        self.assertTrue(r.ok)
        self.assertEqual(r.procesos[0].rafaga_io, 3)

    def test_separador_punto_y_coma(self):
        r = GestorArchivos.parsear("1;0;5;2\n")
        self.assertTrue(r.ok)

    def test_proceso_con_prioridad_cero(self):
        r = GestorArchivos.parsear("1,0,5,0\n")
        self.assertTrue(r.ok)


class TestValidacionDeErrores(unittest.TestCase):
    def test_columnas_de_mas(self):
        r = GestorArchivos.parsear("1,0,5,2,9,7\n")
        self.assertFalse(r.ok)
        self.assertTrue(any("Linea 1" in e for e in r.errores))

    def test_valor_no_numerico(self):
        r = GestorArchivos.parsear("1,0,abc,2\n")
        self.assertFalse(r.ok)
        self.assertIn("no numerico", r.errores[0])

    def test_rafaga_cero(self):
        r = GestorArchivos.parsear("1,0,0,2\n")
        self.assertFalse(r.ok)
        self.assertIn("rafaga", r.errores[0].lower())

    def test_rafaga_negativa(self):
        r = GestorArchivos.parsear("1,0,-4,2\n")
        self.assertFalse(r.ok)

    def test_llegada_negativa(self):
        r = GestorArchivos.parsear("1,-2,4,2\n")
        self.assertFalse(r.ok)

    def test_prioridad_negativa(self):
        r = GestorArchivos.parsear("1,0,4,-1\n")
        self.assertFalse(r.ok)

    def test_pid_duplicado(self):
        r = GestorArchivos.parsear("1,0,4,2\n1,2,3,1\n")
        self.assertFalse(r.ok)
        self.assertTrue(any("duplicado" in e for e in r.errores))

    def test_archivo_vacio(self):
        r = GestorArchivos.parsear("")
        self.assertFalse(r.ok)
        self.assertTrue(r.errores)

    def test_errores_con_numero_de_linea(self):
        texto = "1,0,4,2\nbasura\n2,1,4,2\n"
        r = GestorArchivos.parsear(texto)
        self.assertFalse(r.ok)
        self.assertTrue(any("Linea 2" in e for e in r.errores))
        # Las lineas validas se conservan.
        self.assertEqual([p.pid for p in r.procesos], [1, 2])

    def test_solapa_archivo_ejemplo(self):
        r = GestorArchivos.cargar("data/procesos_ejemplo.txt")
        self.assertTrue(r.ok, msg=str(r.errores))
        self.assertGreaterEqual(len(r.procesos), 4)


class TestExportacionCSV(unittest.TestCase):
    def test_csv_vacio(self):
        self.assertEqual(GestorArchivos.filas_a_csv([]), "")

    def test_csv_filas(self):
        salida = GestorArchivos.filas_a_csv(
            [{"pid": 1, "fin": 5}, {"pid": 2, "fin": 9}]
        )
        lineas = salida.strip().splitlines()
        self.assertEqual(lineas[0], "pid,fin")
        self.assertEqual(lineas[1], "1,5")
        self.assertEqual(lineas[2], "2,9")


if __name__ == "__main__":
    unittest.main()
