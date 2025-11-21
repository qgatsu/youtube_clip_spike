from flask import Flask

from .config import load_app_config
from .routes import register_routes


def create_app() -> Flask:
    app = Flask(__name__)
    app_config = load_app_config()
    app.config.update(app_config)

    register_routes(app)
    return app
