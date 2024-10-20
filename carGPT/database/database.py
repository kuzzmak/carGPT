from langchain_community.utilities import SQLDatabase


class Database:
    """Singleton database class for articles.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.db = SQLDatabase.from_uri("sqlite:///articles.db")
        return cls._instance

    @property
    def instance(self) -> "Database":
        return self._instance
