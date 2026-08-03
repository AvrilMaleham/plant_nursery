# Plant Nursery System

## Overview

This is a plant nursery management system that tracks plants, customers, and orders. The design is based on Brent's notes outlining what the nursery needs for its day to day operations.

## How to Run

```bash
python driver.py
```

## Design Decisions

### Separation of Concerns

I kept all the classes in separate files for a true separation of concerns. Each entity (`Plant`, `Customer`, `Order`) has its own class, and each collection (`PlantCatalog`, `CustomerDirectory`, `OrderHistory`) has its own class. I then created a `NurserySystem` manager class so the driver only needs to talk to one object. This ensures that order creation only happens for customers and plants that are registered in the system, and the order history is updated automatically to avoid mistakes.

### Display Methods on Collection Classes

Each collection class (`PlantCatalog`, `CustomerDirectory`, `OrderHistory`) has a `display_all` method even though a getter for the list already exists. This keeps the print logic inside the class rather than requiring a loop in the driver, which is cleaner and more reusable.

## Assumptions

### Plant

- No new categories will be added at this time, the four categories are fixed using a `Literal` type.
- Same plant name does not mean same price, two batches of the same plant can come in at different prices, which is why each plant has its own ID.
- A name will always be given and data types will be correct for now (no validation on inputs beyond what the type hints describe).
- IDs are generated using UUID for simplicity.
- Only stock and price can be changed once a `Plant` object is created, name and category are read only.

### Customer

- IDs are generated using UUID for simplicity.
- Customer details (name, email, phone) are not updated after creation, only getters are provided, no setters.

### Order

- No new statuses will be added at this time, the three statuses are fixed using a `Literal` type.
- No date manipulation is needed for now, so the order date is stored as a string in DD-MM-YYYY format rather than a `date` object for simplicity.
- Only the status can change once an `Order` object is created, all other fields are read only. Status changes go through `collect_order()` and `cancel_order()` methods rather than a setter, for more control over the business rules.

## Requirements Covered from Brent's Notes

### Plant Requirements

- Each plant tracked by a unique ID (since two batches of the same plant can come in at different times) — `Plant` uses UUID as the ID
- Plant name is recorded — `plant_name` attribute
- Plant category is one of: trees and shrubs, perennials, pot plants, or vegetable seedlings — enforced by the `PlantCategory` Literal type
- Plant price is recorded — `plant_price` attribute
- Plant stock level is tracked — `plant_stock` attribute
- Price cannot be negative (or zero) — validated in `__init__` and the `plant_price` setter, raises `ValueError`
- Stock cannot go below zero — validated in `__init__`, `plant_stock` setter, and `reduce_stock()`, raises `ValueError`
- Can add new plants without accidentally adding the same one twice — `PlantCatalog.catalog_plant()` checks for duplicate IDs before adding
- Can see a list of all plants available — `PlantCatalog.display_all_plants()` and `NurserySystem.display_all_plants()`

### Customer Requirements

- Customers each have a unique ID (since two customers can share the same name) — `Customer` uses UUID as the ID
- Customer name is recorded — `cust_name` attribute
- At least an email address or phone number is required — validated in `__init__`, raises `ValueError` if neither is provided
- Can add new customers without accidentally adding the same one twice — `CustomerDirectory.add_customer()` checks for duplicate IDs before adding
- Can see a list of all customers — `CustomerDirectory.display_all_customers()` and `NurserySystem.display_all_customers()`

### Order Requirements

- Each order records: customer, plant, quantity, date (DD-MM-YYYY), status, and order total — all stored as attributes on `Order`
- Each order is for one type of plant only — each `Order` object holds a single `Plant` reference
- 10% discount applied when ordering 10 or more of the same plant — handled in `__calculate_total()`
- Orders for zero (or fewer) plants are rejected — validated in `__init__`, raises `ValueError` if quantity < 1
- Stock is reduced immediately when an order is placed — `plant.reduce_stock(quantity)` is called in `Order.__init__`
- Stock can never go below zero — `check_stock()` and `reduce_stock()` enforce this before the order is created
- An order can only be cancelled while it is still pending — `cancel_order()` raises `ValueError` if status is "collected" or already "cancelled"
- Cancelling a pending order restores the stock — `cancel_order()` calls `plant.restore_stock(quantity)`
- Once collected, an order can no longer be cancelled — enforced in `cancel_order()`
- Can check whether a plant has enough stock before ordering — `Plant.check_stock()` method, also called automatically during order creation
- Orders can only be placed for customers and plants registered in the system — `NurserySystem.place_order()` validates both before creating the order
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
- Comments where relevant — included to explain design choices and assumptions
- Error conditions handled — `ValueError` and `TypeError` raised with descriptive messages for invalid inputs and illegal operations
