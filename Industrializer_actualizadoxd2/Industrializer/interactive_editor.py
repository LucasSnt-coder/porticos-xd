# -*- coding: utf-8 -*-
"""Editor visual interactivo tipo CAD para Industrializer.

Se mantiene separado del solver existente: reutiliza self.nodes, self.elements,
self.units, _redraw(), _on_calculate() y _invalidate_after_model_change().
"""
from __future__ import annotations

import math
import customtkinter as ctk
from tkinter import messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

try:
    from frame_renderer_enhanced import EnhancedStructureRenderer
except Exception:
    EnhancedStructureRenderer = None


_GRID = 1.0


def install(app_class):
    """Instala el nuevo editor en MainStructuralApp/IndustrializerApp."""
    app_class._build_editor_tab = _build_editor_tab
    app_class._ie_set_mode = _set_mode
    app_class._ie_canvas_click = _canvas_click
    app_class._ie_show_properties = _show_properties
    app_class._ie_save_node = _save_node
    app_class._ie_save_element = _save_element
    app_class._ie_delete_node = _delete_node
    app_class._ie_delete_element = _delete_element
    app_class._ie_save_profile = _save_profile
    app_class._ie_refresh = _refresh_editor
    app_class._ie_clear_all = _clear_all


def _unit_text(self):
    u = self.units
    return f"F: {u.force_symbol}   ·   L: {u.length_symbol}   ·   E/fy: {u.stress_symbol}"


def _build_editor_tab(self):
    """Construye un editor CAD compacto con barra superior + propiedades."""
    self._ie_mode = "select"
    self._ie_selected_node = None
    self._ie_selected_element = None
    self._ie_pending_node = None
    self._ie_profile_A = 0.01
    self._ie_profile_I = 0.0001

    self.tab_editor.grid_columnconfigure(0, weight=0, minsize=300)
    self.tab_editor.grid_columnconfigure(1, weight=1)
    self.tab_editor.grid_rowconfigure(1, weight=1)

    # Barra superior, estilo CAD.
    top = ctk.CTkFrame(self.tab_editor, corner_radius=8)
    top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 6))
    buttons = [
        ("Añadir nodo", "add_node"), ("Añadir elemento", "add_element"),
        ("Editar nodo", "edit_node"), ("Editar elemento", "edit_element"),
        ("Eliminar nodo", "delete_node"), ("Eliminar elemento", "delete_element"),
        ("Perfiles", "profiles"), ("Calcular", "calculate"), ("Borrar todo", "clear"),
    ]
    self._ie_toolbar = {}
    for text, mode in buttons:
        color = "#2f855a" if mode == "calculate" else ("#c53030" if mode == "clear" else None)
        kwargs = {"text": text, "height": 34, "command": lambda m=mode: self._ie_set_mode(m)}
        if color:
            kwargs.update(fg_color=color, hover_color="#276749" if mode == "calculate" else "#9b2c2c")
        b = ctk.CTkButton(top, **kwargs)
        b.pack(side="left", padx=2, pady=5)
        self._ie_toolbar[mode] = b

    # Panel contextual.
    left = ctk.CTkScrollableFrame(self.tab_editor, width=285, label_text="Propiedades")
    left.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
    left.grid_columnconfigure(0, weight=1)
    self._ie_left = left

    self._ie_title = ctk.CTkLabel(left, text="Selecciona una herramienta", font=ctk.CTkFont(size=16, weight="bold"))
    self._ie_title.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 3))
    self._ie_hint = ctk.CTkLabel(left, text="Los campos cambian según la acción.", text_color="gray65", justify="left", wraplength=260)
    self._ie_hint.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 10))
    self._ie_form = ctk.CTkFrame(left, fg_color="transparent")
    self._ie_form.grid(row=2, column=0, sticky="ew", padx=6)
    self._ie_form.grid_columnconfigure(1, weight=1)
    self._ie_status = ctk.CTkLabel(left, text="", text_color="gray65", justify="left", wraplength=260)
    self._ie_status.grid(row=3, column=0, sticky="w", padx=10, pady=10)

    # Hoja de dibujo.
    right = ctk.CTkFrame(self.tab_editor)
    right.grid(row=1, column=1, sticky="nsew")
    right.grid_rowconfigure(1, weight=1)
    right.grid_columnconfigure(0, weight=1)
    viewbar = ctk.CTkFrame(right, fg_color="transparent")
    viewbar.grid(row=0, column=0, sticky="ew", padx=6, pady=5)
    self.fs_label = ctk.CTkLabel(viewbar, text="FS sistema: --", font=ctk.CTkFont(weight="bold"))
    self.fs_label.pack(side="right", padx=8)
    ctk.CTkButton(viewbar, text="Ajustar Vista", width=110, fg_color="gray40", hover_color="gray30", command=self._fit_view).pack(side="left", padx=2)
    ctk.CTkButton(viewbar, text="Estructura", width=95, command=lambda: self._set_diagram_view("structure")).pack(side="left", padx=2)
    ctk.CTkButton(viewbar, text="Deformada", width=95, command=lambda: self._set_diagram_view("deformed")).pack(side="left", padx=2)
    ctk.CTkButton(viewbar, text="D/C", width=70, command=lambda: self._set_diagram_view("DC")).pack(side="left", padx=2)
    ctk.CTkButton(viewbar, text="Axial (N)", width=90, command=lambda: self._set_diagram_view("N")).pack(side="left", padx=2)
    if self.structure_type == "frame":
        ctk.CTkButton(viewbar, text="Cortante (V)", width=100, command=lambda: self._set_diagram_view("V")).pack(side="left", padx=2)
        ctk.CTkButton(viewbar, text="Momento (M)", width=100, command=lambda: self._set_diagram_view("M")).pack(side="left", padx=2)

    canvas_frame = ctk.CTkFrame(right, fg_color="white")
    canvas_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 5))
    self.fig = Figure(figsize=(8, 6), dpi=100)
    self.ax = self.fig.add_subplot(111)
    self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_frame)
    self.canvas.get_tk_widget().pack(fill="both", expand=True)
    if EnhancedStructureRenderer is not None:
        try:
            self.renderer = EnhancedStructureRenderer(self.ax, self.units)
        except Exception:
            pass
    self.canvas.mpl_connect("button_press_event", lambda e: self._ie_canvas_click(e))
    self._setup_canvas_navigation()
    self._ie_show_properties("select")
    self._redraw()


def _set_mode(self, mode):
    if mode == "calculate":
        self._on_calculate()
        return
    if mode == "clear":
        self._ie_clear_all()
        return
    self._ie_mode = mode
    self._ie_pending_node = None
    self._ie_selected_node = None
    self._ie_selected_element = None
    self._ie_show_properties(mode)
    if hasattr(self, "canvas"):
        self.canvas.draw_idle()


def _clear_form(self):
    for child in self._ie_form.winfo_children():
        child.destroy()


def _entry(self, row, label, key, default="", unit=""):
    ctk.CTkLabel(self._ie_form, text=label, anchor="w").grid(row=row, column=0, sticky="w", padx=4, pady=4)
    holder = ctk.CTkFrame(self._ie_form, fg_color="transparent")
    holder.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
    holder.grid_columnconfigure(0, weight=1)
    e = ctk.CTkEntry(holder)
    e.insert(0, str(default))
    e.grid(row=0, column=0, sticky="ew")
    if unit:
        ctk.CTkLabel(holder, text=unit, width=45, text_color="gray60").grid(row=0, column=1, padx=(4, 0))
    return e


def _button(self, row, text, command, color=None):
    kw = {"text": text, "command": command, "height": 34}
    if color:
        kw.update(fg_color=color, hover_color="#9b2c2c")
    ctk.CTkButton(self._ie_form, **kw).grid(row=row, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 4))


def _combo(self, row, label, values, default):
    ctk.CTkLabel(self._ie_form, text=label, anchor="w").grid(row=row, column=0, sticky="w", padx=4, pady=4)
    v = ctk.StringVar(value=default)
    m = ctk.CTkOptionMenu(self._ie_form, values=values, variable=v)
    m.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
    return m


def _show_properties(self, mode):
    _clear_form(self)
    self._ie_title.configure(text={
        "add_node": "Añadir nodo", "add_element": "Añadir elemento",
        "edit_node": "Editar nodo", "edit_element": "Editar elemento",
        "delete_node": "Eliminar nodo", "delete_element": "Eliminar elemento",
        "profiles": "Perfiles", "select": "Propiedades"
    }.get(mode, "Propiedades"))
    self._ie_hint.configure(text=f"Unidades: {_unit_text(self)}")
    self._ie_status.configure(text="")

    if mode in ("add_node", "edit_node", "delete_node"):
        if mode == "add_node":
            self._ie_status.configure(text="Haz clic sobre una intersección de la rejilla para crear el nodo.")
            return
        nid = self._ie_selected_node
        if not nid or nid not in self.nodes:
            self._ie_status.configure(text="Selecciona un nodo en la hoja.")
            return
        n = self.nodes[nid]
        self._ie_node_fields = {}
        r = 0
        self._ie_node_fields["id"] = _entry(self, r, "ID", "id", nid); r += 1
        self._ie_node_fields["x"] = _entry(self, r, "X", "x", n.get("x", 0)); r += 1
        self._ie_node_fields["y"] = _entry(self, r, "Y", "y", n.get("y", 0)); r += 1
        types = ["Libre", "Articulado", "Rodillo", "Empotrado"]
        current = "Empotrado" if (n.get("rx") and n.get("ry") and (n.get("rz") if self.structure_type == "frame" else True)) else ("Articulado" if n.get("rx") and n.get("ry") else ("Rodillo" if n.get("ry") else "Libre"))
        self._ie_support = _combo(self, r, "Apoyo", types, current); r += 1
        self._ie_node_fields["fx"] = _entry(self, r, "Fx", "fx", n.get("fx", 0), self.units.force_symbol); r += 1
        self._ie_node_fields["fy"] = _entry(self, r, "Fy", "fy", n.get("fy", 0), self.units.force_symbol); r += 1
        if self.structure_type == "frame":
            self._ie_node_fields["mz"] = _entry(self, r, "Mz", "mz", n.get("mz", 0), f"{self.units.force_symbol}·{self.units.length_symbol}"); r += 1
        _button(self, r, "Guardar nodo", self._ie_save_node); r += 1
        _button(self, r, "Eliminar nodo", self._ie_delete_node, "#c53030")
        return

    if mode in ("add_element", "edit_element", "delete_element"):
        if mode == "add_element":
            self._ie_status.configure(text="Selecciona primero el nodo i y luego el nodo j.")
            ctk.CTkLabel(self._ie_form, text="Nodo i / j: se seleccionan directamente en el dibujo.", text_color="gray65", wraplength=260).grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=5)
            self._ie_elem_fields = {}
            r = 1
            self._ie_elem_fields["id"] = _entry(self, r, "ID", "id", f"E{getattr(self, '_elem_counter', 1)}"); r += 1
            self._ie_elem_fields["A"] = _entry(self, r, "Área A", "A", self._ie_profile_A, f"{self.units.length_symbol}²"); r += 1
            self._ie_elem_fields["E"] = _entry(self, r, "Módulo E", "E", 200000 if self.units.key != "SI" else 200e9, self.units.stress_symbol); r += 1
            self._ie_elem_fields["fy"] = _entry(self, r, "fy", "fy", 250 if self.units.key != "SI" else 250e6, self.units.stress_symbol); r += 1
            if self.structure_type == "frame":
                self._ie_elem_fields["I"] = _entry(self, r, "Inercia I", "I", self._ie_profile_I, f"{self.units.length_symbol}⁴"); r += 1
                self._ie_elem_fields["w1"] = _entry(self, r, "w (i)", "w1", 0, f"{self.units.force_symbol}/{self.units.length_symbol}"); r += 1
                self._ie_elem_fields["w2"] = _entry(self, r, "w (j)", "w2", 0, f"{self.units.force_symbol}/{self.units.length_symbol}"); r += 1
            self._ie_elem_status_row = r
            ctk.CTkLabel(self._ie_form, text="Selección: — → —", text_color="gray60").grid(row=r, column=0, columnspan=2, sticky="w", padx=4, pady=5)
            _button(self, r + 1, "Crear elemento", self._ie_save_element)
            return
        eid = self._ie_selected_element
        if not eid or eid not in self.elements:
            self._ie_status.configure(text="Selecciona un elemento en la hoja.")
            return
        el = self.elements[eid]
        self._ie_elem_fields = {}
        r = 0
        self._ie_elem_fields["id"] = _entry(self, r, "ID", "id", eid); r += 1
        ctk.CTkLabel(self._ie_form, text=f"Nodos: {el['ni']} → {el['nj']}", text_color="gray65").grid(row=r, column=0, columnspan=2, sticky="w", padx=4, pady=4); r += 1
        self._ie_elem_fields["A"] = _entry(self, r, "Área A", "A", el.get("A", 0), f"{self.units.length_symbol}²"); r += 1
        self._ie_elem_fields["E"] = _entry(self, r, "Módulo E", "E", el.get("E", 0), self.units.stress_symbol); r += 1
        self._ie_elem_fields["fy"] = _entry(self, r, "fy", "fy", el.get("fy", 0), self.units.stress_symbol); r += 1
        if self.structure_type == "frame":
            self._ie_elem_fields["I"] = _entry(self, r, "Inercia I", "I", el.get("I", 0), f"{self.units.length_symbol}⁴"); r += 1
            self._ie_elem_fields["w1"] = _entry(self, r, "w (i)", "w1", el.get("w1", 0), f"{self.units.force_symbol}/{self.units.length_symbol}"); r += 1
            self._ie_elem_fields["w2"] = _entry(self, r, "w (j)", "w2", el.get("w2", 0), f"{self.units.force_symbol}/{self.units.length_symbol}"); r += 1
        _button(self, r, "Guardar elemento", self._ie_save_element); r += 1
        _button(self, r, "Eliminar elemento", self._ie_delete_element, "#c53030")
        return

    if mode == "profiles":
        self._ie_status.configure(text="Por ahora el perfil se define únicamente con A e I. Se usarán como valores por defecto al crear elementos.")
        self._ie_profile_A_field = _entry(self, 0, "Área A", "A", self._ie_profile_A, f"{self.units.length_symbol}²")
        self._ie_profile_I_field = _entry(self, 1, "Inercia I", "I", self._ie_profile_I, f"{self.units.length_symbol}⁴")
        _button(self, 2, "Guardar perfil por defecto", self._ie_save_profile)


def _float(entry, name):
    try:
        return float(entry.get().strip().replace(",", "."))
    except Exception:
        raise ValueError(f"{name} debe ser numérico.")


def _support_values(kind, frame):
    return {
        "Libre": (False, False, False),
        "Rodillo": (False, True, False),
        "Articulado": (True, True, False),
        "Empotrado": (True, True, bool(frame)),
    }[kind]


def _save_node(self):
    try:
        old = self._ie_selected_node
        f = self._ie_node_fields
        nid = f["id"].get().strip()
        if not nid:
            raise ValueError("El ID del nodo no puede estar vacío.")
        if old and nid != old and nid in self.nodes:
            raise ValueError(f"Ya existe el nodo {nid}.")
        data = dict(x=_float(f["x"], "X"), y=_float(f["y"], "Y"),
                    fx=_float(f["fx"], "Fx"), fy=_float(f["fy"], "Fy"), mz=_float(f["mz"], "Mz") if "mz" in f else 0.0)
        data["rx"], data["ry"], data["rz"] = _support_values(self._ie_support.get(), self.structure_type == "frame")
        if old:
            self.nodes.pop(old)
            for el in self.elements.values():
                if el["ni"] == old: el["ni"] = nid
                if el["nj"] == old: el["nj"] = nid
        self.nodes[nid] = data
        self._ie_selected_node = nid
        self._invalidate_after_model_change()
        self._refresh_editor()
        self._redraw()
        self._ie_status.configure(text=f"Nodo {nid} guardado.")
    except Exception as exc:
        messagebox.showerror("Nodo", str(exc))


def _save_element(self):
    try:
        f = self._ie_elem_fields
        eid = f["id"].get().strip()
        if not eid: raise ValueError("El ID del elemento no puede estar vacío.")
        old = self._ie_selected_element if self._ie_mode == "edit_element" else None
        if old and eid != old and eid in self.elements: raise ValueError(f"Ya existe el elemento {eid}.")
        if self._ie_mode == "add_element":
            ni, nj = self._ie_pending_pair
            if ni == nj: raise ValueError("Los nodos i y j deben ser distintos.")
        else:
            ni, nj = self.elements[old]["ni"], self.elements[old]["nj"]
        A, E, fy = _float(f["A"], "Área A"), _float(f["E"], "E"), _float(f["fy"], "fy")
        if A <= 0 or E <= 0: raise ValueError("Área A y E deben ser mayores que cero.")
        d = dict(ni=ni, nj=nj, A=A, E=E, fy=fy)
        if self.structure_type == "frame":
            I = _float(f["I"], "Inercia I")
            if I <= 0: raise ValueError("La inercia I debe ser mayor que cero.")
            d.update(I=I, w1=_float(f["w1"], "w(i)"), w2=_float(f["w2"], "w(j)"))
        if old: self.elements.pop(old)
        self.elements[eid] = d
        self._ie_selected_element = eid
        self._ie_pending_node = None
        self._invalidate_after_model_change()
        self._refresh_editor()
        self._redraw()
        self._ie_status.configure(text=f"Elemento {eid} guardado.")
    except Exception as exc:
        messagebox.showerror("Elemento", str(exc))


def _delete_node(self):
    nid = self._ie_selected_node
    if not nid or nid not in self.nodes:
        self._ie_status.configure(text="Selecciona un nodo para eliminar."); return
    connected = [eid for eid, el in self.elements.items() if el["ni"] == nid or el["nj"] == nid]
    for eid in connected: self.elements.pop(eid, None)
    self.nodes.pop(nid, None)
    self._ie_selected_node = None
    self._invalidate_after_model_change(); self._refresh_editor(); self._redraw()


def _delete_element(self):
    eid = self._ie_selected_element
    if not eid or eid not in self.elements:
        self._ie_status.configure(text="Selecciona un elemento para eliminar."); return
    self.elements.pop(eid, None)
    self._ie_selected_element = None
    self._invalidate_after_model_change(); self._refresh_editor(); self._redraw()


def _save_profile(self):
    try:
        A = _float(self._ie_profile_A_field, "Área A")
        I = _float(self._ie_profile_I_field, "Inercia I")
        if A <= 0 or I <= 0: raise ValueError("A e I deben ser mayores que cero.")
        self._ie_profile_A, self._ie_profile_I = A, I
        self._ie_status.configure(text="Perfil guardado como predeterminado para nuevos elementos.")
    except Exception as exc:
        messagebox.showerror("Perfil", str(exc))


def _canvas_click(self, event):
    if event.inaxes is not self.ax or event.xdata is None or event.ydata is None:
        return
    x, y = round(event.xdata / _GRID) * _GRID, round(event.ydata / _GRID) * _GRID
    mode = self._ie_mode
    if mode == "add_node":
        # No crear dos nodos en la misma intersección.
        for nid, n in self.nodes.items():
            if math.hypot(n["x"] - x, n["y"] - y) < 1e-9:
                self._ie_status.configure(text=f"Ya existe {nid} en ({x:g}, {y:g}).")
                return
        nid = f"N{getattr(self, '_node_counter', 1)}"
        while nid in self.nodes:
            self._node_counter += 1; nid = f"N{self._node_counter}"
        self.nodes[nid] = dict(x=x, y=y, rx=False, ry=False, rz=False, fx=0.0, fy=0.0, mz=0.0)
        self._node_counter += 1
        self._ie_selected_node = nid
        self._invalidate_after_model_change(); self._redraw()
        self._ie_mode = "edit_node"; self._ie_show_properties("edit_node")
        self._ie_status.configure(text=f"Nodo {nid} creado en la intersección ({x:g}, {y:g}).")
        return
    if mode == "add_element":
        nid = _nearest_node(self, x, y)
        if not nid:
            self._ie_status.configure(text="Haz clic sobre un nodo existente."); return
        if self._ie_pending_node is None:
            self._ie_pending_node = nid
            self._ie_status.configure(text=f"Nodo i = {nid}. Ahora selecciona el nodo j.")
        else:
            if nid == self._ie_pending_node:
                self._ie_status.configure(text="El nodo j debe ser diferente de i."); return
            self._ie_pending_pair = (self._ie_pending_node, nid)
            self._ie_status.configure(text=f"Elemento: {self._ie_pending_pair[0]} → {nid}. Completa propiedades y pulsa Crear elemento.")
        return
    nid = _nearest_node(self, x, y)
    if mode == "edit_node" and nid:
        self._ie_selected_node = nid; self._ie_show_properties("edit_node"); return
    if mode == "delete_node" and nid:
        self._ie_selected_node = nid; self._ie_delete_node(); return
    eid = _nearest_element(self, x, y)
    if mode == "edit_element" and eid:
        self._ie_selected_element = eid; self._ie_show_properties("edit_element"); return
    if mode == "delete_element" and eid:
        self._ie_selected_element = eid; self._ie_delete_element(); return
    if mode == "select":
        if nid:
            self._ie_selected_node = nid; self._ie_show_properties("edit_node")
        elif eid:
            self._ie_selected_element = eid; self._ie_show_properties("edit_element")


def _nearest_node(self, x, y):
    if not self.nodes: return None
    nid, dist = min(((k, math.hypot(v["x"]-x, v["y"]-y)) for k,v in self.nodes.items()), key=lambda z:z[1])
    return nid if dist <= max(_GRID * 0.45, 0.2) else None


def _nearest_element(self, x, y):
    best, best_d = None, float("inf")
    for eid, el in self.elements.items():
        a, b = self.nodes.get(el["ni"]), self.nodes.get(el["nj"])
        if not a or not b: continue
        vx, vy = b["x"]-a["x"], b["y"]-a["y"]
        den = vx*vx + vy*vy
        t = 0 if den == 0 else max(0, min(1, ((x-a["x"])*vx+(y-a["y"])*vy)/den))
        px, py = a["x"]+t*vx, a["y"]+t*vy
        d = math.hypot(x-px, y-py)
        if d < best_d: best, best_d = eid, d
    return best if best_d <= max(_GRID*0.35, 0.15) else None


def _refresh_editor(self):
    if hasattr(self, "_ie_status"):
        count = f"Nodos: {len(self.nodes)}   Elementos: {len(self.elements)}"
        self._ie_status.configure(text=count)


def _clear_all(self):
    if not self.nodes and not self.elements:
        self._redraw(); return
    if not messagebox.askyesno("Borrar todo", "¿Eliminar todos los nodos y elementos del modelo?"):
        return
    self.nodes.clear(); self.elements.clear()
    self._node_counter = 1; self._elem_counter = 1
    self._ie_selected_node = self._ie_selected_element = self._ie_pending_node = None
    self._invalidate_after_model_change(); self._redraw(); self._ie_show_properties("select")

