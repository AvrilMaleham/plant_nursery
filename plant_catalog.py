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
            if existing_plant.plant_id == plant.plant_id:
                raise ValueError(f"Plant with ID {plant.plant_id} is already in the catalog")
            
        self.__plant_list.append(plant)
    
    # Included this even though we have the plant_list getter just to be explicit that there is a method to print each plant in the list so we dont need the print statement in the driver for this    
    def display_all_plants(self) -> None:
        """Print a readable list of every plant in the catalog"""
        if not self.__plant_list:
            print("No plants in the catalog")
            return
        
        for plant in self.__plant_list:
            print(plant)
        