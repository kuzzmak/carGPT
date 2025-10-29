"""
Centralized logging configuration for the scraper module.
Import the logger from this module to use throughout the scraper package.
"""

from scraper.paths import SCRAPER_DIR

from shared.logging_config import get_logger, setup_logging

# Setup logging once when this module is imported
setup_logging(SCRAPER_DIR / "logging_config.yaml")

# Create and export the logger
logger = get_logger("scraper")
