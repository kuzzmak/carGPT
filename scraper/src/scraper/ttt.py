import os
import pprint
import random
import re
import signal
import subprocess
import time
from datetime import datetime, timedelta
from typing import Any

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from shared.database import Database
from shared.logging_config import get_logger, setup_logging
from shared.translations import TRANSLATIONS

from scraper.paths import SCRAPER_DIR, SCRIPTS_DIR, TOR_PATH

PAGE_TIMEOUT = 30

# Configure logging
setup_logging(SCRAPER_DIR / "logging_config.yaml")
logger = get_logger("scraper")


class TorFirefoxScraper:
    def __init__(self, database: Database):
        self.database = database
        self.tor_process = None
        self.driver = None
        self.tor_proxy_port = (
            9150  # Tor Browser uses 9150, standalone Tor uses 9050
        )
        self.tor_control_port = 9151

        self._download_tor_if_needed()

        self.tor_executable_path = str(TOR_PATH)

    def _download_tor_if_needed(self):
        if TOR_PATH.exists():
            logger.debug("Using existing tor instance")
            return
        
        logger.debug("Local tor instance does not exist, downloading...")

        download_script = SCRIPTS_DIR / "download_tor.sh"

        result = subprocess.run(
            ["bash", str(download_script), str(SCRAPER_DIR / "_browser")],
            check=True,
        )
        if result.returncode != 0:
            raise RuntimeError("Failed to download Tor Browser")
        
        logger.info("Tor Browser downloaded successfully")


    def start_tor(self):
        """Start Tor browser process"""
        try:
            logger.info("Starting Tor...")

            # First check if Tor is already running
            if self.test_tor_connection():
                logger.info("Tor is already running!")
                return True

            # Try Tor Browser
            if self.start_tor_browser():
                return True

            # If Tor Browser fails, try standalone Tor
            logger.info("Tor Browser failed, trying standalone Tor...")
            return self.start_tor_alternative()

        except Exception as e:
            logger.error(f"Error starting Tor: {e}")
            return False

    def start_tor_browser(self):
        """Start Tor Browser"""
        try:
            # Start Tor browser in detached mode
            env = os.environ.copy()
            env["DISPLAY"] = os.environ.get("DISPLAY", ":0")

            self.tor_process = subprocess.Popen(
                [self.tor_executable_path, "--detach"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=os.setsid,
            )

            logger.info("Waiting for Tor Browser to initialize...")
            # Wait longer for Tor Browser to start up
            max_wait_time = 60  # 60 seconds max wait
            wait_interval = 3
            elapsed_time = 0

            while elapsed_time < max_wait_time:
                time.sleep(wait_interval)
                elapsed_time += wait_interval

                # Test if Tor proxy is available
                if self.test_tor_connection():
                    logger.info(
                        f"Tor Browser started successfully after {elapsed_time} seconds"
                    )
                    return True

                logger.info(
                    f"Waiting for Tor Browser... ({elapsed_time}/{max_wait_time} seconds)"
                )

            logger.error(
                "Tor Browser failed to start within the timeout period"
            )
            return False

        except Exception as e:
            logger.error(f"Error starting Tor Browser: {e}")
            return False

    def start_tor_alternative(self):
        """Alternative method: try to start standalone Tor if available"""
        try:
            logger.info("Trying to start standalone Tor...")

            # Check if tor is installed system-wide
            result = subprocess.run(
                ["which", "tor"], capture_output=True, text=True
            )
            if result.returncode != 0:
                logger.warning("Standalone Tor not found in PATH")
                return False

            tor_binary = result.stdout.strip()
            logger.info(f"Found Tor binary at: {tor_binary}")

            # Create a simple torrc configuration
            torrc_content = """SocksPort 9050
ControlPort 9051
DataDirectory /tmp/tor_data_selenium
"""

            # Create temp directory for Tor data
            os.makedirs("/tmp/tor_data_selenium", exist_ok=True)

            with open("/tmp/tor_selenium.conf", "w") as f:
                f.write(torrc_content)

            # Start Tor with custom config
            self.tor_process = subprocess.Popen(
                [tor_binary, "-f", "/tmp/tor_selenium.conf"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )

            # Wait for Tor to start
            logger.info("Waiting for standalone Tor to initialize...")
            time.sleep(10)

            # Test connection
            if self.test_tor_connection():
                logger.info("Standalone Tor started successfully")
                return True
            else:
                logger.error("Standalone Tor failed to start")
                return False

        except Exception as e:
            logger.error(f"Error starting standalone Tor: {e}")
            return False

    def test_tor_connection(self):
        """Test if Tor proxy is working"""
        try:
            # First try port 9150 (Tor Browser), then 9050 (standalone Tor)
            for port in [9150, 9050]:
                try:
                    proxies = {
                        "http": f"socks5://127.0.0.1:{port}",
                        "https": f"socks5://127.0.0.1:{port}",
                    }

                    # Test connection to check IP
                    response = requests.get(
                        "http://httpbin.org/ip", proxies=proxies, timeout=10
                    )
                    if response.status_code == 200:
                        ip_info = response.json()
                        logger.info(
                            f"Tor connection successful on port {port}. Current IP: {ip_info.get('origin')}"
                        )
                        self.tor_proxy_port = port  # Update the working port
                        return True
                except Exception as e:
                    logger.debug(f"Port {port} test failed: {e}")
                    continue

            return False
        except Exception as e:
            logger.error(f"Tor connection test failed: {e}")
            return False

    def setup_firefox_with_tor(self):
        """Setup Firefox WebDriver with Tor proxy"""
        try:
            # Firefox options
            firefox_options = Options()

            # Try to find Firefox binary
            firefox_paths = [
                "/snap/firefox/current/usr/lib/firefox/firefox",
                "/usr/bin/firefox",
                "/usr/local/bin/firefox",
                "/opt/firefox/firefox",
            ]

            firefox_binary = None
            for path in firefox_paths:
                if os.path.exists(path):
                    firefox_binary = path
                    logger.info(f"Found Firefox binary at: {firefox_binary}")
                    break

            if firefox_binary:
                firefox_options.binary_location = firefox_binary

            # Configure proxy settings for Tor
            firefox_options.set_preference(
                "network.proxy.type", 1
            )  # Manual proxy configuration
            firefox_options.set_preference("network.proxy.socks", "127.0.0.1")
            firefox_options.set_preference(
                "network.proxy.socks_port", self.tor_proxy_port
            )
            firefox_options.set_preference("network.proxy.socks_version", 5)
            firefox_options.set_preference(
                "network.proxy.socks_remote_dns", True
            )

            # Additional privacy settings and anti-detection measures
            firefox_options.set_preference("dom.webdriver.enabled", False)
            firefox_options.set_preference("useAutomationExtension", False)
            firefox_options.set_preference(
                "general.useragent.override",
                "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0",
            )

            # More anti-detection settings
            firefox_options.set_preference(
                "dom.webnotifications.enabled", False
            )
            firefox_options.set_preference("media.navigator.enabled", False)
            firefox_options.set_preference("webgl.disabled", True)
            firefox_options.set_preference("dom.battery.enabled", False)
            firefox_options.set_preference("dom.webdriver.enabled", False)

            # Disable images and other resources to speed up loading (optional)
            # firefox_options.set_preference("permissions.default.image", 2)
            firefox_options.set_preference(
                "dom.ipc.plugins.enabled.libflashplayer.so", False
            )

            # Run in headless mode (optional - comment out to see browser)
            # firefox_options.add_argument("--headless")

            logger.info("Setting up Firefox WebDriver with Tor proxy...")

            # Initialize WebDriver
            self.driver = webdriver.Firefox(options=firefox_options)
            self.driver.set_page_load_timeout(30)

            logger.info("Firefox WebDriver initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error setting up Firefox with Tor: {e}")
            return False

    def scrape_njuskalo_cars(
        self, url="https://www.njuskalo.hr/auti", num_pages=1
    ):
        """Scrape the Njuškalo cars page(s)"""
        if not self.driver:
            logger.error("WebDriver not initialized")
            return

        ads_file = open("urls_new.txt", "w")

        for page_num in range(1, num_pages + 1):
            page_url = f"{url}?page={page_num}" if page_num > 1 else url

            try:
                logger.info(f"Navigating to page {page_num}: {page_url}")
                self.driver.get(page_url)

                # Wait for page to load
                wait = WebDriverWait(self.driver, PAGE_TIMEOUT)

                # Wait for car listings to load
                try:
                    wait.until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    logger.info(f"Page {page_num} loaded successfully")
                except TimeoutException:
                    logger.warning(
                        f"Timeout waiting for page {page_num} to load, going to next page..."
                    )
                    continue

                # Get page title to check for captcha or errors
                # TODO: check this
                # page_title = self.driver.title
                # logger.info(f"Page {page_num} title: {page_title}")

                # if "captcha" in page_title.lower() or "shield" in page_title.lower():
                #     logger.warning(f"CAPTCHA detected on page {page_num}, skipping...")
                #     continue

                # Get ads using the improved function
                ads = get_ads(self.driver)
                if not ads:
                    logger.warning(f"No ads found on page {page_num}")
                    continue

                # Get ad links
                ad_links = get_ad_links(ads)
                if not ad_links:
                    logger.warning(f"No ad links found on page {page_num}")
                    continue

                logger.info(
                    f"Found {len(ad_links)} ad links on page {page_num}"
                )

                for ad_link in ad_links:
                    ads_file.write(ad_link + "\n")
                ads_file.flush()

                for ad_link in ad_links:
                    try:
                        self.handle_link(ad_link)
                        delay = random.randint(1, 10)
                        logger.info(
                            f"Waiting {delay:.2f} seconds before next link..."
                        )
                        time.sleep(delay)
                    except Exception as e:
                        logger.error(f"Error handling link {ad_link}: {e}")
                        continue

                # Add delay between pages
                if page_num < num_pages:
                    delay = random.uniform(2, 5)
                    logger.info(
                        f"Waiting {delay:.2f} seconds before next page..."
                    )
                    time.sleep(delay)

            except Exception as e:
                logger.error(f"Error scraping page {page_num}: {e}")
                continue

        ads_file.close()

    def handle_link(self, link: str) -> None:
        """Handle individual ad link - extract info and save to database"""
        if not self.driver:
            logger.error("WebDriver not initialized")
            return

        self.driver.get(link)
        WebDriverWait(self.driver, PAGE_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        logger.info(f"Navigating to link: {link}")
        article_info = extract_article_info(self.driver)
        article_info["url"] = link
        logger.info(f"Extracted article info: {pprint.pformat(article_info)}")
        self.save_article(article_info)

    def save_article(self, article_info: dict[str, Any]) -> None:
        """Save article information to database"""
        try:
            if not article_info:
                logger.warning("No article info to save")
                return

            if not self.database:
                logger.error("Database not available for saving")
                return

            ad_id = self.database.insert_ad(article_info)
            if ad_id:
                logger.info(
                    f"Successfully saved article to database with ID: {ad_id}"
                )
            else:
                logger.error("Failed to save article to database")
        except Exception as e:
            logger.error(f"Error saving article to database: {e}")

    def cleanup(self):
        """Clean up resources"""
        try:
            if self.driver:
                logger.info("Closing Firefox WebDriver...")
                self.driver.quit()

            if self.tor_process:
                logger.info("Terminating Tor process...")
                os.killpg(os.getpgid(self.tor_process.pid), signal.SIGTERM)

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Utility functions from tor_scraper_selenium.py
def get_ad_links(page_ads: list[WebElement]) -> list[str]:
    """Extract ad links from page ads"""
    ad_links = []
    for ad in page_ads:
        try:
            ad_class = ad.get_attribute("class")
            if (
                ad_class is not None
                and "EntityList-bannerContainer" in ad_class
            ):
                logger.debug("Skipping banner container")
                continue
            article = ad.find_element(By.TAG_NAME, "article")
            article_title = article.find_element(By.CLASS_NAME, "entity-title")
            article_link = article_title.find_element(By.TAG_NAME, "a")
            article_link_url = article_link.get_attribute("href")
            ad_links.append(article_link_url)
        except Exception as e:
            logger.debug(f"Error extracting ad link: {e}")
    return ad_links


def get_ads(driver: WebDriver):
    """Get ads from the current page"""
    try:
        ads = (
            driver.find_element(
                By.CSS_SELECTOR, ".EntityList--ListItemRegularAd"
            )
            .find_element(By.CLASS_NAME, "EntityList-items")
            .find_elements(By.CLASS_NAME, "EntityList-item")
        )
        logger.info(f"Found {len(ads)} ads on the page")
        return ads
    except Exception as e:
        logger.error(f"Error finding ads: {e}")
        return []


def round_up_to_next_hour(dt: datetime) -> datetime:
    """Rounds a datetime up to the next full hour."""
    if dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        return dt
    return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def parse_date_string(date_str: str, base_time: datetime | None = None):
    """
    Parses strings like '26 dana i 21 sat' into a datetime object rounded up to the next full hour.
    Returns None for 'do prodaje'.
    """
    if base_time is None:
        base_time = datetime.now()

    date_str = date_str.strip().lower()

    if date_str == "do prodaje":
        return None

    # Match e.g. '13 dana i 8 sati', '0 dana i 2 sata'
    pattern = r"(\d+)\s*dana?(?:\s*i\s*(\d+)\s*sat[ai]?)?"

    match = re.match(pattern, date_str)

    if not match:
        raise ValueError(f"Unrecognized date format: '{date_str}'")

    days = int(match.group(1))
    hours = int(match.group(2)) if match.group(2) else 0

    result = base_time + timedelta(days=days, hours=hours)
    return round_up_to_next_hour(result)


def get_ad_columns(
    driver: WebDriver,
) -> tuple[list[WebElement], list[WebElement]]:
    """Get the left and right columns of ad details"""
    ad_info = driver.find_element(
        By.CLASS_NAME, "ClassifiedDetailBasicDetails-list"
    )
    ad_left_column = ad_info.find_elements(
        By.CLASS_NAME, "ClassifiedDetailBasicDetails-listTerm"
    )
    ad_right_column = ad_info.find_elements(
        By.CLASS_NAME, "ClassifiedDetailBasicDetails-listDefinition"
    )
    return ad_left_column, ad_right_column


def get_ad_details(
    left_column: list[WebElement], right_column: list[WebElement]
) -> dict[str, str]:
    ad_details = {}
    for prop_name, prop_value in zip(left_column, right_column, strict=True):
        prop_name = prop_name.find_element(
            By.CLASS_NAME, "ClassifiedDetailBasicDetails-textWrapContainer"
        ).text
        prop_value = prop_value.find_element(
            By.CLASS_NAME, "ClassifiedDetailBasicDetails-textWrapContainer"
        ).text
        try:
            ad_details[TRANSLATIONS[prop_name]] = prop_value
        except KeyError:
            print(f"No key for: {prop_name} - value: {prop_value}")

    return ad_details


def transform_data(data):
    """Transform and clean extracted data"""

    def year_transform(year: str):
        return int(year.split(".")[0]) if "." in year else int(year)

    def boolean_transform(value: str):
        return value.lower() == "da"

    def price_transform(price: str):
        price = price.replace(".", "")
        price = price.replace(",", ".")
        price = price.replace("€", "").strip()
        try:
            return float(price)
        except ValueError:
            return price

    transformations = {
        "manufacture_year": lambda x: year_transform(x),
        "model_year": lambda x: year_transform(x),
        "mileage": lambda x: int(x.split()[0].replace(".", "")),
        "power": lambda x: int(x.split()[0]),
        "service_book": lambda x: boolean_transform(x),
        "fuel_consumption": lambda x: float(x.split()[0].replace(",", ".")),
        "average_co2_emission": lambda x: float(
            x.split()[0].replace(",", ".")
        ),
        "owner": lambda x: int(x.split()[0]) if x.split()[0].isdigit() else x,
        "displacement": lambda x: int(x.replace(".", "").replace(" cm3", "")),
        "in_traffic_since": lambda x: year_transform(x),
        "first_registration_in_croatia": lambda x: year_transform(x),
        "garaged": lambda x: boolean_transform(x),
        "video_call_viewing": lambda x: boolean_transform(x),
        "gas": lambda x: boolean_transform(x),
        "price": lambda x: price_transform(x),
    }

    transformed_data = {}
    for key, value in data.items():
        if key in transformations:
            try:
                transformed_data[key] = transformations[key](value)
            except Exception as e:
                logger.debug(f"Error transforming {key}: {e}")
                transformed_data[key] = value  # fallback to original value
        else:
            transformed_data[key] = value  # no transformation needed

    return transformed_data


def extract_article_info(driver: WebDriver) -> dict[str, Any]:
    """Extract detailed information from a car ad page"""
    try:
        left_column, right_column = get_ad_columns(driver)
        ad_details = get_ad_details(left_column, right_column)

        # Extract publication date
        try:
            published_elem = driver.find_element(
                By.CLASS_NAME, "ClassifiedDetailSystemDetails-listData"
            )
            date_time_format = "%d.%m.%Y. u %H:%M"
            date_time_obj = datetime.strptime(
                published_elem.text, date_time_format
            )
            ad_details["date_created"] = date_time_obj.isoformat()
        except Exception as e:
            logger.debug(f"Error extracting publication date: {e}")

        # Extract price
        try:
            price_elem = driver.find_element(
                By.CLASS_NAME, "ClassifiedDetailSummary-priceDomestic"
            )
            price = price_elem.text.strip()
            ad_details["price"] = price
        except Exception as e:
            logger.debug(f"Error extracting price: {e}")

        # Extract ad dates and duration
        try:
            ad_dates = driver.find_elements(
                By.CLASS_NAME, "ClassifiedDetailSystemDetails-listData"
            )
            if len(ad_dates) >= 2:
                ad_date_created = ad_dates[0].text.strip()
                ad_duration = ad_dates[1].text.strip()
                ad_duration_parsed = parse_date_string(
                    ad_duration,
                    datetime.strptime(ad_date_created, "%d.%m.%Y. u %H:%M"),
                )
                ad_details["ad_duration"] = (
                    ad_duration_parsed.isoformat()
                    if ad_duration_parsed
                    else ""
                )
        except Exception as e:
            logger.debug(f"Error extracting ad duration: {e}")

        return transform_data(ad_details)

    except Exception as e:
        logger.error(f"Error extracting article info: {e}")
        return {}


def main():
    """Main function to run the scraper"""
    print("=== Tor + Firefox Selenium Scraper for Njuškalo ===\n")

    db = None  # Initialize db variable
    scraper = None  # Initialize scraper variable

    try:
        # Initialize and check database connection first
        print("Step 1: Initializing database connection...")
        print(
            f"   Connecting to: {os.getenv('CARGPT_DB_HOST', 'localhost')}:{os.getenv('CARGPT_DB_PORT', '5432')}/{os.getenv('CARGPT_DB_NAME', 'ads_db')}"
        )
        try:
            db = Database()
            logger.info("Database connection established successfully")

            # Create ads table if it doesn't exist
            if db.create_ads_table():
                logger.info("Database table verified/created successfully")
                print("✅ Database initialized successfully!")

                # Show current database stats
                try:
                    current_ads = db.get_ads_count()
                    print(f"📊 Current ads in database: {current_ads}")
                except Exception:
                    pass  # Don't fail if we can't get stats
                print()
            else:
                logger.error("Failed to create/verify database table")
                print("\n" + "=" * 50)
                print("DATABASE TROUBLESHOOTING:")
                print("1. Start PostgreSQL database using Docker:")
                print("   cd docker/database && make start")
                print(
                    "   OR: cd docker/database && make start-all (includes pgAdmin)"
                )
                print("")
                print("2. Check if database is running:")
                print("   cd docker/database && make status")
                print("   cd docker/database && make test-connection")
                print("")
                print("3. Environment variables (current values):")
                print(
                    f"   - CARGPT_DB_NAME: {os.getenv('CARGPT_DB_NAME', 'ads_db')}"
                )
                print(
                    f"   - CARGPT_DB_USER: {os.getenv('CARGPT_DB_USER', 'adsuser')}"
                )
                print(
                    f"   - CARGPT_DB_HOST: {os.getenv('CARGPT_DB_HOST', 'localhost')}"
                )
                print(
                    f"   - CARGPT_DB_PORT: {os.getenv('CARGPT_DB_PORT', '5432')}"
                )
                print("")
                print("4. Database management commands:")
                print(
                    "   cd docker/database && make help  # Show all available commands"
                )
                print(
                    "   cd docker/database && make reset # Reset database (removes all data)"
                )
                print("=" * 50)
                return

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            print("\n" + "=" * 50)
            print("DATABASE CONNECTION FAILED - TROUBLESHOOTING:")
            print("")
            print("🔧 Quick Setup (Docker - Recommended):")
            print("   cd docker/database && make start")
            print("   # This starts PostgreSQL with the correct configuration")
            print("")
            print("🔍 Check Database Status:")
            print("   cd docker/database && make status")
            print("   cd docker/database && make test-connection")
            print("   cd docker/database && make logs  # View database logs")
            print("")
            print("🐳 Docker Commands:")
            print("   cd docker/database && make help     # Show all commands")
            print(
                "   cd docker/database && make start-all # Start with pgAdmin UI"
            )
            print(
                "   cd docker/database && make connect   # Connect to database CLI"
            )
            print("")
            print("🧪 Test Database Connection:")
            print("   python carGPT/database/example_usage.py")
            print(
                "   # This will test the connection and show sample operations"
            )
            print("")
            print("📊 Current Environment Variables:")
            print(
                f"   - CARGPT_DB_NAME: {os.getenv('CARGPT_DB_NAME', 'ads_db (default)')}"
            )
            print(
                f"   - CARGPT_DB_USER: {os.getenv('CARGPT_DB_USER', 'adsuser (default)')}"
            )
            print(
                f"   - CARGPT_DB_HOST: {os.getenv('CARGPT_DB_HOST', 'localhost (default)')}"
            )
            print(
                f"   - CARGPT_DB_PORT: {os.getenv('CARGPT_DB_PORT', '5432 (default)')}"
            )
            print("")
            print(f"❌ Error Details: {e}")
            print("=" * 50)
            return

        # Create scraper with database
        scraper = TorFirefoxScraper(database=db)

        # Start Tor
        print("Step 2: Starting Tor...")
        if not scraper.start_tor():
            logger.error("Failed to start Tor.")
            print("\n" + "=" * 50)
            print("TROUBLESHOOTING:")
            print("1. Make sure Tor Browser is downloaded and extracted")
            print("2. Or install Tor system-wide: sudo apt install tor")
            print("3. Or manually start Tor Browser and run this script again")
            print("=" * 50)
            return

        # Setup Firefox with Tor proxy
        print("Step 3: Setting up Firefox with Tor proxy...")
        if not scraper.setup_firefox_with_tor():
            logger.error("Failed to setup Firefox with Tor.")
            print("\n" + "=" * 50)
            print("TROUBLESHOOTING:")
            print(
                "1. Make sure Firefox is installed: sudo apt install firefox"
            )
            print("2. Make sure geckodriver is in PATH")
            print(
                "3. Install geckodriver: sudo apt install firefox-geckodriver"
            )
            print("=" * 50)
            return

        # Scrape Njuškalo cars page
        print("Step 4: Scraping Njuškalo cars page...")
        logger.info("Starting to scrape Njuškalo cars page...")
        scraper.scrape_njuskalo_cars(
            url="https://www.njuskalo.hr/auti",
            num_pages=2,  # Scrape 2 pages
        )

        # Show database statistics
        print("\n✅ Scraping completed!")
        total_ads = db.get_ads_count()
        print(f"📊 Total ads in database: {total_ads}")

    except KeyboardInterrupt:
        print("\n🛑 Scraping interrupted by user")
        # Still show database stats if available
        if db is not None:
            try:
                total_ads = db.get_ads_count()
                print(
                    f"📊 Partial results - Total ads in database: {total_ads}"
                )
                if total_ads > 0:
                    print(
                        "💡 View saved data: cd docker/database && make list-ads"
                    )
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\n❌ Unexpected error: {e}")
    finally:
        print("\nCleaning up...")
        if scraper:
            scraper.cleanup()
        print("Done!")


if __name__ == "__main__":
    main()
