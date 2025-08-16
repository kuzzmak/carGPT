from enum import StrEnum


class AdColumns(StrEnum):
    """String enum for available ad columns in the database."""
    
    # System columns (not directly insertable)
    ID = "id"
    INSERTION_TIME = "insertion_time"
    
    # User data columns
    DATE_CREATED = "date_created"
    PRICE = "price"
    LOCATION = "location"
    MAKE = "make"
    MODEL = "model"
    TYPE = "type"
    CHASSIS_NUMBER = "chassis_number"
    MANUFACTURE_YEAR = "manufacture_year"
    MODEL_YEAR = "model_year"
    MILEAGE = "mileage"
    ENGINE = "engine"
    POWER = "power"
    DISPLACEMENT = "displacement"
    TRANSMISSION = "transmission"
    CONDITION = "condition"
    OWNER = "owner"
    SERVICE_BOOK = "service_book"
    GARAGED = "garaged"
    IN_TRAFFIC_SINCE = "in_traffic_since"
    FIRST_REGISTRATION_IN_CROATIA = "first_registration_in_croatia"
    REGISTERED_UNTIL = "registered_until"
    FUEL_CONSUMPTION = "fuel_consumption"
    ECO_CATEGORY = "eco_category"
    NUMBER_OF_GEARS = "number_of_gears"
    WARRANTY = "warranty"
    AVERAGE_CO2_EMISSION = "average_co2_emission"
    VIDEO_CALL_VIEWING = "video_call_viewing"
    GAS = "gas"
    AUTO_WARRANTY = "auto_warranty"
    NUMBER_OF_DOORS = "number_of_doors"
    CHASSIS_TYPE = "chassis_type"
    NUMBER_OF_SEATS = "number_of_seats"
    DRIVE_TYPE = "drive_type"
    COLOR = "color"
    METALIC_COLOR = "metalic_color"
    SUSPENSION = "suspension"
    TIRE_SIZE = "tire_size"
    INTERNAL_CODE = "internal_code"
    
    @classmethod
    def get_insertable_columns(cls):
        """Get list of columns that can be inserted (excluding system columns)."""
        return [col.value for col in cls if col not in [cls.ID, cls.INSERTION_TIME]]
    
    @classmethod
    def get_all_columns(cls):
        """Get list of all available columns."""
        return [col.value for col in cls]
