from __future__ import annotations

import io
from typing import Dict, List
import requests
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _download_image_to_bytes(session: requests.Session, url: str) -> bytes:
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def _fit_image_to_box(img: Image.Image, max_w: float, max_h: float) -> Image.Image:
    img = img.copy()
    img.thumbnail((max_w, max_h))
    return img


MARGIN_LEFT = 20 * mm
MARGIN_RIGHT = 20 * mm
MARGIN_TOP = 20 * mm
MARGIN_BOTTOM = 20 * mm

PHOTO_BOX_W = 70 * mm
PHOTO_BOX_H = 90 * mm
COLUMN_GAP = 10 * mm
LINE_SPACING = 5


def _draw_wrapped_text(c: canvas.Canvas, text: str, x: float, y: float, max_width: float, font_name: str, font_size: int) -> float:
    """Desenha texto com quebra de linha automática, retornando o y após escrever."""
    if not text:
        return y
    c.setFont(font_name, font_size)
    words = text.split()
    line = ""
    for word in words:
        test = (line + " " + word).strip()
        if pdfmetrics.stringWidth(test, font_name, font_size) <= max_width:
            line = test
        else:
            c.drawString(x, y, line)
            y -= font_size + LINE_SPACING
            line = word
    if line:
        c.drawString(x, y, line)
        y -= font_size + LINE_SPACING
    return y


def build_pdf(session: requests.Session, presos: List[Dict[str, str]], out_path: str) -> None:
    """Gera PDF A4, 1 preso por página, com foto e dados formatados dentro das margens."""
    c = canvas.Canvas(out_path, pagesize=A4)
    page_w, page_h = A4

    content_x = MARGIN_LEFT
    content_y_top = page_h - MARGIN_TOP
    content_w = page_w - MARGIN_LEFT - MARGIN_RIGHT

    for preso in presos:
        # Cabeçalho
        title = f"{preso.get('nome','')}"
        subtitle = f"Código: {preso.get('id','')}   |   Ala: {preso.get('ala','')}   |   Cela: {preso.get('cela','')}"

        c.setFont("Helvetica-Bold", 18)
        c.drawString(content_x, content_y_top, title)
        c.setFont("Helvetica", 11)
        c.drawString(content_x, content_y_top - 18, subtitle)

        y_cursor = content_y_top - 18 - 14

        # Layout principal: foto à esquerda, dados à direita
        x_photo = content_x
        y_photo_top = y_cursor - 6
        y_photo = y_photo_top - PHOTO_BOX_H

        # Desenha foto
        img_bytes = None
        try:
            url = preso.get("imagem_link", "")
            if url:
                img_bytes = _download_image_to_bytes(session, url)
        except Exception:
            img_bytes = None
        if img_bytes:
            try:
                img = Image.open(io.BytesIO(img_bytes))
                img = _fit_image_to_box(img, PHOTO_BOX_W, PHOTO_BOX_H)
                c.drawImage(ImageReader(img), x_photo, y_photo, width=img.width, height=img.height, preserveAspectRatio=True, mask='auto')
            except Exception:
                pass

        # Coluna de dados à direita da foto
        x_col = x_photo + PHOTO_BOX_W + COLUMN_GAP
        col_w = content_x + content_w - x_col
        y_col = y_photo_top

        # Bloco 1: Dados Pessoais
        c.setFont("Helvetica-Bold", 13)
        c.drawString(x_col, y_col, "Dados Pessoais")
        y_col -= 16

        def put(label: str, key: str, font_size: int = 11):
            nonlocal y_col
            value = preso.get(key, "")
            if not value:
                return
            c.setFont("Helvetica-Bold", font_size)
            c.drawString(x_col, y_col, f"{label}:")
            y_col -= font_size + 2
            y_col = _draw_wrapped_text(c, value, x_col, y_col, col_w, "Helvetica", font_size)

        put("Mãe", "mae")
        put("Pai", "pai")
        put("Nascimento", "nascimento")
        put("CPF", "cpf")
        put("Cidade Origem", "cidade_origem")
        put("Estado Origem", "estado_origem")
        put("Endereço", "endereco")

        # Espaço antes do segundo bloco
        y_col -= 6
        c.setFont("Helvetica-Bold", 13)
        c.drawString(x_col, y_col, "Características")
        y_col -= 16

        put("Cor / Etnia", "cor_etnia")
        put("Rosto", "rosto")
        put("Olhos", "olhos")
        put("Nariz", "nariz")
        put("Boca", "boca")
        put("Dentes", "dentes")
        put("Cabelos", "cabelos")
        put("Altura", "altura")
        put("Sinais Particulares", "sinais_particulares")

        # Garante que nada ultrapassou as margens (nova página)
        c.showPage()

    c.save()


