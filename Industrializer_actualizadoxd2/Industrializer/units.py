# -*- coding: utf-8 -*-
"""
units.py
--------
Sistemas de unidades soportados por la aplicacion.

Filosofia de implementacion:
    Todo el motor de calculo (frame_solver.py / truss_solver.py) trabaja
    INTERNAMENTE siempre en el sistema SI Estandar (N, m, Pa).
    La capa de interfaz (app_interface.py) es responsable de:
        1) Convertir los valores que el usuario escribe (en el sistema
           elegido) hacia SI antes de enviarlos al motor de calculo.
        2) Convertir los resultados (que el motor entrega en SI) de vuelta
           al sistema elegido antes de mostrarlos.

    Esto evita "unidades mezcladas" dentro de las matrices de rigidez y
    hace que el codigo de calculo sea independiente del sistema visual.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitSystem:
    key: str
    label: str
    force_symbol: str
    length_symbol: str
    stress_symbol: str
    # Factor multiplicativo para llevar la unidad de PANTALLA a SI (N, m, Pa)
    force_to_si: float
    length_to_si: float
    stress_to_si: float

    # ---- Conversion pantalla -> SI ----
    def force_in(self, value_display: float) -> float:
        return value_display * self.force_to_si

    def length_in(self, value_display: float) -> float:
        return value_display * self.length_to_si

    def stress_in(self, value_display: float) -> float:
        return value_display * self.stress_to_si

    # ---- Conversion SI -> pantalla ----
    def force_out(self, value_si: float) -> float:
        return value_si / self.force_to_si

    def length_out(self, value_si: float) -> float:
        return value_si / self.length_to_si

    def stress_out(self, value_si: float) -> float:
        return value_si / self.stress_to_si

    # Momento (Fuerza * Longitud)
    def moment_in(self, value_display: float) -> float:
        return value_display * self.force_to_si * self.length_to_si

    def moment_out(self, value_si: float) -> float:
        return value_si / (self.force_to_si * self.length_to_si)


UNIT_SYSTEMS = {
    "SI": UnitSystem(
        key="SI", label="SI Estandar (N, m, Pa)",
        force_symbol="N", length_symbol="m", stress_symbol="Pa",
        force_to_si=1.0, length_to_si=1.0, stress_to_si=1.0,
    ),
    "SI_TECH": UnitSystem(
        key="SI_TECH", label="SI Tecnico (kN, m, MPa)",
        force_symbol="kN", length_symbol="m", stress_symbol="MPa",
        force_to_si=1.0e3, length_to_si=1.0, stress_to_si=1.0e6,
    ),
    "IMPERIAL": UnitSystem(
        key="IMPERIAL", label="Imperial (kip, in, ksi)",
        force_symbol="kip", length_symbol="in", stress_symbol="ksi",
        force_to_si=4448.221615,       # 1 kip -> N
        length_to_si=0.0254,           # 1 in -> m
        stress_to_si=6894757.293168,   # 1 ksi -> Pa
    ),
}


def get_unit_system(key: str) -> UnitSystem:
    return UNIT_SYSTEMS[key]
