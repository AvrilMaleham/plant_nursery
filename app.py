"""Flask entry point. Wires the model, controllers, and views together."""

import os
import secrets
from pathlib import Path

from flask import Flask

from controller.nursery_controller import nursery_bp

ROOT = Path(__file__).resolve().parent

# The biggest request the site accepts. Plant photos are the only uploads, and
# a photo for a web page is well under this.
MAX_UPLOAD_MB = 5


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
    # The session cookie remembers who logged in, and it is signed with this
    # key. A key written in the code would let anyone who can read the code
    # sign a cookie for the team login. Set FLASK_SECRET_KEY to keep people
    # logged in across restarts. Without it, a new random key is made each
    # time the site starts, so everyone just has to log in again.
    app.secret_key = (
        os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
    )
    app.config.update(
        # The browser does not send the cookie when another site makes it
        # post a form here, which stops most cross-site request forgery.
        SESSION_COOKIE_SAMESITE="Lax",
        # Scripts on the page cannot read the cookie.
        SESSION_COOKIE_HTTPONLY=True,
        # Only for a site served over HTTPS. Turned on with
        # FLASK_COOKIE_SECURE=1, because the cookie would not be sent at all
        # over plain http://127.0.0.1.
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_COOKIE_SECURE") == "1",
        MAX_CONTENT_LENGTH=MAX_UPLOAD_MB * 1024 * 1024,
    )
    app.register_blueprint(nursery_bp)
    return app


app = create_app()

if __name__ == "__main__":
    # Debug mode swaps the error page for Flask's debugger, which shows the
    # code and lets anyone who can reach the site run Python. It is off unless
    # FLASK_DEBUG=1 is set while developing.
    app.run(
        debug=os.environ.get("FLASK_DEBUG") == "1",
        port=int(os.environ.get("PORT", "5000")),
    )
