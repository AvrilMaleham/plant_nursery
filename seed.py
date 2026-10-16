"""
Load a fresh set of sample plants, customers, orders, payments, and logins.

Running this again clears those tables first, then loads the same sample.
"""

import struct
import zlib
from datetime import date, timedelta
from pathlib import Path

from model.customer import CommunityCustomer, StaffCustomer, StudentCustomer
from model.database import reset_database, session_scope
from model.nursery_system import NurserySystem
from model.payment import CreditCardPayment, DebitCardPayment
from model.plant import Perennial, PotPlant, TreeAndShrub, VegetableSeedling

IMAGE_DIR = Path(__file__).resolve().parent / "view" / "static" / "images"


def write_sample_image(filename: str, colour: tuple[int, int, int]) -> None:
    """
    Write a small solid-colour PNG for a sample plant.

    :param filename (str): File name under view/static/images
    :param colour (tuple[int, int, int]): Red, green, and blue, each 0 to 255
    """
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    width = 80
    height = 60

    def chunk(tag: bytes, data: bytes) -> bytes:
        """
        Build one PNG chunk.

        :param tag (bytes): Four-byte chunk type
        :param data (bytes): Chunk data
        :return (bytes): Length, type, data, and checksum
        """
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    rows = b"".join(
        b"\x00" + bytes(colour) * width for _ in range(height)
    )
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
    )
    png += chunk(b"IDAT", zlib.compress(rows))
    png += chunk(b"IEND", b"")
    (IMAGE_DIR / filename).write_bytes(png)


def main() -> None:
    """
    Replace the nursery tables with the sample data and print them.
    """
    photos = {
        "rose.png": (180, 40, 60),
        "tomato.png": (200, 50, 30),
        "orchid.png": (150, 80, 180),
        "lavender.png": (140, 120, 200),
        "fern.png": (40, 120, 60),
    }
    for filename, colour in photos.items():
        write_sample_image(filename, colour)

    ten_days_ago = (date.today() - timedelta(days=10)).strftime("%d-%m-%Y")
    today = date.today().strftime("%d-%m-%Y")

    reset_database()
    with session_scope() as session:
        system = NurserySystem(session)
        # The first account has to be the team. Sample passwords are the
        # same as the usernames, except the shared team login.
        system.add_user("team", "nursery", "team")
        system.login("team", "nursery")

        rose = TreeAndShrub("Rose", 15.99, 25, "rose.png")
        tomato = VegetableSeedling("Tomato", 4.50, 50, "tomato.png")
        orchid = PotPlant("Orchid", 22.00, 8, "orchid.png", "medium")
        lavender = Perennial("Lavender", 12.75, 30, "lavender.png")
        fern = PotPlant("Fern", 8.00, 15, "fern.png", "small")
        for plant in (rose, tomato, orchid, lavender, fern):
            system.add_plant(plant)

        avril = StaffCustomer("Avril", cust_email="avril@email.com")
        jane = StudentCustomer("Jane", cust_phone="021-555-0199")
        sam = CommunityCustomer("Sam", cust_email="sam@email.com")
        for customer in (avril, jane, sam):
            system.add_customer(customer)
        system.add_user("avril", "avril", "customer", avril)
        system.add_user("jane", "jane", "customer", jane)
        system.add_user("sam", "sam", "customer", sam)

        # Still pending, and old enough to need a follow-up.
        system.place_order(avril, [(lavender, 1)], ten_days_ago)
        # Three roses, then the 1% staff discount.
        system.place_order(avril, [(rose, 3)])

        # Jane cancels her own unpaid order, then places the bulk order.
        system.logout()
        system.login("jane", "jane")
        cancelled = system.place_order(jane, [(tomato, 1)])
        system.cancel_order(cancelled)
        system.place_order(jane, [(tomato, 12)])

        system.logout()
        system.login("team", "nursery")
        # Two different plants on one order. Community customers get no
        # discount. The order is paid with both card types, then collected.
        community_order = system.place_order(
            sam, [(orchid, 2), (lavender, 1)]
        )
        system.record_payment(
            DebitCardPayment(
                sam, community_order, 20.00, "1111222233334444", "ANZ"
            )
        )
        credit = CreditCardPayment(
            sam,
            community_order,
            community_order.remaining_balance,
            "5555666677778888",
            "12-28",
        )
        system.record_payment(credit)
        system.collect_order(community_order)

        print("--- Logins ---")
        print("team / nursery")
        print("avril / avril")
        print("jane / jane")
        print("sam / sam")
        print()
        print("--- All Plants ---")
        system.display_all_plants()
        print()
        print("--- Search: rose, in stock, up to $30 ---")
        for plant in system.search_plants(
            name="rose", max_price=30, in_stock_only=True
        ):
            print(plant)
        print()
        print("--- All Customers ---")
        system.display_all_customers()
        print()
        print("--- All Orders ---")
        system.display_all_orders()
        print()
        print("--- Uncollected for 7 days ---")
        for order in system.orders_uncollected_for_seven_days():
            print(order)
        print()
        print("--- Invoice ---")
        print(system.invoice_for(community_order))
        print()
        print("--- Receipt ---")
        print(system.receipt_for(credit))
        print()
        print("--- Most ordered ---")
        for plant, quantity in system.most_ordered_plants():
            print(plant.plant_name, quantity)
        print()
        print("--- Revenue today ---")
        print(system.revenue("day", today))
        print()
        print("--- Avril activity ---")
        for record in system.customer_activity(avril):
            print(record)
        print()
        print("--- All Payments ---")
        system.display_all_payments()
        print()
        print("--- System Summary ---")
        print(system)


if __name__ == "__main__":
    main()
