# -*- coding: utf-8 -*-
"""Punto de entrada de Industrializer — Santos Corp."""

from industrializer_app import IndustrializerApp, run_app
from interactive_editor_v2 import install

# Sustituye únicamente la pestaña Editor Visual; el solver, resultados,
# procedimiento y exportación existentes permanecen en IndustrializerApp.
install(IndustrializerApp)


if __name__ == "__main__":
    run_app()
