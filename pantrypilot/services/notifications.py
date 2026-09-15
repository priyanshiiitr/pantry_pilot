"""Sending a plain-English message to a user's notification list.

DETERMINISTIC CODE: this just saves a row. Deciding WHAT to tell someone is up to
whoever calls this — an agent action tool, or a future deterministic route.
"""

from sqlalchemy.orm import Session

from pantrypilot.models import Notification


def notify_user(session: Session, user_id: int, message: str, link: str | None = None) -> Notification:
    """Add a notification for `user_id`. `link` is an optional frontend path to open."""
    notification = Notification(user_id=user_id, message=message, link=link)
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification
