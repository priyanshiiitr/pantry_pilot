"""Tests for the admin Overview aggregations (services/dashboard.py).

Covers the three functions behind GET /api/admin/overview: the headline stats,
the "Live network activity" pipeline counts, and the merged recent-activity feed.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import (
    Decision,
    DecisionStatus,
    Delivery,
    DeliveryStatus,
    Driver,
    Offer,
    OfferStatus,
    Pantry,
    PantryResponse,
    Restaurant,
    Role,
    User,
)
from pantrypilot.services.dashboard import (
    get_network_activity,
    get_overview_stats,
    get_recent_network_activity,
)


def make_restaurant(db_session: Session, name: str = "R") -> Restaurant:
    user = User(email=f"{name}@test.local", role=Role.RESTAURANT, display_name=name, password_hash="x")
    restaurant = Restaurant(user=user, name=name, address="x", lat=47.6, lon=-122.3)
    db_session.add_all([user, restaurant])
    db_session.commit()
    return restaurant


def make_pantry(db_session: Session, name: str = "P") -> Pantry:
    user = User(email=f"{name}@test.local", role=Role.PANTRY, display_name=name, password_hash="x")
    pantry = Pantry(user=user, name=name, address="x", lat=47.6, lon=-122.3)
    db_session.add_all([user, pantry])
    db_session.commit()
    return pantry


def make_offer(db_session: Session, restaurant: Restaurant, status: str = OfferStatus.POSTED, **overrides) -> Offer:
    offer = Offer(
        restaurant=restaurant,
        title=overrides.pop("title", "Surplus food"),
        description="D",
        quantity_text="20 meals",
        pickup_deadline=utc_now() + timedelta(hours=2),
        status=status,
        **overrides,
    )
    db_session.add(offer)
    db_session.commit()
    return offer


def test_stats_count_active_offers(db_session: Session) -> None:
    """Offers still in play count; delivered ones don't."""
    restaurant = make_restaurant(db_session)
    make_offer(db_session, restaurant, OfferStatus.POSTED)
    make_offer(db_session, restaurant, OfferStatus.DRIVER_ASSIGNED)
    make_offer(db_session, restaurant, OfferStatus.DELIVERED)

    stats = get_overview_stats(db_session)

    assert stats["active_offers"] == 2


def test_match_rate_is_none_before_anything_finishes(db_session: Session) -> None:
    """A rate over zero finished deliveries would be a divide-by-zero, so it stays None.

    The UI shows an em dash rather than a made-up "0%" or "100%".
    """
    assert get_overview_stats(db_session)["match_rate"] is None


def test_match_rate_counts_delivered_against_finished(db_session: Session) -> None:
    """One delivered and one cancelled is a 50% success rate."""
    restaurant = make_restaurant(db_session)
    pantry = make_pantry(db_session)
    offer = make_offer(db_session, restaurant)
    db_session.add_all(
        [
            Delivery(
                offer=offer, pantry=pantry, status=DeliveryStatus.DELIVERED,
                pantry_response=PantryResponse.ACCEPTED, delivered_at=utc_now(),
            ),
            Delivery(offer=offer, pantry=pantry, status=DeliveryStatus.CANCELLED),
        ]
    )
    db_session.commit()

    assert get_overview_stats(db_session)["match_rate"] == 50.0


def test_trend_is_none_when_yesterday_had_nothing(db_session: Session) -> None:
    """With no history there is nothing honest to compare against, so no arrow is shown."""
    restaurant = make_restaurant(db_session)
    make_offer(db_session, restaurant)

    assert get_overview_stats(db_session)["active_offers_change"] is None


def test_trend_compares_today_against_yesterday(db_session: Session) -> None:
    """Two offers today against one yesterday is +100%.

    The two "today" offers keep their default created_at of now, which is always
    inside the [midnight, now] window the service asks for. The "yesterday" one
    is pinned an hour before midnight rather than to a fixed clock time, so the
    test doesn't depend on what time of day it happens to run.
    """
    an_hour_before_midnight = utc_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=1)

    restaurant = make_restaurant(db_session)
    make_offer(db_session, restaurant)
    make_offer(db_session, restaurant)
    yesterdays_offer = make_offer(db_session, restaurant)
    yesterdays_offer.created_at = an_hour_before_midnight
    db_session.commit()

    assert get_overview_stats(db_session)["active_offers_change"] == 100.0


def test_pending_decisions_are_counted(db_session: Session) -> None:
    """Only pending decisions count — answered ones are no longer waiting on anyone."""
    restaurant = make_restaurant(db_session)
    offer = make_offer(db_session, restaurant)
    db_session.add_all(
        [
            Decision(offer=offer, kind="ask_admin", interrupt_id="i1", interrupt_name="n", card={}),
            Decision(
                offer=offer, kind="ask_admin", interrupt_id="i2", interrupt_name="n", card={},
                status=DecisionStatus.ANSWERED,
            ),
        ]
    )
    db_session.commit()

    assert get_overview_stats(db_session)["pending_decisions"] == 1


def test_network_activity_counts_each_pipeline_stage(db_session: Session) -> None:
    """Each count reflects a real stage: posting, evaluating, receiving, en route, on duty."""
    restaurant = make_restaurant(db_session)
    pantry = make_pantry(db_session)
    offer = make_offer(db_session, restaurant, OfferStatus.AGENT_WORKING)

    driver_user = User(email="d@test.local", role=Role.DRIVER, display_name="D", password_hash="x")
    driver = Driver(user=driver_user, name="D", lat=47.6, lon=-122.3, on_duty=True)
    db_session.add_all([driver_user, driver])
    db_session.add(Delivery(offer=offer, pantry=pantry, status=DeliveryStatus.DRIVER_ASSIGNED, driver=driver))
    db_session.commit()

    network = get_network_activity(db_session)

    assert network["restaurants_posting"] == 1
    assert network["offers_being_evaluated"] == 1
    assert network["pantries_receiving_today"] == 1
    assert network["drivers_en_route"] == 1
    assert network["drivers_on_duty"] == 1


def test_off_duty_drivers_are_not_counted_as_active(db_session: Session) -> None:
    """A driver who clocked off isn't part of tonight's capacity."""
    user = User(email="off@test.local", role=Role.DRIVER, display_name="D", password_hash="x")
    db_session.add_all([user, Driver(user=user, name="D", lat=47.6, lon=-122.3, on_duty=False)])
    db_session.commit()

    assert get_network_activity(db_session)["drivers_on_duty"] == 0


def test_recent_activity_merges_sources_newest_first(db_session: Session) -> None:
    """Offers, matches and escalations land in one feed, ordered by when they happened."""
    restaurant = make_restaurant(db_session)
    pantry = make_pantry(db_session)
    offer = make_offer(db_session, restaurant, title="Bread")
    db_session.add(Delivery(offer=offer, pantry=pantry, status=DeliveryStatus.PLANNED))
    db_session.add(
        Decision(
            offer=offer, kind="ask_admin", interrupt_id="i1", interrupt_name="n",
            card={"title": "Which pantry should get this?"},
        )
    )
    db_session.commit()

    events = get_recent_network_activity(db_session)
    kinds = [event["kind"] for event in events]

    assert "offer_posted" in kinds
    assert "matched" in kinds
    assert "needs_human" in kinds
    assert [event["at"] for event in events] == sorted((e["at"] for e in events), reverse=True)


def test_recent_activity_uses_the_agents_own_decision_title(db_session: Session) -> None:
    """The feed shows what the agent actually wrote when it escalated, not a generic label."""
    restaurant = make_restaurant(db_session)
    offer = make_offer(db_session, restaurant)
    db_session.add(
        Decision(
            offer=offer, kind="ask_admin", interrupt_id="i1", interrupt_name="n",
            card={"title": "Spoilage risk on the cream pastries"},
        )
    )
    db_session.commit()

    escalations = [e for e in get_recent_network_activity(db_session) if e["kind"] == "needs_human"]

    assert escalations[0]["detail"] == "Spoilage risk on the cream pastries"


def test_recent_activity_survives_a_decision_with_an_empty_card(db_session: Session) -> None:
    """A card missing its title falls back to the offer's own title rather than raising."""
    restaurant = make_restaurant(db_session)
    offer = make_offer(db_session, restaurant, title="Unsold sandwiches")
    db_session.add(Decision(offer=offer, kind="ask_admin", interrupt_id="i1", interrupt_name="n", card={}))
    db_session.commit()

    escalations = [e for e in get_recent_network_activity(db_session) if e["kind"] == "needs_human"]

    assert escalations[0]["detail"] == "Unsold sandwiches"


def test_recent_activity_is_empty_on_a_fresh_system(db_session: Session) -> None:
    """Nothing has happened yet is an empty list, not an error."""
    assert get_recent_network_activity(db_session) == []
