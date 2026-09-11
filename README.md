# Plant Nursery System

## Overview

This is a plant nursery management system that tracks plants, customers, and orders. The design is based on Brent's notes outlining what the nursery needs for its day to day operations.

## How to Run

```bash
python driver.py
```

## Design Decisions for Assignment 1

### Separation of Concerns

I kept all the classes in separate files for a true separation of concerns. Each entity (`Plant`, `Customer`, `Order`) has its own class, and each collection (`PlantCatalog`, `CustomerDirectory`, `OrderHistory`) has its own class. I then created a `NurserySystem` manager class so the driver only needs to talk to one object. This ensures that order creation only happens for customers and plants that are registered in the system, and the order history is updated automatically to avoid mistakes.

### Display Methods on Collection Classes

Each collection class (`PlantCatalog`, `CustomerDirectory`, `OrderHistory`) has a `display_all` method even though a getter for the list already exists. This keeps the print logic inside the class rather than requiring a loop in the driver, which is cleaner and more reusable.

## Assumptions for Assignment 1

### Plant

- No new categories will be added at this time, the four categories are fixed using a `Literal` type.
- Same plant name does not mean same price, two batches of the same plant can come in at different prices, which is why each plant has its own ID.
- A name will always be given and data types will be correct for now (no validation on inputs beyond what the type hints describe).
- IDs are generated using UUID for simplicity.
- Only stock and price can be changed once a `Plant` object is created, name and category are read only.
- Stock cannot be set to 0. A plant must be created and restocked with a value greater than 0. Stock can only reach exactly zero when it is reduced through an order.

### Customer

- IDs are generated using UUID for simplicity.
- Customer name, email, and phone can be updated after creation via setters. ID stays read only. At least one of email or phone must remain.

### Order

- No new statuses will be added at this time, the three statuses are fixed using a `Literal` type.
- Order date is stored as a string in DD-MM-YYYY format. It defaults to today, can be set on creation or via a setter, and is validated as a real calendar date.
- Status changes go through `collect_order()` and `cancel_order()` methods rather than a setter, for more control over the business rules.

## Requirements Covered from Brent's Notes for Assignment 1

### Plant Requirements

- Each plant tracked by a unique ID (since two batches of the same plant can come in at different times) — `Plant` uses UUID as the ID
- Plant name is recorded — `plant_name` attribute
- Plant category is one of: trees and shrubs, perennials, pot plants, or vegetable seedlings — enforced by the `PlantCategory` Literal type
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

### Order Requirements

- Each order records: customer, plant, quantity, date (DD-MM-YYYY), status, and order total — all stored as attributes on `Order`
- Order date is settable and validated as a real calendar date in DD-MM-YYYY format — `__init__` and the `order_date` setter raise `ValueError` for invalid dates
- Each order is for one type of plant only — each `Order` object holds a single `Plant` reference
- 10% discount applied when ordering 10 or more of the same plant — handled in `__calculate_total()`
- Orders for zero (or fewer) plants are rejected — validated in `__init__`, raises `ValueError` if quantity < 1
- Stock is reduced immediately when an order is placed — `plant.reduce_stock(quantity)` is called in `Order.__init__`
- Stock can never go below zero — `check_stock()` and `reduce_stock()` enforce this before the order is created
- An order can only be cancelled while it is still pending — `cancel_order()` raises `ValueError` if status is "collected" or already "cancelled"
- Cancelling a pending order restores the stock — `cancel_order()` calls `plant.restore_stock(quantity)`
- Once collected, an order can no longer be cancelled — enforced in `cancel_order()`
- Can check whether a plant has enough stock before ordering — `Plant.check_stock()` method, also called automatically during order creation
- Orders can only be placed for customers and plants registered in the system — `NurserySystem.place_order()` searches by customer ID and plant ID directly before creating the order
- Payment tracking is not required — not implemented, as specified

### Reporting Requirements

- Can pull up a specific customer's order history — `OrderHistory.get_customer_order_history()` and `NurserySystem.get_customer_order_history()`
- Can see every order on record — `OrderHistory.display_all_orders()` and `NurserySystem.display_all_orders()`

### Technical Requirements

- Each class has an initialiser that sets up attributes — all classes implement `__init__`
- Private data members — all attributes use name mangling (`__` prefix)
- Methods specific to each class — e.g. `check_stock()`, `reduce_stock()`, `restore_stock()` on `Plant`; `collect_order()`, `cancel_order()` on `Order`; `get_customer_order_history()` on `OrderHistory`
- Getters and setters — implemented using `@property` decorators; setters only where updates are allowed
- Overloaded `__str__` method for readable string representation — implemented on `Plant`, `Customer`, `Order`, and `NurserySystem`
- Docstrings on every class and method — included throughout
- Type hints on all method parameters and return values — included throughout
- Comments where relevant — included throughout to explain design choices and assumptions (why IDs, setters vs methods, copies of lists, stock reaching zero only through orders, and so on)
- Error conditions handled — `ValueError` and `TypeError` raised with descriptive messages for invalid inputs and illegal operations

## Design Decisions for Assignment 2

### Inheritance Hierarchies in One File

For asignment 1 I kept each class in its own file. For assignment 2 I kept each abstract base class in the same file as the subclasses that inherit from it, for example, `Plant` lives with `TreeAndShrub`, `Perennial`, `PotPlant`, and `VegetableSeedling`.

### Order Rules are in the Customer Class, not the Order Class

Even though whether a customer can place an order or collect an order is related to ordering, I felt it was more closely related to customer as each rule is unique to each customer.

## Assumptions for Assignment 2

### Plant

- If seedlings per punnet is not given, it defaults to 6, because Brent noted that six is average.

### Customer

- Staff and students are blocked when their current balance is already over $100, not when the new order would take them over.

## Requirements Covered from Brent's Notes for Assignment 2

### Multiple Plant Types

- Four types of plants, trees and shrubs, perennials, pot plants, and vegetable seedlings.
- Trees and shrubs, and perennials, are priced per plant.
- Pot plants are priced by pot size, small, medium, or large.
- Vegetable seedlings are priced per punnet. Seedlings per punnet depends on the type. Six is average.
- The unit we sell something in is the same unit we count the stock in.

A base class representing an individual plant available for sale, and derived classes to
capture the different types of plants.

### Multiple Customer Types

- Three types of customers, university staff, university students, and general community.
- Staff get 1% off their order total
- Students get 5% off
- Community customers get no discount.
- Show customer's balance alongside the rest of their details
- Show different types of customers separately, rather than everyone shown together as we have now.
- Community customers can only have one order pending at a time, and they need to pay it off in full before it can be collected.
- Staff and student balances can accumulate across several orders, and they can still collect their orders while owing money. If a staff or student's amount owing goes above $100, we should not let them order more until it is paid down.

A base class representing a customer buying plants from the nursery, and derived classes
to capture the different types of customers.

### Orders Containing Multiple Plant Types (with each plant type represented as a separate order item)

- One order can have multiple items on it.
- Each item has its own plant, quantity, and the cost for that item's quantity
- The existing 10% discount for ordering ten or more of the same plant still applies per item.
- For pot plants, that means ten or more of the same plant in the same pot size, not a mix of sizes.
- For seedlings, that means ten or more punnets of the same type, not individual seedlings.
- Placing an order always adds the total to what they owe, and the balance stays until it is paid.
- An order can be cancelled only while it is still pending and nothing has been paid toward it yet
- Cancelling takes its total back off what the customer owes, same as the stock does.

A class representing an order item, capturing one plant type within an order.
A class representing an order made by a customer, bringing together one or more order items.

### Payments, Including Support for Multiple Payment Types

- Each payment has its own ID, recorded with the amount paid, which customer it was for, which order it was paying toward, and the date.
- Customers have the option of either paying by credit card or debit card.
- For a credit card we need the card number and the expiry date, and when paying there is a 1.5% surcharge added to the amount the customer pays.
- For a debit card we just need the card number and the name of the bank it is with.
- See all the payments made toward a specific order
- A customer may settle an order with several payments, no single payment can be more than what is still owed on that order.

A base class representing a payment made by a customer toward a specific order, and derived classes to capture the different types of payments
A payment history class, the full list of payments across all our customers

### Additional

- Update the central nursery ordering system to include payments. Rememeber it is responsible for adding, searching, updating, and reporting across the different modules.
- Where a class has derived classes, the base class should define the minimum data members and methods required by every type derived from it, and each derived class should override this behaviour where it needs to differ and add whatever else is specific to that type.
- As part of your design, decide which classes should be abstract, and which should be concrete. For each abstract class, decide which methods should be abstract methods that every derived class must implement.
