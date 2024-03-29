from flask import Flask
from .cache import cache

# Initialize the app
app = Flask(__name__, instance_relative_config=True)

# Initialize Cache
cache.init_app(app)

# Init views
# Load the views
from app import views

# Load the config file
app.config.from_object('config')