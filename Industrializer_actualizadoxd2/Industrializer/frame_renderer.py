# -*- coding: utf-8 -*-
"""
frame_renderer.py
------------------
Encargado exclusivamente del DIBUJO (Matplotlib) de la estructura:
geometria, apoyos, cargas y diagramas de esfuerzos internos (N, V, M).

No contiene logica de calculo estructural: solo recibe los datos de
entrada (nodos/elementos, en unidades de PANTALLA ya convertidas) y,
opcionalmente, los resultados del solver para dibujar diagramas.
"""

from __future__ import annotations
import numpy as np


class StructureRenderer:
    def __init__(self, ax, unit_system):
        self.ax = ax
        self.units = unit_system

    # ------------------------------------------------------------------ #
    def clear(self):
        self.ax.clear()
        self.ax.set_aspect("equal", adjustable="datalim")
        self.ax.grid(True, linestyle="--", alpha=0.4)

    def _bounds(self, nodes: dict):
        xs = [n["x"] for n in nodes.values()]
        ys = [n["y"] for n in nodes.values()]
        if not xs:
            return 1.0
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
        return span

    # ------------------------------------------------------------------ #
    # Estructura base: nodos, elementos, apoyos, cargas
    # ------------------------------------------------------------------ #
    def draw_structure(self, nodes: dict, elements: dict, structure_type: str,
                        title: str = "Geometria de la Estructura",
                        node_load_scale: float = None,
                        elem_load_scale: float = None):
        self.clear()
        span = self._bounds(nodes)
        support_size = span * 0.045
        load_len = span * 0.18

        # ---- Elementos ----
        for eid, el in elements.items():
            ni, nj = nodes[el["ni"]], nodes[el["nj"]]
            self.ax.plot([ni["x"], nj["x"]], [ni["y"], nj["y"]],
                         color="#2b6cb0", linewidth=2.5, zorder=2,
                         solid_capstyle="round")
            mx, my = (ni["x"] + nj["x"]) / 2, (ni["y"] + nj["y"]) / 2
            self.ax.annotate(str(eid), (mx, my), color="#c53030",
                              fontsize=9, fontweight="bold", ha="center",
                              va="center",
                              bbox=dict(boxstyle="round,pad=0.15",
                                        fc="white", ec="#c53030", lw=0.8),
                              zorder=5)

            # Carga distribuida sobre el elemento (solo porticos)
            if structure_type == "frame":
                w1 = el.get("w1", 0.0)
                w2 = el.get("w2", 0.0)
                if abs(w1) > 1e-12 or abs(w2) > 1e-12:
                    self._draw_distributed_load(ni, nj, w1, w2, span)

        # ---- Nodos y apoyos ----
        for nid, node in nodes.items():
            x, y = node["x"], node["y"]
            self.ax.plot(x, y, "o", color="#1a202c", markersize=6, zorder=4)
            self.ax.annotate(str(nid), (x, y), textcoords="offset points",
                              xytext=(8, 8), fontsize=9, fontweight="bold",
                              color="#1a202c", zorder=5)
            self._draw_support(x, y, node, structure_type, support_size)

            # Carga puntual nodal
            fx, fy = node.get("fx", 0.0), node.get("fy", 0.0)
            if abs(fx) > 1e-12 or abs(fy) > 1e-12:
                self._draw_point_load(x, y, fx, fy, load_len)
            mz = node.get("mz", 0.0)
            if structure_type == "frame" and abs(mz) > 1e-12:
                self._draw_moment(x, y, mz, support_size * 1.8)

        self.ax.set_title(title, fontsize=11, fontweight="bold")
        self.ax.set_xlabel(f"X [{self.units.length_symbol}]")
        self.ax.set_ylabel(f"Y [{self.units.length_symbol}]")
        self._pad_view(nodes, span)

    def _pad_view(self, nodes, span):
        xs = [n["x"] for n in nodes.values()]
        ys = [n["y"] for n in nodes.values()]
        pad = span * 0.35 + 1e-6
        self.ax.set_xlim(min(xs) - pad, max(xs) + pad)
        self.ax.set_ylim(min(ys) - pad, max(ys) + pad)

    # ------------------------------------------------------------------ #
    def _draw_support(self, x, y, node, structure_type, size):
        rx = node.get("rx", False)
        ry = node.get("ry", False)
        rz = node.get("rz", False) if structure_type == "frame" else False

        if not (rx or ry):
            return

        if rx and ry and (rz or structure_type == "truss"):
            # Empotramiento (fijo) si tiene rz tambien, en porticos.
            if structure_type == "frame" and rz:
                self._draw_fixed_support(x, y, size)
            else:
                self._draw_pin_support(x, y, size)
        elif rx and ry and not rz:
            self._draw_pin_support(x, y, size)
        elif ry and not rx:
            self._draw_roller_support(x, y, size, direction="y")
        elif rx and not ry:
            self._draw_roller_support(x, y, size, direction="x")

    def _draw_pin_support(self, x, y, size):
        # Triangulo (articulacion / pasador)
        tri = np.array([[x, y], [x - size, y - size * 1.6],
                         [x + size, y - size * 1.6], [x, y]])
        self.ax.plot(tri[:, 0], tri[:, 1], color="#2d3748", linewidth=1.5, zorder=3)
        self.ax.plot([x - size * 1.4, x + size * 1.4],
                     [y - size * 1.6, y - size * 1.6],
                     color="#2d3748", linewidth=1.5, zorder=3)
        self._hatch(x, y - size * 1.6, size, orientation="h")

    def _draw_fixed_support(self, x, y, size):
        # Empotramiento: linea con rayado (hatch)
        self.ax.plot([x - size * 1.3, x + size * 1.3], [y, y],
                     color="#2d3748", linewidth=2.0, zorder=3)
        self._hatch(x, y, size, orientation="h")

    def _draw_roller_support(self, x, y, size, direction="y"):
        if direction == "y":
            tri = np.array([[x, y], [x - size, y - size * 1.6],
                             [x + size, y - size * 1.6], [x, y]])
            self.ax.plot(tri[:, 0], tri[:, 1], color="#2d3748", linewidth=1.5, zorder=3)
            circ_y = y - size * 1.9
            for dx in (-size * 0.6, size * 0.6):
                circle = plt_circle(x + dx, circ_y, size * 0.28)
                self.ax.plot(circle[0], circle[1], color="#2d3748", linewidth=1.2, zorder=3)
            self.ax.plot([x - size * 1.4, x + size * 1.4],
                         [circ_y - size * 0.3, circ_y - size * 0.3],
                         color="#2d3748", linewidth=1.5, zorder=3)
        else:
            tri = np.array([[x, y], [x - size * 1.6, y - size],
                             [x - size * 1.6, y + size], [x, y]])
            self.ax.plot(tri[:, 0], tri[:, 1], color="#2d3748", linewidth=1.5, zorder=3)
            circ_x = x - size * 1.9
            for dy in (-size * 0.6, size * 0.6):
                circle = plt_circle(circ_x, y + dy, size * 0.28)
                self.ax.plot(circle[0], circle[1], color="#2d3748", linewidth=1.2, zorder=3)

    def _hatch(self, x, y, size, orientation="h"):
        n = 6
        if orientation == "h":
            xs = np.linspace(x - size * 1.3, x + size * 1.3, n)
            for xi in xs:
                self.ax.plot([xi, xi - size * 0.35], [y, y - size * 0.5],
                             color="#2d3748", linewidth=0.8, zorder=3)

    def _draw_point_load(self, x, y, fx, fy, load_len):
        mag = np.hypot(fx, fy)
        if mag < 1e-12:
            return
        ux, uy = fx / mag, fy / mag
        # La flecha apunta HACIA el nodo (representa la carga aplicada)
        self.ax.annotate(
            "", xy=(x, y), xytext=(x - ux * load_len, y - uy * load_len),
            arrowprops=dict(arrowstyle="-|>", color="#dd6b20", lw=2.2,
                             mutation_scale=16), zorder=6)
        fx_disp = self.units.force_out(fx)
        fy_disp = self.units.force_out(fy)
        label = f"({fx_disp:.3g}, {fy_disp:.3g}) {self.units.force_symbol}"
        self.ax.annotate(label, (x - ux * load_len, y - uy * load_len),
                          fontsize=7.5, color="#dd6b20", ha="center",
                          textcoords="offset points", xytext=(0, -10 if uy >= 0 else 10))

    def _draw_moment(self, x, y, mz, radius):
        theta = np.linspace(0.15 * np.pi, 1.7 * np.pi, 40)
        sign = 1 if mz > 0 else -1
        xs = x + radius * np.cos(theta) * sign
        ys = y + radius * np.sin(theta)
        self.ax.plot(xs, ys, color="#805ad5", linewidth=1.8, zorder=6)
        # Punta de flecha al final del arco
        self.ax.annotate("", xy=(xs[-1], ys[-1]), xytext=(xs[-3], ys[-3]),
                          arrowprops=dict(arrowstyle="-|>", color="#805ad5",
                                          lw=1.8, mutation_scale=12), zorder=6)

    def _draw_distributed_load(self, ni, nj, w1, w2, span):
        n_arrows = 7
        dx, dy = nj["x"] - ni["x"], nj["y"] - ni["y"]
        L = np.hypot(dx, dy)
        if L < 1e-9:
            return
        c, s = dx / L, dy / L
        # normal local (+y): rotacion +90 grados de (c, s)
        nx, ny = -s, c
        max_w = max(abs(w1), abs(w2), 1e-9)
        h_ref = span * 0.10

        pts = np.linspace(0, 1, n_arrows)
        xs_line, ys_line = [], []
        for t in pts:
            w_local = w1 + (w2 - w1) * t
            h = (w_local / max_w) * h_ref
            bx = ni["x"] + dx * t
            by = ni["y"] + dy * t
            tipx = bx + nx * h
            tipy = by + ny * h
            self.ax.annotate("", xy=(bx, by), xytext=(tipx, tipy),
                              arrowprops=dict(arrowstyle="-|>", color="#38a169",
                                              lw=1.3, mutation_scale=10), zorder=3)
            xs_line.append(tipx)
            ys_line.append(tipy)
        self.ax.plot(xs_line, ys_line, color="#38a169", linewidth=1.0,
                     linestyle="--", alpha=0.8, zorder=3)

    # ------------------------------------------------------------------ #
    # Diagramas de esfuerzos internos (Porticos)
    # ------------------------------------------------------------------ #
    def draw_diagram(self, nodes: dict, elements: dict, elem_results: dict,
                      diagram: str, title: str):
        """
        diagram: 'N' | 'V' | 'M'
        """
        self.clear()
        span = self._bounds(nodes)
        scale_ref = span * 0.22

        # Estructura base (lineas grises tenues)
        for el in elements.values():
            ni, nj = nodes[el["ni"]], nodes[el["nj"]]
            self.ax.plot([ni["x"], nj["x"]], [ni["y"], nj["y"]],
                         color="#a0aec0", linewidth=1.6, zorder=1)

        # Determinar el maximo absoluto global para escalar todos los
        # diagramas de forma consistente.
        key_map = {"N": "N", "V": "V", "M": "M"}
        arr_key = key_map[diagram]
        global_max = 1e-9
        for eid, er in elem_results.items():
            vals = er.get(arr_key)
            if vals is not None:
                global_max = max(global_max, float(np.max(np.abs(vals))))

        color_map = {"N": "#c53030", "V": "#2b6cb0", "M": "#805ad5"}
        color = color_map[diagram]

        for eid, el in elements.items():
            er = elem_results.get(eid)
            if er is None:
                continue
            ni, nj = nodes[el["ni"]], nodes[el["nj"]]
            dx, dy = nj["x"] - ni["x"], nj["y"] - ni["y"]
            L = np.hypot(dx, dy)
            if L < 1e-9:
                continue
            c, s = dx / L, dy / L
            nx, ny = -s, c  # normal local +y

            vals = er.get(arr_key)
            x_local = er.get("x")
            if vals is None or x_local is None:
                continue

            scaled = (vals / global_max) * scale_ref if global_max > 1e-9 else vals * 0

            base_x = ni["x"] + c * x_local
            base_y = ni["y"] + s * x_local
            # Para el diagrama de Momento, por convencion de ingenieria
            # civil se dibuja del lado de la fibra en TRACCION (por eso
            # se invierte el signo al graficar, aunque el valor numerico
            # reportado en resultados mantiene la convencion fisica).
            draw_vals = -scaled if diagram == "M" else scaled
            top_x = base_x + nx * draw_vals
            top_y = base_y + ny * draw_vals

            poly_x = np.concatenate([base_x, top_x[::-1]])
            poly_y = np.concatenate([base_y, top_y[::-1]])
            self.ax.fill(poly_x, poly_y, color=color, alpha=0.30, zorder=2)
            self.ax.plot(top_x, top_y, color=color, linewidth=1.6, zorder=3)

            # Etiquetas en extremos y en el maximo absoluto del elemento
            i_max = int(np.argmax(np.abs(vals)))
            for idx, tag in ((0, None), (len(vals) - 1, None), (i_max, "max")):
                v_disp = vals[idx]
                self.ax.annotate(f"{v_disp:.3g}", (top_x[idx], top_y[idx]),
                                  fontsize=7, color=color, ha="center",
                                  fontweight="bold" if tag else "normal",
                                  bbox=dict(boxstyle="round,pad=0.1", fc="white",
                                            ec=color, lw=0.5, alpha=0.85), zorder=5)

        unit_lbl = {"N": self.units.force_symbol, "V": self.units.force_symbol,
                    "M": f"{self.units.force_symbol}\u00b7{self.units.length_symbol}"}
        self.ax.set_title(f"{title}  [{unit_lbl[diagram]}]", fontsize=11, fontweight="bold")
        self.ax.set_xlabel(f"X [{self.units.length_symbol}]")
        self.ax.set_ylabel(f"Y [{self.units.length_symbol}]")
        self._pad_view(nodes, span)


    # ------------------------------------------------------------------ #
    # Forma deformada y mapa Demanda/Capacidad (D/C)
    # ------------------------------------------------------------------ #
    @staticmethod
    def dc_color(dc):
        """Color segun D/C: <0.50 gris, 0.50-0.70 azul, 0.70-0.90 verde,
        0.90-1.00 amarillo/naranja y >1.00 rojo."""
        if dc is None:
            return "#718096"
        dc = float(dc)
        if dc < 0.50:
            return "#a0aec0"   # gris / azul claro
        if dc < 0.70:
            return "#3182ce"   # azul
        if dc < 0.90:
            return "#38a169"   # verde
        if dc <= 1.00:
            return "#ed8936"   # amarillo/naranja
        return "#e53e3e"       # rojo

    @staticmethod
    def dc_label(dc):
        if dc is None:
            return "D/C: N/D"
        return f"D/C: {float(dc):.3f}"

    def _deformed_points_truss(self, ni, nj, er, scale):
        ux_i = self.units.length_out(er.get("ux_i", 0.0))
        uy_i = self.units.length_out(er.get("uy_i", 0.0))
        ux_j = self.units.length_out(er.get("ux_j", 0.0))
        uy_j = self.units.length_out(er.get("uy_j", 0.0))
        return (ni["x"] + scale * ux_i, ni["y"] + scale * uy_i,
                nj["x"] + scale * ux_j, nj["y"] + scale * uy_j)

    def _deformed_points_frame(self, ni, nj, er, scale, n=25):
        """Curva deformada usando desplazamientos y rotaciones nodales.
        Se interpola el desplazamiento transversal con funciones de Hermite."""
        dx, dy = nj["x"] - ni["x"], nj["y"] - ni["y"]
        L = float(np.hypot(dx, dy))
        if L < 1e-12:
            return np.array([ni["x"]]), np.array([ni["y"]])
        c, ss = dx / L, dy / L
        ui = self.units.length_out(er.get("ux_i", 0.0))
        vi = self.units.length_out(er.get("uy_i", 0.0))
        uj = self.units.length_out(er.get("ux_j", 0.0))
        vj = self.units.length_out(er.get("uy_j", 0.0))
        # Transformacion global -> local.
        u_i = c * ui + ss * vi
        v_i = -ss * ui + c * vi
        u_j = c * uj + ss * vj
        v_j = -ss * uj + c * vj
        th_i = float(er.get("rz_i", 0.0))
        th_j = float(er.get("rz_j", 0.0))
        x = np.linspace(0.0, L, n)
        xi = x / L
        N1 = 1 - 3*xi**2 + 2*xi**3
        N2 = L * (xi - 2*xi**2 + xi**3)
        N3 = 3*xi**2 - 2*xi**3
        N4 = L * (-xi**2 + xi**3)
        u = (1-xi) * u_i + xi * u_j
        v = N1*v_i + N2*th_i + N3*v_j + N4*th_j
        xloc = x + scale*u
        yloc = scale*v
        X = ni["x"] + c*xloc - ss*yloc
        Y = ni["y"] + ss*xloc + c*yloc
        return X, Y

    def _draw_deformation_legend(self, dc_mode=False):
        if dc_mode:
            items = [
                ("< 0.50", self.dc_color(0.25), "Sobredimensionado / carga baja"),
                ("0.50–0.70", self.dc_color(0.60), "Conservador"),
                ("0.70–0.90", self.dc_color(0.80), "Optimo / economico"),
                ("0.90–1.00", self.dc_color(0.95), "Cerca del limite"),
                ("> 1.00", self.dc_color(1.10), "Falla / no cumple"),
            ]
            for i, (txt, color, desc) in enumerate(items):
                self.ax.plot([], [], color=color, linewidth=5, label=f"{txt}  —  {desc}")
            self.ax.legend(loc="upper right", fontsize=7.5, framealpha=0.92,
                           title="Demanda / Capacidad (D/C)", title_fontsize=8.5)
        else:
            self.ax.plot([], [], color="#a0aec0", linewidth=1.5, linestyle="--", label="Original")
            self.ax.plot([], [], color="#2b6cb0", linewidth=3, label="Deformada (escala visual)")
            self.ax.legend(loc="upper right", fontsize=8, framealpha=0.92)

    def draw_deformed_structure(self, nodes, elements, structure_type,
                                node_results, elem_results=None,
                                deformation_scale=1.0, color_by_dc=False,
                                title="Forma deformada"):
        """Dibuja estructura original tenue + forma deformada.
        deformation_scale es SOLO una amplificacion grafica; no modifica U."""
        self.clear()
        span = self._bounds(nodes)
        # Original como referencia.
        for el in elements.values():
            ni, nj = nodes[el["ni"]], nodes[el["nj"]]
            self.ax.plot([ni["x"], nj["x"]], [ni["y"], nj["y"]],
                         color="#cbd5e0", linewidth=1.5, linestyle="--", zorder=1)

        elem_results = elem_results or {}
        for eid, el in elements.items():
            ni, nj = nodes[el["ni"]], nodes[el["nj"]]
            eri = node_results.get(el["ni"], {})
            erj = node_results.get(el["nj"], {})
            er = dict(elem_results.get(eid, {}))
            er.update({"ux_i": eri.get("ux", 0.0), "uy_i": eri.get("uy", 0.0),
                       "ux_j": erj.get("ux", 0.0), "uy_j": erj.get("uy", 0.0),
                       "rz_i": eri.get("rz", eri.get("theta", 0.0)),
                       "rz_j": erj.get("rz", erj.get("theta", 0.0))})
            if structure_type == "frame":
                X, Y = self._deformed_points_frame(ni, nj, er, deformation_scale)
            else:
                X1, Y1, X2, Y2 = self._deformed_points_truss(ni, nj, er, deformation_scale)
                X, Y = np.array([X1, X2]), np.array([Y1, Y2])
            dc = er.get("DC")
            color = self.dc_color(dc) if color_by_dc else "#2b6cb0"
            lw = 4.0 if color_by_dc else 3.2
            self.ax.plot(X, Y, color=color, linewidth=lw, solid_capstyle="round", zorder=3)
            xm, ym = X[len(X)//2], Y[len(Y)//2]
            if color_by_dc:
                label = f"{eid}  D/C={dc:.3f}" if dc is not None else f"{eid}  D/C=N/D"
                self.ax.annotate(label, (xm, ym), fontsize=7.5, color=color,
                                 fontweight="bold", ha="center", va="bottom",
                                 bbox=dict(boxstyle="round,pad=0.18", fc="white",
                                           ec=color, lw=0.8, alpha=0.9), zorder=6)
            else:
                self.ax.annotate(str(eid), (xm, ym), fontsize=8, color=color,
                                 fontweight="bold", ha="center", va="bottom",
                                 bbox=dict(boxstyle="round,pad=0.15", fc="white",
                                           ec=color, lw=0.7, alpha=0.85), zorder=6)

        # Nodos deformados.
        for nid, nr in node_results.items():
            n = nodes[nid]
            ux = self.units.length_out(nr.get("ux", 0.0))
            uy = self.units.length_out(nr.get("uy", 0.0))
            xd, yd = n["x"] + deformation_scale*ux, n["y"] + deformation_scale*uy
            self.ax.plot(xd, yd, "o", color="#1a202c", markersize=5.5, zorder=5)
            self.ax.annotate(str(nid), (xd, yd), textcoords="offset points", xytext=(7, 7),
                             fontsize=8, fontweight="bold", color="#1a202c", zorder=6)

        self.ax.set_title(f"{title}  |  Amplificacion visual ×{deformation_scale:g}",
                          fontsize=11, fontweight="bold")
        self.ax.set_xlabel(f"X [{self.units.length_symbol}]")
        self.ax.set_ylabel(f"Y [{self.units.length_symbol}]")
        self._pad_view_deformed(nodes, node_results, span, deformation_scale)
        self._draw_deformation_legend(color_by_dc)

    def _pad_view_deformed(self, nodes, node_results, span, scale):
        xs = [n["x"] for n in nodes.values()]
        ys = [n["y"] for n in nodes.values()]
        for nid, nr in node_results.items():
            if nid not in nodes:
                continue
            xs.append(nodes[nid]["x"] + scale*self.units.length_out(nr.get("ux", 0.0)))
            ys.append(nodes[nid]["y"] + scale*self.units.length_out(nr.get("uy", 0.0)))
        pad = span * 0.35 + 1e-6
        self.ax.set_xlim(min(xs)-pad, max(xs)+pad)
        self.ax.set_ylim(min(ys)-pad, max(ys)+pad)


def plt_circle(cx, cy, r, n=20):
    theta = np.linspace(0, 2 * np.pi, n)
    return cx + r * np.cos(theta), cy + r * np.sin(theta)
