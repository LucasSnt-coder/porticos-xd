# -*- coding: utf-8 -*-
"""
app_interface.py
------------------
Interfaz grafica principal (CustomTkinter) del software de analisis de
estructuras 2D. Contiene la clase MainStructuralApp, que orquesta:
    - El dialogo inicial de configuracion (tipo de estructura + unidades)
    - La pestaña "Editor Visual" (entrada de datos + lienzo grafico)
    - La pestaña "Resultados" (reporte numerico detallado)
    - La pestaña "Procedimiento" (ecuaciones del metodo matricial)
    - La pestaña "Previsualizacion PDF" (memoria de calculo + demo PRO)

Este modulo NO contiene logica de calculo estructural (ver
frame_solver.py / truss_solver.py) ni logica de dibujo de bajo nivel
(ver frame_renderer.py); su responsabilidad es la orquestacion de la UI
y la comunicacion entre el usuario, el motor de calculo y el motor
grafico.
"""

from __future__ import annotations
import traceback
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from units import get_unit_system, UNIT_SYSTEMS
from truss_solver import TrussSolver2D, TrussSolverError
from frame_solver import FrameSolver2D, FrameSolverError
from frame_renderer import StructureRenderer


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

APP_TITLE = "AnalisisEstructural2D - Portico y Armadura (Metodo de Rigidez)"


# ========================================================================
# DIALOGO INICIAL: Tipo de estructura + Sistema de unidades
# ========================================================================
class StartupDialog(ctk.CTkToplevel):
    def __init__(self, master, on_confirm):
        super().__init__(master)
        self.title("Configuracion Inicial")
        self.geometry("460x360")
        self.resizable(False, False)
        self.on_confirm = on_confirm
        self.result = None

        # Manejo seguro de destruccion / grab
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        ctk.CTkLabel(self, text="Nuevo Proyecto Estructural",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(22, 6))
        ctk.CTkLabel(self, text="Seleccione el tipo de estructura y el sistema de unidades",
                     font=ctk.CTkFont(size=12), text_color="gray70").pack(pady=(0, 18))

        ctk.CTkLabel(self, text="Tipo de Estructura:", anchor="w").pack(
            fill="x", padx=40)
        self.structure_var = ctk.StringVar(value="frame")
        frame_radio_box = ctk.CTkFrame(self, fg_color="transparent")
        frame_radio_box.pack(fill="x", padx=40, pady=(4, 16))
        ctk.CTkRadioButton(frame_radio_box, text="Portico 2D (Frame)",
                            variable=self.structure_var, value="frame").pack(
            anchor="w", pady=3)
        ctk.CTkRadioButton(frame_radio_box, text="Armadura 2D (Truss)",
                            variable=self.structure_var, value="truss").pack(
            anchor="w", pady=3)

        ctk.CTkLabel(self, text="Sistema de Unidades:", anchor="w").pack(
            fill="x", padx=40)
        self.units_var = ctk.StringVar(value="SI_TECH")
        self.units_menu = ctk.CTkOptionMenu(
            self, variable=self.units_var,
            values=[UNIT_SYSTEMS[k].label for k in UNIT_SYSTEMS])
        self.units_menu.set(UNIT_SYSTEMS["SI_TECH"].label)
        self.units_menu.pack(fill="x", padx=40, pady=(4, 24))

        ctk.CTkButton(self, text="Comenzar", height=40,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._confirm).pack(fill="x", padx=40)

        self.after(50, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except Exception:
            pass

    def _label_to_key(self, label):
        for k, v in UNIT_SYSTEMS.items():
            if v.label == label:
                return k
        return "SI_TECH"

    def _confirm(self):
        structure_type = self.structure_var.get()
        unit_key = self._label_to_key(self.units_menu.get())
        self.result = (structure_type, unit_key)
        self._safe_destroy()
        self.on_confirm(structure_type, unit_key)

    def _on_close(self):
        # Si el usuario cierra sin elegir, se asumen valores por defecto
        self._confirm()

    def _safe_destroy(self):
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


# ========================================================================
# DIALOGO DEMO: "Membresia PRO" (funcion interactiva de demostracion)
# ========================================================================
class ProUpsellDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("AnalisisEstructural2D PRO")
        self.geometry("420x300")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._safe_destroy)

        ctk.CTkLabel(self, text="\U0001F512  Exportacion a PDF",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(24, 8))
        ctk.CTkLabel(
            self,
            text=("La generacion de la Memoria de Calculo en formato PDF\n"
                  "con sello profesional, portada personalizada y anexos\n"
                  "graficos es una funcion de la version PRO.\n\n"
                  "Esta ventana es una demostracion interactiva: en una\n"
                  "version comercial aqui se gestionaria la suscripcion."),
            justify="center", text_color="gray80").pack(pady=6, padx=20)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=20)
        ctk.CTkButton(btn_row, text="Suscribirse a PRO", fg_color="#d69e2e",
                      hover_color="#b7791f",
                      command=self._safe_destroy).grid(row=0, column=0, padx=6)
        ctk.CTkButton(btn_row, text="Cerrar", fg_color="gray40",
                      command=self._safe_destroy).grid(row=0, column=1, padx=6)

        self.after(50, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except Exception:
            pass

    def _safe_destroy(self):
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


# ========================================================================
# APLICACION PRINCIPAL
# ========================================================================
class MainStructuralApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1360x820")
        self.minsize(1100, 680)

        self.structure_type = "frame"   # 'frame' | 'truss'
        self.units = get_unit_system("SI_TECH")

        self.nodes = {}       # id -> dict de datos EN UNIDADES DE PANTALLA
        self.elements = {}    # id -> dict de datos EN UNIDADES DE PANTALLA
        self.last_results = None
        self.current_diagram = "structure"  # structure|deformed|DC|N|V|M
        self.deformation_scale = 50.0

        # Estado de navegacion (zoom/pan tipo AutoCAD) del lienzo del
        # Editor Visual. Cuando es True, _redraw() conserva el
        # encuadre (xlim/ylim) actual en vez de reajustarlo automaticamente.
        self._manual_view_active = False
        self._pan_active = False
        self._pan_last = None

        self._node_counter = 1
        self._elem_counter = 1

        # Ocultar la ventana principal hasta configurar el proyecto
        self.withdraw()
        self.after(80, self._show_startup_dialog)

    # ------------------------------------------------------------------ #
    def _show_startup_dialog(self):
        self.startup_dialog = StartupDialog(self, on_confirm=self._on_startup_confirm)

    def _on_startup_confirm(self, structure_type, unit_key):
        self.structure_type = structure_type
        self.units = get_unit_system(unit_key)
        self._build_ui()
        self.deiconify()

    # ------------------------------------------------------------------ #
    # CONSTRUCCION DE LA INTERFAZ
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_editor = self.tabview.add("Editor Visual")
        self.tab_results = self.tabview.add("Resultados")
        self.tab_procedure = self.tabview.add("Procedimiento")
        self.tab_pdf = self.tabview.add("Previsualizacion PDF")

        self._build_editor_tab()
        self._build_results_tab()
        self._build_procedure_tab()
        self._build_pdf_tab()

    # ---------------------------------------------------------------- #
    # PESTAÑA 1: EDITOR VISUAL
    # ---------------------------------------------------------------- #
    def _build_editor_tab(self):
        self.tab_editor.grid_columnconfigure(0, weight=0, minsize=390)
        self.tab_editor.grid_columnconfigure(1, weight=1)
        self.tab_editor.grid_rowconfigure(0, weight=1)

        # --------- Panel izquierdo (scrollable) ---------
        left = ctk.CTkScrollableFrame(self.tab_editor, label_text="Datos de Entrada")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        left.grid_columnconfigure(0, weight=1)

        unit_lbl = ctk.CTkLabel(
            left, text=f"Unidades: F[{self.units.force_symbol}]  "
                       f"L[{self.units.length_symbol}]  "
                       f"E,fy[{self.units.stress_symbol}]",
            font=ctk.CTkFont(size=11), text_color="gray60")
        unit_lbl.grid(row=0, column=0, sticky="ew", padx=8, pady=(0, 8))

        # ---- Sub-seccion Nodos ----
        ctk.CTkLabel(left, text="NODOS", font=ctk.CTkFont(weight="bold")).grid(
            row=1, column=0, sticky="w", padx=8, pady=(4, 2))
        self.node_form = {}
        node_grid = ctk.CTkFrame(left, fg_color="transparent")
        node_grid.grid(row=2, column=0, sticky="ew", padx=5, pady=2)
        node_grid.grid_columnconfigure(1, weight=1)

        self._add_labeled_entry(node_grid, "ID:", "id", row=0,
                                default=f"N{self._node_counter}", form=self.node_form)
        self._add_labeled_entry(node_grid, "X:", "x", row=1,
                                default="0", form=self.node_form)
        self._add_labeled_entry(node_grid, "Y:", "y", row=2,
                                default="0", form=self.node_form)

        restr_frame = ctk.CTkFrame(left, fg_color="transparent")
        restr_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(4, 2))
        restr_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(restr_frame, text="Restricciones:", width=92, anchor="w").grid(
            row=0, column=0, sticky="nw", padx=5, pady=3)
        restr_options = ctk.CTkFrame(restr_frame, fg_color="transparent")
        restr_options.grid(row=0, column=1, sticky="ew", padx=5, pady=3)
        restr_options.grid_columnconfigure(0, weight=1)
        self.node_form["rx"] = ctk.CTkCheckBox(restr_options, text="Tx", width=20)
        self.node_form["rx"].grid(row=0, column=0, sticky="w", padx=3, pady=2)
        self.node_form["ry"] = ctk.CTkCheckBox(restr_options, text="Ty", width=20)
        self.node_form["ry"].grid(row=1, column=0, sticky="w", padx=3, pady=2)
        if self.structure_type == "frame":
            self.node_form["rz"] = ctk.CTkCheckBox(restr_options, text="Rz", width=20)
            self.node_form["rz"].grid(row=2, column=0, sticky="w", padx=3, pady=2)

        load_grid = ctk.CTkFrame(left, fg_color="transparent")
        load_grid.grid(row=4, column=0, sticky="ew", padx=5, pady=(4, 2))
        load_grid.grid_columnconfigure(1, weight=1)
        self._add_labeled_entry(load_grid, "Fx:", "fx", row=0,
                                default="0", form=self.node_form)
        self._add_labeled_entry(load_grid, "Fy:", "fy", row=1,
                                default="0", form=self.node_form)
        if self.structure_type == "frame":
            self._add_labeled_entry(load_grid, "Mz:", "mz", row=2,
                                    default="0", form=self.node_form)

        ctk.CTkButton(left, text="+ Agregar Nodo",
                      command=self._on_add_node).grid(row=5, column=0, sticky="ew",
                                                       padx=8, pady=(6, 4))

        self.node_list_box = ctk.CTkTextbox(left, height=90, font=("Consolas", 11))
        self.node_list_box.grid(row=6, column=0, sticky="ew", padx=8, pady=(0, 10))
        self.node_list_box.configure(state="disabled")

        ctk.CTkFrame(left, height=2, fg_color="gray40").grid(
            row=7, column=0, sticky="ew", padx=8, pady=6)

        # ---- Sub-seccion Elementos ----
        ctk.CTkLabel(left, text="ELEMENTOS / BARRAS",
                     font=ctk.CTkFont(weight="bold")).grid(
                         row=8, column=0, sticky="w", padx=8, pady=(4, 2))
        self.elem_form = {}
        elem_grid = ctk.CTkFrame(left, fg_color="transparent")
        elem_grid.grid(row=9, column=0, sticky="ew", padx=5, pady=2)
        elem_grid.grid_columnconfigure(1, weight=1)
        self._add_labeled_entry(elem_grid, "ID:", "id", row=0,
                                default=f"E{self._elem_counter}", form=self.elem_form)
        self._add_labeled_entry(elem_grid, "Nodo i:", "ni", row=1,
                                default="", form=self.elem_form)
        self._add_labeled_entry(elem_grid, "Nodo j:", "nj", row=2,
                                default="", form=self.elem_form)
        self._add_labeled_entry(elem_grid, "Area A:", "A", row=3,
                                default="0.01", form=self.elem_form)
        self._add_labeled_entry(elem_grid, "E:", "E", row=4,
                                default="200000" if self.units.key != "SI" else "200e9",
                                form=self.elem_form)
        if self.structure_type == "frame":
            self._add_labeled_entry(elem_grid, "Inercia I:", "I", row=5,
                                    default="0.0001", form=self.elem_form)
        self._add_labeled_entry(elem_grid, "fy:", "fy",
                                row=6 if self.structure_type == "frame" else 5,
                                default="250" if self.units.key != "SI" else "250e6",
                                form=self.elem_form)

        if self.structure_type == "frame":
            load_elem_grid = ctk.CTkFrame(left, fg_color="transparent")
            load_elem_grid.grid(row=10, column=0, sticky="ew", padx=5, pady=2)
            load_elem_grid.grid_columnconfigure(1, weight=1)
            self._add_labeled_entry(load_elem_grid, "w1 (i):", "w1", row=0,
                                    default="0", form=self.elem_form)
            self._add_labeled_entry(load_elem_grid, "w2 (j):", "w2", row=1,
                                    default="0", form=self.elem_form)
            ctk.CTkLabel(left, text="w: carga distribuida perpendicular a la barra\n"
                                     "(gira con cada elemento; NO es el eje Y global)",
                         font=ctk.CTkFont(size=10), text_color="gray60", justify="left").grid(
                             row=11, column=0, sticky="w", padx=8, pady=(0, 2))

        ctk.CTkButton(left, text="+ Agregar Elemento",
                      command=self._on_add_element).grid(row=12, column=0, sticky="ew",
                                                         padx=8, pady=(6, 4))

        self.elem_list_box = ctk.CTkTextbox(left, height=90, font=("Consolas", 11))
        self.elem_list_box.grid(row=13, column=0, sticky="ew", padx=8, pady=(0, 10))
        self.elem_list_box.configure(state="disabled")

        ctk.CTkFrame(left, height=2, fg_color="gray40").grid(
            row=14, column=0, sticky="ew", padx=8, pady=6)

        # ---- Acciones principales ----
        ctk.CTkButton(left, text="Calcular Estructura", height=38,
                      fg_color="#2f855a", hover_color="#276749",
                      font=ctk.CTkFont(weight="bold"),
                      command=self._on_calculate).grid(row=15, column=0, sticky="ew",
                                                       padx=8, pady=4)
        ctk.CTkButton(left, text="Ver Procedimiento",
                      command=lambda: self.tabview.set("Procedimiento")).grid(
                          row=16, column=0, sticky="ew", padx=8, pady=4)
        ctk.CTkButton(left, text="Previsualizar PDF",
                      command=self._on_preview_pdf).grid(row=17, column=0, sticky="ew",
                                                         padx=8, pady=4)
        ctk.CTkButton(left, text="Borrar Todo", fg_color="#c53030",
                      hover_color="#9b2c2c",
                      command=self._on_clear_all).grid(row=18, column=0, sticky="ew",
                                                       padx=8, pady=(4, 12))

        # --------- Panel derecho (canvas + selector de diagramas) ---------
        right = ctk.CTkFrame(self.tab_editor)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(right, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=6)

        self.btn_view_structure = ctk.CTkButton(
            toolbar, text="Estructura", width=95,
            command=lambda: self._set_diagram_view("structure"))
        self.btn_view_structure.pack(side="left", padx=2)

        self.btn_view_deformed = ctk.CTkButton(
            toolbar, text="Deformada", width=95,
            command=lambda: self._set_diagram_view("deformed"))
        self.btn_view_deformed.pack(side="left", padx=2)

        self.btn_view_dc = ctk.CTkButton(
            toolbar, text="D/C", width=75,
            command=lambda: self._set_diagram_view("DC"))
        self.btn_view_dc.pack(side="left", padx=2)

        self.btn_view_axial = ctk.CTkButton(
            toolbar, text="Axial (N)", width=95,
            command=lambda: self._set_diagram_view("N"))
        self.btn_view_axial.pack(side="left", padx=2)

        if self.structure_type == "frame":
            self.btn_view_shear = ctk.CTkButton(
                toolbar, text="Cortante (V)", width=95,
                command=lambda: self._set_diagram_view("V"))
            self.btn_view_shear.pack(side="left", padx=2)

            self.btn_view_moment = ctk.CTkButton(
                toolbar, text="Momento (M)", width=95,
                command=lambda: self._set_diagram_view("M"))
            self.btn_view_moment.pack(side="left", padx=2)

        scale_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        scale_frame.pack(side="left", padx=6)
        self.deformation_scale_label = ctk.CTkLabel(scale_frame, text="×50", width=35,
                                                     font=ctk.CTkFont(size=10, weight="bold"))
        self.deformation_scale_label.pack(side="left")
        self.deformation_scale_slider = ctk.CTkSlider(
            scale_frame, from_=1, to=200, width=115, number_of_steps=199,
            command=self._on_deformation_scale)
        self.deformation_scale_slider.set(self.deformation_scale)
        self.deformation_scale_slider.pack(side="left", padx=2)

        self.btn_fit_view = ctk.CTkButton(
            toolbar, text="Ajustar Vista", width=100, fg_color="gray40",
            hover_color="gray30", command=self._fit_view)
        self.btn_fit_view.pack(side="left", padx=(10, 2))

        self.fs_label = ctk.CTkLabel(toolbar, text="FS sistema: --",
                                      font=ctk.CTkFont(weight="bold"))
        self.fs_label.pack(side="right", padx=10)

        canvas_frame = ctk.CTkFrame(right, fg_color="white")
        canvas_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        self.fig = Figure(figsize=(7, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.renderer = StructureRenderer(self.ax, self.units)

        ctk.CTkLabel(
            right, text="Rueda del raton: zoom  \u00b7  Shift + mantener rueda "
                        "presionada y arrastrar: mover la hoja  \u00b7  "
                        "\u00abAjustar Vista\u00bb: reencuadrar",
            font=ctk.CTkFont(size=10), text_color="gray60").grid(
                row=2, column=0, sticky="w", padx=8, pady=(0, 4))

        self._setup_canvas_navigation()

        self._redraw()

    # ------------------------------------------------------------------ #
    # NAVEGACION DEL LIENZO: zoom con rueda del raton, paneo con
    # Shift + boton central (estilo AutoCAD). No depende de la logica de
    # calculo ni de dibujo de bajo nivel; solo manipula los limites (xlim/
    # ylim) del eje de Matplotlib ya renderizado.
    # ------------------------------------------------------------------ #
    def _setup_canvas_navigation(self):
        widget = self.canvas.get_tk_widget()
        # Zoom: rueda del raton. Windows/macOS emiten <MouseWheel> con
        # event.delta; Linux/X11 emite <Button-4> (arriba) y <Button-5>
        # (abajo) sin atributo 'delta'.
        widget.bind("<MouseWheel>", self._on_canvas_scroll)
        widget.bind("<Button-4>", self._on_canvas_scroll)
        widget.bind("<Button-5>", self._on_canvas_scroll)
        # Paneo: Shift + boton central (rueda) del raton, presionado y
        # arrastrado.
        widget.bind("<ButtonPress-2>", self._on_pan_start)
        widget.bind("<B2-Motion>", self._on_pan_move)
        widget.bind("<ButtonRelease-2>", self._on_pan_end)

    def _pixel_to_data(self, px, py):
        """Convierte coordenadas de pixel del widget Tkinter (origen
        arriba-izquierda) a coordenadas de datos del eje de Matplotlib
        (origen abajo-izquierda)."""
        height = self.canvas.get_tk_widget().winfo_height()
        inv = self.ax.transData.inverted()
        return inv.transform((px, height - py))

    def _on_canvas_scroll(self, event):
        if not self.nodes:
            return
        # Normaliza la direccion del scroll entre plataformas.
        delta = getattr(event, "delta", 0)
        num = getattr(event, "num", None)
        if delta:
            zoom_in = delta > 0
        elif num == 4:
            zoom_in = True
        elif num == 5:
            zoom_in = False
        else:
            return
        self._zoom_canvas(event.x, event.y, zoom_in)
        return "break"

    def _zoom_canvas(self, px, py, zoom_in, factor=0.85):
        try:
            xdata, ydata = self._pixel_to_data(px, py)
        except Exception:
            return
        f = factor if zoom_in else 1.0 / factor
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        new_xlim = (xdata - (xdata - xlim[0]) * f, xdata + (xlim[1] - xdata) * f)
        new_ylim = (ydata - (ydata - ylim[0]) * f, ydata + (ylim[1] - ydata) * f)
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        self._manual_view_active = True
        self.canvas.draw_idle()

    def _on_pan_start(self, event):
        # Solo inicia el paneo si Shift esta presionado (bit 0x0001 del
        # estado de modificadores de Tkinter).
        if not (event.state & 0x0001):
            return
        if not self.nodes:
            return
        self._pan_active = True
        self._pan_last = (event.x, event.y)

    def _on_pan_move(self, event):
        if not self._pan_active or self._pan_last is None:
            return
        try:
            x0, y0 = self._pixel_to_data(*self._pan_last)
            x1, y1 = self._pixel_to_data(event.x, event.y)
        except Exception:
            return
        dx, dy = x1 - x0, y1 - y0
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
        self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
        self._pan_last = (event.x, event.y)
        self._manual_view_active = True
        self.canvas.draw_idle()

    def _on_pan_end(self, event):
        self._pan_active = False
        self._pan_last = None

    def _fit_view(self):
        """Reencuadra automaticamente la vista a la extension de la
        estructura (equivalente a 'zoom extents')."""
        self._manual_view_active = False
        self._redraw()

    def _add_labeled_entry(self, parent, label_text, key, row, default, form):
        ctk.CTkLabel(parent, text=label_text, width=92, anchor="w").grid(
            row=row, column=0, sticky="w", padx=5, pady=3)
        entry = ctk.CTkEntry(parent, width=110)
        entry.insert(0, default)
        entry.grid(row=row, column=1, sticky="ew", padx=5, pady=3)
        form[key] = entry

    # ---------------------------------------------------------------- #
    # PESTAÑA 2: RESULTADOS
    # ---------------------------------------------------------------- #
    def _build_results_tab(self):
        self.tab_results.grid_rowconfigure(0, weight=1)
        self.tab_results.grid_columnconfigure(0, weight=1)
        self.results_scroll = ctk.CTkScrollableFrame(
            self.tab_results, label_text="Resultados del Analisis",
            label_font=ctk.CTkFont(size=15, weight="bold"))
        self.results_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.results_scroll.grid_columnconfigure(0, weight=1)
        self._results_placeholder = ctk.CTkLabel(
            self.results_scroll,
            text="Aun no se ha calculado la estructura.\n"
                 "Ingrese los datos en 'Editor Visual' y presione 'Calcular Estructura'.",
            font=ctk.CTkFont(size=13), text_color="gray60", justify="center")
        self._results_placeholder.grid(row=0, column=0, pady=60)

    def _clear_container(self, container):
        for child in list(container.winfo_children()):
            child.destroy()

    def _fs_display(self, fs):
        """Devuelve (texto, color) para un valor de Factor de Seguridad."""
        if fs is None:
            return "N/D", "gray70"
        if fs == float("inf"):
            return "sin esfuerzo (inf)", "gray70"
        color = "#e53e3e" if fs < 1.0 else ("#d69e2e" if fs < 1.5 else "#38a169")
        return f"{fs:.3f}", color

    def _build_table(self, parent, headers, rows):
        """Tabla sencilla (encabezado + filas alternadas) hecha con CTkLabel."""
        frame = ctk.CTkFrame(parent, fg_color="#111827", corner_radius=8)
        ncols = len(headers)
        for c in range(ncols):
            frame.grid_columnconfigure(c, weight=1)
        for c, htxt in enumerate(headers):
            ctk.CTkLabel(frame, text=htxt, font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="#63b3ed", fg_color="#1f2937").grid(
                             row=0, column=c, sticky="nsew", padx=1, pady=1, ipady=4)
        if not rows:
            ctk.CTkLabel(frame, text="— sin datos relevantes —",
                         font=ctk.CTkFont(size=11), text_color="gray60",
                         fg_color="#151b26").grid(
                             row=1, column=0, columnspan=ncols, pady=8, sticky="nsew")
        for r, rowdata in enumerate(rows, start=1):
            bg = "#1a2130" if r % 2 == 0 else "#151b26"
            for c, val in enumerate(rowdata):
                ctk.CTkLabel(frame, text=str(val), font=ctk.CTkFont(size=11),
                             text_color="#e2e8f0", fg_color=bg).grid(
                                 row=r, column=c, sticky="nsew", padx=1, pady=1, ipady=3)
        return frame

    def _build_elem_table(self, parent, results):
        """Tabla de resultados por elemento, con la celda de FS coloreada."""
        u = self.units
        if self.structure_type == "frame":
            headers = ["Elem", "Nodos", f"L [{u.length_symbol}]", f"N [{u.force_symbol}]",
                       f"V_i / V_j [{u.force_symbol}]",
                       f"M_i / M_j [{u.force_symbol}\u00b7{u.length_symbol}]",
                       f"M_max [{u.force_symbol}\u00b7{u.length_symbol}]", "FS"]
        else:
            headers = ["Elem", "Nodos", f"L [{u.length_symbol}]", f"N [{u.force_symbol}]",
                       "Estado", "FS"]
        frame = ctk.CTkFrame(parent, fg_color="#111827", corner_radius=8)
        for c in range(len(headers)):
            frame.grid_columnconfigure(c, weight=1)
        for c, h in enumerate(headers):
            ctk.CTkLabel(frame, text=h, font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="#63b3ed", fg_color="#1f2937").grid(
                             row=0, column=c, sticky="nsew", padx=1, pady=1, ipady=4)
        r = 1
        for eid, er in results["elem_results"].items():
            bg = "#1a2130" if r % 2 == 0 else "#151b26"
            fs_txt, fs_color = self._fs_display(er.get("FS"))
            if self.structure_type == "frame":
                vals = [eid, f"{er['ni']}\u2192{er['nj']}",
                        f"{u.length_out(er['L']):.4g}",
                        f"{u.force_out(er['N_end']):.3f}",
                        f"{u.force_out(er['V_i']):.3f} / {u.force_out(er['V_j']):.3f}",
                        f"{u.moment_out(er['M_i']):.3f} / {u.moment_out(er['M_j']):.3f}",
                        f"{u.moment_out(er['M_max']):.3f}"]
            else:
                estado = "Traccion" if er["N"] >= 0 else "Compresion"
                vals = [eid, f"{er['ni']}\u2192{er['nj']}",
                        f"{u.length_out(er['L']):.4g}",
                        f"{u.force_out(er['N']):.3f}", estado]
            vals.append(fs_txt)
            for c, val in enumerate(vals):
                is_fs = (c == len(vals) - 1)
                ctk.CTkLabel(frame, text=str(val),
                             font=ctk.CTkFont(size=11, weight="bold" if is_fs else "normal"),
                             text_color=fs_color if is_fs else "#e2e8f0",
                             fg_color=bg).grid(row=r, column=c, sticky="nsew",
                                                padx=1, pady=1, ipady=3)
            r += 1
        return frame

    def _build_elem_diagrams_figure(self, parent, results):
        """Grafica, para cada elemento por separado, sus diagramas de
        esfuerzos internos (N, V, M en porticos; N en armaduras), a
        diferencia del Editor Visual que los superpone sobre la
        geometria completa de la estructura."""
        u = self.units
        elems = list(results["elem_results"].items())
        n = len(elems)
        if n == 0:
            return
        cols = ["N", "V", "M"] if self.structure_type == "frame" else ["N"]
        ncols = len(cols)
        fig_h = max(1.9 * n, 2.3)
        fig = Figure(figsize=(9.2, fig_h), dpi=100)
        color_map = {"N": "#c53030", "V": "#2b6cb0", "M": "#805ad5"}
        unit_map = {"N": u.force_symbol, "V": u.force_symbol,
                    "M": f"{u.force_symbol}\u00b7{u.length_symbol}"}
        axes = fig.subplots(n, ncols, squeeze=False)

        for i, (eid, er) in enumerate(elems):
            for j, key in enumerate(cols):
                ax = axes[i][j]
                if self.structure_type == "truss":
                    L_disp = u.length_out(er["L"])
                    x = np.array([0.0, L_disp])
                    val = u.force_out(er["N"])
                    vals = np.array([val, val])
                else:
                    x = u.length_out(er["x"])
                    conv = u.force_out if key in ("N", "V") else u.moment_out
                    vals = conv(er[key])

                color = color_map[key]
                ax.axhline(0, color="#718096", linewidth=0.8)
                ax.fill_between(x, vals, 0, color=color, alpha=0.32)
                ax.plot(x, vals, color=color, linewidth=1.6)
                vmax = float(np.max(np.abs(vals)))
                vmax = vmax if vmax > 1e-9 else 1.0
                ax.set_ylim(-vmax * 1.35, vmax * 1.35)
                i_max = int(np.argmax(np.abs(vals)))
                ax.annotate(f"{vals[i_max]:.3g}", (x[i_max], vals[i_max]),
                            fontsize=7, color=color, fontweight="bold",
                            ha="center",
                            va="bottom" if vals[i_max] >= 0 else "top")
                if j == 0:
                    ax.set_ylabel(eid, fontsize=9, fontweight="bold",
                                  color="#2d3748", rotation=0, ha="right",
                                  va="center", labelpad=20)
                if i == 0:
                    ax.set_title(f"{key} [{unit_map[key]}]", fontsize=10,
                                 fontweight="bold", color=color)
                ax.tick_params(labelsize=7)
                ax.grid(True, linestyle=":", alpha=0.4)

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)

    def _populate_results(self, results):
        self._clear_container(self.results_scroll)
        u = self.units

        # ---- Encabezado ----
        header = ctk.CTkFrame(self.results_scroll, fg_color="#1f2937", corner_radius=10)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="REPORTE DE RESULTADOS",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#63b3ed").grid(row=0, column=0, sticky="w",
                                                 padx=16, pady=(12, 2))
        subt = (f"{'Portico 2D' if self.structure_type=='frame' else 'Armadura 2D'}"
                f"   \u00b7   Unidades: {u.label}")
        ctk.CTkLabel(header, text=subt, font=ctk.CTkFont(size=12),
                     text_color="gray70").grid(row=1, column=0, sticky="w",
                                                padx=16, pady=(0, 12))
        fs = results.get("FS_system")
        fs_txt, fs_color = self._fs_display(fs)
        ctk.CTkLabel(header, text=f"FS minimo del sistema:  {fs_txt}",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=fs_color).grid(row=0, column=1, rowspan=2,
                                                padx=16, sticky="e")

        # ---- Reacciones ----
        ctk.CTkLabel(self.results_scroll, text="Reacciones en los Apoyos",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#f6ad55").grid(row=1, column=0, sticky="w", pady=(6, 4))
        if self.structure_type == "frame":
            headers = ["Nodo", f"Rx [{u.force_symbol}]", f"Ry [{u.force_symbol}]",
                       f"Mz [{u.force_symbol}\u00b7{u.length_symbol}]"]
        else:
            headers = ["Nodo", f"Rx [{u.force_symbol}]", f"Ry [{u.force_symbol}]"]
        rows = []
        for nid, nr in results["node_results"].items():
            if self.structure_type == "frame":
                rx, ry, mz = u.force_out(nr["Rx"]), u.force_out(nr["Ry"]), u.moment_out(nr["Mz"])
                if abs(rx) > 1e-9 or abs(ry) > 1e-9 or abs(mz) > 1e-9:
                    rows.append([nid, f"{rx:.3f}", f"{ry:.3f}", f"{mz:.3f}"])
            else:
                rx, ry = u.force_out(nr["rx"]), u.force_out(nr["ry"])
                if abs(rx) > 1e-9 or abs(ry) > 1e-9:
                    rows.append([nid, f"{rx:.3f}", f"{ry:.3f}"])
        self._build_table(self.results_scroll, headers, rows).grid(
            row=2, column=0, sticky="ew", pady=(0, 14))

        # ---- Desplazamientos ----
        ctk.CTkLabel(self.results_scroll, text="Desplazamientos y Rotaciones Nodales",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#f6ad55").grid(row=3, column=0, sticky="w", pady=(6, 4))
        if self.structure_type == "frame":
            headers_d = ["Nodo", f"u [{u.length_symbol}]", f"v [{u.length_symbol}]", "theta [rad]"]
        else:
            headers_d = ["Nodo", f"u [{u.length_symbol}]", f"v [{u.length_symbol}]"]
        rows_d = []
        for nid, nr in results["node_results"].items():
            ux, uy = u.length_out(nr["ux"]), u.length_out(nr["uy"])
            if self.structure_type == "frame":
                rows_d.append([nid, f"{ux:.5g}", f"{uy:.5g}", f"{nr['rz']:.5g}"])
            else:
                rows_d.append([nid, f"{ux:.5g}", f"{uy:.5g}"])
        self._build_table(self.results_scroll, headers_d, rows_d).grid(
            row=4, column=0, sticky="ew", pady=(0, 14))

        # ---- Resultados por elemento ----
        ctk.CTkLabel(self.results_scroll, text="Esfuerzos Internos por Elemento",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#f6ad55").grid(row=5, column=0, sticky="w", pady=(6, 4))
        self._build_elem_table(self.results_scroll, results).grid(
            row=6, column=0, sticky="ew", pady=(0, 14))

        # ---- Diagramas por elemento (separados, no sobre la geometria) ----
        ctk.CTkLabel(self.results_scroll,
                     text="Diagramas de Esfuerzos Internos por Elemento (individuales)",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#f6ad55").grid(row=7, column=0, sticky="w", pady=(6, 4))
        diag_frame = ctk.CTkFrame(self.results_scroll, fg_color="white", corner_radius=8)
        diag_frame.grid(row=8, column=0, sticky="ew", pady=(0, 10))
        self._build_elem_diagrams_figure(diag_frame, results)

    # ---------------------------------------------------------------- #
    # PESTAÑA 3: PROCEDIMIENTO
    # ---------------------------------------------------------------- #
    def _build_procedure_tab(self):
        self.tab_procedure.grid_rowconfigure(0, weight=1)
        self.tab_procedure.grid_columnconfigure(0, weight=1)
        self.proc_box = ctk.CTkTextbox(self.tab_procedure, font=("Consolas", 12),
                                        wrap="word", fg_color="#111827")
        self.proc_box.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        # CTkTextbox no expone metodos de "tags" (colores/subrayado) de
        # forma nativa; se accede al widget tkinter.Text interno, que si
        # los soporta, para dar formato de colores por paso/matriz/resultado.
        self._proc_txt = getattr(self.proc_box, "_textbox", self.proc_box)
        self._setup_proc_tags()
        self._render_procedure_placeholder()

    def _setup_proc_tags(self):
        t = self._proc_txt
        t.tag_configure("h1", foreground="#63b3ed", font=("Segoe UI", 17, "bold"),
                        justify="center", spacing3=14)
        t.tag_configure("eq", foreground="#f6e05e", font=("Segoe UI", 14, "italic"),
                        justify="center", spacing1=4, spacing3=16)
        t.tag_configure("h2", foreground="#f6ad55", font=("Segoe UI", 13, "bold"),
                        spacing1=14, spacing3=6)
        t.tag_configure("p", foreground="#e2e8f0", font=("Segoe UI", 11), spacing3=4)
        t.tag_configure("dim", foreground="#9ca3af", font=("Segoe UI", 10, "italic"),
                        spacing3=10)
        t.tag_configure("mat", foreground="#68d391", font=("Consolas", 10), spacing3=8)
        t.tag_configure("res", foreground="#fc8181", font=("Consolas", 12, "bold"),
                        underline=True, spacing1=4, spacing3=14)

    def _pw(self, tag, text):
        """Inserta texto con un tag de formato (color/estilo) en la
        pestaña de Procedimiento."""
        self._proc_txt.insert("end", text, tag)

    def _mat_str(self, M, max_dim=10):
        n = min(M.shape[0], max_dim)
        m = min(M.shape[1], max_dim)
        lines = []
        for i in range(n):
            row_txt = "  ".join(f"{v:>10.3e}" for v in M[i, :m])
            lines.append(f"[ {row_txt} ]")
        return "\n".join(lines)

    def _vec_str(self, v):
        return "{ " + ",  ".join(f"{val:.4g}" for val in v) + " }"

    def _render_procedure_placeholder(self):
        t = self._proc_txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        self._pw("h1", "PROCEDIMIENTO \u2014 METODO DIRECTO DE LA RIGIDEZ\n\n")
        self._pw("eq", "[K] {U} = {F}      \u27f6      {U} = [K]\u207b\u00b9 {F}\n\n")
        self._pw("p", "Calcule la estructura en la pestaña 'Editor Visual' para ver aqui, "
                      "paso a paso, el ensamblaje numerico completo de la matriz de "
                      "rigidez, la reduccion por condiciones de apoyo y la solucion del "
                      "sistema.\n")
        t.configure(state="disabled")

    def _populate_procedure(self, results, solver):
        t = self._proc_txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        u = self.units

        self._pw("h1", "PROCEDIMIENTO \u2014 METODO DIRECTO DE LA RIGIDEZ\n")
        self._pw("dim", f"{'Portico 2D' if self.structure_type=='frame' else 'Armadura 2D'}"
                         f"   \u00b7   {len(self.nodes)} nodos   \u00b7   "
                         f"{len(self.elements)} elementos   \u00b7   "
                         f"Motor de calculo interno en SI (N, m, Pa)\n\n")
        self._pw("eq", "[K] {U} = {F}      \u27f6      {U} = [K]\u207b\u00b9 {F}\n\n")

        n_dof = results["K"].shape[0]
        free = results["free_dofs"]
        restrained = results["restrained_dofs"]
        n_free = len(free)
        dof_per_node = 3 if self.structure_type == "frame" else 2

        # ---- Paso 1 ----
        self._pw("h2", "1) Grados de libertad del sistema\n")
        self._pw("p", f"Cada nodo tiene {dof_per_node} grados de libertad "
                      f"({'u, v, theta' if dof_per_node == 3 else 'u, v'}). Con "
                      f"{len(self.nodes)} nodos, el sistema completo tiene {n_dof} "
                      f"grados de libertad.\n\n")

        # ---- Paso 2: matrices locales por elemento ----
        self._pw("h2", "2) Matriz de rigidez de cada elemento\n")
        self._pw("p", "Para cada elemento se calcula su matriz de rigidez local a partir "
                      "de E, A" + (", I" if self.structure_type == "frame" else "") +
                      " y su longitud L, y se transforma a coordenadas globales con la "
                      "matriz de transformacion T segun su angulo de inclinacion theta. "
                      "El resultado se suma (ensambla) dentro de la matriz global [K].\n\n")

        max_elems = 25
        for i, (eid, el) in enumerate(self.elements.items()):
            if i >= max_elems:
                self._pw("dim", f"... ({len(self.elements) - max_elems} elemento(s) "
                                 "adicional(es) omitido(s) por extension) ...\n\n")
                break
            si_el = solver.elements[eid]
            if self.structure_type == "frame":
                L, c, s = solver._geometry(si_el)
                theta = float(np.degrees(np.arctan2(s, c)))
                k_local = solver._local_stiffness(L, si_el["E"], si_el["A"], si_el["I"])
                T = solver._transformation(c, s)
                k_glob = T.T @ k_local @ T
            else:
                k_glob, L, c, s = solver._element_stiffness_global(si_el)
                theta = float(np.degrees(np.arctan2(s, c)))

            self._pw("p", f"\u2022 Elemento {eid} ({el['ni']} \u2192 {el['nj']})   "
                          f"L = {u.length_out(L):.4g} {u.length_symbol}   "
                          f"theta = {theta:.2f}\u00b0\n")
            if k_glob.shape[0] <= 6:
                self._pw("mat", self._mat_str(k_glob) + "\n\n")
            else:
                self._pw("dim", f"   (matriz {k_glob.shape[0]}x{k_glob.shape[0]}, "
                                 "se omite por tamaño)\n\n")

        # ---- Paso 3: ensamblaje ----
        self._pw("h2", "3) Ensamblaje de la matriz de rigidez global [K] y {F}\n")
        self._pw("p", "Cada matriz elemental se suma en las posiciones correspondientes a "
                      "los grados de libertad de sus nodos i y j, obteniendo la matriz de "
                      f"rigidez global [K] de tamaño {n_dof}x{n_dof} y el vector de cargas "
                      "{F}.\n\n")
        K = results["K"]
        if n_dof <= 10:
            self._pw("mat", self._mat_str(K) + "\n\n")
        else:
            self._pw("dim", f"[K] es de {n_dof}x{n_dof}: demasiado grande para "
                             "mostrarse completa aqui.\n\n")

        # ---- Paso 4: condiciones de contorno ----
        self._pw("h2", "4) Aplicacion de condiciones de contorno (apoyos)\n")
        self._pw("p", f"Se identifican los grados de libertad restringidos por los "
                      f"apoyos ({len(restrained)} en total) y se eliminan las "
                      f"filas/columnas correspondientes de [K] y {{F}}, dejando "
                      f"{n_free} grados de libertad libres.\n\n")

        # ---- Paso 5: sistema reducido y solucion ----
        self._pw("h2", "5) Sistema reducido y solucion\n")
        Kff = K[np.ix_(free, free)]
        self._pw("p", f"Se resuelve el sistema reducido [Kff]{{Uf}} = {{Ff}}, de tamaño "
                      f"{n_free}x{n_free}:\n")
        if n_free <= 10:
            self._pw("mat", self._mat_str(Kff) + "\n\n")
        else:
            self._pw("dim", f"[Kff] es de {n_free}x{n_free}: demasiado grande para "
                             "mostrarse completa aqui.\n\n")

        U = results["U"]
        Uf = U[free]
        self._pw("p", "El vector solucion de desplazamientos/rotaciones libres {Uf} "
                      "obtenido es:\n")
        self._pw("res", self._vec_str(Uf) + "\n\n")

        # ---- Paso 6: reacciones ----
        self._pw("h2", "6) Reacciones en los apoyos\n")
        self._pw("p", "Con {U} completo, se calculan las reacciones en los grados "
                      "restringidos como {R} = [K]{U} - {F}:\n")
        reac_lines = []
        for nid, nr in results["node_results"].items():
            if self.structure_type == "frame":
                rx, ry, mz = u.force_out(nr["Rx"]), u.force_out(nr["Ry"]), u.moment_out(nr["Mz"])
                if abs(rx) > 1e-9 or abs(ry) > 1e-9 or abs(mz) > 1e-9:
                    reac_lines.append(f"  {nid}:  Rx = {rx:.3f} {u.force_symbol}    "
                                       f"Ry = {ry:.3f} {u.force_symbol}    "
                                       f"Mz = {mz:.3f} {u.force_symbol}\u00b7{u.length_symbol}")
            else:
                rx, ry = u.force_out(nr["rx"]), u.force_out(nr["ry"])
                if abs(rx) > 1e-9 or abs(ry) > 1e-9:
                    reac_lines.append(f"  {nid}:  Rx = {rx:.3f} {u.force_symbol}    "
                                       f"Ry = {ry:.3f} {u.force_symbol}")
        if not reac_lines:
            reac_lines = ["  (sin reacciones significativas)"]
        self._pw("res", "\n".join(reac_lines) + "\n\n")

        # ---- Paso 7: verificacion de seguridad ----
        self._pw("h2", "7) Verificacion de seguridad\n")
        self._pw("p", "Se calcula, para cada elemento, el esfuerzo combinado y su Factor "
                      "de Seguridad FS = fy / sigma_combinado; el minimo de todos ellos "
                      "es el FS del sistema completo:\n")
        fs_txt, _ = self._fs_display(results.get("FS_system"))
        self._pw("res", f"FS_sistema = {fs_txt}\n")

        t.configure(state="disabled")

    # ---------------------------------------------------------------- #
    # PESTAÑA 4: PREVISUALIZACION PDF
    # ---------------------------------------------------------------- #
    def _build_pdf_tab(self):
        self.tab_pdf.grid_rowconfigure(1, weight=1)
        self.tab_pdf.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self.tab_pdf, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkLabel(top, text="Vista Previa \u2014 Memoria de Calculo (PDF)",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Convertir a PDF", fg_color="#d69e2e",
                      hover_color="#b7791f",
                      command=self._on_convert_pdf).pack(side="right")

        outer = ctk.CTkFrame(self.tab_pdf, fg_color="#2d3748")
        outer.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        self.pdf_scroll = ctk.CTkScrollableFrame(outer, fg_color="#2d3748")
        self.pdf_scroll.grid(row=0, column=0, sticky="nsew")
        self.pdf_scroll.grid_columnconfigure(0, weight=1)

        self._pdf_placeholder = ctk.CTkLabel(
            self.pdf_scroll,
            text="Presione 'Previsualizar PDF' en el Editor Visual (o calcule la\n"
                 "estructura) para generar la memoria de calculo.",
            font=ctk.CTkFont(size=13), text_color="gray70", justify="center")
        self._pdf_placeholder.grid(row=0, column=0, pady=80)

    # ---- helpers para las "hojas" tipo PDF (Matplotlib estilo papel) ----
    def _new_page_fig(self):
        fig = Figure(figsize=(8.5, 11), dpi=92, facecolor="white")
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.add_patch(Rectangle((0.02, 0.015), 0.96, 0.97, fill=False,
                                edgecolor="#d1d5db", linewidth=1.3))
        return fig, ax

    def _style_pdf_table(self, tbl, fontsize=8.5):
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(fontsize)
        for (r, c), cell in tbl.get_celld().items():
            cell.set_edgecolor("#cbd5e0")
            if r == 0:
                cell.set_facecolor("#2b6cb0")
                cell.get_text().set_color("white")
                cell.get_text().set_fontweight("bold")
            else:
                cell.set_facecolor("#f7fafc" if r % 2 == 0 else "white")

    def _render_pdf_page1(self, results):
        fig, ax = self._new_page_fig()
        u = self.units
        ax.text(0.5, 0.92, "MEMORIA DE CALCULO", fontsize=22, fontweight="bold",
                ha="center", family="serif", color="#1a202c")
        ax.text(0.5, 0.885,
                "Analisis Estructural 2D \u2014 Metodo Directo de la Rigidez",
                fontsize=12, ha="center", family="serif", color="#4a5568",
                style="italic")
        ax.plot([0.08, 0.92], [0.855, 0.855], color="#1a202c", linewidth=1.2)

        info = [
            ("Tipo de estructura", "Portico 2D" if self.structure_type == "frame" else "Armadura 2D"),
            ("Sistema de unidades", u.label),
            ("Numero de nodos", str(len(self.nodes))),
            ("Numero de elementos", str(len(self.elements))),
            ("Fecha de generacion", datetime.now().strftime("%d/%m/%Y %H:%M")),
        ]
        y = 0.78
        for label, value in info:
            ax.text(0.10, y, f"{label}:", fontsize=11, family="serif", color="#2d3748")
            ax.text(0.55, y, value, fontsize=11, family="serif", fontweight="bold",
                    color="#1a202c")
            y -= 0.045

        y -= 0.03
        ax.text(0.10, y, "Resumen General de Resultados", fontsize=13,
                fontweight="bold", family="serif", color="#1a202c")
        y -= 0.06
        fs = results.get("FS_system")
        fs_txt, _ = self._fs_display(fs)
        fs_color_pdf = "#276749"
        if fs is not None and fs != float("inf"):
            fs_color_pdf = "#c53030" if fs < 1.0 else ("#b7791f" if fs < 1.5 else "#276749")
        ax.text(0.10, y, "Factor de Seguridad minimo del sistema:", fontsize=11,
                family="serif", color="#2d3748")
        ax.text(0.72, y, fs_txt, fontsize=12, fontweight="bold", family="serif",
                color=fs_color_pdf)

        ax.text(0.5, 0.055, "Pagina 1 de 3", fontsize=9, ha="center",
                family="serif", color="#a0aec0")
        ax.text(0.5, 0.03,
                "Este documento es una previsualizacion. La exportacion con formato\n"
                "profesional (sello, portada personalizada, anexos graficos) requiere "
                "la version PRO.",
                fontsize=7.5, ha="center", family="serif", style="italic",
                color="#a0aec0")
        return fig

    def _render_pdf_page2(self, results):
        fig, ax = self._new_page_fig()
        u = self.units
        ax.text(0.5, 0.94, "REACCIONES Y DESPLAZAMIENTOS", fontsize=16,
                fontweight="bold", ha="center", family="serif", color="#1a202c")
        ax.plot([0.08, 0.92], [0.905, 0.905], color="#1a202c", linewidth=1.0)

        ax.text(0.09, 0.87, "Reacciones en los Apoyos", fontsize=12,
                fontweight="bold", family="serif", color="#2b6cb0")
        if self.structure_type == "frame":
            headers_r = ["Nodo", f"Rx [{u.force_symbol}]", f"Ry [{u.force_symbol}]",
                         f"Mz [{u.force_symbol}\u00b7{u.length_symbol}]"]
        else:
            headers_r = ["Nodo", f"Rx [{u.force_symbol}]", f"Ry [{u.force_symbol}]"]
        rows_r = []
        for nid, nr in results["node_results"].items():
            if self.structure_type == "frame":
                rx, ry, mz = u.force_out(nr["Rx"]), u.force_out(nr["Ry"]), u.moment_out(nr["Mz"])
                if abs(rx) > 1e-9 or abs(ry) > 1e-9 or abs(mz) > 1e-9:
                    rows_r.append([nid, f"{rx:.3f}", f"{ry:.3f}", f"{mz:.3f}"])
            else:
                rx, ry = u.force_out(nr["rx"]), u.force_out(nr["ry"])
                if abs(rx) > 1e-9 or abs(ry) > 1e-9:
                    rows_r.append([nid, f"{rx:.3f}", f"{ry:.3f}"])
        if not rows_r:
            rows_r = [["\u2014"] * len(headers_r)]
        tbl1 = ax.table(cellText=rows_r, colLabels=headers_r, cellLoc="center",
                         loc="upper center", bbox=[0.09, 0.62, 0.82, 0.22])
        self._style_pdf_table(tbl1)

        ax.text(0.09, 0.55, "Desplazamientos y Rotaciones Nodales", fontsize=12,
                fontweight="bold", family="serif", color="#2b6cb0")
        if self.structure_type == "frame":
            headers_d = ["Nodo", f"u [{u.length_symbol}]", f"v [{u.length_symbol}]",
                         "theta [rad]"]
        else:
            headers_d = ["Nodo", f"u [{u.length_symbol}]", f"v [{u.length_symbol}]"]
        rows_d = []
        for nid, nr in results["node_results"].items():
            ux, uy = u.length_out(nr["ux"]), u.length_out(nr["uy"])
            if self.structure_type == "frame":
                rows_d.append([nid, f"{ux:.5g}", f"{uy:.5g}", f"{nr['rz']:.5g}"])
            else:
                rows_d.append([nid, f"{ux:.5g}", f"{uy:.5g}"])
        tbl2 = ax.table(cellText=rows_d, colLabels=headers_d, cellLoc="center",
                         loc="upper center", bbox=[0.09, 0.28, 0.82, 0.22])
        self._style_pdf_table(tbl2)

        ax.text(0.5, 0.055, "Pagina 2 de 3", fontsize=9, ha="center",
                family="serif", color="#a0aec0")
        return fig

    def _render_pdf_page3(self, results):
        fig, ax = self._new_page_fig()
        u = self.units
        ax.text(0.5, 0.94, "RESULTADOS POR ELEMENTO", fontsize=16,
                fontweight="bold", ha="center", family="serif", color="#1a202c")
        ax.plot([0.08, 0.92], [0.905, 0.905], color="#1a202c", linewidth=1.0)

        items = list(results["elem_results"].items())
        max_rows = 22
        truncated = len(items) > max_rows
        items = items[:max_rows]

        if self.structure_type == "frame":
            col_labels = ["Elem", "Nodos", f"N [{u.force_symbol}]",
                          f"V_i/V_j [{u.force_symbol}]",
                          f"M_i/M_j [{u.force_symbol}\u00b7{u.length_symbol}]", "FS"]
        else:
            col_labels = ["Elem", "Nodos", f"N [{u.force_symbol}]", "Estado", "FS"]

        rows, fs_flags = [], []
        for eid, er in items:
            fs_txt, _ = self._fs_display(er.get("FS"))
            if self.structure_type == "frame":
                rows.append([eid, f"{er['ni']}-{er['nj']}",
                             f"{u.force_out(er['N_end']):.3f}",
                             f"{u.force_out(er['V_i']):.2f}/{u.force_out(er['V_j']):.2f}",
                             f"{u.moment_out(er['M_i']):.2f}/{u.moment_out(er['M_j']):.2f}",
                             fs_txt])
            else:
                estado = "Traccion" if er["N"] >= 0 else "Compresion"
                rows.append([eid, f"{er['ni']}-{er['nj']}",
                             f"{u.force_out(er['N']):.3f}", estado, fs_txt])
            fs_flags.append(er.get("FS"))

        tbl = ax.table(cellText=rows, colLabels=col_labels, cellLoc="center",
                       loc="upper center", bbox=[0.06, 0.35, 0.88, 0.52])
        self._style_pdf_table(tbl, fontsize=8)
        ncols = len(col_labels)
        for (r, c), cell in tbl.get_celld().items():
            if r > 0 and c == ncols - 1:
                fs_val = fs_flags[r - 1]
                if fs_val is not None and fs_val != float("inf"):
                    cell.get_text().set_color(
                        "#c53030" if fs_val < 1.0 else
                        ("#b7791f" if fs_val < 1.5 else "#276749"))
                    cell.get_text().set_fontweight("bold")

        if truncated:
            ax.text(0.5, 0.30,
                    f"(mostrando los primeros {max_rows} de "
                    f"{len(results['elem_results'])} elementos)",
                    fontsize=8, ha="center", family="serif", style="italic",
                    color="#a0aec0")

        ax.text(0.5, 0.055, "Pagina 3 de 3", fontsize=9, ha="center",
                family="serif", color="#a0aec0")
        return fig

    def _populate_pdf_preview(self, results):
        self._clear_container(self.pdf_scroll)
        for i, render_fn in enumerate((self._render_pdf_page1,
                                        self._render_pdf_page2,
                                        self._render_pdf_page3)):
            fig = render_fn(results)
            canvas = FigureCanvasTkAgg(fig, master=self.pdf_scroll)
            canvas.draw()
            canvas.get_tk_widget().grid(row=i, column=0, pady=16)

    # ==================================================================
    # LOGICA DE EVENTOS
    # ==================================================================
    def _get_float(self, entry_widget, field_name):
        raw = entry_widget.get().strip()
        try:
            return float(raw)
        except ValueError:
            raise ValueError(f"El campo '{field_name}' debe ser numerico (recibido: '{raw}').")

    def _on_add_node(self):
        try:
            nid = self.node_form["id"].get().strip()
            if not nid:
                raise ValueError("El ID del nodo no puede estar vacio.")
            if nid in self.nodes:
                raise ValueError(f"Ya existe un nodo con ID '{nid}'.")
            x = self._get_float(self.node_form["x"], "X")
            y = self._get_float(self.node_form["y"], "Y")
            rx = bool(self.node_form["rx"].get())
            ry = bool(self.node_form["ry"].get())
            rz = bool(self.node_form["rz"].get()) if "rz" in self.node_form else False
            fx = self._get_float(self.node_form["fx"], "Fx")
            fy = self._get_float(self.node_form["fy"], "Fy")
            mz = self._get_float(self.node_form["mz"], "Mz") if "mz" in self.node_form else 0.0

            self.nodes[nid] = dict(x=x, y=y, rx=rx, ry=ry, rz=rz, fx=fx, fy=fy, mz=mz)
            self._node_counter += 1
            self.node_form["id"].delete(0, "end")
            self.node_form["id"].insert(0, f"N{self._node_counter}")
            self._refresh_lists()
            self._redraw()
        except Exception as exc:
            messagebox.showerror("Error al agregar nodo", str(exc))

    def _on_add_element(self):
        try:
            eid = self.elem_form["id"].get().strip()
            if not eid:
                raise ValueError("El ID del elemento no puede estar vacio.")
            if eid in self.elements:
                raise ValueError(f"Ya existe un elemento con ID '{eid}'.")
            ni = self.elem_form["ni"].get().strip()
            nj = self.elem_form["nj"].get().strip()
            if ni not in self.nodes or nj not in self.nodes:
                raise ValueError("Los nodos 'Nodo i' y 'Nodo j' deben existir previamente.")
            if ni == nj:
                raise ValueError("El nodo inicial y final no pueden ser el mismo.")
            A = self._get_float(self.elem_form["A"], "Area A")
            E = self._get_float(self.elem_form["E"], "Modulo E")
            fy = self._get_float(self.elem_form["fy"], "fy")
            if A <= 0 or E <= 0:
                raise ValueError("Area y Modulo E deben ser mayores que cero.")

            el = dict(ni=ni, nj=nj, A=A, E=E, fy=fy)
            if self.structure_type == "frame":
                I = self._get_float(self.elem_form["I"], "Inercia I")
                if I <= 0:
                    raise ValueError("La Inercia I debe ser mayor que cero.")
                w1 = self._get_float(self.elem_form["w1"], "w1")
                w2 = self._get_float(self.elem_form["w2"], "w2")
                el.update(I=I, w1=w1, w2=w2)

            self.elements[eid] = el
            self._elem_counter += 1
            self.elem_form["id"].delete(0, "end")
            self.elem_form["id"].insert(0, f"E{self._elem_counter}")
            self._refresh_lists()
            self._redraw()
        except Exception as exc:
            messagebox.showerror("Error al agregar elemento", str(exc))

    def _refresh_lists(self):
        self.node_list_box.configure(state="normal")
        self.node_list_box.delete("0.0", "end")
        for nid, n in self.nodes.items():
            r = "".join([
                "X" if n["rx"] else "-",
                "Y" if n["ry"] else "-",
                ("Z" if n.get("rz") else "-") if self.structure_type == "frame" else "",
            ])
            self.node_list_box.insert(
                "end", f"{nid:<5} x={n['x']:<7g} y={n['y']:<7g} "
                       f"restr=[{r}] F=({n['fx']:g},{n['fy']:g})\n")
        self.node_list_box.configure(state="disabled")

        self.elem_list_box.configure(state="normal")
        self.elem_list_box.delete("0.0", "end")
        for eid, e in self.elements.items():
            extra = ""
            if self.structure_type == "frame":
                extra = f" I={e['I']:g} w=({e.get('w1',0):g},{e.get('w2',0):g})"
            self.elem_list_box.insert(
                "end", f"{eid:<5} {e['ni']}->{e['nj']}  A={e['A']:g} "
                       f"E={e['E']:g}{extra}\n")
        self.elem_list_box.configure(state="disabled")

    def _on_clear_all(self):
        if not messagebox.askyesno("Confirmar", "Esto borrara todos los nodos y "
                                                 "elementos ingresados. ¿Continuar?"):
            return
        self.nodes.clear()
        self.elements.clear()
        self.last_results = None
        self._node_counter = 1
        self._elem_counter = 1
        self._manual_view_active = False
        self.node_form["id"].delete(0, "end")
        self.node_form["id"].insert(0, "N1")
        self.elem_form["id"].delete(0, "end")
        self.elem_form["id"].insert(0, "E1")
        self._refresh_lists()
        self.fs_label.configure(text="FS sistema: --")
        self._set_diagram_view("structure")
        self._render_procedure_placeholder()

        self._clear_container(self.results_scroll)
        self._results_placeholder = ctk.CTkLabel(
            self.results_scroll,
            text="Estructura reiniciada.\nIngrese datos y calcule para ver resultados.",
            font=ctk.CTkFont(size=13), text_color="gray60", justify="center")
        self._results_placeholder.grid(row=0, column=0, pady=60)

        self._clear_container(self.pdf_scroll)
        self._pdf_placeholder = ctk.CTkLabel(
            self.pdf_scroll, text="Sin datos calculados aun.",
            font=ctk.CTkFont(size=13), text_color="gray70")
        self._pdf_placeholder.grid(row=0, column=0, pady=80)

    # ------------------------------------------------------------------ #
    # Conversion de unidades de pantalla -> SI (para el motor de calculo)
    # ------------------------------------------------------------------ #
    def _build_solver_inputs(self):
        u = self.units
        si_nodes = {}
        for nid, n in self.nodes.items():
            si_nodes[nid] = dict(
                x=u.length_in(n["x"]), y=u.length_in(n["y"]),
                rx=n["rx"], ry=n["ry"], rz=n.get("rz", False),
                fx=u.force_in(n["fx"]), fy=u.force_in(n["fy"]),
                mz=u.moment_in(n.get("mz", 0.0)),
            )
        si_elements = {}
        for eid, e in self.elements.items():
            entry = dict(
                ni=e["ni"], nj=e["nj"],
                A=self._area_in(e["A"]),
                E=u.stress_in(e["E"]),
                fy=u.stress_in(e["fy"]),
            )
            if self.structure_type == "frame":
                entry["I"] = self._inertia_in(e["I"])
                entry["w1"] = self._distload_in(e.get("w1", 0.0))
                entry["w2"] = self._distload_in(e.get("w2", 0.0))
            si_elements[eid] = entry
        return si_nodes, si_elements

    def _area_in(self, value_display):
        # Area: [longitud]^2
        return value_display * (self.units.length_to_si ** 2)

    def _inertia_in(self, value_display):
        # Inercia: [longitud]^4
        return value_display * (self.units.length_to_si ** 4)

    def _distload_in(self, value_display):
        # Carga distribuida: [fuerza]/[longitud]
        return value_display * (self.units.force_to_si / self.units.length_to_si)

    def _area_out(self, value_si):
        return value_si / (self.units.length_to_si ** 2)

    def _inertia_out(self, value_si):
        return value_si / (self.units.length_to_si ** 4)

    # ------------------------------------------------------------------ #
    # CALCULO
    # ------------------------------------------------------------------ #
    def _on_calculate(self):
        if len(self.nodes) < 2 or len(self.elements) < 1:
            messagebox.showerror("Datos incompletos",
                                  "Se requieren al menos 2 nodos y 1 elemento.")
            return
        try:
            si_nodes, si_elements = self._build_solver_inputs()
            if self.structure_type == "truss":
                solver = TrussSolver2D(si_nodes, si_elements)
            else:
                solver = FrameSolver2D(si_nodes, si_elements)
            results = solver.solve()
            self.last_results = results
            self._populate_results(results)
            self._populate_procedure(results, solver)
            self._populate_pdf_preview(results)

            fs = results.get("FS_system")
            fs_txt, fs_color = self._fs_display(fs)
            self.fs_label.configure(text=f"FS sistema: {fs_txt}", text_color=fs_color)

            self._set_diagram_view("DC")
            self.tabview.set("Resultados")
        except (TrussSolverError, FrameSolverError) as exc:
            messagebox.showerror("Error de calculo estructural", str(exc))
        except Exception as exc:
            messagebox.showerror("Error inesperado",
                                  f"{exc}\n\n{traceback.format_exc(limit=2)}")

    def _on_preview_pdf(self):
        if self.last_results is None:
            if len(self.nodes) < 2 or len(self.elements) < 1:
                messagebox.showinfo("Sin datos",
                                     "Ingrese la estructura y calculela primero "
                                     "para generar la memoria de calculo.")
                self.tabview.set("Editor Visual")
                return
            self._on_calculate()
            if self.last_results is None:
                return
        self.tabview.set("Previsualizacion PDF")

    def _on_convert_pdf(self):
        ProUpsellDialog(self)

    # ------------------------------------------------------------------ #
    # RENDERIZADO / DIAGRAMAS
    # ------------------------------------------------------------------ #
    def _set_diagram_view(self, mode):
        self.current_diagram = mode
        self._redraw()

    def _on_deformation_scale(self, value):
        self.deformation_scale = float(value)
        if hasattr(self, "deformation_scale_label"):
            self.deformation_scale_label.configure(text=f"×{self.deformation_scale:.0f}")
        if self.current_diagram in ("deformed", "DC"):
            self._redraw()

    def _redraw(self):
        # Si el usuario ya hizo zoom/paneo manualmente, se conserva el
        # encuadre actual del lienzo en vez de reajustarlo automaticamente
        # cada vez que cambian los datos o la vista de diagrama.
        preserve_view = self._manual_view_active
        saved_xlim = self.ax.get_xlim() if preserve_view else None
        saved_ylim = self.ax.get_ylim() if preserve_view else None

        if not self.nodes:
            self.renderer.clear()
            self.ax.set_title("Agregue nodos y elementos para comenzar",
                               fontsize=11, color="#6b7280")
            self.canvas.draw()
            return

        if self.current_diagram == "structure" or self.last_results is None:
            self.renderer.draw_structure(self.nodes, self.elements, self.structure_type)
        elif self.current_diagram in ("deformed", "DC"):
            nr = self.last_results.get("node_results", {})
            self.renderer.draw_deformed_structure(
                self.nodes, self.elements, self.structure_type,
                nr, self.last_results.get("elem_results", {}),
                deformation_scale=self.deformation_scale,
                color_by_dc=(self.current_diagram == "DC"),
                title=("Forma deformada" if self.current_diagram == "deformed"
                       else "Demanda / Capacidad + Forma deformada"))
        else:
            u = self.units
            elem_results_display = {}
            for eid, er in self.last_results["elem_results"].items():
                if self.structure_type == "truss":
                    el = self.elements[eid]
                    ni_d, nj_d = self.nodes[el["ni"]], self.nodes[el["nj"]]
                    L_disp = float(np.hypot(nj_d["x"] - ni_d["x"], nj_d["y"] - ni_d["y"]))
                    n_val = u.force_out(er["N"])
                    elem_results_display[eid] = {
                        "N": np.array([n_val, n_val]),
                        "x": np.array([0.0, L_disp]),
                    }
                else:
                    conv = u.force_out if self.current_diagram in ("N", "V") else u.moment_out
                    elem_results_display[eid] = {
                        self.current_diagram: conv(er[self.current_diagram]),
                        "x": u.length_out(er["x"]),
                    }
            titles = {"N": "Diagrama de Fuerza Axial",
                      "V": "Diagrama de Fuerza Cortante",
                      "M": "Diagrama de Momento Flector"}
            if self.structure_type == "truss" and self.current_diagram != "N":
                self.renderer.draw_structure(self.nodes, self.elements, self.structure_type)
            else:
                self.renderer.draw_diagram(self.nodes, self.elements,
                                            elem_results_display,
                                            self.current_diagram if self.structure_type == "frame" else "N",
                                            titles.get(self.current_diagram, "Diagrama"))

        if preserve_view and saved_xlim is not None:
            self.ax.set_xlim(saved_xlim)
            self.ax.set_ylim(saved_ylim)
        self.canvas.draw()


def run_app():
    app = MainStructuralApp()
    app.mainloop()
