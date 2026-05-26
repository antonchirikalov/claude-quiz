import os
import pathlib

from flask import Flask

from app.routes import bp

_ROOT = pathlib.Path(__file__).parent.parent


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(_ROOT / "templates"),
        static_folder=str(_ROOT / "static"),
        instance_relative_config=True,
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

    if test_config:
        app.config.update(test_config)

    app.register_blueprint(bp)
    return app
