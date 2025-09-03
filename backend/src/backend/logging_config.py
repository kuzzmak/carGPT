"""
Logging configuration and setup for the backend application.

This module provides a comprehensive logging infrastructure with:
- Multiple output handlers (console, file, rotating file)
- Configurable log levels per package/module
- Package-based filtering (ignore lists)
- YAML-based configuration
- Structured logging format
- Environment-specific configurations
"""

import logging
import logging.config
from pathlib import Path
import sys
from typing import Any

import yaml


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

    def load_config(self, config_path: str | None = None) -> None:
        """
        Load logging configuration from YAML file.

        Args:
            config_path: Path to the YAML configuration file.
                        If None, looks for 'logging_config.yaml' in the backend root.
        """
        if config_path is None:
            # Look for config in backend root directory
            backend_root = Path(__file__).parent.parent.parent
            config_path_obj = backend_root / "logging_config.yaml"
        else:
            config_path_obj = Path(config_path)

        if not config_path_obj.exists():
            print(
                f"Warning: Logging config file not found at {config_path_obj}"
            )
            print("Creating default configuration...")
            self._create_default_config(config_path_obj)

        try:
            with config_path_obj.open(encoding="utf-8") as f:
                self._config = yaml.safe_load(f)

            self._setup_logging()
            print(f"Logging configuration loaded from: {config_path_obj}")

        except Exception as e:
            print(f"Error loading logging config: {e}")
            self._load_fallback_config()

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
                    "filename": "logs/backend.log",
                    "encoding": "utf-8",
                },
                "rotating_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "DEBUG",
                    "formatter": "detailed",
                    "filename": "logs/backend_rotating.log",
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
                "backend": {
                    "level": "DEBUG",
                    "handlers": ["console", "file", "rotating_file"],
                    "propagate": False,
                }
            },
            "root": {
                "level": "INFO",
                "handlers": ["console", "error_file"],
            },
            "custom": {
                "enabled_loggers": ["console", "file"],
                "ignored_packages": [
                    # "urllib3.connectionpool",
                    # "selenium.webdriver.remote.remote_connection",
                    # "asyncio",
                    # "aiofiles",
                    # "httpx",
                    # "httpcore",
                ],
                "package_levels": {
                    # "psycopg2": "WARNING",
                    # "requests": "WARNING",
                    # "selenium": "WARNING",
                    # "urllib3": "WARNING",
                    # "openai": "INFO",
                    # "mcp": "INFO",
                },
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

    def reload_config(self, config_path: str | None = None) -> None:
        """
        Reload the logging configuration.

        Args:
            config_path: Path to the YAML configuration file
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


def setup_logging(config_path: str | None = None) -> None:
    """
    Initialize the logging system.

    Args:
        config_path: Path to the YAML configuration file
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


def reload_logging_config(config_path: str | None = None) -> None:
    """
    Reload the logging configuration.

    Args:
        config_path: Path to the YAML configuration file
    """
    logger_manager.reload_config(config_path)


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
