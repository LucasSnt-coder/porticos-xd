# AnalisisEstructural2D

Software de analisis de estructuras planas (**Porticos 2D** y **Armaduras 2D**)
mediante el **Metodo Directo de la Rigidez**, con interfaz grafica en
`CustomTkinter` y visualizacion en `Matplotlib`.

## Instalacion

```bash
pip install -r requirements.txt
python main.py
```

Requiere Python 3.9+ con Tkinter disponible en el sistema (viene incluido en
la mayoria de instalaciones estandar de Python en Windows/macOS; en Linux
puede requerir `sudo apt install python3-tk`).

## Estructura del proyecto

| Archivo               | Responsabilidad                                                |
|------------------------|----------------------------------------------------------------|
| `units.py`             | Sistemas de unidades (SI, SI Tecnico, Imperial) y conversiones |
| `truss_solver.py`      | Motor de calculo para Armaduras 2D (rigidez, axial-only)       |
| `frame_solver.py`      | Motor de calculo para Porticos 2D (rigidez, viga-columna, cargas distribuidas) |
| `frame_renderer.py`    | Dibujo de geometria, apoyos, cargas y diagramas N/V/M          |
| `app_interface.py`     | Interfaz CustomTkinter (`MainStructuralApp`) y orquestacion    |
| `main.py`              | Punto de entrada                                               |

El motor de calculo trabaja **siempre internamente en SI (N, m, Pa)**; la
capa de interfaz convierte de/hacia el sistema de unidades elegido por el
usuario al iniciar el proyecto.

## Convenciones de signos (importante)

- Ejes locales de cada elemento: `x` va del nodo `i` al nodo `j`; `y` local
  es perpendicular, rotado +90° (antihorario) respecto de `x`.
- Rotaciones y momentos nodales: positivos en sentido **antihorario (CCW)**.
- Fuerza axial `N`: **positiva = traccion**, negativa = compresion.
- Carga distribuida `w` (porticos): definida en el eje local `+y`. Una carga
  "hacia abajo" en una barra horizontal se ingresa como **negativa**.
- Momento flector `M(x)`: convencion de **"sagging" positivo** (concavidad
  hacia +y local; fibra +y en compresion, fibra -y en traccion para una barra
  horizontal con y apuntando hacia arriba).
- Cortante `V(x)`: convencion estandar de vigas, consistente con
  `dV/dx = +w(x)` y `dM/dx = V(x)` (con `w` definido como se indica arriba).

Estas formulas fueron **verificadas numericamente** contra soluciones
analiticas conocidas (ver `Validacion` abajo) antes de integrarse a la
interfaz grafica.

## Validacion del motor de calculo

Se comprobaron, con resultados exactos (o al espesor de precision de punto
flotante):

1. **Cercha triangular simetrica** con carga vertical en el apice: reacciones
   y fuerzas axiales coinciden con la solucion clasica de equilibrio de
   nodos.
2. **Voladizo con carga puntual en la punta**: momento en el empotramiento
   `M = P*L`, cortante constante `V = P`, deflexion en la punta
   `= P*L^3/(3EI)`.
3. **Voladizo con carga uniformemente distribuida**: reaccion `R = w*L`,
   momento en el empotramiento `= w*L^2/2`, deflexion en la punta
   `= w*L^4/(8EI)`.
4. **Viga simplemente apoyada con carga uniformemente distribuida**:
   reacciones `= w*L/2` en cada apoyo, momento maximo en el centro de la luz
   `= w*L^2/8`, deflexion en el centro `= 5*w*L^4/(384EI)` (verificado con un
   modelo de 2 elementos para capturar el nodo central).

Todos estos casos se reprodujeron con error numerico menor a 1e-6 respecto
de la solucion analitica cerrada.

## Limitaciones conocidas / alcance de esta version

- El Factor de Seguridad combina el esfuerzo normal por axial y por flexion
  usando el modulo resistente de la seccion si se provee (`Sx`, no expuesto
  aun en la UI) o, en su defecto, una **seccion rectangular equivalente**
  estimada a partir de `A` e `I` (`h = sqrt(12*I/A)`). Para secciones reales
  (perfiles IPE/W, tubulares, etc.) se recomienda verificar el resultado con
  el modulo resistente real de la seccion.
- Las cargas distribuidas se soportan en el eje local `y` (transversal),
  uniformes o trapezoidales. No se implementa carga axial distribuida.
- La exportacion real a PDF con formato profesional está representada como
  una funcion de demostracion ("Membresia PRO"), tal como se solicito en la
  especificacion original; el contenido de la memoria de calculo se puede
  consultar en texto plano en la pestaña correspondiente.
- Este software es una herramienta de apoyo al calculo; no reemplaza la
  revision de un ingeniero estructural calificado ni el cumplimiento de
  normativas locales (ACI, AISC, NEC, Eurocodigo, etc.).
