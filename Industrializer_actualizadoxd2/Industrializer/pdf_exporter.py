# -*- coding: utf-8 -*-
"""Exporta la memoria de la previsualización a PDF con sello de fondo."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image


def _watermark_image(seal_path):
    """Convierte el sello en una marca de agua tenue con fondo transparente."""
    im = Image.open(seal_path).convert("RGBA")
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            luminance = (r + g + b) / 3
            alpha = int(max(0, min(85, (255 - luminance) * 0.34)))
            px[x, y] = (65, 85, 110, alpha)
    buf = BytesIO()
    im.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return ImageReader(buf)


def _draw_watermark(c, watermark, width, height):
    if watermark is None:
        return
    c.saveState()
    c.drawImage(watermark, 18, 18, width=width - 36, height=height - 36,
                preserveAspectRatio=True, anchor="c", mask="auto")
    c.restoreState()


def _header(c, title, page_no, watermark):
    w, h = letter
    _draw_watermark(c, watermark, w, h)
    c.setStrokeColor(colors.HexColor("#1a202c"))
    c.line(58, h - 65, w - 58, h - 65)
    c.setFillColor(colors.HexColor("#1a202c"))
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w / 2, h - 48, title)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#718096"))
    c.drawCentredString(w / 2, 28, f"Industrializer · Santos Corp. · Página {page_no}")


def _table(c, x, y, headers, rows, col_widths, row_h=19):
    c.setFont("Helvetica-Bold", 7.5)
    c.setStrokeColor(colors.HexColor("#cbd5e0"))
    curx = x
    for i, h in enumerate(headers):
        c.setFillColor(colors.HexColor("#2b6cb0"))
        c.rect(curx, y - row_h, col_widths[i], row_h, fill=1, stroke=1)
        c.setFillColor(colors.white)
        c.drawCentredString(curx + col_widths[i] / 2, y - row_h + 6, str(h))
        curx += col_widths[i]
    c.setFont("Helvetica", 7.2)
    for r, row in enumerate(rows):
        curx = x
        yy = y - row_h * (r + 2)
        for i, val in enumerate(row):
            c.setFillColor(colors.HexColor("#f7fafc") if r % 2 == 0 else colors.white)
            c.rect(curx, yy, col_widths[i], row_h, fill=1, stroke=1)
            c.setFillColor(colors.HexColor("#1a202c"))
            c.drawCentredString(curx + col_widths[i] / 2, yy + 6, str(val)[:28])
            curx += col_widths[i]


def export_preview_pdf(results, nodes, elements, structure_type, units, seal_path=None):
    default_name = f"Industrializer_memoria_{datetime.now():%Y%m%d_%H%M}.pdf"
    path = filedialog.asksaveasfilename(
        title="Guardar memoria de cálculo",
        defaultextension=".pdf",
        initialfile=default_name,
        filetypes=[("PDF", "*.pdf")],
    )
    if not path:
        raise RuntimeError("La exportación fue cancelada por el usuario.")

    watermark = _watermark_image(seal_path) if seal_path and Path(seal_path).exists() else None
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    u = units

    _header(c, "MEMORIA DE CÁLCULO", 1, watermark)
    c.setFont("Helvetica", 11)
    c.setFillColor(colors.HexColor("#2d3748"))
    info = [
        ("Tipo de estructura", "Pórtico 2D" if structure_type == "frame" else "Armadura 2D"),
        ("Sistema de unidades", u.label),
        ("Número de nodos", len(nodes)),
        ("Número de elementos", len(elements)),
        ("Fecha", datetime.now().strftime("%d/%m/%Y %H:%M")),
    ]
    yy = h - 105
    for label, value in info:
        c.drawString(70, yy, f"{label}:")
        c.setFont("Helvetica-Bold", 11)
        c.drawString(230, yy, str(value))
        c.setFont("Helvetica", 11)
        yy -= 25
    fs = results.get("FS_system")
    fs_txt = "sin esfuerzo" if fs == float("inf") else ("N/D" if fs is None else f"{fs:.3f}")
    c.setFont("Helvetica-Bold", 13)
    c.drawString(70, yy - 15, "Factor de Seguridad mínimo:")
    c.drawString(270, yy - 15, fs_txt)
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.HexColor("#718096"))
    c.drawCentredString(w / 2, 65, "Documento generado desde la previsualización de Industrializer.")
    c.showPage()

    _header(c, "REACCIONES Y DESPLAZAMIENTOS", 2, watermark)
    c.setFillColor(colors.HexColor("#2b6cb0"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(58, h - 95, "Reacciones en los apoyos")
    if structure_type == "frame":
        headers = ["Nodo", f"Rx [{u.force_symbol}]", f"Ry [{u.force_symbol}]", f"Mz [{u.force_symbol}·{u.length_symbol}]"]
        rows = []
        for nid, nr in results["node_results"].items():
            rx, ry, mz = u.force_out(nr["Rx"]), u.force_out(nr["Ry"]), u.moment_out(nr["Mz"])
            if abs(rx) > 1e-9 or abs(ry) > 1e-9 or abs(mz) > 1e-9:
                rows.append([nid, f"{rx:.3f}", f"{ry:.3f}", f"{mz:.3f}"])
    else:
        headers = ["Nodo", f"Rx [{u.force_symbol}]", f"Ry [{u.force_symbol}]"]
        rows = []
        for nid, nr in results["node_results"].items():
            rx, ry = u.force_out(nr["rx"]), u.force_out(nr["ry"])
            if abs(rx) > 1e-9 or abs(ry) > 1e-9:
                rows.append([nid, f"{rx:.3f}", f"{ry:.3f}"])
    if not rows:
        rows = [["—"] * len(headers)]
    _table(c, 58, h - 112, headers, rows, [80, 120, 120, 130][:len(headers)])

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#2b6cb0"))
    c.drawString(58, h - 300, "Desplazamientos y rotaciones nodales")
    if structure_type == "frame":
        headers = ["Nodo", f"u [{u.length_symbol}]", f"v [{u.length_symbol}]", "theta [rad]"]
        rows = [[nid, f"{u.length_out(nr['ux']):.5g}", f"{u.length_out(nr['uy']):.5g}", f"{nr['rz']:.5g}"]
                for nid, nr in results["node_results"].items()]
    else:
        headers = ["Nodo", f"u [{u.length_symbol}]", f"v [{u.length_symbol}]"]
        rows = [[nid, f"{u.length_out(nr['ux']):.5g}", f"{u.length_out(nr['uy']):.5g}"]
                for nid, nr in results["node_results"].items()]
    _table(c, 58, h - 317, headers, rows, [80, 120, 120, 130][:len(headers)])
    c.showPage()

    _header(c, "RESULTADOS POR ELEMENTO", 3, watermark)
    if structure_type == "frame":
        headers = ["Elem", "Nodos", f"N [{u.force_symbol}]", f"V_i/V_j [{u.force_symbol}]",
                   f"M_i/M_j [{u.force_symbol}·{u.length_symbol}]", "FS"]
        widths = [55, 75, 80, 95, 130, 55]
        rows = []
        for eid, er in list(results["elem_results"].items())[:20]:
            fs = er.get("FS")
            fs_txt = "∞" if fs == float("inf") else ("N/D" if fs is None else f"{fs:.3f}")
            rows.append([eid, f"{er['ni']}-{er['nj']}", f"{u.force_out(er['N_end']):.3f}",
                         f"{u.force_out(er['V_i']):.2f}/{u.force_out(er['V_j']):.2f}",
                         f"{u.moment_out(er['M_i']):.2f}/{u.moment_out(er['M_j']):.2f}", fs_txt])
    else:
        headers = ["Elem", "Nodos", f"N [{u.force_symbol}]", "Estado", "FS"]
        widths = [70, 100, 120, 120, 70]
        rows = []
        for eid, er in list(results["elem_results"].items())[:25]:
            fs = er.get("FS")
            fs_txt = "∞" if fs == float("inf") else ("N/D" if fs is None else f"{fs:.3f}")
            rows.append([eid, f"{er['ni']}-{er['nj']}", f"{u.force_out(er['N']):.3f}",
                         "Tracción" if er["N"] >= 0 else "Compresión", fs_txt])
    _table(c, 58, h - 92, headers, rows, widths)
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.HexColor("#718096"))
    c.drawString(58, 55, "Los diagramas se visualizaron previamente en el Editor Visual con escala automática.")
    c.save()
    return path
