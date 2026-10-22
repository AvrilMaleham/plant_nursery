"""Shared request setup for the nursery controllers."""

import uuid
from functools import wraps
from typing import Callable

from flask import (
    Blueprint,
    Response,
    flash,
    g,
    redirect,
    request,
    session,
    url_for,
)

from model.database import SessionLocal, init_db
from model.exceptions import (
    InsufficientStockError,
    LoginFailedError,
    NotAuthorisedError,
    OrderCannotBeCancelledError,
    OrderCannotBeCollectedError,
    OrderNotAllowedError,
)
from model.nursery_system import NurserySystem
from model.user import TEAM_ROLE

nursery_bp = Blueprint("nursery", __name__)
_database_ready = False

# These are the failures a screen should explain, rather than a traceback.
RULE_ERRORS = (
    ValueError,
    TypeError,
    LoginFailedError,
    NotAuthorisedError,
    InsufficientStockError,
    OrderNotAllowedError,
    OrderCannotBeCollectedError,
    OrderCannotBeCancelledError,
)


def system() -> NurserySystem:
    """
    Return the nursery system for this request.

    :return (NurserySystem): The system bound to the open database session
    """
    return g.system


def is_team() -> bool:
    """
    Return whether the logged-in person is the nursery team.

    :return (bool): True when the current login has the team role
    """
    user = system().current_user
    return user is not None and user.role == TEAM_ROLE


@nursery_bp.before_request
def open_nursery() -> None:
    """Open a database session and restore the logged-in person, if any."""
    if request.endpoint == "static":
        return
    global _database_ready
    if not _database_ready:
        init_db()
        _database_ready = True
    g.db = SessionLocal()
    g.system = NurserySystem(g.db)
    raw_user_id = session.get("user_id")
    if not raw_user_id:
        return
    try:
        found = g.system.resume(uuid.UUID(raw_user_id))
    except ValueError:
        found = False
    if not found:
        session.clear()


@nursery_bp.teardown_request
def close_nursery(error: BaseException | None) -> None:
    """
    Commit the request when it succeeded, and always close the session.

    :param error (BaseException | None): An error raised while handling the
        request, or None
    """
    db = g.pop("db", None)
    if db is None:
        return
    if error is None:
        db.commit()
    else:
        db.rollback()
    db.close()


@nursery_bp.after_request
def keep_pages_fresh(response: Response) -> Response:
    """
    Stop the browser from showing a logged-in page after logout.

    The back button would otherwise restore the previous page from its
    cache, even though the session has already been cleared.

    :param response (Response): The page or redirect about to be sent
    :return (Response): The same response, marked so it is not stored
    """
    response.headers["Cache-Control"] = "no-store"
    return response


@nursery_bp.app_context_processor
def nav_context() -> dict[str, object]:
    """
    Give every template the logged-in person, for navigation only.

    :return (dict[str, object]): The current user and whether they are the team
    """
    current = getattr(g, "system", None)
    user = current.current_user if current is not None else None
    return {
        "current_user": user,
        "is_team": user is not None and user.role == TEAM_ROLE,
    }


def signed_in(view: Callable) -> Callable:
    """
    Send a person who is not logged in to the login screen.

    :param view (Callable): The controller to protect
    :return (Callable): The wrapped controller
    """

    @wraps(view)
    def wrapper(*args: object, **kwargs: object) -> object:
        if system().current_user is None:
            return redirect(url_for("nursery.login"))
        return view(*args, **kwargs)

    return wrapper


def explain(error: Exception) -> object:
    """
    Undo a refused action and send the person back with the model's reason.

    :param error (Exception): The refusal from the model
    :return (object): A redirect to the previous screen, or the dashboard
    """
    g.db.rollback()
    flash(str(error), "error")
    target = request.referrer or ""
    if not target.startswith(request.host_url):
        target = url_for("nursery.home")
    return redirect(target)
