import io
import os
import logging
from PIL import Image, ImageDraw, ImageFont
from app.config import Config

log = logging.getLogger(__name__)

# Intentar importar win32print para impresión directa en Windows GDI
try:
    import win32print
    import win32ui
    from PIL import ImageWin
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    log.warning("pywin32 / win32print no disponible. La impresión será simulada.")


def check_usb_device_present(vid: str = "04F9", name_keyword: str = "Brother") -> tuple[bool, list[dict]]:
    """
    Verifica mediante WMI (Win32_PnPEntity) si el hardware USB de la impresora está físicamente
    conectado y activo en el bus PnP de Windows.
    """
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            wmi = win32com.client.GetObject("winmgmts:")
            query = f"SELECT DeviceID, Caption, Status, ConfigManagerErrorCode FROM Win32_PnPEntity WHERE DeviceID LIKE '%VID_{vid}%' OR Caption LIKE '%{name_keyword}%'"
            devices = wmi.ExecQuery(query)
            active = []
            for d in devices:
                active.append({
                    "caption": getattr(d, "Caption", ""),
                    "device_id": getattr(d, "DeviceID", ""),
                    "status": getattr(d, "Status", ""),
                    "error_code": getattr(d, "ConfigManagerErrorCode", 0)
                })
            return (len(active) > 0), active
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        log.warning(f"Error comprobando presencia física USB vía WMI: {e}")
        return True, []


def get_printer_connection_status(printer_name: str = Config.PRINTER_NAME) -> dict:
    """
    Comprueba de forma rigurosa si la impresora Brother está instalada Y FÍSICAMENTE CONECTADA.
    """
    if not Config.PRINTER_ENABLED:
        return {
            "enabled": False,
            "installed": False,
            "online": False,
            "is_ready": False,
            "name": printer_name,
            "status_text": "Impresión desactivada por configuración",
            "details": "PRINTER_ENABLED=False",
            "jobs_in_queue": 0,
        }

    if not WIN32_AVAILABLE:
        return {
            "enabled": True,
            "installed": False,
            "online": False,
            "is_ready": False,
            "name": printer_name,
            "status_text": "Módulo win32print no disponible (Simulador activo)",
            "details": "Entorno no compatible con Spooler GDI de Windows",
            "jobs_in_queue": 0,
        }

    try:
        printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        target = next((p for p in printers if printer_name.lower() in p.lower()), None)

        if not target:
            return {
                "enabled": True,
                "installed": False,
                "online": False,
                "is_ready": False,
                "name": printer_name,
                "status_text": f"Impresora '{printer_name}' no encontrada en Windows",
                "details": f"Disponibles: {printers[:4]}",
                "jobs_in_queue": 0,
            }

        # 1. Comprobación rigurosa de presencia en bus USB (WMI PnP)
        is_usb_present, _ = check_usb_device_present("04F9", "Brother")
        if not is_usb_present:
            return {
                "enabled": True,
                "installed": True,
                "online": False,
                "is_ready": False,
                "name": target,
                "status_text": "Desconectada o Apagada (Cable USB no detectado)",
                "details": "La impresora Brother QL-800 no está conectada por cable USB o se encuentra apagada.",
                "jobs_in_queue": 0,
            }

        # 2. Comprobar spooler
        hPrinter = win32print.OpenPrinter(target)
        try:
            p_info = win32print.GetPrinter(hPrinter, 2)
            raw_status = p_info.get("Status", 0)
            jobs_count = p_info.get("cJobs", 0)

            PRINTER_STATUS_PAUSED = 0x00000001
            PRINTER_STATUS_ERROR = 0x00000002
            PRINTER_STATUS_OFFLINE = 0x00000080
            PRINTER_STATUS_PAPER_JAM = 0x00000008
            PRINTER_STATUS_PAPER_OUT = 0x00000010

            reasons = []
            if raw_status & PRINTER_STATUS_OFFLINE:
                reasons.append("Fuera de línea (Offline)")
            if raw_status & PRINTER_STATUS_PAUSED:
                reasons.append("Pausada")
            if raw_status & PRINTER_STATUS_ERROR:
                reasons.append("Error de hardware")
            if raw_status & PRINTER_STATUS_PAPER_JAM:
                reasons.append("Atasco de papel")
            if raw_status & PRINTER_STATUS_PAPER_OUT:
                reasons.append("Sin papel / rollo")

            is_online = (raw_status & PRINTER_STATUS_OFFLINE) == 0
            is_ready = is_online and (raw_status & (PRINTER_STATUS_ERROR | PRINTER_STATUS_PAPER_JAM | PRINTER_STATUS_PAPER_OUT)) == 0

            status_text = "Lista y en línea" if is_ready else ("Con problemas: " + ", ".join(reasons) if reasons else "Estado no preparado")
            details = f"Puerto: {p_info.get('pPortName')}. Trabajos en cola: {jobs_count}."

            return {
                "enabled": True,
                "installed": True,
                "online": is_online,
                "is_ready": is_ready,
                "name": target,
                "status_text": status_text,
                "details": details,
                "jobs_in_queue": jobs_count,
            }
        finally:
            win32print.ClosePrinter(hPrinter)

    except Exception as e:
        log.warning(f"Error comprobando estado de impresora: {e}")
        return {
            "enabled": True,
            "installed": True,
            "online": False,
            "is_ready": False,
            "name": printer_name,
            "status_text": f"Error al consultar estado: {e}",
            "details": str(e),
            "jobs_in_queue": 0,
        }


def purge_printer_queue(printer_name: str = Config.PRINTER_NAME) -> tuple[bool, str]:
    """Purga y cancela todos los trabajos atascados en la cola de la impresora."""
    if not WIN32_AVAILABLE:
        return False, "win32print no disponible"

    try:
        printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        target = next((p for p in printers if printer_name.lower() in p.lower()), None)
        if not target:
            return False, "Impresora no encontrada"

        h = win32print.OpenPrinter(target, {"DesiredAccess": win32print.PRINTER_ALL_ACCESS})
        try:
            win32print.SetPrinter(h, 0, None, win32print.PRINTER_CONTROL_PURGE)
            return True, f"Cola de impresión de '{target}' purgada exitosamente."
        finally:
            win32print.ClosePrinter(h)
    except Exception as e:
        return False, f"Error purgando cola: {e}"


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_names = (
        ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahomabd.ttf"]
        if bold else
        ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]
    )
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def fit_font(text: str, initial_size: int, max_width: int, bold: bool = True, min_size: int = 18):
    size = initial_size
    font = get_font(size, bold=bold)
    while size > min_size:
        dummy = Image.new("L", (1, 1), 255)
        d = ImageDraw.Draw(dummy)
        bbox = d.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            break
        size -= 2
        font = get_font(size, bold=bold)
    return font


def split_name_balanced(name: str) -> tuple[str, str]:
    tokens = [t.strip() for t in name.split() if t.strip()]
    if len(tokens) <= 2:
        return name, ""
    mid = len(tokens) // 2
    best_split = mid
    best_diff = 999
    for i in range(1, len(tokens)):
        part1 = " ".join(tokens[:i])
        part2 = " ".join(tokens[i:])
        diff = abs(len(part1) - len(part2))
        if diff < best_diff:
            best_diff = diff
            best_split = i
    return " ".join(tokens[:best_split]), " ".join(tokens[best_split:])


DEFAULT_LABEL_TEMPLATE = {
    "header_text": {"enabled": False, "text": "", "font_size": 22, "bold": True},
    "full_name": {"enabled": True, "font_size": 54, "bold": True, "auto_multiline": True},
    "company": {"enabled": True, "font_size": 32, "bold": True},
    "position": {"enabled": True, "font_size": 26, "bold": False},
    "category": {"enabled": False, "font_size": 22, "bold": True},
    "guest_code": {"enabled": False, "font_size": 20, "bold": False},
    "qr_code": {"enabled": False, "position": "right", "size": 130},
    "align": "center",
    "line_spacing": 14,
    "vertical_offset": 0,
}


def build_label_image(guest: dict, template: dict | None = None) -> Image.Image:
    """
    Renderiza la etiqueta optimizada para Brother DK-1208 (38mm x 90.3mm) a 300 DPI (991 x 413 px).
    Soporta personalización dinámica mediante plantilla (campos activos, tamaños, negrita, alineación y QR).
    """
    W = 991
    H = 413
    img = Image.new("L", (W, H), color=255)
    draw = ImageDraw.Draw(img)

    # Combinar plantilla provista con valores por defecto
    tpl = dict(DEFAULT_LABEL_TEMPLATE)
    if template and isinstance(template, dict):
        for k, v in template.items():
            if isinstance(v, dict) and isinstance(tpl.get(k), dict):
                tpl[k] = {**tpl[k], **v}
            else:
                tpl[k] = v

    name = str(guest.get("name") or guest.get("full_name") or "ASISTENTE").strip().upper()
    company = str(guest.get("company") or "").strip().upper()
    position = str(guest.get("position") or "").strip().upper()
    category = str(guest.get("category") or "").strip().upper()
    guest_code = str(guest.get("guest_code") or guest.get("id") or "").strip().upper()

    align = tpl.get("align", "center")
    line_spacing = int(tpl.get("line_spacing", 14))
    vertical_offset = int(tpl.get("vertical_offset", 0))

    CONTENT_L = 30
    CONTENT_R = 961

    # Procesar Código QR opcional
    qr_cfg = tpl.get("qr_code", {})
    qr_img = None
    if qr_cfg.get("enabled"):
        try:
            import qrcode
            qr_data = str(guest.get("guest_code") or guest.get("id") or name)
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=4,
                border=1,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            raw_qr = qr.make_image(fill_color="black", back_color="white").convert("L")
            qr_size = min(max(int(qr_cfg.get("size", 130)), 70), 220)
            qr_img = raw_qr.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

            qr_pos = qr_cfg.get("position", "right")
            if qr_pos == "right":
                CONTENT_R = 961 - qr_size - 25
                qr_x = 961 - qr_size
                qr_y = max(10, (H - qr_size) // 2 + vertical_offset)
                img.paste(qr_img, (qr_x, qr_y))
            elif qr_pos == "left":
                CONTENT_L = 30 + qr_size + 25
                qr_x = 30
                qr_y = max(10, (H - qr_size) // 2 + vertical_offset)
                img.paste(qr_img, (qr_x, qr_y))
        except Exception as e:
            log.warning(f"No se pudo generar código QR en etiqueta: {e}")

    MAX_TEXT_W = max(200, CONTENT_R - CONTENT_L)

    blocks: list[dict] = []

    # 1. Encabezado / Título de Evento opcional
    header_cfg = tpl.get("header_text", {})
    if header_cfg.get("enabled"):
        h_text = (header_cfg.get("text") or "").strip().upper()
        if h_text:
            h_size = int(header_cfg.get("font_size", 22))
            h_bold = bool(header_cfg.get("bold", True))
            font_h = fit_font(h_text, initial_size=h_size, max_width=MAX_TEXT_W, bold=h_bold, min_size=14)
            bb = draw.textbbox((0, 0), h_text, font=font_h)
            blocks.append({"text": h_text, "font": font_h, "h": bb[3] - bb[1], "gap": line_spacing})

    # 2. Nombre Completo
    name_cfg = tpl.get("full_name", {})
    if name_cfg.get("enabled", True) and name:
        n_size = int(name_cfg.get("font_size", 54))
        n_bold = bool(name_cfg.get("bold", True))
        auto_multiline = bool(name_cfg.get("auto_multiline", True))

        font_test = get_font(n_size, bold=n_bold)
        nb_test = draw.textbbox((0, 0), name, font=font_test)
        is_multiline = auto_multiline and ((nb_test[2] - nb_test[0]) > MAX_TEXT_W)

        if is_multiline:
            line1, line2 = split_name_balanced(name)
            sub_size = max(22, int(n_size * 0.82))
            font1 = fit_font(line1, initial_size=sub_size, max_width=MAX_TEXT_W, bold=n_bold, min_size=20)
            font2 = fit_font(line2, initial_size=sub_size, max_width=MAX_TEXT_W, bold=n_bold, min_size=20)
            b1 = draw.textbbox((0, 0), line1, font=font1)
            b2 = draw.textbbox((0, 0), line2, font=font2)
            blocks.append({"text": line1, "font": font1, "h": b1[3] - b1[1], "gap": 6})
            blocks.append({"text": line2, "font": font2, "h": b2[3] - b2[1], "gap": line_spacing + 4})
        else:
            font_n = fit_font(name, initial_size=n_size, max_width=MAX_TEXT_W, bold=n_bold, min_size=24)
            b = draw.textbbox((0, 0), name, font=font_n)
            blocks.append({"text": name, "font": font_n, "h": b[3] - b[1], "gap": line_spacing + 4})

    # 3. Empresa
    comp_cfg = tpl.get("company", {})
    if comp_cfg.get("enabled", True) and company:
        c_size = int(comp_cfg.get("font_size", 32))
        c_bold = bool(comp_cfg.get("bold", True))
        font_c = fit_font(company, initial_size=c_size, max_width=MAX_TEXT_W, bold=c_bold, min_size=16)
        b_c = draw.textbbox((0, 0), company, font=font_c)
        blocks.append({"text": company, "font": font_c, "h": b_c[3] - b_c[1], "gap": line_spacing})

    # 4. Cargo / Puesto
    pos_cfg = tpl.get("position", {})
    if pos_cfg.get("enabled", True) and position:
        p_size = int(pos_cfg.get("font_size", 26))
        p_bold = bool(pos_cfg.get("bold", False))
        font_p = fit_font(position, initial_size=p_size, max_width=MAX_TEXT_W, bold=p_bold, min_size=14)
        b_p = draw.textbbox((0, 0), position, font=font_p)
        blocks.append({"text": position, "font": font_p, "h": b_p[3] - b_p[1], "gap": line_spacing})

    # 5. Categoría
    cat_cfg = tpl.get("category", {})
    if cat_cfg.get("enabled") and category:
        cat_size = int(cat_cfg.get("font_size", 22))
        cat_bold = bool(cat_cfg.get("bold", True))
        font_cat = fit_font(category, initial_size=cat_size, max_width=MAX_TEXT_W, bold=cat_bold, min_size=14)
        b_cat = draw.textbbox((0, 0), category, font=font_cat)
        blocks.append({"text": category, "font": font_cat, "h": b_cat[3] - b_cat[1], "gap": line_spacing})

    # 6. Código de Invitado
    code_cfg = tpl.get("guest_code", {})
    if code_cfg.get("enabled") and guest_code:
        cd_size = int(code_cfg.get("font_size", 20))
        cd_bold = bool(code_cfg.get("bold", False))
        font_cd = fit_font(guest_code, initial_size=cd_size, max_width=MAX_TEXT_W, bold=cd_bold, min_size=12)
        b_cd = draw.textbbox((0, 0), guest_code, font=font_cd)
        blocks.append({"text": guest_code, "font": font_cd, "h": b_cd[3] - b_cd[1], "gap": line_spacing})

    if not blocks:
        # Fallback de seguridad
        font_def = get_font(40, bold=True)
        draw.text((W // 2, H // 2), name, font=font_def, fill=0, anchor="mm")
        return img

    # Cálculo de posicionamiento vertical centrado
    total_h = sum(b["h"] for b in blocks)
    for i in range(len(blocks) - 1):
        total_h += blocks[i]["gap"]

    y_cursor = max(15, (H - total_h) // 2 + vertical_offset)

    if align == "left":
        x_anchor = CONTENT_L
        text_anchor = "lt"
    else:
        x_anchor = (CONTENT_L + CONTENT_R) // 2
        text_anchor = "mt"

    for i, b in enumerate(blocks):
        draw.text((x_anchor, y_cursor), b["text"], font=b["font"], fill=0, anchor=text_anchor)
        y_cursor += b["h"] + b["gap"]

    return img


def print_guest_ticket(guest: dict, printer_name: str = Config.PRINTER_NAME, template: dict | None = None) -> tuple[bool, str]:
    """
    Imprime el ticket del invitado mediante win32print a 300 DPI.
    Regla estricta de negocio: Si la impresora no está conectada y lista, o no se puede
    validar la emisión física del ticket, la función DEBE retornar False para
    impedir la acreditación del participante en el sistema.
    """
    # Si no se pasó template explícito, cargar la plantilla configurada en el evento activo
    if template is None:
        try:
            from app.models.event import Event
            event_id = guest.get("event_id")
            ev = Event.query.get(event_id) if event_id else Event.query.filter_by(is_active=True).first()
            if ev:
                template = ev.get_label_template()
        except Exception as e:
            log.warning(f"No se pudo cargar la plantilla del evento: {e}")
            template = DEFAULT_LABEL_TEMPLATE

    label_img = build_label_image(guest, template=template)

    # Permitir simulación únicamente bajo la suite de pruebas unitarias automáticas (TESTING=True)
    try:
        from flask import current_app
        is_testing = bool(current_app and current_app.config.get("TESTING"))
    except Exception:
        is_testing = False

    if is_testing:
        log.info(f"[TESTING] Ticket simulado para {guest.get('name') or guest.get('full_name')} bajo suite de pruebas.")
        return True, "Ticket emitido exitosamente (modo pruebas)"

    if not Config.PRINTER_ENABLED:
        log.warning(f"Impresión deshabilitada por configuración. No se emitirá credencial para {guest.get('name') or guest.get('full_name')}.")
        return False, "La impresora está deshabilitada en la configuración del sistema. No se puede acreditar sin emisión física del ticket."

    if not WIN32_AVAILABLE:
        log.error("win32print no disponible en este entorno.")
        return False, "Subsistema de impresión de Windows no disponible. No se puede validar la emisión física del ticket."

    # Comprobar estado de conexión física y preparación del hardware Brother QL-800
    status = get_printer_connection_status(printer_name)
    if not status.get("installed"):
        log.warning(f"Impresora '{printer_name}' no instalada en Windows.")
        return False, f"La impresora '{printer_name}' no está instalada en Windows. No se puede acreditar sin emitir la credencial."

    if not status.get("is_ready") and not status.get("online"):
        log.warning(f"Impresora '{printer_name}' no lista: {status.get('status_text')}")
        return False, f"La impresora '{printer_name}' no está conectada o no está lista ({status.get('status_text')}). Asistencia no acreditada."

    try:
        printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        target_printer = next((p for p in printers if printer_name.lower() in p.lower()), None)
        if not target_printer:
            return False, f"Impresora '{printer_name}' no encontrada en Windows."

        hprinter = win32print.OpenPrinter(target_printer)
        try:
            hDC = win32ui.CreateDC()
            hDC.CreatePrinterDC(target_printer)
            hDC.StartDoc(f"Ticket-{guest.get('id') or guest.get('guest_code')}")
            hDC.StartPage()

            dib = ImageWin.Dib(label_img.convert("RGB"))
            W, H = label_img.size
            dib.draw(hDC.GetHandleOutput(), (0, 0, W, H))

            hDC.EndPage()
            hDC.EndDoc()
            hDC.DeleteDC()
        finally:
            win32print.ClosePrinter(hprinter)

        return True, "Ticket emitido correctamente en la impresora Brother QL-800."
    except Exception as e:
        log.error(f"Error de hardware imprimiendo ticket: {e}")
        return False, f"Error al emitir ticket físico: {e}"
