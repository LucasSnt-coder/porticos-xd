# -*- coding: utf-8 -*-
"""Renderer mejorado: añade escala explícita a los diagramas."""
from __future__ import annotations
import numpy as np
from frame_renderer import StructureRenderer


class EnhancedStructureRenderer(StructureRenderer):
    def draw_diagram(self, nodes, elements, elem_results, diagram, title):
        self.clear()
        span = self._bounds(nodes)
        scale_ref = span * 0.22

        for el in elements.values():
            ni, nj = nodes[el["ni"]], nodes[el["nj"]]
            self.ax.plot([ni["x"], nj["x"]], [ni["y"], nj["y"]],
                         color="#a0aec0", linewidth=1.6, zorder=1)

        arr_key = diagram
        global_max = 0.0
        for er in elem_results.values():
            vals = er.get(arr_key)
            if vals is not None and len(vals):
                global_max = max(global_max, float(np.max(np.abs(vals))))

        color_map = {"N": "#c53030", "V": "#2b6cb0", "M": "#805ad5"}
        color = color_map[diagram]
        visual_multiplier = (scale_ref / global_max) if global_max > 1e-14 else 0.0

        for eid, el in elements.items():
            er = elem_results.get(eid)
            if er is None:
                continue
            ni, nj = nodes[el["ni"]], nodes[el["nj"]]
            dx, dy = nj["x"] - ni["x"], nj["y"] - ni["y"]
            L = np.hypot(dx, dy)
            if L < 1e-12:
                continue
            c, s = dx / L, dy / L
            nx, ny = -s, c
            vals = er.get(arr_key)
            x_local = er.get("x")
            if vals is None or x_local is None:
                continue

            scaled = vals * visual_multiplier if visual_multiplier else np.zeros_like(vals)
            base_x = ni["x"] + c * x_local
            base_y = ni["y"] + s * x_local
            draw_vals = -scaled if diagram == "M" else scaled
            top_x = base_x + nx * draw_vals
            top_y = base_y + ny * draw_vals

            poly_x = np.concatenate([base_x, top_x[::-1]])
            poly_y = np.concatenate([base_y, top_y[::-1]])
            self.ax.fill(poly_x, poly_y, color=color, alpha=0.30, zorder=2)
            self.ax.plot(top_x, top_y, color=color, linewidth=1.6, zorder=3)

            i_max = int(np.argmax(np.abs(vals))) if len(vals) else 0
            label_indices = sorted(set((0, len(vals) - 1, i_max)))
            for idx in label_indices:
                v_disp = vals[idx]
                self.ax.annotate(
                    f"{v_disp:.3g}",
                    (top_x[idx], top_y[idx]),
                    fontsize=7,
                    color=color,
                    ha="center",
                    fontweight="bold" if idx == i_max else "normal",
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", ec=color,
                              lw=0.5, alpha=0.85),
                    zorder=5,
                )

        unit_lbl = {"N": self.units.force_symbol, "V": self.units.force_symbol,
                    "M": f"{self.units.force_symbol}\u00b7{self.units.length_symbol}"}
        self.ax.set_title(f"{title}  [{unit_lbl[diagram]}]", fontsize=11, fontweight="bold")
        self.ax.set_xlabel(f"X [{self.units.length_symbol}]")
        self.ax.set_ylabel(f"Y [{self.units.length_symbol}]")
        self._pad_view(nodes, span)

        if global_max <= 1e-14:
            scale_text = "Escala axial: sin esfuerzo axial significativo (N ≈ 0)"
        else:
            scale_text = (
                f"Escala visual: x {visual_multiplier:.4g} "
                f"({self.units.length_symbol} de dibujo / {unit_lbl[diagram]})"
            )
        self.ax.text(
            0.015, 0.985, scale_text,
            transform=self.ax.transAxes,
            ha="left", va="top", fontsize=9, fontweight="bold",
            color=color,
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=color,
                      lw=0.9, alpha=0.92),
            zorder=20,
        )
