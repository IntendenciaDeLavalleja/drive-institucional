from flask import Blueprint, abort, render_template, request, session

from ..extensions import db, limiter
from ..models import ShareAccessLog, ShareLink, utcnow
from .drive import stream_object

bp = Blueprint("share", __name__, url_prefix="/s")


def resolve(token):
    link = ShareLink.query.filter_by(token_hash=ShareLink.digest(token)).first()
    if not link:
        abort(404)
    return link


def log_access(link, event, outcome):
    db.session.add(
        ShareAccessLog(
            share_link_id=link.id,
            event=event,
            outcome=outcome,
            ip_address=request.remote_addr,
            user_agent=(request.user_agent.string or "")[:255],
        )
    )


@bp.route("/<token>", methods=["GET", "POST"])
@limiter.limit("30 per minute")
def open_share(token):
    link = resolve(token)
    if not link.usable:
        log_access(link, "VIEW", "UNAVAILABLE")
        db.session.commit()
        return render_template("share_unavailable.html"), 410
    if link.password_hash and session.get(f"share_{link.id}") is not True:
        if request.method == "POST" and link.check_password(request.form.get("password")):
            session[f"share_{link.id}"] = True
            log_access(link, "PASSWORD", "SUCCESS")
            db.session.commit()
        elif request.method == "POST":
            log_access(link, "PASSWORD", "FAILED")
            db.session.commit()
            return render_template("public_share.html", link=link, password_required=True, error=True), 401
        else:
            return render_template("public_share.html", link=link, password_required=True)
    log_access(link, "VIEW", "SUCCESS")
    link.last_accessed_at = utcnow()
    db.session.commit()
    return render_template("public_share.html", link=link, password_required=False)


@bp.get("/<token>/download")
@limiter.limit("60 per minute")
def download(token):
    link = (
        ShareLink.query.filter_by(token_hash=ShareLink.digest(token))
        .with_for_update()
        .first()
    )
    if not link:
        abort(404)
    entitlement_key = f"share_download_{link.id}"
    already_entitled = session.get(entitlement_key) is True
    base_available = (
        link.is_active
        and not link.file.deleted_at
        and (not link.expires_at or link.expires_at > utcnow())
    )
    has_quota = link.max_downloads is None or link.download_count < link.max_downloads
    if not base_available or (not has_quota and not already_entitled):
        log_access(link, "DOWNLOAD", "UNAVAILABLE")
        db.session.commit()
        return render_template("share_unavailable.html"), 410
    if link.password_hash and session.get(f"share_{link.id}") is not True:
        log_access(link, "DOWNLOAD", "PASSWORD_REQUIRED")
        db.session.commit()
        return render_template("public_share.html", link=link, password_required=True), 401
    # El primer request consume un cupo. Los Range posteriores del mismo navegador
    # conservan una habilitación de sesión para poder completar el archivo.
    if not already_entitled:
        link.download_count += 1
        session[entitlement_key] = True
    link.last_accessed_at = utcnow()
    log_access(link, "DOWNLOAD", "SUCCESS")
    db.session.commit()
    return stream_object(link.file)
