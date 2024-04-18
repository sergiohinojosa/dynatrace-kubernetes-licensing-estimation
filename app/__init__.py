from flask import Flask
from .cache import cache
import logging
from logging.config import dictConfig

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            }, 
            "rotating-handler": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "log/app.log",
                "maxBytes": 1000000,
                "backupCount": 5,
                "formatter": "default",
            },
        },
        "root": {"level": "INFO", "handlers": ["console", "rotating-handler"]},
    }
)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Initialize the app
app = Flask(__name__, instance_relative_config=True)

# Initialize Cache
cache.init_app(app)

# Init views
# Load the views
from app import views

# Load the config file
app.config.from_object('config')