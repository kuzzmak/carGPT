from pathlib import Path

SCRAPER_DIR = Path(__file__).parent.parent.parent
SCRIPTS_DIR = SCRAPER_DIR / "scripts"
TOR_PATH = (
    SCRAPER_DIR / "_browser" / "tor-browser" / "Browser" / "start-tor-browser"
)
