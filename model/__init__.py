"""
Domain model for the nursery.

These classes hold the business rules. Controllers call them. Templates only
display what a controller passes in.

PostgreSQL will store Plant, Customer, and Payment with single-table
inheritance: one table per hierarchy, and a type column for the concrete
class. IndividualPlant and UniversityCustomer stay abstract in Python. They
do not get a table or a type value. The type column stores the same string
the class already returns, such as "pot plants", "staff", or "credit card".

Customers add no columns of their own, so a second table per type would only
hold an id. Payments add one field each, expiry date or bank name, and every
payment screen reads them together. Plants add pot size or seedlings per
punnet for one type only, and search, price, and stock filters read the
whole catalog at once. One table avoids a join or a union on those reads.

Joined tables would keep pot size and expiry date out of the other rows, but
trees, shrubs, perennials, staff, and students would each be a table of ids.
Concrete tables would copy the shared columns into every table, and an
order's plant would be a union across four tables.
"""
