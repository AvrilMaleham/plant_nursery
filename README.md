# Plant Nursery System

## Overview

This is a plant nursery management system that tracks plants, customers, orders, and payments. The design is based on Brent's notes outlining what the nursery needs for its day to day operations.

## How to Run

```bash
python driver.py
```

The first run walks through the demonstration, then saves the nursery to `nursery_system.pkl`. A second run loads that file and prints the plants, customers, orders, and payments that were saved. Delete `nursery_system.pkl` to run the full demonstration from scratch.

## Design Decisions

### Separation of Concerns

I kept all the classes in separate files for a true separation of concerns. Each entity (`Plant`, `Customer`, `Order`, `OrderItem`, `Payment`) has its own class, and each collection (`PlantCatalog`, `CustomerDirectory`, `OrderHistory`, `PaymentHistory`) has its own class. I then created a `NurserySystem` manager class so the driver only needs to talk to one object. This ensures that order creation only happens for customers and plants that are registered in the system, and the order history is updated automatically to avoid mistakes.

### Display Methods on Collection Classes

Each collection class (`PlantCatalog`, `CustomerDirectory`, `OrderHistory`, `PaymentHistory`) has a `display_all` method even though a getter for the list already exists. This keeps the print logic inside the class rather than requiring a loop in the driver, which is cleaner and more reusable.

### Inheritance Hierarchies in One File

For assignment 1 I kept each class in its own file. For assignment 2 I kept each abstract base class in the same file as the subclasses that inherit from it, for example, `Plant` lives with `TreeAndShrub`, `Perennial`, `PotPlant`, and `VegetableSeedling`. `Plant`, `Customer`, and `Payment` are the abstract bases, each one defines the shared data and the methods every subtype must implement, and the subclasses add what is specific to that type.

### Order Rules are in the Customer Class, not the Order Class

Even though whether a customer can place an order or collect an order is related to ordering, I felt it was more closely related to customer as each rule is unique to each customer.

### The Same Plant Can Only Appear Once in an Order

If someone tries to order the same plant twice, it will be rejected because we need to enforce the 10% discount. The other option would have been to merge the two lines but in this case I have chosen to apply the discount at order item level, not order level.

### Payments Follow the Existing Structure

Payments follow the same structure as orders. `PaymentHistory` holds the list, `NurserySystem` checks the payment is allowed, and `Order.record_payment` is what actually changes the amount owed, the same way `collect_order()` and `cancel_order()` are what change status. `NurserySystem` is still the one place that adds, searches, updates, and reports across plants, customers, orders, and payments.

### Saving with Pickle

I used a pickle file rather than a text file or JSON because it is the simplest code wise. Saving the whole `NurserySystem` object keeps plants, customers, orders, and payments linked as the same objects when they are loaded again, without rebuilding them line by line.

### Custom Exceptions in Their Own File

Invalid order operations now raise custom exceptions instead of a generic `ValueError`, so the driver can catch the specific problem. I put them in `exceptions.py` rather than inside each class file so `Plant`, `Order`, and `NurserySystem` can all import the same types. The exception classes only store a message and pass it to `Exception`. They do not print.

## Assumptions

### Plant

- No new categories will be added at this time, the four types are trees and shrubs, perennials, pot plants, and vegetable seedlings.
- Same plant name does not mean same price, two batches of the same plant can come in at different prices, which is why each plant has its own ID.
- A name will always be given and data types will be correct for now (no validation on inputs beyond what the type hints describe).
- IDs are generated using UUID for simplicity.
- Only stock and price can be changed once a `Plant` object is created, name and type are read only.
- Stock cannot be set to 0. A plant must be created and restocked with a value greater than 0. Stock can only reach exactly zero when it is reduced through an order.
- If seedlings per punnet is not given, it defaults to 6, because Brent noted that six is average.
- Each pot size is its own catalog entry, because a mix of sizes should not get the 10% discount.

### Customer

- IDs are generated using UUID for simplicity.
- Customer name, email, and phone can be updated after creation via setters. ID stays read only. At least one of email or phone must remain.
- Staff and students are blocked when their current balance is already over $100, not when the new order would take them over.

### Order

- No new statuses will be added at this time, the three statuses are fixed using a `Literal` type.
- Order date is stored as a string in DD-MM-YYYY format. It defaults to today, can be set on creation or via a setter, and is validated as a real calendar date.
- Status changes go through `collect_order()` and `cancel_order()` methods rather than a setter, for more control over the business rules.
- Order items cannot be updated after they are created. There would be a lot of downstream changes from changing an order item such as stock, discounts, order total and customer balance.

### Payment

- Card number, expiry date, and bank name just need to be given, Brent did not specify a format.
- The 1.5% surcharge is added to what the customer pays, the order only comes down by the amount applied to it.

## Requirements Covered from Brent's Notes

### Plant Requirements

- Each plant tracked by a unique ID (since two batches of the same plant can come in at different times) — `Plant` uses UUID as the ID
- Plant name is recorded — `plant_name` attribute
- Four types of plants, trees and shrubs, perennials, pot plants, and vegetable seedlings — `Plant` is abstract, the four subclasses are `TreeAndShrub`, `Perennial`, `PotPlant`, and `VegetableSeedling`
- Trees and shrubs, and perennials, are priced per plant.
- Pot plants are priced by pot size, small, medium, or large.
- Vegetable seedlings are priced per punnet. Seedlings per punnet depends on the type. Six is average.
- The unit we sell something in is the same unit we count the stock in — `sale_unit()` returns `plant`, `pot`, or `punnet`
- Plant price is recorded — `plant_price` attribute
- Plant stock level is tracked — `plant_stock` attribute
- Price cannot be negative (or zero) — validated in `__init__` and the `plant_price` setter, raises `ValueError`
- Stock cannot be set to 0 — validated in `__init__` and the `plant_stock` setter, raises `ValueError`. Stock can only reach exactly zero when reduced through an order via `reduce_stock()`
- Stock cannot go below zero — `check_stock()` and `reduce_stock()` enforce this before the order is created
- Can add new plants without accidentally adding the same one twice — `PlantCatalog.catalog_plant()` checks for duplicate IDs before adding
- Can see a list of all plants — `PlantCatalog.display_all_plants()` and `NurserySystem.display_all_plants()`
- Can see a list of available plants with non-zero current stock — `PlantCatalog.get_available_plants()`, `PlantCatalog.display_available_plants()`, and the matching `NurserySystem` methods

### Customer Requirements

- Customers each have a unique ID (since two customers can share the same name) — `Customer` uses UUID as the ID
- Customer name is recorded — `cust_name` attribute
- At least an email address or phone number is required — validated in `__init__` and the `cust_email` / `cust_phone` setters, raises `ValueError` if neither is provided
- Customer name, email, and phone can be updated after creation — `cust_name`, `cust_email`, and `cust_phone` setters. ID has no setter.
- Can add new customers without accidentally adding the same one twice — `CustomerDirectory.add_customer()` checks for duplicate IDs before adding
- Can see a list of all customers — `CustomerDirectory.display_all_customers()` and `NurserySystem.display_all_customers()`
- Three types of customers, university staff, university students, and general community — `Customer` is abstract, the three subclasses are `StaffCustomer`, `StudentCustomer`, and `CommunityCustomer`
- Staff get 1% off their order total
- Students get 5% off
- Community customers get no discount.
- The customer discount comes off the order as a whole — `apply_discount()` uses `discount_rate()` from the subclass
- Show customer's balance alongside the rest of their details
- Show different types of customers separately, rather than everyone shown together as we have now.
- Community customers can only have one order pending at a time, and they need to pay it off in full before it can be collected — `can_place_order()` and `can_collect_order()` on `CommunityCustomer`
- Staff and student balances can accumulate across several orders, and they can still collect their orders while owing money. If a staff or student's amount owing goes above $100, we should not let them order more until it is paid down — `can_place_order()` and `can_collect_order()` on `StaffCustomer` and `StudentCustomer`

### Order Requirements

- Each order records: customer, date (DD-MM-YYYY), status, order total, and one or more items — all stored as attributes on `Order`
- One order can have multiple items on it.
- Each item has its own plant, quantity, and the cost for that item's quantity — `OrderItem`
- Order date is settable and validated as a real calendar date in DD-MM-YYYY format — `__init__` and the `order_date` setter raise `ValueError` for invalid dates
- The existing 10% discount for ordering ten or more of the same plant still applies per item — handled in `OrderItem`
- For pot plants, that means ten or more of the same plant in the same pot size, not a mix of sizes.
- For seedlings, that means ten or more punnets of the same type, not individual seedlings.
- Orders for zero (or fewer) plants are rejected — validated in `__init__`, raises `ValueError` if quantity < 1
- Stock is reduced immediately when an order is placed — `OrderItem` reduces stock when it is created
- Stock can never go below zero — `check_stock()` and `reduce_stock()` enforce this before the order is created
- Placing an order always adds the total to what they owe, and the balance stays until it is paid.
- An order can be cancelled only while it is still pending and nothing has been paid toward it yet — `cancel_order()` raises `OrderCannotBeCancelledError` if status is "collected", already "cancelled", or anything has been paid toward it
- Cancelling takes its total back off what the customer owes, same as the stock does.
- Once collected, an order can no longer be cancelled — enforced in `cancel_order()`
- Can check whether a plant has enough stock before ordering — `Plant.check_stock()` method, also called automatically during order creation
- Orders can only be placed for customers and plants registered in the system — `NurserySystem.place_order()` searches by customer ID and plant ID directly before creating the order

### Payment Requirements

- Each payment has its own ID, recorded with the amount paid, which customer it was for, which order it was paying toward, and the date.
- Customers have the option of either paying by credit card or debit card — `Payment` is abstract, the two subclasses are `CreditCardPayment` and `DebitCardPayment`
- For a credit card we need the card number and the expiry date, and when paying there is a 1.5% surcharge added to the amount the customer pays — `amount_charged()` uses `surcharge_rate()` from the subclass
- For a debit card we just need the card number and the name of the bank it is with.
- A customer may settle an order with several payments, no single payment can be more than what is still owed on that order.
- See a customer's payment history — `PaymentHistory.get_customer_payments()` and `NurserySystem.get_customer_payments()`
- See all the payments made toward a specific order — `PaymentHistory.get_order_payments()` and `NurserySystem.get_order_payments()`
- See the full list of payments across all customers — `PaymentHistory.display_all_payments()` and `NurserySystem.display_all_payments()`

### Reporting Requirements

- Can pull up a specific customer's order history — `OrderHistory.get_customer_order_history()` and `NurserySystem.get_customer_order_history()`
- Can see every order on record — `OrderHistory.display_all_orders()` and `NurserySystem.display_all_orders()`

### Technical Requirements

- Each class has an initialiser that sets up attributes — all classes implement `__init__`
- Private data members — all attributes use name mangling (`__` prefix)
- Methods specific to each class — e.g. `check_stock()`, `reduce_stock()`, `restore_stock()` on `Plant`; `collect_order()`, `cancel_order()` on `Order`; `get_customer_order_history()` on `OrderHistory`
- Getters and setters — implemented using `@property` decorators; setters only where updates are allowed
- Overloaded `__str__` method for readable string representation — implemented on `Plant`, `Customer`, `Order`, `OrderItem`, `Payment`, and `NurserySystem`
- Docstrings on every class and method — included throughout
- Type hints on all method parameters and return values — included throughout
- Comments where relevant — included throughout to explain design choices and assumptions (why IDs, setters vs methods, copies of lists, stock reaching zero only through orders, and so on)
- Error conditions handled — `ValueError`, `TypeError`, and custom exceptions raised with descriptive messages for invalid inputs and illegal operations
