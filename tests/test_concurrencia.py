"""Pruebas del motor de concurrencia y de los cinco simuladores.

Se verifica el comportamiento observable: terminacion sin interbloqueo en los
protocolos correctos, deteccion real de interbloqueo en los incorrectos,
reproducibilidad, y las invariantes de cada problema.
"""

from __future__ import annotations

import unittest

from concurrency import crear, claves
from concurrency.base import (
    LIMITE_PASOS,
    Actor,
    EstadoActor,
    Micro,
    SimuladorConcurrencia,
)
from concurrency.barbero import Barbero
from concurrency.filosofos import Filosofos
from concurrency.fumadores import Fumadores
from concurrency.lectores_escritores import LectoresEscritores
from concurrency.productor_consumidor import ProductorConsumidor


def _firma(sim: SimuladorConcurrencia) -> list[tuple]:
    return [tuple(sorted(e.to_dict().items())) for e in sim.eventos]


class _Demo(SimuladorConcurrencia):
    """Dos actores siempre listos, para probar el reparto circular."""

    titulo = "Demo"

    def __init__(self, pasos: int = 4) -> None:
        self.pasos = pasos
        super().__init__()

    def _construir(self) -> None:
        self.semaforos = {}
        self.variables = {}
        self.actores = [
            Actor(nombre, "Demo", self._programa()) for nombre in ("A", "B")
        ]

    def _programa(self):
        def gen():
            for _ in range(self.pasos):
                yield Micro("accion", "trabajar", fn=lambda a: "ok")
            yield Micro("fin", "Terminar")

        return gen


class TestMotor(unittest.TestCase):
    def test_fabrica_conocida(self):
        for clave in claves():
            self.assertIsInstance(crear(clave), SimuladorConcurrencia)

    def test_fabrica_desconocida(self):
        with self.assertRaises(KeyError):
            crear("no_existe")

    def test_reparto_circular_entre_actores_listos(self):
        sim = _Demo(4)
        sim.ejecutar_completo()
        ejecutados = [e.actor for e in sim.eventos if e.actor != "sistema"]
        for a, b in zip(ejecutados, ejecutados[1:]):
            self.assertNotEqual(a, b, "dos operaciones seguidas del mismo actor")
        self.assertEqual(ejecutados.count("A"), ejecutados.count("B"))

    def test_reiniciar_devuelve_al_inicio(self):
        sim = Fumadores(4)
        sim.ejecutar_completo()
        sim.reiniciar()
        self.assertEqual(sim.paso_actual, 0)
        self.assertEqual(sim.variables["cigarros"], 0)
        self.assertFalse(sim.terminado)
        self.assertFalse(sim.interbloqueo)
        self.assertEqual(len(sim.eventos), 1)


class TestProductorConsumidor(unittest.TestCase):
    def test_correcto_termina_y_conserva(self):
        sim = ProductorConsumidor(2, 2, 3, 3, "correcto")
        sim.ejecutar_completo()
        self.assertTrue(sim.terminado)
        self.assertFalse(sim.interbloqueo)
        self.assertEqual(sim.variables["producidos"], 6)
        self.assertEqual(sim.variables["consumidos"], 6)
        self.assertEqual(sim.variables["insertados"], sim.variables["extraidos"])
        self.assertTrue(sim.buffer.vacio)
        self.assertEqual(sim.violaciones, [])

    def test_capacidad_uno_no_interbloquea(self):
        sim = ProductorConsumidor(1, 1, 1, 5, "correcto")
        sim.ejecutar_completo()
        self.assertFalse(sim.interbloqueo)
        self.assertEqual(sim.variables["consumidos"], 5)

    def test_protocolo_incorrecto_interbloquea(self):
        sim = ProductorConsumidor(2, 1, 1, 2, "incorrecto")
        sim.ejecutar_completo()
        self.assertTrue(sim.interbloqueo)
        self.assertTrue(sim.terminado)

    def test_invariante_buzon(self):
        sim = ProductorConsumidor(3, 2, 2, 3, "correcto")
        sim.ejecutar_completo()
        self.assertEqual(sim.violaciones, [])

    def test_determinista(self):
        a = ProductorConsumidor(2, 2, 3, 3, "correcto")
        b = ProductorConsumidor(2, 2, 3, 3, "correcto")
        a.ejecutar_completo()
        b.ejecutar_completo()
        self.assertEqual(_firma(a), _firma(b))

    def test_validacion(self):
        with self.assertRaises(ValueError):
            ProductorConsumidor(0, 1, 1, 1)
        with self.assertRaises(ValueError):
            ProductorConsumidor(1, 1, 0, 1)
        with self.assertRaises(ValueError):
            ProductorConsumidor(1, 1, 1, 1, "raro")


class TestLectoresEscritores(unittest.TestCase):
    def _verifica(self, prioridad):
        sim = LectoresEscritores(3, 2, 2, 2, prioridad)
        sim.ejecutar_completo()
        self.assertTrue(sim.terminado)
        self.assertFalse(sim.interbloqueo)
        self.assertEqual(sim.variables["lecturas"], 3 * 2)
        self.assertEqual(sim.variables["escrituras"], 2 * 2)
        self.assertEqual(sim.variables["lectores_en_sala"], 0)
        self.assertFalse(sim.variables["escritor_en_sala"])
        self.assertEqual(sim.violaciones, [])

    def test_prioridad_lectores(self):
        self._verifica("lectores")

    def test_prioridad_escritores(self):
        self._verifica("escritores")

    def test_exclusion_mutua_siempre(self):
        sim = LectoresEscritores(4, 2, 2, 2, "lectores")
        while not sim.terminado:
            sim.paso()
            self.assertFalse(
                sim.variables["escritor_en_sala"]
                and sim.variables["lectores_en_sala"] > 0,
                "escritor y lectores simultaneos",
            )
        self.assertEqual(sim.violaciones, [])

    def test_validacion(self):
        with self.assertRaises(ValueError):
            LectoresEscritores(0, 1, 1, 1)


class TestFilosofos(unittest.TestCase):
    def test_ingenuo_interbloquea(self):
        sim = Filosofos(5, 1, "ingenuo")
        sim.ejecutar_completo()
        self.assertTrue(sim.interbloqueo)

    def test_jerarquico_no_interbloquea(self):
        sim = Filosofos(5, 2, "jerarquico")
        sim.ejecutar_completo()
        self.assertFalse(sim.interbloqueo)
        self.assertEqual(sim.variables["comidas"], 5 * 2)
        self.assertEqual(sim.variables["comiendo_ahora"], 0)
        self.assertEqual(sim.violaciones, [])

    def test_camarero_no_interbloquea_y_limita(self):
        sim = Filosofos(5, 2, "camarero")
        maximos = []
        while not sim.terminado:
            sim.paso()
            maximos.append(sim.variables["comiendo_ahora"])
        self.assertFalse(sim.interbloqueo)
        self.assertEqual(sim.variables["comidas"], 5 * 2)
        self.assertLessEqual(max(maximos), 5 - 1)
        self.assertEqual(sim.violaciones, [])

    def test_tres_filosofos_jerarquico(self):
        sim = Filosofos(3, 3, "jerarquico")
        sim.ejecutar_completo()
        self.assertFalse(sim.interbloqueo)
        self.assertEqual(sim.variables["comidas"], 9)

    def test_validacion(self):
        with self.assertRaises(ValueError):
            Filosofos(1, 1, "ingenuo")
        with self.assertRaises(ValueError):
            Filosofos(5, 1, "raro")


class TestBarbero(unittest.TestCase):
    def test_todos_los_clientes_resueltos(self):
        sim = Barbero(6, 3)
        sim.ejecutar_completo()
        self.assertTrue(sim.terminado)
        self.assertFalse(sim.interbloqueo)
        self.assertEqual(
            sim.variables["atendidos"] + sim.variables["rechazados"], 6
        )
        self.assertEqual(sim.variables["esperando"], 0)
        self.assertEqual(sim.violaciones, [])

    def test_suficientes_sillas_atiende_a_todos(self):
        sim = Barbero(4, 4)
        sim.ejecutar_completo()
        self.assertEqual(sim.variables["atendidos"], 4)
        self.assertEqual(sim.variables["rechazados"], 0)

    def test_pocas_sillas_rechaza(self):
        sim = Barbero(5, 1)
        sim.ejecutar_completo()
        self.assertGreater(sim.variables["rechazados"], 0)

    def test_espera_nunca_excede_sillas(self):
        sim = Barbero(8, 2)
        while not sim.terminado:
            sim.paso()
            self.assertLessEqual(sim.variables["esperando"], 2)
        self.assertEqual(sim.violaciones, [])

    def test_validacion(self):
        with self.assertRaises(ValueError):
            Barbero(0, 1)
        with self.assertRaises(ValueError):
            Barbero(1, 0)


class TestFumadores(unittest.TestCase):
    def test_termina_una_ronda_por_fumada(self):
        sim = Fumadores(6)
        sim.ejecutar_completo()
        self.assertTrue(sim.terminado)
        self.assertFalse(sim.interbloqueo)
        self.assertEqual(sim.variables["cigarros"], 6)
        self.assertEqual(sim.variables["rondas_hechas"], 6)
        self.assertEqual(sim.violaciones, [])

    def test_reparto_equitativo(self):
        sim = Fumadores(6)
        sim.ejecutar_completo()
        cigarros = [a.datos["cigarros"] for a in sim.actores if a.rol == "Fumador"]
        self.assertEqual(sum(cigarros), 6)
        self.assertEqual(cigarros, [2, 2, 2])

    def test_mesa_nunca_mas_de_dos(self):
        sim = Fumadores(9)
        while not sim.terminado:
            sim.paso()
            self.assertLessEqual(len(sim.mesa), 2)
        self.assertEqual(sim.violaciones, [])

    def test_determinista_con_desfase(self):
        a = Fumadores(5, 1)
        b = Fumadores(5, 1)
        a.ejecutar_completo()
        b.ejecutar_completo()
        self.assertEqual(_firma(a), _firma(b))

    def test_validacion(self):
        with self.assertRaises(ValueError):
            Fumadores(0)
        with self.assertRaises(ValueError):
            Fumadores(3, -1)


class TestSeguridad(unittest.TestCase):
    def test_limite_de_pasos_no_se_desborda(self):
        # Un interbloqueo se detecta mucho antes del limite de seguridad.
        sim = Filosofos(5, 1, "ingenuo")
        sim.ejecutar_completo(maximo=LIMITE_PASOS)
        self.assertLess(sim.paso_actual, LIMITE_PASOS)

    def test_semaforos_no_negativos(self):
        for clave in claves():
            sim = crear(clave)
            sim.ejecutar_completo()
            for sem in sim.semaforos.values():
                self.assertGreaterEqual(sem.valor, 0, f"{clave}:{sem.nombre}")
                for nombre in sem.bloqueados:
                    actor = next(a for a in sim.actores if a.nombre == nombre)
                    self.assertIs(actor.estado, EstadoActor.BLOQUEADO)


if __name__ == "__main__":
    unittest.main()
