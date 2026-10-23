from flask import Blueprint, render_template

from ...models import SLOTS

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return render_template("main/index.html", slots=SLOTS)


@bp.get("/health")
def health():
    return {"status": "ok"}
