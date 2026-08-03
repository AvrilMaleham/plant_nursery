# plant_nursery

Create a README.md file explaining how your design reflects and supports the requirements
described in Brent's notes, including any assumptions you made where the notes did not
specify enough detail. Any format and structure is acceptable, as long as the explanation is
clear and your design decisions are justified

PLANT:
no new categories will be added at this moment
same name does not equal same price
assuming a name will be given and data types will be correct for now
how do we generate the ID - UUID cos easier
assuming only attribute stock and price can be changed

Included this even though we have the plant_list getter just to be explicit that there is a method to print each plant in the list so we dont need the print statement in the driver for this

CUSTOMER:
how do we generate the ID - UUID cos easier
Assuming Customer details are not updated after creation

Included this even though we have the plant_list getter just to be explicit that there is a method to print each plant in the list so we dont need the print statement in the driver for this

ORDER:
Assuming there will be no new statuses for now
Assuming we don't need to do any date manipulation for now so date is saved as string, not date for simplicity
Assuming only status can be changed once an Order object is created

I kept all the classes separate for a true separation of concerns. then i created the nursery system manager in order to have the collection objects all in one place so the driver only needs to talk to one collection object and we can be sure that order creation only happens for customers and plants that are in the system, then it updates the order history too to avoid mistakes.
