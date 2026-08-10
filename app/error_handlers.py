from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException


def register_error_handlers(app):
    """Render the same friendly error page for browser and API requests."""

    for status_code in (400, 401, 403, 404, 429, 500):
        app.register_error_handler(status_code, _http_error)
    app.register_error_handler(HTTPException, _http_error)


def _http_error(error):
    status_code = error.code if isinstance(error, HTTPException) else 500
    messages = {
        400: "La solicitud no es válida.",
        401: "Necesitás iniciar sesión para continuar.",
        403: "No tenés permisos para acceder a este recurso.",
        404: "La página que buscás no existe.",
        429: "Límite de peticiones excedido. Intentá nuevamente más tarde.",
        500: "Ocurrió un error interno del servidor.",
    }
    message = messages.get(status_code, getattr(error, "description", "Ocurrió un error."))

    if status_code == 500:
        from .extensions import db

        db.session.rollback()

    if request.is_json or request.path.startswith("/api/"):
        return jsonify({"error": "Error", "message": message, "code": status_code}), status_code

    return render_template(
        "errors.html",
        error=error,
        code=status_code,
        message=message,
    ), status_code
