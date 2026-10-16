"""
Load a fresh set of sample plants, customers, orders, and payments.

Running this again clears those tables first, then loads the same sample.
"""

from model.customer import CommunityCustomer, StaffCustomer, StudentCustomer
from model.database import reset_database, session_scope
from model.nursery_system import NurserySystem
from model.payment import CreditCardPayment, DebitCardPayment
from model.plant import Perennial, PotPlant, TreeAndShrub, VegetableSeedling


def main() -> None:
    """
    Replace the nursery tables with the sample data and print them.
    """
    reset_database()
    with session_scope() as session:
        system = NurserySystem(session)

        rose = TreeAndShrub("Rose", 15.99, 25)
        tomato = VegetableSeedling("Tomato", 4.50, 50)
        orchid = PotPlant("Orchid", 22.00, 8, "medium")
        lavender = Perennial("Lavender", 12.75, 30)
        fern = PotPlant("Fern", 8.00, 15, "small")
        for plant in (rose, tomato, orchid, lavender, fern):
            system.add_plant(plant)

        avril = StaffCustomer("Avril", cust_email="avril@email.com")
        jane = StudentCustomer("Jane", cust_phone="021-555-0199")
        sam = CommunityCustomer("Sam", cust_email="sam@email.com")
        for customer in (avril, jane, sam):
            system.add_customer(customer)

        # Three roses, then the 1% staff discount.
        system.place_order(avril, [(rose, 3)])
        # Twelve punnets gets 10% off that line, then the 5% student discount.
        system.place_order(jane, [(tomato, 12)])
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
        system.record_payment(
            CreditCardPayment(
                sam,
                community_order,
                community_order.remaining_balance,
                "5555666677778888",
                "12-28",
            )
        )
        system.collect_order(community_order)

        print("--- All Plants ---")
        system.display_all_plants()
        print()
        print("--- All Customers ---")
        system.display_all_customers()
        print()
        print("--- All Orders ---")
        system.display_all_orders()
        print()
        print("--- All Payments ---")
        system.display_all_payments()
        print()
        print("--- System Summary ---")
        print(system)


if __name__ == "__main__":
    main()
