# -*- coding: utf-8 -*-
"""
frame_solver.py
----------------
Motor de calculo para PORTICOS PLANOS (Frame 2D) mediante el Metodo
Directo de la Rigidez, incluyendo cargas distribuidas (uniformes o
trapezoidales) sobre los elementos.

Convenciones (SIEMPRE en unidades SI internamente: N, m, Pa):
    - 3 grados de libertad por nodo (globales): (u, v, theta).
    - Eje local x: va del nodo inicial (i) al nodo final (j).
    - Eje local y: perpendicular a x, girado +90 grados (CCW) respecto a x.
    - Rotaciones positivas: sentido anti-horario (CCW).
    - Carga distribuida "w" definida en EJE LOCAL y, positiva en +y local.
    - Fuerza Axial N: TRACCION positiva.
    - Fuerza Cortante V: convencion de vigas (positiva si, al cortar la
      barra, la porcion izquierda tiende a subir respecto a la derecha,
      equivalente a: dM/dx = V).
    - Momento Flector M: POSITIVO si produce concavidad hacia +y local
      (fibra +y en tension) -> convencion "sagging" clasica de vigas.

Matriz de rigidez local de un elemento portico (6x6), orden de GDL:
    [u_i, v_i, th_i, u_j, v_j, th_j]

    k_local =
    [ EA/L      0            0        -EA/L      0            0      ]
    [ 0        12EI/L^3      6EI/L^2   0        -12EI/L^3      6EI/L^2]
    [ 0         6EI/L^2      4EI/L     0        -6EI/L^2       2EI/L  ]
    [-EA/L      0            0         EA/L      0            0      ]
    [ 0       -12EI/L^3     -6EI/L^2   0         12EI/L^3     -6EI/L^2]
    [ 0         6EI/L^2      2EI/L     0        -6EI/L^2       4EI/L  ]

Este es el resultado estandar de la Resistencia de Materiales / Metodo de
Rigidez para un elemento viga-columna (ver Kassimali, "Matrix Analysis
of Structures"; Hibbeler, "Structural Analysis").

Estructuras de datos de entrada (todas en SI):
    nodes = {
        node_id: {
            "x": float, "y": float,
            "rx": bool, "ry": bool, "rz": bool,
            "fx": float, "fy": float, "mz": float,
        }, ...
    }
    elements = {
        elem_id: {
            "ni": node_id, "nj": node_id,
            "A": float, "I": float, "E": float, "fy": float,
            # Carga distribuida transversal (local y), trapezoidal:
            # w1 en el nodo i, w2 en el nodo j (uniforme si w1 == w2).
            "w1": float, "w2": float,
        }, ...
    }
"""

from __future__ import annotations
import numpy as np


class FrameSolverError(Exception):
    """Errores de validacion o de calculo del solver de porticos."""
    pass


class FrameSolver2D:
    def __init__(self, nodes: dict, elements: dict):
        self.nodes = nodes
        self.elements = elements
        self._validate()

        self.node_ids = list(self.nodes.keys())
        self.node_index = {nid: i for i, nid in enumerate(self.node_ids)}
        self.n_nodes = len(self.node_ids)
        self.n_dof = 3 * self.n_nodes

    # ------------------------------------------------------------------ #
    def _validate(self):
        if len(self.nodes) < 2:
            raise FrameSolverError("Se requieren al menos 2 nodos.")
        if len(self.elements) < 1:
            raise FrameSolverError("Se requiere al menos 1 elemento.")
        for eid, el in self.elements.items():
            for k in ("ni", "nj"):
                if el[k] not in self.nodes:
                    raise FrameSolverError(
                        f"Elemento {eid}: nodo '{el[k]}' no existe.")
            if el["ni"] == el["nj"]:
                raise FrameSolverError(
                    f"Elemento {eid}: nodo inicial y final son el mismo.")
            if el.get("A", 0) <= 0:
                raise FrameSolverError(f"Elemento {eid}: Area debe ser > 0.")
            if el.get("I", 0) <= 0:
                raise FrameSolverError(f"Elemento {eid}: Inercia debe ser > 0.")
            if el.get("E", 0) <= 0:
                raise FrameSolverError(f"Elemento {eid}: Modulo E debe ser > 0.")

        has_restraint = any(
            n.get("rx") or n.get("ry") or n.get("rz") for n in self.nodes.values()
        )
        if not has_restraint:
            raise FrameSolverError(
                "La estructura no tiene ningun apoyo/restriccion definido.")

    # ------------------------------------------------------------------ #
    # Geometria
    # ------------------------------------------------------------------ #
    def _geometry(self, el: dict):
        ni, nj = self.nodes[el["ni"]], self.nodes[el["nj"]]
        dx = nj["x"] - ni["x"]
        dy = nj["y"] - ni["y"]
        L = float(np.hypot(dx, dy))
        if L < 1e-12:
            raise FrameSolverError("Elemento de longitud nula detectado.")
        c, s = dx / L, dy / L
        return L, c, s

    def _dof_map(self, nid: str):
        i = self.node_index[nid]
        return [3 * i, 3 * i + 1, 3 * i + 2]

    def _transformation(self, c, s):
        T = np.zeros((6, 6))
        R = np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
        T[0:3, 0:3] = R
        T[3:6, 3:6] = R
        return T

    def _local_stiffness(self, L, E, A, I):
        EA_L = E * A / L
        EI = E * I
        return np.array([
            [ EA_L,          0,             0,        -EA_L,          0,             0       ],
            [ 0,   12 * EI / L**3,  6 * EI / L**2,     0,  -12 * EI / L**3,  6 * EI / L**2   ],
            [ 0,    6 * EI / L**2,  4 * EI / L,        0,   -6 * EI / L**2,  2 * EI / L      ],
            [-EA_L,          0,             0,         EA_L,          0,             0       ],
            [ 0,  -12 * EI / L**3, -6 * EI / L**2,     0,   12 * EI / L**3, -6 * EI / L**2   ],
            [ 0,    6 * EI / L**2,  2 * EI / L,        0,   -6 * EI / L**2,  4 * EI / L      ],
        ])

    # ------------------------------------------------------------------ #
    # Vector de CARGAS NODALES CONSISTENTES (formulacion de Elementos
    # Finitos, ver Logan "A First Course in the Finite Element Method")
    # equivalente a una carga distribuida trapezoidal (w1 en i, w2 en j)
    # actuando en +y local. Se obtiene por superposicion de:
    #   (a) carga uniforme de magnitud w1 en toda la longitud
    #   (b) carga triangular que crece linealmente de 0 (en i) a (w2-w1)
    #       (en j)
    #
    # Estas cargas nodales consistentes se SUMAN directamente al vector
    # de cargas global (igual que una carga puntual cualquiera) para
    # resolver los desplazamientos. Para recuperar las fuerzas internas
    # reales de cada elemento, se restan de nuevo: vale la relacion
    #       {p_local} = [k_local]{d_local} - {f0_local}
    #
    #   Uniforme w (toda la luz L):
    #       V_i = w*L/2         V_j = w*L/2
    #       M_i = w*L^2/12      M_j = -w*L^2/12
    #
    #   Triangular (0 en i, w0 en j):
    #       V_i = 3*w0*L/20     V_j = 7*w0*L/20
    #       M_i = w0*L^2/30     M_j = -w0*L^2/20
    #
    # El vector devuelto (f0_local) sigue el orden de GDL local:
    # [N_i, V_i, M_i, N_j, V_j, M_j].
    # ------------------------------------------------------------------ #
    def _fixed_end_forces(self, L, w1, w2):
        f0 = np.zeros(6)
        if abs(w1) < 1e-12 and abs(w2) < 1e-12:
            return f0

        # (a) componente uniforme w1
        Vi = w1 * L / 2.0
        Vj = w1 * L / 2.0
        Mi = w1 * L**2 / 12.0
        Mj = -w1 * L**2 / 12.0

        # (b) componente triangular (0 en i, (w2-w1) en j)
        w0 = w2 - w1
        Vi += 3.0 * w0 * L / 20.0
        Vj += 7.0 * w0 * L / 20.0
        Mi += w0 * L**2 / 30.0
        Mj += -w0 * L**2 / 20.0

        f0[1] = Vi
        f0[2] = Mi
        f0[4] = Vj
        f0[5] = Mj
        return f0

    # ------------------------------------------------------------------ #
    # Ensamblaje
    # ------------------------------------------------------------------ #
    def assemble(self):
        n = self.n_dof
        K = np.zeros((n, n))
        F_applied = np.zeros(n)   # cargas nodales directas
        F_equiv = np.zeros(n)     # cargas nodales equivalentes (de distribuidas)

        elem_cache = {}
        for eid, el in self.elements.items():
            L, c, s = self._geometry(el)
            k_local = self._local_stiffness(L, el["E"], el["A"], el["I"])
            T = self._transformation(c, s)
            k_global = T.T @ k_local @ T

            w1 = el.get("w1", 0.0)
            w2 = el.get("w2", w1)
            f0_local = self._fixed_end_forces(L, w1, w2)
            f0_global = T.T @ f0_local

            elem_cache[eid] = dict(L=L, c=c, s=s, k_local=k_local, T=T,
                                    f0_local=f0_local, f0_global=f0_global)

            dofs = self._dof_map(el["ni"]) + self._dof_map(el["nj"])
            for a in range(6):
                for b in range(6):
                    K[dofs[a], dofs[b]] += k_global[a, b]
                # La carga nodal consistente se SUMA directamente (ver
                # nota arriba): reemplaza, para efectos de la solucion
                # global, a la carga distribuida real.
                F_equiv[dofs[a]] += f0_global[a]

        for nid, node in self.nodes.items():
            dofs = self._dof_map(nid)
            F_applied[dofs[0]] += node.get("fx", 0.0)
            F_applied[dofs[1]] += node.get("fy", 0.0)
            F_applied[dofs[2]] += node.get("mz", 0.0)

        self._elem_cache = elem_cache
        return K, F_applied, F_equiv

    def _restrained_dofs(self):
        restrained = []
        for nid, node in self.nodes.items():
            i = self.node_index[nid]
            if node.get("rx"):
                restrained.append(3 * i)
            if node.get("ry"):
                restrained.append(3 * i + 1)
            if node.get("rz"):
                restrained.append(3 * i + 2)
        return sorted(set(restrained))

    # ------------------------------------------------------------------ #
    # Resolucion
    # ------------------------------------------------------------------ #
    def solve(self, n_samples: int = 21) -> dict:
        K, F_applied, F_equiv = self.assemble()
        F_total = F_applied + F_equiv
        n = self.n_dof
        restrained = self._restrained_dofs()
        free = [d for d in range(n) if d not in restrained]

        if not free:
            raise FrameSolverError("La estructura esta totalmente restringida; no hay grados de libertad libres.")

        Kff = K[np.ix_(free, free)]
        if np.linalg.cond(Kff) > 1e14 or abs(np.linalg.det(Kff)) < 1e-20:
            raise FrameSolverError(
                "La matriz de rigidez reducida es singular. La estructura "
                "es inestable (mecanismo) o esta mal restringida.")

        Ff = F_total[free]
        Uf = np.linalg.solve(Kff, Ff)

        U = np.zeros(n)
        for idx, d in enumerate(free):
            U[d] = Uf[idx]

        R_full = K @ U - F_total  # reacciones (fisicas) en GDL restringidos

        node_results = {}
        for nid in self.node_ids:
            dofs = self._dof_map(nid)
            node = self.nodes[nid]
            node_results[nid] = {
                "ux": U[dofs[0]], "uy": U[dofs[1]], "rz": U[dofs[2]],
                "Rx": R_full[dofs[0]] if node.get("rx") else 0.0,
                "Ry": R_full[dofs[1]] if node.get("ry") else 0.0,
                "Mz": R_full[dofs[2]] if node.get("rz") else 0.0,
            }

        elem_results = {}
        min_fs = None
        for eid, el in self.elements.items():
            cache = self._elem_cache[eid]
            L, T, k_local, f0_local = cache["L"], cache["T"], cache["k_local"], cache["f0_local"]
            dofs = self._dof_map(el["ni"]) + self._dof_map(el["nj"])
            d_global = U[dofs]
            d_local = T @ d_global

            # Fuerzas internas en los extremos (orden GDL local):
            # [N_i, V_i, M_i, N_j, V_j, M_j]. La carga nodal consistente
            # se resta de nuevo (ver nota en _fixed_end_forces) para
            # recuperar la fuerza interna FISICA real del elemento.
            p_local = k_local @ d_local - f0_local

            w1 = el.get("w1", 0.0)
            w2 = el.get("w2", w1)

            x = np.linspace(0, L, n_samples)

            # Axial: N(x) tension positiva. p_local[0] es la fuerza que el
            # nudo i ejerce sobre el elemento en +x local; en equilibrio,
            # si el elemento esta en traccion, el nudo "tira" del elemento
            # hacia afuera => fuerza sobre el elemento en -x => p_local[0]
            # negativo. Por lo tanto: N = -p_local[0] (constante, sin
            # carga axial distribuida).
            N_axial = -p_local[0] * np.ones_like(x)

            # Cortante y Momento: se construyen integrando la carga
            # distribuida local a partir del cortante y momento en el
            # extremo i, usando las relaciones diferenciales de vigas:
            #   dV/dx = -w(x)      dM/dx = V(x)
            # V_i (convencion de vigas) = p_local[1] (cortante que el
            # nudo i ejerce sobre el elemento, coincide con la convencion
            # estandar de "cortante justo a la derecha del apoyo i").
            V0 = p_local[1]
            M0 = -p_local[2]   # ver nota de convencion de signos abajo

            wx = w1 + (w2 - w1) * (x / L)
            # Relaciones diferenciales de vigas (con w definido en +y
            # local): dV/dx = +w(x)   dM/dx = V(x)
            # V(x) = V0 + integral(0,x) w(s) ds
            V = V0 + (w1 * x + (w2 - w1) * x**2 / (2.0 * L))
            # M(x) = M0 + integral(0,x) V(s) ds
            M = M0 + V0 * x + (w1 * x**2 / 2.0 + (w2 - w1) * x**3 / (6.0 * L))

            sigma_axial = N_axial / el["A"]
            c_ext = None  # distancia a fibra extrema (no siempre conocida)
            M_abs_max = float(np.max(np.abs(M)))
            V_abs_max = float(np.max(np.abs(V)))
            N_abs_max = float(np.max(np.abs(N_axial)))

            fy = el.get("fy", None)
            FS = None
            if fy:
                # Tension normal maxima aproximada: axial + flexion, usando
                # el modulo elastico de la seccion si se provee, o una
                # aproximacion con I y una altura estimada. Si no se
                # dispone del modulo resistente exacto, se reporta con
                # base en el esfuerzo normal por axial solamente mas una
                # fraccion de la flexion normalizada respecto a I.
                Sx = el.get("Sx")  # modulo resistente de la seccion [m^3], opcional
                if Sx:
                    sigma_flex_max = M_abs_max / Sx
                else:
                    # Estimacion: seccion rectangular equivalente a partir
                    # de A e I (h = sqrt(12*I/A)), c = h/2
                    h_eq = np.sqrt(12.0 * el["I"] / el["A"]) if el["A"] > 0 else 0.0
                    c_eq = h_eq / 2.0
                    sigma_flex_max = (M_abs_max * c_eq / el["I"]) if el["I"] > 0 else 0.0
                sigma_comb_max = abs(N_abs_max / el["A"]) + sigma_flex_max
                if sigma_comb_max > 1e-9:
                    FS = fy / sigma_comb_max
                else:
                    FS = float("inf")
                DC = (sigma_comb_max / fy) if fy > 0 else None
            else:
                DC = None

            elem_results[eid] = {
                "L": L, "x": x, "N": N_axial, "V": V, "M": M,
                "N_end": N_axial[0], "V_i": V[0], "V_j": V[-1],
                "M_i": M[0], "M_j": M[-1],
                "M_max": M_abs_max, "V_max": V_abs_max, "N_max": N_abs_max,
                "sigma_axial": sigma_axial, "FS": FS, "DC": DC,
                "ni": el["ni"], "nj": el["nj"],
                "w1": w1, "w2": w2,
            }
            if FS is not None:
                min_fs = FS if min_fs is None else min(min_fs, FS)

        return {
            "type": "frame",
            "U": U,
            "K": K,
            "F_applied": F_applied,
            "F_equiv": F_equiv,
            "F_total": F_total,
            "node_results": node_results,
            "elem_results": elem_results,
            "FS_system": min_fs,
            "free_dofs": free,
            "restrained_dofs": restrained,
        }
