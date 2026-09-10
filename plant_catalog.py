from plant import Plant

class PlantCatalog:
    """A complete catalog of plants available at the nursery"""
    
    def __init__(self) -> None:
        """Initialise a new PlantCatalog object"""
        
        self.__plant_list = []
        
    # ---------- Getters and Setters ----------
        
    @property
    def plant_list(self) -> list[Plant]:
        """Get the list of plants"""
        # A copy is returned so callers cannot append to or clear the internal list.
        # New plants still have to go through catalog_plant(), which checks for duplicate IDs.
        return self.__plant_list.copy()
        
     # ---------- Methods ----------

    def catalog_plant(self, plant: Plant) -> None:
        """
        Adds a new plant to the catalog.

        :param plant: Plant to add to the catalog
        :raises TypeError: If plant is not a Plant object
        :raises ValueError: If a plant with the same ID is already in the catalog
        """
        if not isinstance(plant, Plant):
            raise TypeError("Only plants may be added to the catalog")
        
        for existing_plant in self.__plant_list:
            # Duplicate check is by plant ID, not object identity, so the same plant
            # cannot be catalogued twice even if it is held in a different variable.
            if existing_plant.plant_id == plant.plant_id:
                raise ValueError(f"Plant with ID {plant.plant_id} is already in the catalog")
            
        self.__plant_list.append(plant)
    
    def get_available_plants(self) -> list[Plant]:
        """
        Return plants that currently have stock available to sell

        :return: A list of Plant objects with current stock greater than 0
        """
        available_plants = []
        # Available means currently in stock, not just present in the catalog.
        # Sold out plants (stock of 0 after an order) stay in the catalog but are left out here.
        for plant in self.__plant_list:
            if plant.plant_stock > 0:
                available_plants.append(plant)
        return available_plants
    
    # display_all_plants exists alongside the plant_list getter so printing stays inside
    # the catalog. The driver can call one method instead of looping itself.
    # This prints every plant, including sold out ones. display_available_plants() is
    # the filtered list of what can actually be sold right now. 
    def display_all_plants(self) -> None:
        """Print a readable list of every plant in the catalog"""
        if not self.__plant_list:
            print("No plants in the catalog")
            return
        
        for plant in self.__plant_list:
            print(plant)

    def display_available_plants(self) -> None:
        """Print a readable list of plants with non-zero current stock"""
        available_plants = self.get_available_plants()
        if not available_plants:
            print("No plants currently in stock")
            return

        for plant in available_plants:
            print(plant)
        