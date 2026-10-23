"""
Integration tests for three nursery workflows.

Each test starts at a screen, follows the links and forms a person would use,
and checks the page that comes back. The records are read again in a new
login, so the result has to have been stored in PostgreSQL.
"""

import re
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

from flask.testing import FlaskClient

from model.customer import StaffCustomer, StudentCustomer
from model.database import session_scope
from model.nursery_system import NurserySystem
from model.plant import Perennial, PotPlant, TreeAndShrub, VegetableSeedling

IMAGES = Path(__file__).resolve().parents[1] / "view" / "static" / "images"
# A one-pixel PNG. The catalog stores the file and the plant page shows it.
PHOTO = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def page(response: object) -> str:
    """
    Return the HTML from a response that finished on a page.

    :param response (object): The response from the test client
    :return (str): The page HTML
    """
    assert response.status_code == 200
    return response.get_data(as_text=True)


def login(client: FlaskClient, username: str, password: str) -> str:
    """
    Sign in through the login form.

    :param client (FlaskClient): The browser session
    :param username (str): Login name
    :param password (str): The password as typed
    :return (str): The dashboard HTML
    """
    response = client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
    return page(response)


def logout(client: FlaskClient) -> None:
    """
    Sign out through the logout button.

    :param client (FlaskClient): The browser session
    """
    response = client.post("/logout", follow_redirects=True)
    assert response.status_code == 200


def shows_stock(html: str, stock: int) -> None:
    """
    Check the stock shown on a plant page.

    :param html (str): The plant page HTML
    :param stock (int): The stock that should be shown
    """
    assert re.search(rf"Stock</dt>\s*<dd>\s*{stock}\s*</dd>", html), html


def record_id(path: str) -> str:
    """
    Return the id at the end of a page address.

    :param path (str): A path such as /plants/<id>
    :return (str): The id
    """
    return path.rstrip("/").rsplit("/", 1)[-1]


def linked_path(html: str, prefix: str) -> str:
    """
    Return the first link whose address starts with prefix and then an id.

    :param html (str): The page HTML
    :param prefix (str): The start of the address, such as /plants
    :return (str): The matching path
    """
    found = re.findall(
        rf'href="({re.escape(prefix)}/[0-9a-fA-F-]{{36}})"', html
    )
    assert found, f"No {prefix} link on the page"
    return found[0]


def open_order(client: FlaskClient) -> str:
    """
    Open the first order in the order list.

    :param client (FlaskClient): The browser session
    :return (str): The order page path
    """
    listing = page(client.get("/orders"))
    order_path = linked_path(listing, "/orders")
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

    detail_path = linked_path(found, "/plants")
    detail = page(client.get(detail_path))
    assert "Tomato" in detail
    assert "vegetable seedlings" in detail
    assert "$4.50 per punnet" in detail
    assert "Seedlings per punnet</dt><dd>6</dd>" in detail
    assert 'src="/static/images/tomato.png"' in detail
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
    assert "12 punnet" in invoice
    assert "Total cost" in invoice
    assert "$54.00" in invoice
    assert "Bulk discount" in invoice
    assert "$5.40" in invoice
    assert "Customer discount" in invoice
    assert "$2.43" in invoice
    assert "Outstanding" in invoice
    assert "$46.17" in invoice
    assert "pending" in invoice

    shows_stock(page(client.get(f"/plants/{tomato_id}")), 38)

    # The credit card adds 1.5%. $10.00 charged is $10.15, and $36.17 remains.
    receipt = client.post(
        f"{order_path}/pay",
        data={
            "amount": "10.00",
            "method": "credit card",
            "card_number": "5555666677778888",
            "expiry_date": "12-28",
        },
        follow_redirects=True,
    )
    receipt_html = page(receipt)
    assert "Payment recorded." in receipt_html
    assert "Paid" in receipt_html
    assert "$10.00" in receipt_html
    assert "credit card" in receipt_html
    assert "Card surcharge" in receipt_html
    assert "$0.15" in receipt_html
    assert "Charged" in receipt_html
    assert "$10.15" in receipt_html
    assert "Still to pay after this payment" in receipt_html
    assert "$36.17" in receipt_html

    overpaid = client.post(
        f"{order_path}/pay",
        data={
            "amount": "36.18",
            "method": "debit card",
            "card_number": "1111222233334444",
            "bank_name": "ANZ",
        },
        headers={"Referer": f"http://localhost{order_path}"},
        follow_redirects=True,
    )
    assert "Payment cannot be more than what is still owed" in page(overpaid)
    still_open = page(client.get(order_path))
    assert "$36.17" in still_open
    assert "pending" in still_open

    # Anything already paid stops the order from being cancelled.
    cancelled = client.post(
        f"{order_path}/cancel",
        headers={"Referer": f"http://localhost{order_path}"},
        follow_redirects=True,
    )
    assert "Cannot cancel an order that has already been paid toward" in page(
        cancelled
    )
    assert "pending" in page(client.get(order_path))

    settled = client.post(
        f"{order_path}/pay",
        data={
            "amount": "36.17",
            "method": "debit card",
            "card_number": "1111222233334444",
            "bank_name": "ANZ",
        },
        follow_redirects=True,
    )
    settled_html = page(settled)
    assert "debit card" in settled_html
    assert "Still to pay after this payment</dt><dd>$0.00</dd>" in settled_html

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
    shows_stock(page(client.get(f"/plants/{tomato_id}")), 38)


def test_team_sells_at_the_counter_and_collects(client: FlaskClient) -> None:
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

    before = {path.name for path in IMAGES.iterdir()}
    try:
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
        plant_html = page(added)
        plant_path = added.request.path
        plant_id = record_id(plant_path)
        assert "Camellia added to the catalog." in plant_html
        assert "trees and shrubs" in plant_html
        assert "$16.00 per plant" in plant_html
        shows_stock(plant_html, 10)
        photo_name = re.search(r'/static/images/([^"]+)"', plant_html)
        assert photo_name is not None
        assert photo_name.group(1) != "camellia.png"
        stored_photo = client.get(f"/static/images/{photo_name.group(1)}")
        assert stored_photo.status_code == 200
        assert stored_photo.data == PHOTO

        updated = client.post(
            f"{plant_path}/update",
            data={"price": "16.00", "stock": "20"},
            follow_redirects=True,
        )
        updated_html = page(updated)
        assert "Camellia price and stock updated." in updated_html
        shows_stock(updated_html, 20)

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
        customer_html = page(created)
        customer_id = record_id(created.request.path)
        assert "Sam added." in customer_html
        assert "community" in customer_html
        assert "sam@email.com" in customer_html
        assert "Owes</dt><dd>$0.00</dd>" in customer_html

        # Two plants at $16 with no community discount is $32.00.
        first = client.post(
            "/orders/new",
            data={"customer_id": customer_id, f"qty-{plant_id}": "2"},
            follow_redirects=True,
        )
        first_html = page(first)
        order_path = first.request.path
        assert "Order placed." in first_html
        assert "Sam" in first_html
        assert "Total cost" in first_html
        assert "$32.00" in first_html
        assert "Bulk discount" not in first_html
        assert "Customer discount" not in first_html
        assert "Outstanding" in first_html
        assert "Status</dt><dd>pending</dd>" in first_html
        shows_stock(page(client.get(plant_path)), 18)

        # The same pending-order rule applies when the team sells for them.
        blocked = client.post(
            "/orders/new",
            data={"customer_id": customer_id, f"qty-{plant_id}": "1"},
        )
        assert (
            "Community customers may only have one pending order at a time"
            in page(blocked)
        )
        shows_stock(page(client.get(plant_path)), 18)

        # Nothing has been paid, so the team can cancel and the stock returns.
        cancelled = client.post(
            f"{order_path}/cancel",
            follow_redirects=True,
        )
        cancelled_html = page(cancelled)
        assert "Order cancelled." in cancelled_html
        assert "Status</dt><dd>cancelled</dd>" in cancelled_html
        shows_stock(page(client.get(plant_path)), 20)

        # Collection is refused until a community order is paid in full.
        second = client.post(
            "/orders/new",
            data={"customer_id": customer_id, f"qty-{plant_id}": "2"},
            follow_redirects=True,
        )
        second_html = page(second)
        second_path = second.request.path
        assert "Order placed." in second_html
        assert "Status</dt><dd>pending</dd>" in second_html
        too_soon = client.post(
            f"{second_path}/collect",
            headers={"Referer": f"http://localhost{second_path}"},
            follow_redirects=True,
        )
        assert (
            "Community customers must pay an order in full "
            "before it can be collected"
            in page(too_soon)
        )
        assert "Status</dt><dd>pending</dd>" in page(client.get(second_path))

        receipt = client.post(
            f"{second_path}/pay",
            data={
                "amount": "32.00",
                "method": "debit card",
                "card_number": "1111222233334444",
                "bank_name": "ANZ",
            },
            follow_redirects=True,
        )
        receipt_html = page(receipt)
        assert "Payment recorded." in receipt_html
        assert "debit card" in receipt_html
        assert "Paid</dt><dd>$32.00</dd>" in receipt_html
        assert "Still to pay after this payment</dt><dd>$0.00</dd>" in receipt_html

        collected = client.post(
            f"{second_path}/collect",
            follow_redirects=True,
        )
        collected_html = page(collected)
        assert "Order marked as collected." in collected_html
        assert "Status</dt><dd>collected</dd>" in collected_html

        # Sam sees the sale, and the team screens stay closed.
        logout(client)
        sam_home = login(client, "samUsername", "SamPassword")
        assert "Hello, Sam" in sam_home
        assert "Community customer" in sam_home
        assert "You currently owe $0.00." in sam_home
        sam_order = page(client.get(second_path))
        assert "Status</dt><dd>collected</dd>" in sam_order
        assert "Invoice" in sam_order
        assert "$32.00" in sam_order
        assert "Mark collected" not in sam_order

        refused = client.post(
            f"{second_path}/collect",
            headers={"Referer": f"http://localhost{second_path}"},
            follow_redirects=True,
        )
        assert "Only the nursery team can do that" in page(refused)
        assert "Status</dt><dd>collected</dd>" in page(client.get(second_path))

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
    finally:
        for image in IMAGES.iterdir():
            if image.name not in before:
                image.unlink()


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
    order_html = page(client.get(order_path))
    assert "Uncollected for 7 days or more" in order_html
    assert "Status</dt><dd>pending</dd>" in order_html
    assert "$94.98" in order_html
    shows_stock(page(client.get(f"/plants/{rose_id}")), 14)

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
    shows_stock(page(client.get(f"/plants/{rose_id}")), 14)

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
    receipt = client.post(
        f"{order_path}/pay",
        data={
            "amount": "20.00",
            "method": "debit card",
            "card_number": "1111222233334444",
            "bank_name": "ANZ",
        },
        follow_redirects=True,
    )
    receipt_html = page(receipt)
    assert "Payment recorded." in receipt_html
    assert "Paid</dt><dd>$20.00</dd>" in receipt_html
    assert "Card surcharge</dt><dd>$0.00</dd>" in receipt_html
    assert "Still to pay after this payment</dt><dd>$74.98</dd>" in receipt_html

    reported = page(client.get(
        "/reports",
        query_string={
            "period": "day",
            "on_date": today,
            "plant_id": rose_id,
            "customer_id": customer_id,
        },
    ))
    most, after_most = reported.split("Least ordered", 1)
    least, after_least = after_most.split("Revenue", 1)
    history, activity = after_least.split("Customer activity", 1)
    assert most.index("Rose") < most.index("Lavender")
    assert ">Rose</td><td>6</td>" in most
    assert ">Lavender</td><td>0</td>" in least
    assert least.index("Lavender") < least.index("Rose")
    assert "Charged in that day: $20.00" in reported
    assert "Avril" in history
    assert placed_on in history
    assert re.search(r"pending</td>\s*<td>\s*6\s*</td>", history)
    assert "placed" in activity
    assert "Paid $20.00 toward order" in activity

    collected = client.post(
        f"{order_path}/collect",
        follow_redirects=True,
    )
    collected_html = page(collected)
    assert "Order marked as collected." in collected_html
    assert "Status</dt><dd>collected</dd>" in collected_html
    assert "Uncollected for 7 days or more" not in collected_html

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
    activity_after = followed_up.split("Customer activity", 1)[1]
    assert "placed" in activity_after
    assert "Paid $20.00 toward order" in activity_after
    assert "collected" in activity_after

    logout(client)
    avril_again = login(client, "avrilUsername", "AvrilPassword")
    assert "not been collected within seven days" not in avril_again
    assert "You currently owe $74.98." in avril_again
    finished = page(client.get(order_path))
    assert "Status</dt><dd>collected</dd>" in finished
    assert "Mark collected" not in finished
