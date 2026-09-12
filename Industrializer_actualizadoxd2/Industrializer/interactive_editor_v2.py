# -*- coding: utf-8 -*-
"""Ajustes finales del editor interactivo sobre interactive_editor."""
from __future__ import annotations

from matplotlib.ticker import MultipleLocator
from interactive_editor import install as _base_install

_GRID = 1.0


def install(app_class):
    """Instala el editor base y añade rejilla/selección/vistas seguras."""
    _base_install(app_class)
    app_class._ie_view = _view
    original = app_class._redraw
    app_class._ie_original_redraw_v2 = original
    app_class._redraw = _redraw


def _view(self, kind):
    self.current_diagram = kind
    self._redraw()


def _redraw(self):
    self._ie_original_redraw_v2(self)
    if not hasattr(self, "ax"):
        return
    # Rejilla de trabajo: cada intersección de 1 unidad es un punto válido
    # para insertar nodos mediante el ajuste automático (snap).
    self.ax.xaxis.set_major_locator(MultipleLocator(_GRID))
    self.ax.yaxis.set_major_locator(MultipleLocator(_GRID))
    self.ax.grid(True, which="major", linestyle=":", linewidth=0.55, alpha=0.35)

    # Resaltar nodo seleccionado y primer extremo durante la creación de un
    # elemento. Se dibuja encima del renderer existente.
    nid = getattr(self, "_ie_selected_node", None)
    if nid in self.nodes:
        n = self.nodes[nid]
        self.ax.plot(n["x"], n["y"], marker="o", markersize=13,
                     markerfacecolor="none", markeredgewidth=2.2,
                     markeredgecolor="#f6ad55", zorder=30)
    pending = getattr(self, "_ie_pending_node", None)
    if pending in self.nodes:
        n = self.nodes[pending]
        self.ax.plot(n["x"], n["y"], marker="o", markersize=16,
                     markerfacecolor="none", markeredgewidth=2.2,
                     markeredgecolor="#63b3ed", zorder=31)
    self.canvas.draw_idle()
