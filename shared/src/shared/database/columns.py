from enum import StrEnum, auto


class ConversationsColumns(StrEnum):
    """String enum for available conversation columns in the database."""

    ID = auto()
    SESSION_ID = auto()
    USER_ID = auto()
    CREATED_AT = auto()
    UPDATED_AT = auto()


class AdColumns(StrEnum):
    """String enum for available ad columns in the database."""

    # System columns (not directly insertable)
    ID = auto()
    INSERTION_TIME = auto()
    URL = auto()

    # User data columns
    DATE_CREATED = auto()
    AD_EXPIRES = auto()
    PRICE = auto()
    LOCATION = auto()
    MAKE = auto()
    MODEL = auto()
    TYPE = auto()
    CHASSIS_NUMBER = auto()
    MANUFACTURE_YEAR = auto()
    MODEL_YEAR = auto()
    MILEAGE = auto()
    ENGINE = auto()
    POWER = auto()
    DISPLACEMENT = auto()
    TRANSMISSION = auto()
    CONDITION = auto()
    OWNER = auto()
    SERVICE_BOOK = auto()
    GARAGED = auto()
    IN_TRAFFIC_SINCE = auto()
    FIRST_REGISTRATION_IN_CROATIA = auto()
    REGISTERED_UNTIL = auto()
    FUEL_CONSUMPTION = auto()
    ECO_CATEGORY = auto()
    NUMBER_OF_GEARS = auto()
    WARRANTY = auto()
    AVERAGE_CO2_EMISSION = auto()
    VIDEO_CALL_VIEWING = auto()
    GAS = auto()
    AUTO_WARRANTY = auto()
    NUMBER_OF_DOORS = auto()
    CHASSIS_TYPE = auto()
    NUMBER_OF_SEATS = auto()
    DRIVE_TYPE = auto()
    COLOR = auto()
    METALIC_COLOR = auto()
    SUSPENSION = auto()
    TIRE_SIZE = auto()
    INTERNAL_CODE = auto()

    @classmethod
    def get_insertable_columns(cls):
        """Get list of columns that can be inserted (excluding system columns)."""
        return [
            col.value for col in cls if col not in [cls.ID, cls.INSERTION_TIME]
        ]

    @classmethod
    def get_all_columns(cls):
        """Get list of all available columns."""
        return [col.value for col in cls]

    @classmethod
    def get_numerical_columns(cls):
        """Get list of columns that support range searches."""
        return [
            cls.PRICE,
            cls.MANUFACTURE_YEAR,
            cls.MODEL_YEAR,
            cls.MILEAGE,
            cls.POWER,
            cls.DISPLACEMENT,
            cls.IN_TRAFFIC_SINCE,
            cls.FIRST_REGISTRATION_IN_CROATIA,
            cls.NUMBER_OF_DOORS,
            cls.NUMBER_OF_SEATS,
        ]


class ImageColumns(StrEnum):
    ID = auto()
    AD_ID = auto()
    IMAGE_URL = auto()
    IMAGE_ORDER = auto()  # To maintain the order of images
