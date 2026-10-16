"""Flask entry point. Wires the model, controllers, and views together."""

from pathlib import Path

from flask import Flask

from controller.nursery_controller import nursery_bp

ROOT = Path(__file__).resolve().parent


def create_app() -> Flask:
    """
    Create the Flask application and register its controllers.

    Templates and static files live under view/ so the interface stays
    separate from the model and the controllers.

    :return (Flask): The configured application
    """
    app = Flask(
        __name__,
        template_folder=str(ROOT / "view" / "templates"),
        static_folder=str(ROOT / "view" / "static"),
    )
    app.register_blueprint(nursery_bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
