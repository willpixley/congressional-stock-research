"""Gunicorn *development* config file"""

wsgi_app = "project.wsgi:application"
loglevel = "debug"
workers = 2
bind = "0.0.0.0:8000"
reload = True
accesslog = errorlog = "/var/log/gunicorn/dev.log"
capture_output = True
pidfile = "/var/run/gunicorn/dev.pid"
daemon = True