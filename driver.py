from plant import Plant
from customer import Customer
from nursery_system import NurserySystem

# Initialise the system
system = NurserySystem()

# ---------- Plants ----------

# Add plants
print("--- Adding Plants ---")
rose = Plant("Rose", "trees and shrubs", 15.99, 25)
system.add_plant(rose)

tomato = Plant("Tomato", "vegetable seedlings", 4.50, 50)
system.add_plant(tomato)

orchid = Plant("Orchid", "pot plants", 22.00, 8)
system.add_plant(orchid)

lavender = Plant("Lavender", "perennials", 12.75, 30)
system.add_plant(lavender)

print("Plants added successfully\n")

# Display all plants
print("--- All Plants ---")
system.display_all_plants()
print()

# Error: adding a plant with invalid price
print("--- Error: Invalid plant price ---")
try:
    bad_plant = Plant("Daisy", "perennials", -5.00, 10)
except ValueError as e:
    print(f"Caught: {e}\n")

# Error: adding a plant with invalid category
print("--- Error: Invalid plant category ---")
try:
    bad_plant = Plant("Cactus", "succulents", 8.00, 15)
except ValueError as e:
    print(f"Caught: {e}\n")

# ---------- Customers ----------

# Add customers 
print("--- Adding Customers ---")
avril = Customer("Avril", cust_email="avril@email.com")
system.add_customer(avril)

jane = Customer("Jane", cust_phone="021-555-0199")
system.add_customer(jane)

# Two customers with the same name but different IDs
another_jane = Customer("Jane", cust_email="jane2@email.com")
system.add_customer(another_jane)

print("Customers added successfully\n")

# Display all customers
print("--- All Customers ---")
system.display_all_customers()
print()

# Error: customer with no contact info
print("--- Error: Customer with no contact details ---")
try:
    bad_customer = Customer("John")
except ValueError as e:
    print(f"Caught: {e}\n")

# ---------- Orders ----------

print("--- Placing Orders ---")

# Normal order
order1 = system.place_order(avril, rose, 3)
print(f"Order placed: {order1}")
print(f"Rose stock after order: {rose.plant_stock}\n")

# Order with 10+ discount
order2 = system.place_order(jane, tomato, 12)
print(f"Order placed (10% discount applied): {order2}")
print(f"Expected total: 12 x $4.50 x 0.9 = ${12 * 4.50 * 0.9:.2f}")
print(f"Actual total: ${order2.order_total}\n")

# Error: order for zero plants
print("--- Error: Order for zero plants ---")
try:
    system.place_order(avril, orchid, 0)
except ValueError as e:
    print(f"Caught: {e}\n")

# Error: order exceeding stock
print("--- Error: Order exceeding available stock ---")
try:
    system.place_order(jane, orchid, 100)
except ValueError as e:
    print(f"Caught: {e}\n")

# Error: order for unregistered customer
print("--- Error: Order for unregistered customer ---")
try:
    unregistered = Customer("Mary", cust_email="mary@email.com")
    system.place_order(unregistered, rose, 1)
except ValueError as e:
    print(f"Caught: {e}\n")

# Error: order for unregistered plant
print("--- Error: Order for unregistered plant ---")
try:
    echinacea = Plant("Echinacea", "perennials", 9.99, 100)
    system.place_order(avril, echinacea, 1)
except ValueError as e:
    print(f"Caught: {e}\n")

# ---------- Order Status ----------

# Collect an order
print("--- Collecting Order ---")
system.collect_order(order1)
print(f"Order 1 status: {order1.order_status}\n")

# Error: cancel a collected order
print("--- Error: Cancel collected order ---")
try:
    system.cancel_order(order1)
except ValueError as e:
    print(f"Caught: {e}\n")

# Cancel a pending order (stock restored)
print("--- Cancelling Pending Order ---")
print(f"Tomato stock before cancel: {tomato.plant_stock}")
system.cancel_order(order2)
print(f"Order 2 status: {order2.order_status}")
print(f"Tomato stock after cancel: {tomato.plant_stock}\n")

# Error: cancel an already cancelled order
print("--- Error: Cancel already cancelled order ---")
try:
    system.cancel_order(order2)
except ValueError as e:
    print(f"Caught: {e}\n")

# ---------- Search ----------

print("--- Searching by ID ---")
# Search for a plant
found_plant = system.find_plant(rose.plant_id)
print(f"Found plant: {found_plant}")
# Search for a customer
found_customer = system.find_customer(avril.cust_id)
print(f"Found customer: {found_customer}")
# Search for an order
found_order = system.find_order(order1.order_id)
print(f"Found order: {found_order}\n")

# ---------- Reporting ----------

# Customer order history
print("--- Avril's Order History ---")
avril_orders = system.get_customer_order_history(avril)
for order in avril_orders:
    print(order)
print()

# All orders
print("--- All Orders ---")
system.display_all_orders()
print()

# System summary
print("--- System Summary ---")
print(system)
