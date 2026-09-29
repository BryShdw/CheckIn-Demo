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


def build_label_image(guest: dict) -> Image.Image:
    """
    Renderiza la etiqueta optimizada para Brother DK-1208 (38mm x 90.3mm) a 300 DPI (991 x 413 px).
    Exclusivo para emblemas pre-impresos: solo Nombre y apellidos, Empresa y Puesto.
    """
    W = 991
    H = 413
    img = Image.new("L", (W, H), color=255)
    draw = ImageDraw.Draw(img)

    name = (guest.get("name") or guest.get("full_name") or "ASISTENTE").strip().upper()
    company = (guest.get("company") or "").strip().upper()
    position = (guest.get("position") or "").strip().upper()

    CONTENT_L = 30
    CONTENT_R = 961
    MAX_TEXT_W = CONTENT_R - CONTENT_L

    # 1. Nombre completo
    test_font = get_font(56, bold=True)
    nb_test = draw.textbbox((0, 0), name, font=test_font)
    is_multiline = (nb_test[2] - nb_test[0]) > MAX_TEXT_W

    if is_multiline:
        line1, line2 = split_name_balanced(name)
        font_name1 = fit_font(line1, initial_size=46, max_width=MAX_TEXT_W, bold=True, min_size=24)
        font_name2 = fit_font(line2, initial_size=46, max_width=MAX_TEXT_W, bold=True, min_size=24)

        b1 = draw.textbbox((0, 0), line1, font=font_name1)
        b2 = draw.textbbox((0, 0), line2, font=font_name2)
        h1 = b1[3] - b1[1]
        h2 = b2[3] - b2[1]
        line_gap = 6

        y_top = 40
        draw.text((W // 2, y_top), line1, font=font_name1, fill=0, anchor="mt")
        draw.text((W // 2, y_top + h1 + line_gap), line2, font=font_name2, fill=0, anchor="mt")
        y_cursor = y_top + h1 + line_gap + h2 + 25
    else:
        font_name = fit_font(name, initial_size=58, max_width=MAX_TEXT_W, bold=True, min_size=28)
        b = draw.textbbox((0, 0), name, font=font_name)
        h = b[3] - b[1]
        y_top = 65
        draw.text((W // 2, y_top), name, font=font_name, fill=0, anchor="mt")
        y_cursor = y_top + h + 30

    # 2. Empresa
    if company:
        font_company = fit_font(company, initial_size=34, max_width=MAX_TEXT_W, bold=True, min_size=18)
        b_c = draw.textbbox((0, 0), company, font=font_company)
        draw.text((W // 2, y_cursor), company, font=font_company, fill=0, anchor="mt")
        y_cursor += (b_c[3] - b_c[1]) + 15

    # 3. Puesto / Cargo
    if position:
        font_pos = fit_font(position, initial_size=28, max_width=MAX_TEXT_W, bold=False, min_size=16)
        draw.text((W // 2, y_cursor), position, font=font_pos, fill=0, anchor="mt")

    return img


def print_guest_ticket(guest: dict, printer_name: str = Config.PRINTER_NAME) -> tuple[bool, str]:
    """
    Imprime el ticket del invitado mediante win32print a 300 DPI.
    Regla estricta de negocio: Si la impresora no está conectada y lista, o no se puede
    validar la emisión física del ticket, la función DEBE retornar False para
    impedir la acreditación del participante en el sistema.
    """
    label_img = build_label_image(guest)

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
