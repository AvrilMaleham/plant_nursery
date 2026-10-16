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

Each entity and each collection has its own file. `Order`, `OrderItem`, `PlantCatalog`, `CustomerDirectory`, `OrderHistory`, and `PaymentHistory` are each in their own file because they do different jobs. A base class stays in the same file as the classes that inherit from it, because those types only make sense together: `plant.py` holds the plant hierarchy, `customer.py` holds the customer hierarchy, and `payment.py` holds the payment hierarchy. The four custom exceptions share `exceptions.py` so `Plant`, `Order`, and `NurserySystem` can import the same types.

`NurserySystem` is the only object the driver talks to. It checks that a customer and the plants are already registered, asks the customer whether a new order is allowed, and then adds the order to `OrderHistory`. That keeps registration and the business rules in one place, so the driver cannot create an order for someone who was never added, or forget to record it.

### Display Methods on Collection Classes

Each collection has a getter that returns a copy of its list, and a `display_all` method that prints it. The copy means a caller cannot append to or clear the real list. The display method is separate so the empty-state message and the loop stay inside the collection, and the driver does not have to repeat that loop for plants, customers, orders, and payments.

`CustomerDirectory` also has `display_staff_customers`, `display_student_customers`, and `display_community_customers`. Brent asked to see the types separately rather than one mixed list. Those methods call `get_customers_by_type`, which matches `customer_type()`, so the directory does not need to import `StaffCustomer` or `CommunityCustomer`.

### Inheritance Hierarchies

`Plant`, `Customer`, and `Payment` are abstract. They hold the data and checks every subtype needs, and the concrete classes only add what is different.

Trees, shrubs, and perennials are both sold per plant, so `sale_unit()` returning `"plant"` lives once on `IndividualPlant`. `TreeAndShrub` and `Perennial` only supply their own `plant_type()`. `PotPlant` and `VegetableSeedling` stay direct subclasses of `Plant` because their units are `"pot"` and `"punnet"`.

Staff and students share the $100 limit and may collect while they still owe money. That behaviour is `can_place_order()` and `can_collect_order()` on `UniversityCustomer`. `StaffCustomer` and `StudentCustomer` only supply the type name and the discount rate. `CommunityCustomer` stays a direct subclass of `Customer` because its rules are different: one pending order, and the order must be paid off before collection.

Both card payments need a card number, so the attribute, the required-value check, and the getter are on `Payment`. `CreditCardPayment` adds the expiry date and a 1.5% surcharge. `DebitCardPayment` adds the bank name and no surcharge.

A subclass does not define `__init__` when it would only pass the same arguments to its parent. `UniversityCustomer`, `IndividualPlant`, `StaffCustomer`, `StudentCustomer`, `CommunityCustomer`, `TreeAndShrub`, and `Perennial` are created by the initialiser they inherit. `PotPlant`, `VegetableSeedling`, `CreditCardPayment`, and `DebitCardPayment` do define `__init__`, because each one adds and checks something of its own.

### Order Rules are in the Customer Class, not the Order Class

`Order` should not contain `if customer_type() == "staff"`. The rule belongs to the customer, and the three types do not share one rule. `NurserySystem.place_order()` asks `customer.can_place_order(pending_count)`. The pending count comes from `OrderHistory`, because a customer does not store their own orders. If the answer is no, the system raises `OrderNotAllowedError`. `Order.collect_order()` asks `customer.can_collect_order(remaining_balance)` and raises `OrderCannotBeCollectedError` when the answer is no. Adding another customer type would mean a new subclass, not a new branch inside `Order`.

### The Same Plant Can Only Appear Once in an Order

The 10% discount is per line, in `OrderItem.__calculate_cost()`, using `BULK_DISCOUNT_QUANTITY` (10) and `BULK_DISCOUNT_RATE` (0.10). Quantity means that plant's sale unit. If the same catalog entry could appear on two lines, neither line might reach 10, and the discount would be missed, or the two lines would have to be merged. `Order.__init__` rejects a repeated plant ID instead. A different pot size is a different `PotPlant` object, so a small fern and a large fern can both be on one order, and only ten or more of the same size gets the discount. Ten punnets of one seedling type works the same way, because stock and quantity are punnets, not individual seedlings.

### Payments Follow the Existing Structure

`PaymentHistory` holds the list, the same way `OrderHistory` holds orders. `NurserySystem.record_payment()` checks that the customer is registered, the order is in this nursery, and the payment's customer is the customer on the order. `Order.record_payment()` is what changes the amount paid and the balance, and it rejects a payment larger than what is still owed. That matches `collect_order()` and `cancel_order()`, which are the methods that change status. `amount` is what comes off the order. `amount_charged()` adds `surcharge_rate()`, so a credit card payment of the remaining balance reduces the order by that balance and charges the customer 1.5% more.

### Saving with Pickle

I used a pickle file rather than text or JSON because the nursery is a graph of objects, not a flat list. One `NurserySystem` pickle keeps each order pointing at the same customer and plant objects that are in the catalog and directory. Loading does not have to rebuild subclasses, UUIDs, or those links line by line. `load_from_file()` replaces the four collections on the new system with the ones from the file.

### Custom Exceptions in Their Own File

Illegal order operations raise `InsufficientStockError`, `OrderNotAllowedError`, `OrderCannotBeCollectedError`, or `OrderCannotBeCancelledError` instead of a generic `ValueError`, so the driver can catch the specific problem. They live in `exceptions.py` so `Plant`, `Order`, and `NurserySystem` import the same types. Each one stores the message in `__message` and passes it to `Exception`. They do not print. Ordinary bad input, such as a price of 0 or a missing card number, is still a `ValueError` because that is invalid data, not an illegal step in an order that already exists.

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
- Staff and students are blocked when their current balance is already over $100, not when the new order would take them over. `UniversityCustomer.can_place_order()` compares `balance` with `CREDIT_LIMIT`.

### Order

- No new statuses will be added at this time, the three statuses are fixed using a `Literal` type.
- Order date is stored as a string in DD-MM-YYYY format. It defaults to today, can be set on creation or via a setter, and is validated as a real calendar date.
- Status changes go through `collect_order()` and `cancel_order()` methods rather than a setter, for more control over the business rules.
- Order items cannot be updated after they are created. There would be a lot of downstream changes from changing an order item such as stock, discounts, order total and customer balance.

### Payment

- Card number, expiry date, and bank name just need to be given, Brent did not specify a format.
- The 1.5% surcharge is added to what the customer pays, the order only comes down by the amount applied to it. The rate is `CREDIT_CARD_SURCHARGE_RATE`. A debit card uses `DEBIT_CARD_SURCHARGE_RATE`, which is 0.

## Requirements Covered from Brent's Notes

### Plant Requirements

- Two batches of the same plant can arrive at different prices, so identity is `plant_id` (a UUID), not the name. `PlantCatalog.catalog_plant()` rejects a second add of the same ID.
- The four sale types are subclasses. `TreeAndShrub` and `Perennial` inherit `IndividualPlant.sale_unit()`, which returns `"plant"`, and their price is `plant_price` per plant. `PotPlant` stores `pot_size` (`small`, `medium`, or `large`) and is stocked by the pot. `VegetableSeedling` is stocked by the punnet, `sale_unit()` returns `"punnet"`, and `seedlings_per_punnet` defaults to 6. An order quantity is always in that same unit, because `OrderItem` stores the plant and reduces `plant_stock` by the quantity it was given.
- Price and starting stock must be greater than 0. Both checks are in the `plant_price` and `plant_stock` setters, and `Plant.__init__` assigns through those setters so creation and a later update use the same rule. `reduce_stock()` writes the private stock field itself, so an order can still take stock to exactly 0. `check_stock()` stops it going below 0 and raises `InsufficientStockError`.
- `PlantCatalog.display_all_plants()` prints everything, including sold-out plants. `get_available_plants()` and `display_available_plants()` keep only stock greater than 0. `NurserySystem` exposes the same operations.

### Customer Requirements

- Two people can share a name, so identity is `cust_id`. At least one of email or phone is required in `Customer.__init__` and again in the setters, so clearing one contact method cannot leave both empty. Name, email, and phone have setters. ID and balance do not. Balance changes only through `add_to_balance()` and `reduce_balance()`.
- `Customer.__str__` prints the type, the contact details, and the balance together.
- `CustomerDirectory.display_all_customers()` prints everyone. The three `display_*_customers()` methods print one type at a time, using `customer_type()`.
- The discount comes off the whole order, after each line has already applied its own bulk discount. `Order.__init__` sums `item_cost`, then calls `customer.apply_discount()`. That method uses `discount_rate()`: `STAFF_DISCOUNT_RATE` (0.01), `STUDENT_DISCOUNT_RATE` (0.05), or `COMMUNITY_DISCOUNT_RATE` (0.0).
- Community customers cannot hold two pending orders, and they cannot collect until the order's remaining balance is 0. Those are `CommunityCustomer.can_place_order()` and `can_collect_order()`. `NurserySystem` passes the pending count from `OrderHistory.get_pending_order_count()`.
- Staff and students can accumulate a balance and can collect while they still owe money. Both rules are on `UniversityCustomer`: `can_place_order()` allows another order only while `balance` is at most `CREDIT_LIMIT` ($100), and `can_collect_order()` returns `True`. `NurserySystem.place_order()` turns a false answer into `OrderNotAllowedError`.

### Order Requirements

- An order is one `Order` with a customer, a DD-MM-YYYY date, a status, a total, an amount paid, and a list of `OrderItem`s. `place_order()` takes a list of `(plant, quantity)` pairs, so one order can mix shrubs, pot plants, and seedlings. Each pair becomes an `OrderItem` with its own plant, quantity, and `item_cost`.
- `OrderItem.validate()` is the quantity and stock check. Quantity must be at least 1, and `plant.check_stock()` must pass. `Order.__init__` runs that check for every line before it creates any `OrderItem`, so a later line failing does not leave an earlier line's stock already reduced. Creating the item then reduces stock immediately.
- Ten or more on one line gets 10% off that line only, inside `__calculate_cost()`. For a pot plant the line is one pot size. For a seedling the line is a number of punnets. The customer discount is applied afterwards to the sum of the lines.
- Placing the order calls `add_to_balance(order_total)`, so the amount owing stays until a payment or a cancellation. `cancel_order()` is allowed only while the status is still `"pending"` and `amount_paid` is 0. It restores each item's stock, takes the total back off the balance, and sets the status to `"cancelled"`. A collected order, a cancelled order, or one that has been paid toward raises `OrderCannotBeCancelledError`.
- `collect_order()` refuses an order that is already collected or cancelled, then asks the customer whether collection is allowed. There is no status setter, so those are the only transitions.
- `NurserySystem.place_order()` looks the customer and each plant up by ID before it builds the `Order`. A valid object that was never added is rejected. The ID check, rather than object identity, still accepts the registered customer if the caller holds another Python object with the same ID.

### Payment Requirements

- A payment has to be a `CreditCardPayment` or a `DebitCardPayment`. `Payment` is abstract and stores the ID, the amount applied to the order, the customer, the order, the date, and the card number. Credit adds `expiry_date` and `CREDIT_CARD_SURCHARGE_RATE` (0.015). Debit adds `bank_name` and a surcharge of 0. `amount_charged()` is `amount * (1 + surcharge_rate())`, so the surcharge is what the customer pays, not an extra reduction of the order.
- `Order.record_payment()` rejects an amount that is not greater than 0 or is more than `remaining_balance`. Calling it again is allowed, so one order can be settled in parts. Each call adds to `amount_paid` and calls `reduce_balance()`.
- `NurserySystem.record_payment()` records the payment only after the registration and ownership checks. `get_customer_payments()`, `get_order_payments()`, and `display_all_payments()` are the three views Brent asked for: one customer, one order, and every payment.

### Reporting Requirements

- `get_customer_order_history()` returns every order for that customer ID, after `NurserySystem` has checked the customer is registered. `display_all_orders()` prints the full history, including collected and cancelled orders.

### Technical Requirements

- A class that adds or checks its own attributes defines `__init__`. A subclass that does not add attributes uses the parent initialiser. That is why staff, students, community customers, trees, shrubs, and perennials do not define their own.
- Attributes use name mangling (`__`). Attributes that hold another object or a list are annotated, for example `OrderItem.__plant: Plant` and `PlantCatalog.__plant_list: list[Plant]`.
- Getters and setters use `@property`. Setters exist only where a change is allowed. Status, balance, and a placed order's items change through methods instead.
- `__str__` is implemented on `Plant`, `Customer`, `Order`, `OrderItem`, `Payment`, the payment subclasses, and `NurserySystem`.
- Every class and method has a docstring. Parameters and return values include their types. Method parameters and return values have type hints, and so do the object and list attributes.
- Comments explain the choices that are not obvious from the code, such as why stock can reach 0 only through an order, and why a list getter returns a copy.
- Invalid data raises `ValueError` or `TypeError`. An order that breaks one of Brent's rules raises one of the four custom exceptions, and `driver.py` catches them.
