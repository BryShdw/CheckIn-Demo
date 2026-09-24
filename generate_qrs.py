"""
generate_qrs.py
---------------
Genera un codigo QR por cada invitado en guests.csv.
- Guarda los QR como PNG en la carpeta qr_output/
- Genera tarjetas con: ID, Nombres y Apellidos, Empresa y Cargo
- Opcionalmente genera un documento Word con todos los QR (para imprimir tarjetas)

Uso:
    python generate_qrs.py                   # solo PNG
    python generate_qrs.py --word            # PNG + documento Word
    python generate_qrs.py --word --open     # abre el doc Word al terminar
"""
import sys, io
# Forzar UTF-8 en stdout para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import csv
import os
import argparse
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

# ─── Configuración ────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
CSV_FILE    = BASE_DIR / "guests.csv"
OUTPUT_DIR  = BASE_DIR / "qr_output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Tamaño de la tarjeta en píxeles (~9x6cm a 150dpi)
CARD_W, CARD_H = 850, 567
BG_COLOR   = (255, 255, 255)
TEXT_COLOR = (25, 25, 25)
ACCENT     = (20, 60, 140)   # azul evento

# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_font(size: int, bold: bool = True):
    candidates = [
        ("C:/Windows/Fonts/arialbd.ttf", True),
        ("C:/Windows/Fonts/arial.ttf", False),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", True),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", False),
    ]
    for path, is_bold in candidates:
        if bold and not is_bold:
            continue
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_qr_image(data: str, size: int = 300) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((size, size), Image.LANCZOS)


def make_card(guest: dict) -> Image.Image:
    """
    Genera tarjeta de invitación con:
    - Encabezado evento
    - Nombre completo
    - Empresa
    - Cargo
    - Código ID + QR
    """
    card = Image.new("RGB", (CARD_W, CARD_H), BG_COLOR)
    draw = ImageDraw.Draw(card)

    # Franja superior
    draw.rectangle([0, 0, CARD_W, 85], fill=ACCENT)
    draw.text((35, 25), "🎟  INVITACION OFICIAL — DEMO 2026", font=get_font(28), fill=(255, 255, 255))

    # QR en el lateral derecho
    qr_size = 280
    qr_img  = make_qr_image(guest["id"], size=qr_size)
    qr_x    = CARD_W - qr_size - 40
    qr_y    = 115
    card.paste(qr_img, (qr_x, qr_y))

    # Texto ID bajo el QR
    draw.text((qr_x + (qr_size // 2), qr_y + qr_size + 12), guest["id"],
              font=get_font(22, bold=False), fill=(100, 100, 100), anchor="mm")

    # Datos (lado izquierdo)
    left_x = 40
    y      = 120

    # Nombres y Apellidos
    name = guest["name"]
    font_name = get_font(32)
    if len(name) > 24:
        words = name.split()
        mid = len(words) // 2
        name = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])
    draw.text((left_x, y), name, font=font_name, fill=TEXT_COLOR)
    y += 85 if "\n" in name else 55

    # Separador sutil
    draw.line([(left_x, y), (qr_x - 30, y)], fill=(220, 220, 220), width=2)
    y += 20

    # Empresa
    if guest.get("company"):
        draw.text((left_x, y), "EMPRESA", font=get_font(16, bold=False), fill=(140, 140, 140))
        y += 24
        draw.text((left_x, y), guest["company"], font=get_font(24), fill=ACCENT)
        y += 45

    # Cargo
    if guest.get("position"):
        draw.text((left_x, y), "CARGO", font=get_font(16, bold=False), fill=(140, 140, 140))
        y += 24
        draw.text((left_x, y), guest["position"], font=get_font(22, bold=False), fill=(60, 60, 60))
        y += 40

    # Pie inferior
    draw.rectangle([0, CARD_H - 45, CARD_W, CARD_H], fill=(245, 245, 248))
    draw.text((35, CARD_H - 32), "Muestra este código QR en la entrada para tu registro y etiqueta.",
              font=get_font(17, bold=False), fill=(130, 130, 130))

    # Borde exterior
    draw.rectangle([0, 0, CARD_W - 1, CARD_H - 1], outline=(210, 210, 210), width=2)

    return card


def generate_word_doc(guests: list, output_path: Path):
    from docx import Document
    from docx.shared import Inches, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    for section in doc.sections:
        section.top_margin    = Cm(1)
        section.bottom_margin = Cm(1)
        section.left_margin   = Cm(1)
        section.right_margin  = Cm(1)

    for i, guest in enumerate(guests):
        img_path = OUTPUT_DIR / f"{guest['id']}_card.png"
        card = make_card(guest)
        card.save(str(img_path), dpi=(150, 150))

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture(str(img_path), width=Inches(8.0))

        if i < len(guests) - 1:
            doc.add_page_break()

    doc.save(str(output_path))
    print(f"  [OK] Documento Word guardado: {output_path}")


def load_guests_from_csv(csv_path: Path) -> list[dict]:
    guests = []
    content = ""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            content = csv_path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue

    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        gid = (row.get("ID") or row.get("id") or "").strip()
        if not gid:
            continue
        guests.append({
            "id":       gid,
            "name":     (row.get("Nombres y Apellidos") or row.get("Nombre") or "").strip(),
            "company":  (row.get("Empresa") or "").strip(),
            "position": (row.get("Cargo") or "").strip(),
        })
    return guests


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Genera QRs e invitaciones desde guests.csv.")
    parser.add_argument("--word", action="store_true", help="Genera documento Word con las tarjetas")
    parser.add_argument("--open", action="store_true", help="Abre el documento Word al terminar")
    args = parser.parse_args()

    guests = load_guests_from_csv(CSV_FILE)
    print(f"\n[QR] Generando QR e invitaciones para {len(guests)} invitados desde {CSV_FILE.name}...\n")

    for guest in guests:
        gid = guest["id"]

        # PNG del QR solo
        qr_img = make_qr_image(gid, size=400)
        qr_path = OUTPUT_DIR / f"{gid}_qr.png"
        qr_img.save(str(qr_path))

        # PNG de la tarjeta completa
        card = make_card(guest)
        card_path = OUTPUT_DIR / f"{gid}_card.png"
        card.save(str(card_path), dpi=(150, 150))

        print(f"  [OK] {gid}  ->  {guest['name']} ({guest['company']})")

    print(f"\n[DIR] Archivos guardados en: {OUTPUT_DIR}\n")

    if args.word:
        try:
            word_path = BASE_DIR / "invitaciones_demo.docx"
            generate_word_doc(guests, word_path)

            if args.open:
                import subprocess
                subprocess.Popen(["start", str(word_path)], shell=True)
        except ImportError:
            print("  [WARN] python-docx no instalado. Ejecuta: pip install python-docx")


if __name__ == "__main__":
    main()
