"""
Integration tests for three nursery workflows.

Each test starts at a screen, follows the links and forms a person would use,
and checks the page that comes back. The records are read again in a new
login, so the result has to have been stored in PostgreSQL.

Pages are read through tests/web.py, which gives the words, the labelled
values, and the table rows a person would see. Nothing here depends on the
tags or classes in a template. Photos uploaded by a test go to a temporary
folder, so view/static/images is only read.
"""

from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

from flask.testing import FlaskClient

from model.customer import StaffCustomer, StudentCustomer
from model.database import session_scope
from model.nursery_system import NurserySystem
from model.plant import Perennial, PotPlant, TreeAndShrub, VegetableSeedling
from web import PHOTO, login, logout, page, record_id, referred_from


def stock_of(client: FlaskClient, plant_path: str) -> str:
    """
    Read the stock a plant page shows.

    :param client (FlaskClient): The browser session
    :param plant_path (str): The plant page, such as /plants/<id>
    :return (str): The stock as shown
    """
    return page(client.get(plant_path)).value("Stock")


def open_order(client: FlaskClient) -> str:
    """
    Open the first order in the order list.

    :param client (FlaskClient): The browser session
    :return (str): The order page path
    """
    order_path = page(client.get("/orders")).link_to("/orders")
    assert client.get(order_path).status_code == 200
    return order_path


def test_customer_searches_orders_and_pays(client: FlaskClient) -> None:
    """
    A student searches the catalog, places a bulk order, and pays it.

    The invoice shows the bulk discount and the student discount. A credit
    card receipt shows the surcharge. Paying more than the balance is refused,
    and the order is still there after logging in again.
    """
    with session_scope() as session:
        system = NurserySystem(session)
        system.add_user("teamUsername", "TeamPassword", "team")
        system.login("teamUsername", "TeamPassword")
        tomato = VegetableSeedling("Tomato", 4.50, 50, "tomato.png")
        rose = TreeAndShrub("Rose", 15.99, 25, "rose.png")
        fern = PotPlant("Fern", 8.00, 15, "fern.png", "small")
        cactus = PotPlant("Cactus", 6.00, 1, "cactus.png", "small")
        cactus.reduce_stock(1)
        for plant in (tomato, rose, fern, cactus):
            system.add_plant(plant)
        jane = StudentCustomer("Jane", cust_phone="021-555-0199")
        system.add_customer(jane)
        system.add_user("janeUsername", "JanePassword", "customer", jane)
        tomato_id = str(tomato.plant_id)

    # The order screens are behind the login.
    locked = client.get("/orders", follow_redirects=True)
    assert "Password" in page(locked)

    refused = client.post(
        "/login",
        data={"username": "janeUsername", "password": "wrong"},
    )
    assert "Username or password is incorrect" in page(refused)

    home = login(client, "janeUsername", "JanePassword")
    assert "Logged in as Jane." in home
    assert "Hello, Jane" in home
    assert "Student customer" in home
    assert "You currently owe $0.00." in home

    # A customer does not get the team screens.
    reports = client.get("/reports", follow_redirects=True)
    assert "Only the nursery team can do that" in page(reports)

    catalog = page(client.get("/plants"))
    assert "Out of stock" in catalog
    assert "Cactus" in catalog

    # Name, type, price band, and stock together. Tomato is $4.50.
    # Rose is too expensive, fern has the wrong name, and cactus is sold out.
    found = page(client.get(
        "/plants",
        query_string={
            "name": "tom",
            "plant_type": "vegetable seedlings",
            "price_band": "under-10",
            "in_stock": "on",
        },
    ))
    assert "Tomato" in found
    assert "Rose" not in found
    assert "Fern" not in found
    assert "Cactus" not in found
    assert "No plants match that search." not in found

    detail_path = found.link_to("/plants")
    detail = page(client.get(detail_path))
    assert "Tomato" in detail
    assert "vegetable seedlings" in detail
    assert "$4.50 per punnet" in detail
    assert detail.value("Seedlings per punnet") == "6"
    assert "/static/images/tomato.png" in detail.images
    photo = client.get("/static/images/tomato.png")
    assert photo.status_code == 200
    assert photo.data.startswith(b"\x89PNG")

    # Twelve punnets: 10% off the line, then 5% off for a student.
    # 12 x $4.50 = $54.00, bulk $5.40, student discount $2.43, total $46.17.
    ordered = client.post(
        "/orders/new",
        data={f"qty-{tomato_id}": "12"},
        follow_redirects=True,
    )
    invoice = page(ordered)
    order_path = ordered.request.path
    assert "Order placed." in invoice
    assert invoice.value("Order number")
    assert invoice.value("Customer") == "Jane"
    assert invoice.value("Status") == "pending"

    # Each line shows its own bulk discount and cost.
    lines = invoice.section("Invoice")
    assert lines.headers == [
        "Item",
        "Quantity",
        "Cost per unit",
        "Bulk discount (10+)",
        "Line cost",
    ]
    assert lines.rows == [
        ["Tomato", "12 punnet", "$4.50", "-$5.40", "$48.60"]
    ]
    assert invoice.value("Total cost") == "$54.00"
    assert invoice.value("Bulk discount") == "-$5.40"
    assert invoice.value("Customer discount") == "-$2.43"
    assert invoice.value("Total to pay") == "$46.17"
    assert invoice.value("Payments") == "$0.00"
    assert invoice.value("Outstanding") == "$46.17"

    assert stock_of(client, f"/plants/{tomato_id}") == "38"

    # The credit card adds 1.5%. $10.00 charged is $10.15, and $36.17 remains.
    receipt = page(client.post(
        f"{order_path}/pay",
        data={
            "amount": "10.00",
            "method": "credit card",
            "card_number": "5555666677778888",
            "expiry_date": "12-28",
        },
        follow_redirects=True,
    ))
    assert "Payment recorded." in receipt
    assert receipt.value("Paid") == "$10.00"
    assert "credit card" in receipt.value("How")
    assert receipt.value("Card surcharge") == "$0.15"
    assert receipt.value("Charged") == "$10.15"
    assert receipt.value("Still to pay after this payment") == "$36.17"
    assert receipt.value("Order number") == invoice.value("Order number")
    assert receipt.link_to("/orders") == order_path

    overpaid = client.post(
        f"{order_path}/pay",
        data={
            "amount": "36.18",
            "method": "debit card",
            "card_number": "1111222233334444",
            "bank_name": "ANZ",
        },
        headers=referred_from(order_path),
        follow_redirects=True,
    )
    assert "Payment cannot be more than what is still owed" in page(overpaid)
    still_open = page(client.get(order_path))
    assert still_open.value("Outstanding") == "$36.17"
    assert still_open.value("Status") == "pending"

    # Anything already paid stops the order from being cancelled.
    cancelled = client.post(
        f"{order_path}/cancel",
        headers=referred_from(order_path),
        follow_redirects=True,
    )
    assert "Cannot cancel an order that has already been paid toward" in page(
        cancelled
    )
    assert page(client.get(order_path)).value("Status") == "pending"

    settled = page(client.post(
        f"{order_path}/pay",
        data={
            "amount": "36.17",
            "method": "debit card",
            "card_number": "1111222233334444",
            "bank_name": "ANZ",
        },
        follow_redirects=True,
    ))
    assert "debit card" in settled.value("How")
    assert settled.value("Still to pay after this payment") == "$0.00"

    # Once the order is paid in full, a printed invoice still shows what the
    # order came to.
    paid_invoice = page(client.get(order_path))
    assert paid_invoice.value("Total to pay") == "$46.17"
    assert paid_invoice.value("Payments") == "$46.17"
    assert paid_invoice.value("Outstanding") == "$0.00"

    payments = page(client.get("/payments"))
    assert "credit card" in payments
    assert "$10.15" in payments
    assert "debit card" in payments
    assert "$36.17" in payments

    # A new login reads the same order back from the database.
    logout(client)
    again = login(client, "janeUsername", "JanePassword")
    assert "You currently owe $0.00." in again
    own_orders = page(client.get("/orders"))
    assert "Jane" in own_orders
    assert "$46.17" in own_orders
    assert "$0.00" in own_orders
    assert stock_of(client, f"/plants/{tomato_id}") == "38"


def test_team_sells_at_the_counter_and_collects(
    client: FlaskClient, photo_dir: Path
) -> None:
    """
    The team adds a plant and a community customer, then sells and collects.

    A second order is refused while the first is still pending. Cancelling
    the unpaid order puts the stock back and allows another order. The
    customer can see the collected order, and cannot collect it or open the
    team screens.
    """
    with session_scope() as session:
        system = NurserySystem(session)
        system.add_user("teamUsername", "TeamPassword", "team")
        system.login("teamUsername", "TeamPassword")
        # Already sold out. Stock reaches 0 only through reduce_stock.
        cactus = PotPlant("Cactus", 6.00, 1, "cactus.png", "small")
        cactus.reduce_stock(1)
        system.add_plant(cactus)
        cactus_id = str(cactus.plant_id)

    home = login(client, "teamUsername", "TeamPassword")
    assert "Logged in as the nursery team." in home
    assert "Nursery desk" in home

    added = client.post(
        "/plants/new",
        data={
            "plant_name": "Camellia",
            "plant_type": "trees and shrubs",
            "price": "16.00",
            "stock": "10",
            "photo": (BytesIO(PHOTO), "camellia.png"),
        },
        follow_redirects=True,
    )
    plant = page(added)
    plant_path = added.request.path
    plant_id = record_id(plant_path)
    assert "Camellia added to the catalog." in plant
    assert "trees and shrubs" in plant
    assert "$16.00 per plant" in plant
    assert plant.value("Stock") == "10"

    # The upload is saved under a new name, and the page shows that file.
    uploads = list(photo_dir.iterdir())
    assert len(uploads) == 1
    assert uploads[0].name != "camellia.png"
    assert uploads[0].read_bytes() == PHOTO
    assert plant.images == [f"/static/images/{uploads[0].name}"]

    # Price and stock have their own forms, so one change never depends
    # on the other.
    repriced = page(client.post(
        f"{plant_path}/price",
        data={"price": "16.00"},
        follow_redirects=True,
    ))
    assert "Camellia price updated." in repriced
    assert "$16.00 per plant" in repriced
    assert repriced.value("Stock") == "10"

    updated = page(client.post(
        f"{plant_path}/stock",
        data={"stock": "20"},
        follow_redirects=True,
    ))
    assert "Camellia stock updated." in updated
    assert updated.value("Stock") == "20"

    # A sold-out plant can be repriced without being restocked, and a
    # new batch can then be added. Stock still cannot be set to 0.
    cactus_path = f"/plants/{cactus_id}"
    assert "Out of stock" in page(client.get(cactus_path))
    cactus_repriced = page(client.post(
        f"{cactus_path}/price",
        data={"price": "7.50"},
        follow_redirects=True,
    ))
    assert "Cactus price updated." in cactus_repriced
    assert "$7.50 per pot" in cactus_repriced
    assert "Out of stock" in cactus_repriced

    zero_stock = client.post(
        f"{cactus_path}/stock",
        data={"stock": "0"},
        headers=referred_from(cactus_path),
        follow_redirects=True,
    )
    assert "Plant stock must be greater than 0" in page(zero_stock)
    assert "Out of stock" in page(client.get(cactus_path))

    cactus_restocked = page(client.post(
        f"{cactus_path}/stock",
        data={"stock": "12"},
        follow_redirects=True,
    ))
    assert "Cactus stock updated." in cactus_restocked
    assert cactus_restocked.value("Stock") == "12"
    assert "$7.50 per pot" in cactus_restocked
    assert "Out of stock" not in cactus_restocked

    created = client.post(
        "/customers/new",
        data={
            "cust_name": "Sam",
            "customer_type": "community",
            "cust_email": "sam@email.com",
            "cust_phone": "",
            "username": "samUsername",
            "password": "SamPassword",
        },
        follow_redirects=True,
    )
    customer = page(created)
    customer_id = record_id(created.request.path)
    assert "Sam added." in customer
    assert "community" in customer
    assert "sam@email.com" in customer
    assert customer.value("Owes") == "$0.00"

    # Two plants at $16 with no community discount is $32.00.
    first = client.post(
        "/orders/new",
        data={"customer_id": customer_id, f"qty-{plant_id}": "2"},
        follow_redirects=True,
    )
    first_order = page(first)
    order_path = first.request.path
    assert "Order placed." in first_order
    assert first_order.value("Customer") == "Sam"
    assert first_order.value("Total cost") == "$32.00"
    assert "Bulk discount" not in first_order.definitions
    assert "Customer discount" not in first_order.definitions
    assert first_order.value("Total to pay") == "$32.00"
    assert first_order.value("Outstanding") == "$32.00"
    assert first_order.value("Status") == "pending"
    assert stock_of(client, plant_path) == "18"

    # The same pending-order rule applies when the team sells for them.
    blocked = client.post(
        "/orders/new",
        data={"customer_id": customer_id, f"qty-{plant_id}": "1"},
    )
    assert (
        "Community customers may only have one pending order at a time"
        in page(blocked)
    )
    assert stock_of(client, plant_path) == "18"

    # Nothing has been paid, so the team can cancel and the stock returns.
    cancelled = page(client.post(
        f"{order_path}/cancel",
        follow_redirects=True,
    ))
    assert "Order cancelled." in cancelled
    assert cancelled.value("Status") == "cancelled"
    assert stock_of(client, plant_path) == "20"

    # Collection is refused until a community order is paid in full.
    second = client.post(
        "/orders/new",
        data={"customer_id": customer_id, f"qty-{plant_id}": "2"},
        follow_redirects=True,
    )
    second_order = page(second)
    second_path = second.request.path
    assert "Order placed." in second_order
    assert second_order.value("Status") == "pending"
    too_soon = client.post(
        f"{second_path}/collect",
        headers=referred_from(second_path),
        follow_redirects=True,
    )
    assert (
        "Community customers must pay an order in full "
        "before it can be collected"
        in page(too_soon)
    )
    assert page(client.get(second_path)).value("Status") == "pending"

    receipt = page(client.post(
        f"{second_path}/pay",
        data={
            "amount": "32.00",
            "method": "debit card",
            "card_number": "1111222233334444",
            "bank_name": "ANZ",
        },
        follow_redirects=True,
    ))
    assert "Payment recorded." in receipt
    assert "debit card" in receipt.value("How")
    assert receipt.value("Paid") == "$32.00"
    assert receipt.value("Still to pay after this payment") == "$0.00"

    collected = page(client.post(
        f"{second_path}/collect",
        follow_redirects=True,
    ))
    assert "Order marked as collected." in collected
    assert collected.value("Status") == "collected"

    # Sam sees the sale, and the team screens stay closed.
    logout(client)
    sam_home = login(client, "samUsername", "SamPassword")
    assert "Hello, Sam" in sam_home
    assert "Community customer" in sam_home
    assert "You currently owe $0.00." in sam_home
    sam_order = page(client.get(second_path))
    assert sam_order.value("Status") == "collected"
    assert sam_order.value("Total to pay") == "$32.00"
    sold = [row[0] for row in sam_order.section("Invoice").rows]
    assert sold == ["Camellia"]
    assert "Mark collected" not in sam_order

    refused = client.post(
        f"{second_path}/collect",
        headers=referred_from(second_path),
        follow_redirects=True,
    )
    assert "Only the nursery team can do that" in page(refused)
    assert page(client.get(second_path)).value("Status") == "collected"

    for address in ("/customers", "/reports", "/plants/new"):
        blocked_page = client.get(address, follow_redirects=True)
        assert "Only the nursery team can do that" in page(blocked_page)

    logout(client)
    # A later login reads the collected order back from the database.
    with client.application.test_client() as fresh:
        login(fresh, "samUsername", "SamPassword")
        collected_orders = page(fresh.get("/orders?status=collected"))
        assert "Sam" in collected_orders
        assert "$32.00" in collected_orders
        assert "No orders to show." in page(
            fresh.get("/orders?status=pending")
        )


def test_overdue_order_is_flagged_and_reported(client: FlaskClient) -> None:
    """
    An order left for ten days is flagged, and the team can report on it.

    The staff customer is told why a further order would pass $100. The team
    then sees the follow-up, the plant history, which plant was ordered most,
    the customer's activity, and the day's revenue. Collecting the order
    clears the follow-up for both of them.
    """
    placed_on = (date.today() - timedelta(days=10)).strftime("%d-%m-%Y")
    today = date.today().strftime("%d-%m-%Y")
    with session_scope() as session:
        system = NurserySystem(session)
        system.add_user("teamUsername", "TeamPassword", "team")
        system.login("teamUsername", "TeamPassword")
        rose = TreeAndShrub("Rose", 15.99, 20, "rose.png")
        lavender = Perennial("Lavender", 12.75, 10, "lavender.png")
        system.add_plant(rose)
        system.add_plant(lavender)
        avril = StaffCustomer("Avril", cust_email="avril@email.com")
        system.add_customer(avril)
        system.add_user("avrilUsername", "AvrilPassword", "customer", avril)
        # Six roses, then the 1% staff discount: $95.94 becomes $94.98.
        system.place_order(avril, [(rose, 6)], placed_on)
        rose_id = str(rose.plant_id)
        customer_id = str(avril.cust_id)

    home = login(client, "avrilUsername", "AvrilPassword")
    assert "Hello, Avril" in home
    assert "You currently owe $94.98." in home
    assert "not been collected within seven days" in home
    assert placed_on in home

    order_path = open_order(client)
    order = page(client.get(order_path))
    assert "Uncollected for 7 days or more" in order
    assert order.value("Status") == "pending"
    assert order.value("Total to pay") == "$94.98"
    assert stock_of(client, f"/plants/{rose_id}") == "14"

    # One more rose would be $15.83 and would take the balance over $100.
    blocked = client.post(
        "/orders/new",
        data={f"qty-{rose_id}": "1"},
    )
    assert (
        "Staff and students cannot place an order that would "
        "take what they owe over $100"
        in page(blocked)
    )
    assert "You currently owe $94.98." in page(client.get("/"))
    assert stock_of(client, f"/plants/{rose_id}") == "14"

    hidden = client.get("/reports", follow_redirects=True)
    assert "Only the nursery team can do that" in page(hidden)

    logout(client)
    desk = login(client, "teamUsername", "TeamPassword")
    assert "not been collected within seven days" in desk
    assert "Avril" in desk
    assert placed_on in desk

    pending = page(client.get("/orders?status=pending"))
    assert "Uncollected for 7 days or more" in pending
    assert "Avril" in pending

    # A debit card has no surcharge, so $20.00 paid is $20.00 charged.
    receipt = page(client.post(
        f"{order_path}/pay",
        data={
            "amount": "20.00",
            "method": "debit card",
            "card_number": "1111222233334444",
            "bank_name": "ANZ",
        },
        follow_redirects=True,
    ))
    assert "Payment recorded." in receipt
    assert receipt.value("Paid") == "$20.00"
    assert receipt.value("Card surcharge") == "$0.00"
    assert receipt.value("Still to pay after this payment") == "$74.98"

    reported = page(client.get(
        "/reports",
        query_string={
            "period": "day",
            "on_date": today,
            "plant_id": rose_id,
            "customer_id": customer_id,
        },
    ))
    most = reported.section("Most ordered")
    least = reported.section("Least ordered")
    assert most.rows == [["Rose", "6"], ["Lavender", "0"]]
    assert least.rows == [["Lavender", "0"], ["Rose", "6"]]
    assert "Charged in that day: $20.00" in reported.section("Revenue")

    # One row for the one order: date, customer, status, quantity.
    [history_row] = reported.section("Plant order history").rows
    assert history_row[0] == placed_on
    assert history_row[1].startswith("Avril")
    assert history_row[2:] == ["pending", "6"]

    activity = reported.section("Customer activity").items
    assert any("placed" in record for record in activity)
    assert any("Paid $20.00 toward order" in record for record in activity)

    collected = page(client.post(
        f"{order_path}/collect",
        follow_redirects=True,
    ))
    assert "Order marked as collected." in collected
    assert collected.value("Status") == "collected"
    assert "Uncollected for 7 days or more" not in collected

    # Staff can be collected while they still owe the rest.
    desk_after = page(client.get("/"))
    assert "not been collected within seven days" not in desk_after
    assert "collected" in page(client.get("/orders?status=collected"))

    followed_up = page(client.get(
        "/reports",
        query_string={
            "on_date": today,
            "customer_id": customer_id,
            "plant_id": rose_id,
        },
    ))
    after = followed_up.section("Customer activity").items
    assert any("placed" in record for record in after)
    assert any("Paid $20.00 toward order" in record for record in after)
    assert any("collected" in record for record in after)

    logout(client)
    avril_again = login(client, "avrilUsername", "AvrilPassword")
    assert "not been collected within seven days" not in avril_again
    assert "You currently owe $74.98." in avril_again
    finished = page(client.get(order_path))
    assert finished.value("Status") == "collected"
    assert "Mark collected" not in finished
