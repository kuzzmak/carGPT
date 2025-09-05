from copy import deepcopy
import logging
import logging.config
from pathlib import Path
import sys
from typing import Any

import yaml

from shared.paths import SHARED_DIR


class LoggerManager:
    """
    Centralized logger management with configuration file support.

    Features:
    - YAML configuration file support
    - Multiple handler types (console, file, rotating)
    - Package-based filtering and level control
    - Environment-specific configurations
    - Automatic log directory creation
    """

    _instance: "LoggerManager | None" = None
    _initialized: bool = False

    def __new__(cls) -> "LoggerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._config: dict[str, Any] = {}
            self._loggers: dict[str, logging.Logger] = {}
            self._default_config_loaded = False
            LoggerManager._initialized = True

    def load_config(
        self,
        config_path: str | Path | None = None,
    ) -> None:
        """
        Loads and sets up the logging configuration for the application.

        This method first attempts to load a base logging configuration from a default YAML file.
        If a specific configuration file path is provided, it tries to load and merge it with the base configuration.
        If the specific configuration file does not exist, a default configuration is created at the specified path.
        In case of any errors during loading or merging, it falls back to setting up basic logging.

        Args:
            config_path (str | Path | None, optional): Path to a specific logging configuration YAML file.
                If None, only the base configuration is used.

        Raises:
            Exception: If loading the base configuration fails.
        """
        base_config_path = SHARED_DIR / "logging_config_base.yaml"

        # Try to load base config
        try:
            with Path.open(base_config_path, encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
                print(
                    f"Base logging configuration loaded from: {base_config_path}"
                )
        except Exception as e:
            err = "Error loading base logging config"
            # TODO: fallback
            raise Exception(err) from e

        # No specific config needed
        if config_path is None:
            self._setup_logging()
            return

        # Specific config path provided but not found, creating one
        config_path = Path(config_path)
        if not config_path.exists():
            print(
                f"Warning: Specific logging config file not found at {config_path}, creating default there."
            )
            self._create_default_config(config_path)
            self._setup_logging()
            return

        # Try to load specific config
        try:
            with config_path.open(encoding="utf-8") as f:
                specific_config = yaml.safe_load(f)
            print(f"Specific logging configuration loaded from: {config_path}")
        except Exception as e:
            print(f"Error loading specific logging config: {e}")
            # We set up logging with basic configuration
            self._setup_logging()
            return

        try:
            self._config = self._merge_configs(self._config, specific_config)
        except Exception as e:
            print(f"Error merging logging config: {e}")

        self._setup_logging()

    def _merge_configs(
        self, base_config: dict[str, Any], specific_config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Merge specific configuration into base configuration.

        This method performs a deep merge where:
        - Lists are replaced entirely from specific config
        - Dictionaries are merged recursively
        - Primitive values in specific config override base config

        Args:
            base_config: The base configuration dictionary
            specific_config: The specific configuration to merge in

        Returns:
            Merged configuration dictionary
        """
        # Create a deep copy of base config to avoid modifying the original
        merged = deepcopy(base_config)

        def _deep_merge(
            base_dict: dict[str, Any], specific_dict: dict[str, Any]
        ) -> dict[str, Any]:
            """Recursively merge two dictionaries."""
            for key, value in specific_dict.items():
                if key in base_dict:
                    if isinstance(base_dict[key], dict) and isinstance(
                        value, dict
                    ):
                        # Both are dicts, merge recursively
                        base_dict[key] = _deep_merge(base_dict[key], value)
                    else:
                        # Either not both dicts, or one is None - replace with specific value
                        base_dict[key] = deepcopy(value)
                else:
                    # Key doesn't exist in base, add it
                    base_dict[key] = deepcopy(value)
            return base_dict

        return _deep_merge(merged, specific_config)

    def _create_default_config(self, config_path: Path) -> None:
        """Create a default logging configuration file."""
        default_config = self._get_default_config()

        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with config_path.open("w", encoding="utf-8") as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)

        self._config = default_config
        print(f"Default logging configuration created at: {config_path}")

    def _get_default_config(self) -> dict[str, Any]:
        """Get the default logging configuration."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                "simple": {"format": "%(levelname)s - %(name)s - %(message)s"},
                "json": {
                    "format": '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "file": "%(filename)s", "line": %(lineno)d, "message": "%(message)s"}',
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "simple",
                    "stream": "ext://sys.stdout",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "level": "DEBUG",
                    "formatter": "detailed",
                    "filename": "logs/log.log",
                    "encoding": "utf-8",
                },
                "rotating_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "DEBUG",
                    "formatter": "detailed",
                    "filename": "logs/log_rotating.log",
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 5,
                    "encoding": "utf-8",
                },
                "error_file": {
                    "class": "logging.FileHandler",
                    "level": "ERROR",
                    "formatter": "detailed",
                    "filename": "logs/errors.log",
                    "encoding": "utf-8",
                },
            },
            "loggers": {
                "root": {
                    "level": "INFO",
                    "handlers": ["console", "error_file"],
                },
            },
            "custom": {
                "enabled_loggers": ["console", "file"],
                "ignored_packages": [],
                "package_levels": {},
                "log_directory": "logs",
                "max_file_size_mb": 10,
                "backup_count": 5,
            },
        }

    def _setup_logging(self) -> None:
        """Set up logging based on the loaded configuration."""
        # Create logs directory if it doesn't exist
        log_dir = Path(
            self._config.get("custom", {}).get("log_directory", "logs")
        )
        log_dir.mkdir(parents=True, exist_ok=True)

        # Apply the logging configuration
        logging.config.dictConfig(self._config)

        # Apply custom package-level configurations
        self._apply_package_filters()

        # Set ignored packages to higher log levels
        self._apply_ignore_list()

    def _apply_package_filters(self) -> None:
        """Apply custom log levels for specific packages."""
        custom_config = self._config.get("custom", {})
        package_levels = custom_config.get("package_levels", {})

        for package, level in package_levels.items():
            logger = logging.getLogger(package)
            logger.setLevel(getattr(logging, level.upper()))

    def _apply_ignore_list(self) -> None:
        """Apply ignore list by setting packages to WARNING level or higher."""
        custom_config = self._config.get("custom", {})
        ignored_packages = custom_config.get("ignored_packages", [])

        for package in ignored_packages:
            logger = logging.getLogger(package)
            logger.setLevel(logging.WARNING)
            # Add null handler to prevent propagation of INFO/DEBUG messages
            logger.addHandler(logging.NullHandler())

    def _load_fallback_config(self) -> None:
        """Load a basic fallback configuration if YAML config fails."""
        logs_dir = Path("logs")
        logs_dir.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(
                    logs_dir / "fallback.log", encoding="utf-8"
                ),
            ],
        )
        print("Fallback logging configuration loaded")

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance for the given name.

        Args:
            name: Logger name, typically __name__ from the calling module

        Returns:
            Configured logger instance
        """
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(name)

        return self._loggers[name]

    def reload_config(
        self,
        config_path: str | Path | None = None,
    ) -> None:
        """
        Reload the logging configuration.

        Args:
            config_path: Path to the specific YAML configuration file
        """
        self.load_config(config_path)
        print("Logging configuration reloaded")

    def list_active_loggers(self) -> list[str]:
        """Get a list of all active logger names."""
        return list(logging.Logger.manager.loggerDict.keys())

    def set_package_level(self, package: str, level: str) -> None:
        """
        Dynamically set log level for a specific package.

        Args:
            package: Package name
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        logger = logging.getLogger(package)
        logger.setLevel(getattr(logging, level.upper()))
        print(f"Set {package} log level to {level.upper()}")

    def add_ignore_package(self, package: str) -> None:
        """
        Add a package to the ignore list (set to WARNING level).

        Args:
            package: Package name to ignore INFO/DEBUG messages from
        """
        logger = logging.getLogger(package)
        logger.setLevel(logging.WARNING)
        logger.addHandler(logging.NullHandler())
        print(f"Added {package} to ignore list")

    def remove_ignore_package(
        self, package: str, new_level: str = "INFO"
    ) -> None:
        """
        Remove a package from the ignore list and set new level.

        Args:
            package: Package name to remove from ignore list
            new_level: New log level to set
        """
        logger = logging.getLogger(package)
        logger.setLevel(getattr(logging, new_level.upper()))
        # Remove null handlers
        logger.handlers = [
            h
            for h in logger.handlers
            if not isinstance(h, logging.NullHandler)
        ]
        print(
            f"Removed {package} from ignore list, set level to {new_level.upper()}"
        )


# Global logger manager instance
logger_manager = LoggerManager()


def setup_logging(config_path: str | Path | None = None) -> None:
    """
    Initialize the logging system with support for hierarchical configurations.

    Args:
        config_path: Path to the specific YAML configuration file
    """
    logger_manager.load_config(config_path)


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name, typically __name__ from the calling module

    Returns:
        Configured logger instance
    """
    return logger_manager.get_logger(name)


def reload_logging_config(config_path: str | Path | None = None) -> None:
    """
    Reload the logging configuration with support for hierarchical configs.

    Args:
        config_path: Path to the specific YAML configuration file
    """
    logger_manager.reload_config(
        config_path,
    )


def set_package_log_level(package: str, level: str) -> None:
    """
    Set log level for a specific package.

    Args:
        package: Package name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logger_manager.set_package_level(package, level)


def ignore_package(package: str) -> None:
    """
    Add a package to the ignore list.

    Args:
        package: Package name to ignore INFO/DEBUG messages from
    """
    logger_manager.add_ignore_package(package)


def unignore_package(package: str, level: str = "INFO") -> None:
    """
    Remove a package from the ignore list.

    Args:
        package: Package name to remove from ignore list
        level: New log level to set
    """
    logger_manager.remove_ignore_package(package, level)
