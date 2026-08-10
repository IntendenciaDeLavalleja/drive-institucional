import os


def _int_env(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


bind = f"0.0.0.0:{_int_env('PORT', 5000)}"
workers = _int_env("GUNICORN_WORKERS", 2)
threads = _int_env("GUNICORN_THREADS", 4)
worker_class = "gthread"
timeout = _int_env("GUNICORN_TIMEOUT", 900)
graceful_timeout = _int_env("GUNICORN_GRACEFUL_TIMEOUT", 60)
keepalive = _int_env("GUNICORN_KEEPALIVE", 5)
accesslog = "-"
errorlog = "-"
capture_output = True
max_requests = 1000
max_requests_jitter = 100
forwarded_allow_ips = "*"
worker_tmp_dir = "/dev/shm"
