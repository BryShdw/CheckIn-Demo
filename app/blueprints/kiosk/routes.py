from flask import Blueprint, render_template

kiosk_bp = Blueprint("kiosk", __name__)


@kiosk_bp.route("/")
def index():
    return render_template("kiosk/index.html")
