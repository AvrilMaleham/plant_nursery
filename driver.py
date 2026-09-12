from plant import Plant, TreeAndShrub, Perennial, PotPlant, VegetableSeedling
from customer import Customer, StaffCustomer, StudentCustomer, CommunityCustomer
from payment import Payment, CreditCardPayment, DebitCardPayment
from nursery_system import NurserySystem

# Driver for the nursery system. Each section shows a happy path first, then the
# error cases for that feature, so it is clear what the classes accept and reject.

# Initialise the system. All plants, customers, and orders go through this object
# rather than being stored in the driver itself. If a previous run saved data,
# that file is loaded here so plants, customers, orders, and payments come back.
system = NurserySystem()

# A second run should show the saved nursery, not add another copy of the demo data.
if system.loaded_from_file:
    print("--- Loaded existing nursery data ---")
    print(f"Delete {NurserySystem.DATA_FILE} to run the full demonstration again.\n")
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
    print()
    raise SystemExit

# ---------- Plants ----------

# Add one plant from each subclass so the catalog and later order examples have stock to use.
print("--- Adding Plants ---")
rose = TreeAndShrub("Rose", 15.99, 25)
system.add_plant(rose)

tomato = VegetableSeedling("Tomato", 4.50, 50)
system.add_plant(tomato)

orchid = PotPlant("Orchid", 22.00, 8, "medium")
system.add_plant(orchid)

lavender = Perennial("Lavender", 12.75, 30)
system.add_plant(lavender)

print("Plants added successfully\n")

# Full catalog, including every plant just added. Later this is printed again after
# a sold out orchid can be compared with the available list.
print("--- All Plants ---")
system.display_all_plants()
print()

# Price must be greater than 0. A negative price is rejected at creation.
print("--- Error: Invalid plant price ---")
try:
    bad_plant = Perennial("Daisy", -5.00, 10)
except ValueError as e:
    print(f"Caught: {e}\n")

# Plant is abstract, so a plant must be created as one of the four subclasses.
print("--- Error: Cannot create a Plant directly ---")
try:
    bad_plant = Plant("Cactus", 8.00, 15)
except TypeError as e:
    print(f"Caught: {e}\n")

# Pot size must be small, medium, or large.
print("--- Error: Invalid pot size ---")
try:
    bad_plant = PotPlant("Cactus", 8.00, 15, "tiny")
except ValueError as e:
    print(f"Caught: {e}\n")

# A plant cannot be created already sold out. Stock of 0 is only valid after an order.
print("--- Error: Plant created with zero stock ---")
try:
    bad_plant = PotPlant("Fern", 10.00, 0, "small")
except ValueError as e:
    print(f"Caught: {e}\n")

# The stock setter also rejects 0. Direct restocking must be a positive amount.
print("--- Error: Setting plant stock to 0 ---")
try:
    rose.plant_stock = 0
except ValueError as e:
    print(f"Caught: {e}\n")

# ---------- Customers ----------

# Add one customer from each subclass. Names do not have to be unique,
# which is why another_jane can share Jane's name but still has her own ID.
print("--- Adding Customers ---")
avril = StaffCustomer("Avril", cust_email="avril@email.com")
system.add_customer(avril)

jane = StudentCustomer("Jane", cust_phone="021-555-0199")
system.add_customer(jane)

# Two customers with the same name but different IDs, to show that identity is by ID.
another_jane = CommunityCustomer("Jane", cust_email="jane2@email.com")
system.add_customer(another_jane)

print("Customers added successfully\n")

# Display all customers, then each type on its own list.
print("--- All Customers ---")
system.display_all_customers()
print()

print("--- Staff Customers ---")
system.display_staff_customers()
print()

print("--- Student Customers ---")
system.display_student_customers()
print()

print("--- Community Customers ---")
system.display_community_customers()
print()

# Customer is abstract, so a customer must be created as one of the three subclasses.
print("--- Error: Cannot create a Customer directly ---")
try:
    bad_customer = Customer("John", cust_email="john@email.com")
except TypeError as e:
    print(f"Caught: {e}\n")

# A customer must have at least an email or a phone number so they can be contacted.
print("--- Error: Customer with no contact details ---")
try:
    bad_customer = StaffCustomer("John")
except ValueError as e:
    print(f"Caught: {e}\n")

# Name, email, and phone can be updated after creation through setters.
print("--- Updating Customer Details ---")
jane.cust_name = "Jane Smith"
jane.cust_email = "jane@email.com"
print(f"Jane after update: {jane}\n")

# Avril only has an email, so clearing it would leave no contact method and is rejected.
print("--- Error: Clearing last contact method ---")
try:
    avril.cust_email = ""
except ValueError as e:
    print(f"Caught: {e}\n")

# ---------- Orders ----------

print("--- Placing Orders ---")

# A staff order of 3 roses. Stock drops immediately, the 1% staff discount comes off
# the order total, and that total is added to what Avril owes.
order1 = system.place_order(avril, [(rose, 3)])
print(f"Order placed: {order1}")
print(f"Rose stock after order: {rose.plant_stock}")
print(f"Avril balance after order: {avril.balance}\n")

# Order date is settable so staff can record a date other than today.
print("--- Setting Order Date ---")
order1.order_date = "01-09-2026"
print(f"Order 1 date updated: {order1.order_date}\n")

# Impossible calendar dates are rejected, not just badly formatted strings.
print("--- Error: Invalid order date ---")
try:
    order1.order_date = "32-13-2026"
except ValueError as e:
    print(f"Caught: {e}\n")

# 10 or more of the same plant gets 10% off that item, then the student 5% comes off
# the order as a whole.
order2 = system.place_order(jane, [(tomato, 12)])
print(f"Order placed (item 10% then student 5%): {order2}")
print(f"Expected item cost: 12 x $4.50 x 0.9 = ${12 * 4.50 * 0.9:.2f}")
print(f"Expected order total: $48.60 x 0.95 = ${48.60 * 0.95:.2f}")
print(f"Actual total: ${order2.order_total}")
print(f"Jane balance after order: {jane.balance}\n")

# Quantity of 0 is not a valid order item.
print("--- Error: Order for zero plants ---")
try:
    system.place_order(avril, [(orchid, 0)])
except ValueError as e:
    print(f"Caught: {e}\n")

# Ordering more than current stock is rejected so stock can never go below zero.
print("--- Error: Order exceeding available stock ---")
try:
    system.place_order(jane, [(orchid, 100)])
except ValueError as e:
    print(f"Caught: {e}\n")

# Mary is a valid Customer object but has not been added to the system, so the order is refused.
print("--- Error: Order for unregistered customer ---")
try:
    unregistered = CommunityCustomer("Mary", cust_email="mary@email.com")
    system.place_order(unregistered, [(rose, 1)])
except ValueError as e:
    print(f"Caught: {e}\n")

# Echinacea has not been added to the catalog, so it cannot be ordered either.
print("--- Error: Order for unregistered plant ---")
try:
    echinacea = Perennial("Echinacea", 9.99, 100)
    system.place_order(avril, [(echinacea, 1)])
except ValueError as e:
    print(f"Caught: {e}\n")

# The same plant cannot appear twice on one order, so the bulk discount is not split
# across two lines of the same plant.
print("--- Error: Duplicate plant on one order ---")
try:
    system.place_order(avril, [(rose, 1), (rose, 1)])
except ValueError as e:
    print(f"Caught: {e}\n")

# One order can hold different plant types as separate items.
print("--- Multi-item Community Order ---")
order_community = system.place_order(another_jane, [(rose, 4), (orchid, 2), (tomato, 1)])
print(f"Order placed: {order_community}")
print(f"Community Jane balance: {another_jane.balance}\n")

# Community customers can only have one pending order at a time.
print("--- Error: Community customer already has a pending order ---")
try:
    system.place_order(another_jane, [(lavender, 1)])
except ValueError as e:
    print(f"Caught: {e}\n")

# Community customers must pay in full before collecting.
print("--- Error: Collect unpaid community order ---")
try:
    system.collect_order(order_community)
except ValueError as e:
    print(f"Caught: {e}\n")

# ---------- Order Status ----------

# Staff may collect while still owing. There is no status setter, this method is the path.
print("--- Collecting Staff Order ---")
system.collect_order(order1)
print(f"Order 1 status: {order1.order_status}")
print(f"Avril still owing after collect: {avril.balance}\n")

# Once collected, an order can no longer be cancelled.
print("--- Error: Cancel collected order ---")
try:
    system.cancel_order(order1)
except ValueError as e:
    print(f"Caught: {e}\n")

# Cancelling a pending order restores the stock and takes the total back off the balance.
print("--- Cancelling Pending Order ---")
print(f"Tomato stock before cancel: {tomato.plant_stock}")
print(f"Jane balance before cancel: {jane.balance}")
system.cancel_order(order2)
print(f"Order 2 status: {order2.order_status}")
print(f"Tomato stock after cancel: {tomato.plant_stock}")
print(f"Jane balance after cancel: {jane.balance}\n")

# Sell out remaining orchids through an order (not the stock setter) so stock can reach 0 legally.
# All plants should still include orchid at 0 and available plants should not.
print("--- Selling Out Orchid ---")
order3 = system.place_order(avril, [(orchid, orchid.plant_stock)])
print(f"Order placed: {order3}")
print(f"Orchid stock after order: {orchid.plant_stock}")
print(f"Avril balance after order: {avril.balance}\n")

# Avril now owes more than $100, so staff cannot place another order until it is paid down.
print("--- Error: Staff owing more than $100 ---")
try:
    system.place_order(avril, [(lavender, 1)])
except ValueError as e:
    print(f"Caught: {e}\n")

# ---------- Payments ----------

# Payment is abstract, so a payment must be created as credit or debit.
print("--- Error: Cannot create a Payment directly ---")
try:
    bad_payment = Payment(another_jane, order_community, 10.00)
except TypeError as e:
    print(f"Caught: {e}\n")

# No single payment can be more than what is still owed on that order.
print("--- Error: Payment more than remaining balance ---")
try:
    too_much = DebitCardPayment(
        another_jane, order_community, 1000.00, "1111222233334444", "ANZ"
    )
    system.record_payment(too_much)
except ValueError as e:
    print(f"Caught: {e}\n")

# A payment must be from the customer who owns the order.
print("--- Error: Payment from a different customer ---")
try:
    wrong_customer = DebitCardPayment(
        avril, order_community, 10.00, "1111222233334444", "ANZ"
    )
    system.record_payment(wrong_customer)
except ValueError as e:
    print(f"Caught: {e}\n")

# A customer may settle an order with several payments. Debit has no surcharge,
# so amount charged equals the amount applied to the order.
print("--- Partial Debit Payment ---")
community_debit = DebitCardPayment(
    another_jane, order_community, 50.00, "1111222233334444", "ANZ"
)
system.record_payment(community_debit)
print(f"Payment recorded: {community_debit}")
print(f"Amount charged: {community_debit.amount_charged()}")
print(f"Order remaining: {order_community.remaining_balance}")
print(f"Community Jane balance: {another_jane.balance}\n")

# An order can be cancelled only while nothing has been paid toward it yet.
print("--- Error: Cancel order that has been paid toward ---")
try:
    system.cancel_order(order_community)
except ValueError as e:
    print(f"Caught: {e}\n")

# Still unpaid, so community still cannot collect.
print("--- Error: Collect community order after partial payment ---")
try:
    system.collect_order(order_community)
except ValueError as e:
    print(f"Caught: {e}\n")

# Credit card adds a 1.5% surcharge to what the customer pays. The order is
# reduced by the amount applied, not by the charged amount.
print("--- Credit Card Payment for Remaining Balance ---")
community_remaining = order_community.remaining_balance
community_credit = CreditCardPayment(
    another_jane, order_community, community_remaining,
    "5555666677778888", "12-28",
)
system.record_payment(community_credit)
print(f"Payment recorded: {community_credit}")
print(f"Amount applied to order: {community_credit.amount}")
print(f"Amount charged (with 1.5% surcharge): {community_credit.amount_charged()}")
print(f"Order remaining: {order_community.remaining_balance}")
print(f"Community Jane balance: {another_jane.balance}\n")

# Paid in full, so the community order can be collected, and they can order again.
print("--- Collect Paid Community Order ---")
system.collect_order(order_community)
print(f"Community order status: {order_community.order_status}\n")

print("--- Community Order After Previous One Collected ---")
order_community_2 = system.place_order(another_jane, [(lavender, 1)])
print(f"Order placed: {order_community_2}\n")

# Staff can pay at any time, including toward a collected order that still has a balance.
# Paying this down lets Avril order again once owing is $100 or less.
print("--- Staff Debit Payment to Pay Down Balance ---")
avril_debit = DebitCardPayment(
    avril, order3, 80.00, "9999000011112222", "Kiwibank"
)
system.record_payment(avril_debit)
print(f"Payment recorded: {avril_debit}")
print(f"Avril balance after payment: {avril.balance}\n")

print("--- Staff Order After Paying Down Below $100 ---")
order4 = system.place_order(avril, [(lavender, 1)])
print(f"Order placed: {order4}")
print(f"Avril balance after order: {avril.balance}\n")

print("--- All Plants (includes sold out) ---")
system.display_all_plants()
print()

print("--- Available Plants (non-zero stock) ---")
system.display_available_plants()
print()

# An order that is already cancelled cannot be cancelled again.
print("--- Error: Cancel already cancelled order ---")
try:
    system.cancel_order(order2)
except ValueError as e:
    print(f"Caught: {e}\n")

# ---------- Search ----------

# Lookups are by ID so plants, customers, and orders can be found after they are created.
print("--- Searching by ID ---")
# Search for a plant by the ID that was generated on creation.
found_plant = system.find_plant(rose.plant_id)
print(f"Found plant: {found_plant}")
# Search for a customer the same way, by ID rather than name (names are not unique).
found_customer = system.find_customer(avril.cust_id)
print(f"Found customer: {found_customer}")
# Search for an order by its ID.
found_order = system.find_order(order1.order_id)
print(f"Found order: {found_order}")
# Search for a payment by its ID.
found_payment = system.find_payment(community_debit.payment_id)
print(f"Found payment: {found_payment}\n")

# ---------- Reporting ----------

# All orders Avril has placed, including collected and pending ones.
print("--- Avril's Order History ---")
avril_orders = system.get_customer_order_history(avril)
for order in avril_orders:
    print(order)
print()

# Every order on record, regardless of customer or status.
print("--- All Orders ---")
system.display_all_orders()
print()

print("--- Community Jane's Payments ---")
system.display_customer_payments(another_jane)
print()

print("--- Payments Toward Community Order ---")
system.display_order_payments(order_community)
print()

print("--- All Payments ---")
system.display_all_payments()
print()

# Short count of plants, customers, orders, and payments currently in the system.
print("--- System Summary ---")
print(system)

# Save everything so the next run can load it back in.
system.save_to_file()
