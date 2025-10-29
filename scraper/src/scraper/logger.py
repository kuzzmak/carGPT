from scraper.paths import SCRAPER_DIR

from shared.logging_config import get_logger, setup_logging

setup_logging(SCRAPER_DIR / "logging_config.yaml")

logger = get_logger("scraper")
