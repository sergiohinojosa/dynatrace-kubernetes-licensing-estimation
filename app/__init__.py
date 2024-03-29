from flask import Flask
from .cache import cache

# Initialize the app
app = Flask(__name__, instance_relative_config=True)
cache.init_app(app)

# Load the config file
app.config.from_object('config')