"""
Load a fresh set of sample plants, customers, orders, payments, and logins.

Running this again clears those tables first, then loads the same sample.
"""

from datetime import date, timedelta

from model.customer import CommunityCustomer, StaffCustomer, StudentCustomer
from model.database import reset_database, session_scope
from model.nursery_system import NurserySystem
from model.payment import CreditCardPayment, DebitCardPayment
from model.plant import Perennial, PotPlant, TreeAndShrub, VegetableSeedling


def main() -> None:
    """
    Replace the nursery tables with the sample data and print them.
    """
    ten_days_ago = date.today() - timedelta(days=10)
    today = date.today()

    reset_database()
    with session_scope() as session:
        system = NurserySystem(session)
        # The first account has to be the team.
        system.add_user("teamUsername", "TeamPassword", "team")
        system.login("teamUsername", "TeamPassword")

        rose = TreeAndShrub("Rose", 15.99, 25, "rose.png")
        tomato = VegetableSeedling("Tomato", 4.50, 50, "tomato.png")
        orchid = PotPlant("Orchid", 22.00, 8, "orchid.png", "medium")
        lavender = Perennial("Lavender", 12.75, 30, "lavender.png")
        fern = PotPlant("Fern", 8.00, 15, "fern.png", "small")
        # Already sold out. The in-stock filter hides it, and an order for
        # it is refused because there is no stock. Stock reaches 0 through
        # reduce_stock, which is the only path that allows exactly zero.
        cactus = PotPlant("Cactus", 6.00, 1, "cactus.png", "small")
        cactus.reduce_stock(1)
        for plant in (rose, tomato, orchid, lavender, fern, cactus):
            system.add_plant(plant)

        avril = StaffCustomer("Avril", cust_email="avril@email.com")
        jane = StudentCustomer("Jane", cust_phone="021-555-0199")
        sam = CommunityCustomer("Sam", cust_email="sam@email.com")
        for customer in (avril, jane, sam):
            system.add_customer(customer)
        system.add_user("avrilUsername", "AvrilPassword", "customer", avril)
        system.add_user("janeUsername", "JanePassword", "customer", jane)
        system.add_user("samUsername", "SamPassword", "customer", sam)

        # Still pending, and old enough to need a follow-up.
        system.place_order(avril, [(lavender, 1)], ten_days_ago)
        # Three roses, then the 1% staff discount.
        system.place_order(avril, [(rose, 3)])

        # Jane cancels her own unpaid order, then places the bulk order.
        system.logout()
        system.login("janeUsername", "JanePassword")
        cancelled = system.place_order(jane, [(tomato, 1)])
        system.cancel_order(cancelled)
        system.place_order(jane, [(tomato, 12)])

        system.logout()
        system.login("teamUsername", "TeamPassword")
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

        # Paid, so it no longer counts as Sam's one pending order. The next
        # order stays pending: two payments, a balance left, and a community
        # customer who cannot collect or cancel until it is paid off.
        partial = system.place_order(sam, [(fern, 4)])
        system.record_payment(
            DebitCardPayment(
                sam, partial, 12.00, "9999888877776666", "Westpac"
            )
        )
        partial_credit = CreditCardPayment(
            sam, partial, 10.00, "4444333322221111", "06-27"
        )
        system.record_payment(partial_credit)

        print("--- Logins ---")
        print("teamUsername / TeamPassword")
        print("avrilUsername / AvrilPassword")
        print("janeUsername / JanePassword")
        print("samUsername / SamPassword")
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
        print("--- Partly paid receipt ---")
        print(system.receipt_for(partial_credit))
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
