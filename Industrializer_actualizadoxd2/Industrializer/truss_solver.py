# -*- coding: utf-8 -*-
"""
truss_solver.py
---------------
Motor de calculo para ARMADURAS PLANAS (Truss 2D) mediante el Metodo
Directo de la Rigidez.

Convenciones (SIEMPRE en unidades SI internamente: N, m, Pa):
    - 2 grados de libertad por nodo: (u, v) -> desplazamiento en X, Y.
    - Elementos trabajan SOLO a esfuerzo axial (articulados en ambos
      extremos). No transmiten momento.
    - Fuerza axial N > 0  => TRACCION (el elemento se alarga).
      Fuerza axial N < 0  => COMPRESION.

Estructuras de datos de entrada (todas en SI):
    nodes = {
        node_id: {
            "x": float, "y": float,
            "rx": bool, "ry": bool,           # True = grado restringido
            "fx": float, "fy": float,         # cargas puntuales nodales
        }, ...
    }
    elements = {
        elem_id: {
            "ni": node_id, "nj": node_id,
            "A": float,      # area de la seccion transversal [m^2]
            "E": float,      # modulo de elasticidad [Pa]
            "fy": float,     # limite elastico del material [Pa]
        }, ...
    }
"""

from __future__ import annotations
import numpy as np


class TrussSolverError(Exception):
    """Errores de validacion o de calculo del solver de armaduras."""
    pass


class TrussSolver2D:
    def __init__(self, nodes: dict, elements: dict):
        self.nodes = nodes
        self.elements = elements
        self._validate()

        # Mapeo id de nodo -> indice consecutivo 0..n-1
        self.node_ids = list(self.nodes.keys())
        self.node_index = {nid: i for i, nid in enumerate(self.node_ids)}
        self.n_nodes = len(self.node_ids)
        self.n_dof = 2 * self.n_nodes

    # ------------------------------------------------------------------ #
    # Validacion de entradas
    # ------------------------------------------------------------------ #
    def _validate(self):
        if len(self.nodes) < 2:
            raise TrussSolverError("Se requieren al menos 2 nodos.")
        if len(self.elements) < 1:
            raise TrussSolverError("Se requiere al menos 1 elemento.")
        for eid, el in self.elements.items():
            for k in ("ni", "nj"):
                if el[k] not in self.nodes:
                    raise TrussSolverError(
                        f"Elemento {eid}: nodo '{el[k]}' no existe.")
            if el["ni"] == el["nj"]:
                raise TrussSolverError(
                    f"Elemento {eid}: nodo inicial y final son el mismo.")
            if el.get("A", 0) <= 0:
                raise TrussSolverError(f"Elemento {eid}: Area debe ser > 0.")
            if el.get("E", 0) <= 0:
                raise TrussSolverError(f"Elemento {eid}: Modulo E debe ser > 0.")

        has_restraint = any(
            n.get("rx") or n.get("ry") for n in self.nodes.values()
        )
        if not has_restraint:
            raise TrussSolverError(
                "La estructura no tiene ningun apoyo/restriccion definido.")

    # ------------------------------------------------------------------ #
    # Geometria auxiliar
    # ------------------------------------------------------------------ #
    def _geometry(self, el: dict):
        ni, nj = self.nodes[el["ni"]], self.nodes[el["nj"]]
        dx = nj["x"] - ni["x"]
        dy = nj["y"] - ni["y"]
        L = float(np.hypot(dx, dy))
        if L < 1e-12:
            raise TrussSolverError("Elemento de longitud nula detectado.")
        c, s = dx / L, dy / L
        return L, c, s

    def _dof_map(self, nid: str):
        i = self.node_index[nid]
        return [2 * i, 2 * i + 1]

    # ------------------------------------------------------------------ #
    # Ensamblaje
    # ------------------------------------------------------------------ #
    def _element_stiffness_global(self, el: dict):
        """Matriz de rigidez 4x4 del elemento, en coordenadas globales."""
        L, c, s = self._geometry(el)
        E, A = el["E"], el["A"]
        k = (E * A / L) * np.array([
            [ c * c,  c * s, -c * c, -c * s],
            [ c * s,  s * s, -c * s, -s * s],
            [-c * c, -c * s,  c * c,  c * s],
            [-c * s, -s * s,  c * s,  s * s],
        ])
        return k, L, c, s

    def assemble(self):
        n = self.n_dof
        K = np.zeros((n, n))
        F = np.zeros(n)

        for el in self.elements.values():
            k_glob, *_ = self._element_stiffness_global(el)
            dofs = self._dof_map(el["ni"]) + self._dof_map(el["nj"])
            for a in range(4):
                for b in range(4):
                    K[dofs[a], dofs[b]] += k_glob[a, b]

        for nid, node in self.nodes.items():
            dofs = self._dof_map(nid)
            F[dofs[0]] += node.get("fx", 0.0)
            F[dofs[1]] += node.get("fy", 0.0)

        return K, F

    def _restrained_dofs(self):
        restrained = []
        for nid, node in self.nodes.items():
            i = self.node_index[nid]
            if node.get("rx"):
                restrained.append(2 * i)
            if node.get("ry"):
                restrained.append(2 * i + 1)
        return sorted(set(restrained))

    # ------------------------------------------------------------------ #
    # Resolucion
    # ------------------------------------------------------------------ #
    def solve(self) -> dict:
        K, F = self.assemble()
        n = self.n_dof
        restrained = self._restrained_dofs()
        free = [d for d in range(n) if d not in restrained]

        if not free:
            raise TrussSolverError("La estructura esta totalmente restringida; no hay grados de libertad libres.")

        Kff = K[np.ix_(free, free)]

        # Deteccion temprana de inestabilidad (mecanismo / matriz singular)
        if np.linalg.cond(Kff) > 1e14 or abs(np.linalg.det(Kff)) < 1e-20:
            raise TrussSolverError(
                "La matriz de rigidez reducida es singular. La estructura "
                "es inestable (mecanismo) o esta mal restringida.")

        Ff = F[free]
        Uf = np.linalg.solve(Kff, Ff)

        U = np.zeros(n)
        for idx, d in enumerate(free):
            U[d] = Uf[idx]

        R_full = K @ U - F  # reacciones en TODOS los grados (0 en los libres)

        # ---- Resultados por nodo ----
        node_results = {}
        for nid in self.node_ids:
            dofs = self._dof_map(nid)
            node_results[nid] = {
                "ux": U[dofs[0]], "uy": U[dofs[1]],
                "rx": R_full[dofs[0]] if nid_is_restrained(self.nodes[nid], "rx") else 0.0,
                "ry": R_full[dofs[1]] if nid_is_restrained(self.nodes[nid], "ry") else 0.0,
            }

        # ---- Resultados por elemento ----
        elem_results = {}
        min_fs = None
        for eid, el in self.elements.items():
            k_glob, L, c, s = self._element_stiffness_global(el)
            dofs = self._dof_map(el["ni"]) + self._dof_map(el["nj"])
            d = U[dofs]
            # Fuerza axial (traccion positiva):
            # N = (EA/L) * [-c, -s, c, s] . d
            N = (el["E"] * el["A"] / L) * np.array([-c, -s, c, s]) @ d
            sigma = N / el["A"]
            fy = el.get("fy", None)
            if fy and abs(sigma) > 1e-9:
                FS = fy / abs(sigma)
            elif fy:
                FS = float("inf")
            else:
                FS = None

            # Demand/Capacity (D/C): 1.0 representa la capacidad nominal.
            DC = (abs(sigma) / fy) if (fy and fy > 0) else None

            elem_results[eid] = {
                "L": L, "N": N, "sigma": sigma, "FS": FS, "DC": DC,
                "ni": el["ni"], "nj": el["nj"],
            }
            if FS is not None:
                min_fs = FS if min_fs is None else min(min_fs, FS)

        return {
            "type": "truss",
            "U": U,
            "K": K,
            "F": F,
            "node_results": node_results,
            "elem_results": elem_results,
            "FS_system": min_fs,
            "free_dofs": free,
            "restrained_dofs": restrained,
        }


def nid_is_restrained(node: dict, key: str) -> bool:
    return bool(node.get(key))
