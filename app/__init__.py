import os
import uuid
from pathlib import Path

from flask import Flask, g, redirect, request, send_from_directory, url_for
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import CONFIGS
from .extensions import csrf, db, limiter, login_manager, mail, migrate
from .models import User
from .storage import storage


def create_app(config_name=None, overrides=None):
    name = config_name or os.getenv("FLASK_CONFIG", "default")
    app = Flask(__name__)
    public_dir = Path(app.root_path).parent / "public"

    @app.get("/public/<path:filename>")
    def public_asset(filename):
        return send_from_directory(public_dir, filename)

    app.config.from_object(CONFIGS[name])
    if overrides:
        app.config.update(overrides)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY es obligatoria")
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL es obligatoria")

    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=app.config["TRUSTED_PROXY_COUNT"],
        x_proto=app.config["TRUSTED_PROXY_COUNT"],
        x_host=app.config["TRUSTED_PROXY_COUNT"],
    )
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Iniciá sesión para continuar."
    csrf.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    storage.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.before_request
    def request_context():
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    @app.after_request
    def secure_headers(response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if current_user.is_authenticated:
            response.headers["Cache-Control"] = "no-store"
        return response

    from .routes.auth import bp as auth_bp
    from .routes.drive import bp as drive_bp
    from .routes.public_share import bp as share_bp
    from .routes.units import bp as units_bp
    from .routes.users import bp as users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(drive_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(share_bp)
    app.register_blueprint(units_bp)

    from .error_handlers import register_error_handlers

    register_error_handlers(app)

    from .commands import create_admin, init_storage, prune_expired_files

    app.cli.add_command(create_admin)
    app.cli.add_command(init_storage)
    app.cli.add_command(prune_expired_files)

    @app.get("/health")
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
            storage.healthcheck()
        except Exception:
            db.session.rollback()
            app.logger.exception("Falló la verificación de salud")
            return {"status": "unavailable"}, 503
        return {"status": "ok"}, 200

    @app.get("/")
    def root():
        return redirect(url_for("drive.index"))

    @app.template_filter("filesize")
    def filesize(value):
        size = float(value or 0)
        units = ["B", "KB", "MB", "GB", "TB"]
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024

    @app.template_filter("datetime_local")
    def datetime_local(value):
        return value.strftime("%d/%m/%Y %H:%M") if value else "—"

    return app
