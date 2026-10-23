# Plant Nursery System

## Overview

This is a plant nursery management system that tracks plants, customers, orders, and payments. The design is based on Brent's notes outlining what the nursery needs for its day to day operations. The finished version is a website on this computer. The nursery team and each customer log in, and PostgreSQL stores the plants, customers, orders, payments, and logins.

## Getting started

Do the steps in order. Run every command in a terminal, inside this project folder. Use the same terminal for steps 2 to 6.

### Before you start

- Python 3.10 or later. Check it with:

```bash
python --version
```

- PostgreSQL installed and running on port 5432.
- The username and password you chose when you installed PostgreSQL. These are the same ones pgAdmin asks for. The username is usually `postgres`.

### 1. Install the Python packages

```bash
pip install -r requirements.txt
```

### 2. Set the database connection

Replace `YOUR_USERNAME` and `YOUR_PASSWORD` with your own, then run it:

```bash
export DATABASE_URL="postgresql+psycopg://YOUR_USERNAME:YOUR_PASSWORD@127.0.0.1:5432/plant_nursery"
```

Nothing is printed when it works. This only lasts for the terminal you ran it in. If you open a new terminal window, run it again.

### 3. Create the database and load the sample

```bash
python seed.py
```

This creates the `plant_nursery` database, creates the tables, and loads the sample data. It ends with a line starting `Nursery System: 6 plants, 3 customers...`. Running it again clears the tables and loads the same sample.

### 4. Start the website

```bash
python app.py
```

Leave this terminal running while you use the site.

### 5. Open the website and log in

Open http://127.0.0.1:5000 and log in with one of these:

| Who | Username | Password |
| --- | --- | --- |
| Nursery team | teamUsername | TeamPassword |
| Avril, staff | avrilUsername | AvrilPassword |
| Jane, student | janeUsername | JanePassword |
| Sam, community | samUsername | SamPassword |

The team sees the whole nursery. A customer only sees their own details, orders, and payments.

### 6. Run the tests (optional)

Open a second terminal in this folder, run step 2 again in it, then run:

```bash
python -m pytest
```

The tests use a separate database called `plant_nursery_test`, so your sample data is not changed.

### Optional: see the data in pgAdmin

Right-click the server and choose Refresh. Open Databases, then `plant_nursery`, then Schemas, public, Tables. The tables are `plants`, `customers`, `orders`, `order_items`, `payments`, and `users`.

### About the sample data

The sample covers every part of the site: a sold-out cactus, Avril's lavender order that has been pending for ten days, Jane's cancelled order and her order of twelve tomato punnets, and Sam's order of an orchid and lavender, paid with a debit card and then a credit card, and collected.

The unit tests in `tests/test_business_rules.py` check the business rules without the database. The integration tests in `tests/test_workflows.py` sign in through the web pages and follow an order, a counter sale, and the reports from start to finish. To run one file:

```bash
python -m pytest tests/test_business_rules.py
python -m pytest tests/test_workflows.py
```

## Design Decisions

### Separation of Concerns

Each entity and each collection has its own file. `Order`, `OrderItem`, `PlantCatalog`, `CustomerDirectory`, `OrderHistory`, and `PaymentHistory` are each in their own file because they do different jobs. A base class stays in the same file as the classes that inherit from it, because those types only make sense together: `plant.py` holds the plant hierarchy, `customer.py` holds the customer hierarchy, and `payment.py` holds the payment hierarchy. The six custom exceptions (four for order rules, two for login and access) share `exceptions.py` so `Plant`, `Order`, and `NurserySystem` can import the same types.

`NurserySystem` is the only object the rest of the application talks to. It checks that a customer and the plants are already registered, asks the customer whether a new order is allowed, and then adds the order to `OrderHistory`. That keeps registration and the business rules in one place, so an order cannot be created for someone who was never added, or left unrecorded.

### Display Methods on Collection Classes

Each collection has a getter that returns a copy of its list, and a `display_all` method that prints it. The copy means a caller cannot append to or clear the real list. The display method is separate so the empty-state message and the loop stay inside the collection, and the caller does not have to repeat that loop for plants, customers, orders, and payments.

`CustomerDirectory` also has `display_staff_customers`, `display_student_customers`, and `display_community_customers`. Brent asked to see the types separately rather than one mixed list. Those methods call `get_customers_by_type`, which matches `customer_type()`, so the directory does not need to import `StaffCustomer` or `CommunityCustomer`.

### Inheritance Hierarchies

`Plant`, `Customer`, and `Payment` are abstract. They hold the data and checks every subtype needs, and the concrete classes only add what is different.

Trees, shrubs, and perennials are both sold per plant, so `sale_unit()` returning `"plant"` lives once on `IndividualPlant`. `TreeAndShrub` and `Perennial` only supply their own `plant_type()`. `PotPlant` and `VegetableSeedling` stay direct subclasses of `Plant` because their units are `"pot"` and `"punnet"`.

Staff and students share the $100 limit and may collect while they still owe money. That behaviour is `can_place_order()` and `can_collect_order()` on `UniversityCustomer`. `StaffCustomer` and `StudentCustomer` only supply the type name and the discount rate. `CommunityCustomer` stays a direct subclass of `Customer` because its rules are different: one pending order, and the order must be paid off before collection.

Both card payments need a card number, so the attribute, the required-value check, and the getter are on `Payment`. `CreditCardPayment` adds the expiry date and a 1.5% surcharge. `DebitCardPayment` adds the bank name and no surcharge.

A subclass does not define `__init__` when it would only pass the same arguments to its parent. `UniversityCustomer`, `IndividualPlant`, `StaffCustomer`, `StudentCustomer`, `CommunityCustomer`, `TreeAndShrub`, and `Perennial` are created by the initialiser they inherit. `PotPlant`, `VegetableSeedling`, `CreditCardPayment`, and `DebitCardPayment` do define `__init__`, because each one adds and checks something of its own.

### Order Rules are in the Customer Class, not the Order Class

`Order` should not contain `if customer_type() == "staff"`. The rule belongs to the customer, and the three types do not share one rule. `NurserySystem.place_order()` prices the order first, then asks `customer.can_place_order(pending_count, order_total)`. The pending count comes from `OrderHistory`, because a customer does not store their own orders. The order total lets staff and students be refused when this order would take them over $100, and community customers ignore it. If the answer is no, the system raises `OrderNotAllowedError`. `Order.collect_order()` asks `customer.can_collect_order(remaining_balance)` and raises `OrderCannotBeCollectedError` when the answer is no. Adding another customer type would mean a new subclass, not a new branch inside `Order`.

### The Same Plant Can Only Appear Once in an Order

The 10% discount is per line, in `OrderItem.__calculate_cost()`, using `BULK_DISCOUNT_QUANTITY` (10) and `BULK_DISCOUNT_RATE` (0.10). Quantity means that plant's sale unit. If the same catalog entry could appear on two lines, neither line might reach 10, and the discount would be missed, or the two lines would have to be merged. `Order.__init__` rejects a repeated plant ID instead. A different pot size is a different `PotPlant` object, so a small fern and a large fern can both be on one order, and only ten or more of the same size gets the discount. Ten punnets of one seedling type works the same way, because stock and quantity are punnets, not individual seedlings.

### Payments Follow the Existing Structure

`PaymentHistory` holds the list, the same way `OrderHistory` holds orders. `NurserySystem.record_payment()` checks that the customer is registered, the order is in this nursery, and the payment's customer is the customer on the order. `Order.record_payment()` is what changes the amount paid and the balance, and it rejects a payment larger than what is still owed. That matches `collect_order()` and `cancel_order()`, which are the methods that change status. `amount` is what comes off the order. `amount_charged()` adds `surcharge_rate()`, so a credit card payment of the remaining balance reduces the order by that balance and charges the customer 1.5% more.

### Saving in PostgreSQL

Plants, customers, orders, order items, payments, and users are stored in PostgreSQL on port 5432, which is the server pgAdmin opens. SQLAlchemy maps the classes onto those tables. `seed.py` creates the `plant_nursery` database if it is missing, creates the tables, and loads the sample. The connection is the `DATABASE_URL` environment variable, including the password from the PostgreSQL installer. The password is not stored in the project.

### A Customer Number Instead of Showing the ID

Two customers can share a name, so a name on its own is not enough on screen. The stored identity stays `cust_id`, a UUID, and that is what the database and the routes use. A UUID is awkward to read out at the desk. `Customer.customer_number` takes the first eight characters of that UUID and shows them in uppercase. The number comes from the existing ID, so it stays the same for that customer and does not need its own column. The customer sees it on their own pages. The nursery team sees it wherever a customer is chosen or listed, including orders, payments, invoices, and receipts.

### Custom Exceptions in Their Own File

Illegal order operations raise `InsufficientStockError`, `OrderNotAllowedError`, `OrderCannotBeCollectedError`, or `OrderCannotBeCancelledError` instead of a generic `ValueError`, so the caller can catch the specific problem. They live in `exceptions.py` so `Plant`, `Order`, and `NurserySystem` import the same types. Each one stores the message in `__message` and passes it to `Exception`. They do not print. Ordinary bad input, such as a price of 0 or a missing card number, is still a `ValueError` because that is invalid data, not an illegal step in an order that already exists.

### Login, and What Each Person Can Do

Everyone logs in with a username and password before they see a dashboard. `User` stores the role as `team` or `customer`. The team account is not linked to a customer. A customer account must be linked to one. Those rules are checked in `User.__init__` and again by checks on the `users` table.

`NurserySystem.login()` looks the username up and checks the password. A missing username and a wrong password both raise `LoginFailedError` with the same message, so the login page does not reveal which of the two failed. The controller then stores the user id in the session cookie. The next request calls `resume()`, and the role checks run as that person. Logging out clears the cookie. Pages are sent with `Cache-Control: no-store`, so the back button does not restore a logged-in page from the browser cache after logout.

`__require_login()`, `__require_team()`, and `__require_self_or_team()` are the checks the other methods call first. A customer can see their own details, search plants, place an order, pay toward their own orders, cancel their own pending unpaid order, and open their own invoice and receipts. The team can add and remove plants and customers, change price and stock, place an order or take a payment for someone at the counter, see every customer, order, and payment, and open the reports. `collect_order()` calls `__require_team()` before it asks the order whether collection is allowed, because only the team can confirm the plants have left the nursery. The earlier rules still run after the role check. A community customer still cannot hold two pending orders, and still has to pay in full before collection. A staff member or student still cannot place an order that would take what they owe over $100, so a balance of $90 blocks a $20 order but allows a $10 one.

When the team adds a customer, the form also creates that customer's login through `add_user()`. A customer does not register themselves.

### Passwords Are Stored as Hashes

`User` hashes the password with Werkzeug's `generate_password_hash` before it is saved. `check_password()` compares what was typed with that hash. The `users` table has `password_hash` and no column for the typed password. The sample passwords in the table above are what you type on the login page.

### Model, View, and Controller

`model/` holds the domain classes, the custom exceptions, the invoice and receipt objects, and the database mapping. `NurserySystem` is still the only object the controllers talk to for the nursery rules. `view/templates/` and `view/static/` present the pages, the CSS, and the plant photos. A template shows what it was given and sends the next action back as a form or a link. `controller/` reads that action, calls `NurserySystem`, and chooses the template. `app.py` creates the Flask application and points it at the `view` folders.

`controller/blueprint.py` opens one database session for each request. The session commits when the request finishes, and rolls back when it does not. A refused rule is also rolled back in `explain()`, and the exception message is flashed on the page the person came from. A failed payment or a refused order does not stay half-saved, and the person is told the reason in the model's own words.

### Single-Table Inheritance in PostgreSQL

Plants, customers, and payments each use single-table inheritance. `Plant`, `Customer`, and `Payment` stay abstract, and each hierarchy has one table: `plants`, `customers`, and `payments`. The type is a column on that table (`plant_type`, `customer_type`, `payment_type`). SQLAlchemy uses that column as `polymorphic_on`, so a loaded row is built as a `PotPlant`, a `StudentCustomer`, or a `CreditCardPayment`. Columns that belong to one subtype stay on the same table and are null for the others: `pot_size` and `seedlings_per_punnet` on plants, `expiry_date` and `bank_name` on payments. Check constraints keep that split, so a pot plant cannot be saved without a pot size, and a tree cannot be saved with one. Staff, students, and community customers already share the same columns, which is why they do not need a column that only one of them uses.

The lists on screen are mixed types read together, and each subtype only adds a column or two, so one table and one row per object matches how the pages load them. Joined-table inheritance would put those few columns in a second table and join it for every list. Concrete-table inheritance would repeat the shared columns once per subtype. Orders, order items, and users are separate tables. An order item points at its plant and its order. A payment points at its customer and its order. A user points at a customer only when the role is `customer`.

The file save from the earlier version is gone. Each successful request commits to PostgreSQL, so the data is still there after the website stops and is loaded again when it starts. `seed.py` creates the database if it is missing, creates the tables, and loads the sample. Starting the website also creates any missing tables, through `init_db()`, and does not load the sample.

### Search, Photos, and Managing the Catalog

`NurserySystem.search_plants()` matches part of the common name, ignoring letter case, and can also keep one of the four plant types, a minimum price, a maximum price, and plants whose stock is greater than 0. The search page turns the examples from Brent's notes into three bands before it calls that method. Under $10 uses a maximum of 9.99. From $10 to $30 uses 10 and 30. Over $30 uses a minimum of 30.01. A plant priced at exactly $10 or exactly $30 stays in the middle band, because the model includes its maximum and the bands are built so a boundary price belongs to one band. The plant page shows the stored fields and the photo from `view/static/images/`.

When the team adds a plant, the photo has to be a PNG, JPG, GIF, or WEBP file. It is saved under a new id plus that extension, so a later upload does not overwrite an existing file. Price and stock updates go through `update_plant_price()` and `update_plant_stock()`, which use the same setters as before, so stock still cannot be typed in as 0. They are separate routes (`/plants/<id>/price` and `/plants/<id>/stock`) with a form each. One combined form would send the stock of a sold-out plant as 0, which the model refuses, and that refusal would also roll back the price change. `remove_plant()` refuses a plant that appears on any order, including a cancelled one, so the order history still has its plant. `remove_customer()` refuses a customer who has placed any order. When a customer has never ordered, their login is deleted with them.

### Invoices, Receipts, and Orders Waiting to Be Collected

`Invoice` is built from the order. Each `InvoiceLine` shows the plant, the quantity in that plant's sale unit, the line cost, and the bulk discount on that line, which is the difference between the full line and `item_cost` when the quantity is at least 10. The customer discount is the difference between the sum of the line costs and `order_total`. The order page is the invoice. It shows the order number (`Order.order_number`, eight characters taken from the order ID the same way the customer number is), the customer, the date, and a table with each item's quantity, price per unit, bulk discount, and line cost. The bulk discount column only appears when a line has one. Under the table are the total cost, the bulk discount, the customer discount, and the **total to pay**, followed by what has been paid and what is still outstanding. The total to pay stays on the page after the order is settled, so a printed copy still shows what the order came to. The print button uses the browser print dialog. The buttons and the payment form are marked `no-print`, so the printed page is the invoice.

`Receipt` is built from one payment. It shows the amount applied to the order, the card type, the surcharge from `amount_charged()`, and what was still owed on the order after that payment. `receipt_for()` walks that order's payments in time order so an earlier receipt still shows the balance left at that time, even after a later payment. A credit card payment of the remaining balance still reduces the order by the balance and charges 1.5% more. The receipt page has its own print button.

`Order.is_uncollected_too_long()` is true when the status is still `pending` and at least `UNCOLLECTED_AFTER_DAYS` (7) days have passed since the order date. Collected and cancelled orders are not flagged. The team dashboard and the customer's own order list both show that flag, and the order's `__str__` adds the same follow-up text.

### Reports

`plant_order_history()` returns every order that includes that plant, oldest first, including cancelled orders. `customer_activity()` builds an `ActivityRecord` for each placed, paid, collected, and cancelled event, sorted by date. `most_ordered_plants()` and `least_ordered_plants()` count quantity on orders that are not cancelled. A plant that has never been ordered is included as 0, so it still appears at the top of the least-ordered list. Ties are alphabetical by plant name. `revenue()` totals `amount_charged()` for payments in a day, a week, or a month, so a credit card surcharge is part of the revenue. A week is the chosen date plus the next six days. A month is the calendar month that contains the chosen date. All five reports call `__require_team()`.

### Login and Authorisation Exceptions

`LoginFailedError` and `NotAuthorisedError` are the two exceptions added for this version. They live in `exceptions.py` with the original four, and they store their message the same way. The controllers catch them in `RULE_ERRORS`, together with `ValueError`, `TypeError`, and the four order exceptions, and `explain()` flashes `str(error)`. A wrong password, a customer opening someone else's order, and a customer trying to collect an order all come back as a message on the page.

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
- Staff and students are blocked when the new order would take what they owe over $100, as Brent's final notes say, not only when they already owe more than $100. `UniversityCustomer.can_place_order()` compares `balance + order_total` with `CREDIT_LIMIT`. Owing exactly $100 after the order is allowed, because the limit is "over $100". A customer who already owes exactly $100 is blocked from any further order, since any order total is more than $0.

### Order

- No new statuses will be added at this time, the three statuses are fixed using a `Literal` type.
- Order date is stored as a string in DD-MM-YYYY format. It defaults to today, can be set on creation or via a setter, and is validated as a real calendar date.
- Status changes go through `collect_order()` and `cancel_order()` methods rather than a setter, for more control over the business rules.
- Order items cannot be updated after they are created. There would be a lot of downstream changes from changing an order item such as stock, discounts, order total and customer balance.

### Payment

- Card number, expiry date, and bank name just need to be given, Brent did not specify a format.
- The 1.5% surcharge is added to what the customer pays, the order only comes down by the amount applied to it. The rate is `CREDIT_CARD_SURCHARGE_RATE`. A debit card uses `DEBIT_CARD_SURCHARGE_RATE`, which is 0.

### Login and the Website

- The nursery team shares one username and password. The team creates a customer's login when they add that customer. A customer does not sign themselves up.
- A wrong username and a wrong password show the same message.
- The website runs on this one computer. It is not set up for anyone to reach it from another machine.
- The session cookie uses `FLASK_SECRET_KEY` when that variable is set. Otherwise it uses a fixed local value, which is enough for one computer in the nursery.
- Plant photos are PNG, JPG, GIF, or WEBP. The sample plants already have photos in the project.
- A price search uses three bands: under $10, $10 to $30, and over $30. A plant at exactly $10 or $30 is in the middle band.
- An order needs a follow-up when it is still pending and at least seven days have passed since the order date. The order date counts as day zero. Collected and cancelled orders are not flagged.
- Only the team can mark an order collected. The customer can cancel their own order while it is still pending and nothing has been paid toward it. The team can cancel one for them.
- A plant that has been on any order, including a cancelled order, cannot be removed. A customer who has placed any order cannot be removed. A customer who has never ordered has their login removed with them.
- Popularity counts the quantity on orders that are not cancelled. A plant that has never been ordered is included with a count of 0. Cancelled orders still appear in a plant's order history.
- Revenue is the amount charged, so a credit card surcharge is included. A week is the chosen date and the next six days. A month is the calendar month that contains the chosen date.
- Card numbers are stored as they were typed. Brent did not ask for them to be hidden or checked as real card numbers.
- The invoice and the receipt are printed from those pages, through the browser's print dialog. The buttons and the navigation are left off the printed page.

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
- Staff and students can accumulate a balance and can collect while they still owe money. Both rules are on `UniversityCustomer`: `can_place_order()` allows an order only when `balance` plus the new order's total is at most `CREDIT_LIMIT` ($100), and `can_collect_order()` returns `True`. `NurserySystem.place_order()` turns a false answer into `OrderNotAllowedError`.

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
- Invalid data raises `ValueError` or `TypeError`. An order that breaks one of Brent's rules raises one of the four order exceptions, and a failed login or a disallowed action raises `LoginFailedError` or `NotAuthorisedError`. The caller catches all six.

## Requirements from Brent's Final Notes

### Who Can Log In

- The team shares one login. Each customer has their own, created when the team adds them. `login()` checks the username and the hashed password and raises `LoginFailedError` when they do not match. After login, `resume()` restores that person on the next request, and the navigation and the model checks follow the role. A customer reaches their own dashboard. The team reaches the nursery dashboard.

### What a Customer Can Do

- The customer page shows their own name, contact details, customer number, type, and balance. They can update their own name, email, and phone. At least one of email or phone still has to remain.
- `search_plants()` is the plant search. The page can narrow it by type, by one of the three price bands, and to plants with stock greater than 0. The plant page shows every stored field and the photo.
- A customer places an order from plants they choose. The same `place_order()` path checks stock, the pending-order rule, the $100 limit, the bulk discount, and the customer discount. They pay toward their own order with a credit card or a debit card, and they can cancel it while it is pending and unpaid. Their pages list their own orders and payments. The order page is their invoice, and each payment has a receipt.

### What the Team Can Do

- The team adds and removes plants and customers, uploads a photo for a new plant, and updates price and stock. Price and stock have separate forms, so a sold-out plant can be repriced without being restocked, and a new batch can be added without touching the price. `remove_plant()` and `remove_customer()` refuse a plant or a customer that is already on an order. The team can search for a plant by name with the same search the customers use.
- The team places an order and records a payment for a chosen customer. Those calls go through `place_order()` and `record_payment()`, so the customer's own rules still apply. The team sees every order, with a status filter, every payment, and customers one type at a time through `filter_customers()`. They can cancel an order under the same unpaid-pending rule, and they are the only ones who can call `collect_order()`.
- The team can open any customer's invoice and any receipt.

### Orders Waiting Seven Days

- `is_uncollected_too_long()` flags a pending order once seven days have passed. The team dashboard lists those orders, and the customer's own list marks theirs the same way.

### Reports

- `plant_order_history()` is the order history for one plant. `customer_activity()` is the dated record of that customer's orders being placed, paid toward, collected, or cancelled. `most_ordered_plants()` and `least_ordered_plants()` rank the catalog. `revenue()` totals what was charged over a day, a week, or a month. The reports page is limited to the team.

### Database, Layout, and Tests

- Plants, customers, orders, order items, payments, and users are stored in PostgreSQL through SQLAlchemy. The three class hierarchies use single-table inheritance, described above. `seed.py` loads a sample that exercises the rules from all three sets of notes.
- `model/`, `view/`, and `controller/` are the three layers. The templates do not apply the business rules, and the model does not build HTML.
- `LoginFailedError` and `NotAuthorisedError` are the two new custom exceptions. The controllers flash those, and the original four, with the message the model raised.
- `tests/test_business_rules.py` holds the unit tests for discounts, the credit limit, the pending-order rule, collection, cancellation, stock, payments, the seven-day flag, invoices, receipts, and password hashing. `tests/test_workflows.py` holds three integration tests: a customer searching, ordering, and paying; the team selling at the counter and collecting; and an overdue order being flagged, reported, and then cleared.

## Generative AI

Cursor, with the Grok model, was used while building this application and while updating this README. It was used to draft and revise the Flask pages, the controllers, the SQLAlchemy mapping, the sample data in `seed.py`, and the pytest tests, and to check this README against Brent's notes and the code.

Cursor, with Anthropic's Claude model, was then used to review the finished application against the three assignment briefs. It was used to find places where this README did not match the code, and to correct the README text about the $100 limit, the number of custom exceptions, and the Python version. It was not used to write the application code in that step.

The design decisions and assumptions in this file are the ones in the submitted code.
