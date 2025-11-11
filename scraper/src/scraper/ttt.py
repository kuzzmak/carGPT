import os
import pprint
import random
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
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.logger import logger
from scraper.paths import SCRAPER_DIR, SCRIPTS_DIR, TOR_PATH
from scraper.utils import (
    get_ad_details,
    get_ad_links,
    parse_date_string,
    transform_data,
)

from shared.database import AdColumns, Database
from shared.database.database import ADS_TABLE_NAME

PAGE_TIMEOUT = 30


class TorFirefoxScraper:
    def __init__(self, database: Database):
        self.database = database
        self.tor_process = None
        self.driver = None
        self.tor_proxy_port = (
            9150  # Tor Browser uses 9150, standalone Tor uses 9050
        )
        self.tor_control_port = 9151
        self.url_base = "https://www.njuskalo.hr/auti"

        self._download_tor_if_needed()

        self.tor_executable_path = str(TOR_PATH)

        self.ending_ad_timestamp_path = SCRAPER_DIR / "ending_ad_timestamp.txt"

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

    def setup_firefox_with_tor(self) -> bool:
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

    def get_new_identity(self) -> None:
        self.cleanup()
        time.sleep(2)

        if not self.start_tor():
            logger.error("Failed to restart Tor")
            return

        if not self.setup_firefox_with_tor():
            logger.error("Failed to restart Firefox")
            return

        logger.info("Successfully restarted Tor and Firefox for new identity")

    def goto(self, url: str) -> None:
        """Navigate to a URL"""
        if not self.driver:
            err = "WebDriver not initialized"
            logger.error(err)
            raise RuntimeError(err)

        try:
            logger.debug(f"Navigating to URL: {url}")
            self.driver.get(url)
            WebDriverWait(self.driver, PAGE_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            logger.debug(f"Navigated to {url}")
        except TimeoutException:
            logger.error(f"Timeout loading page: {url}")
            raise
        except Exception as e:
            logger.error(f"Error navigating to {url}: {e}")
            raise

    def get_ads(self):
        """Get ads from the current page"""
        if not self.driver:
            err = "WebDriver not initialized"
            logger.error(err)
            raise RuntimeError(err)

        try:
            ads = (
                self.driver.find_element(
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

    def scrape_njuskalo_cars(self, num_pages: int = 1):
        """Scrape the Njuškalo cars page(s)"""
        saved_first_article = False

        last_scraped_ad_timestamp = None
        if self.ending_ad_timestamp_path.exists():
            with self.ending_ad_timestamp_path.open("r") as f:
                last_scraped_ad_timestamp = f.read().strip()
            logger.info(
                f"Found existing ending ad timestamp: {last_scraped_ad_timestamp}"
            )
            last_scraped_ad_timestamp = datetime.fromisoformat(
                last_scraped_ad_timestamp
            )

        for page_num in range(1, num_pages + 1):
            page_url = (
                f"{self.url_base}?page={page_num}"
                if page_num > 1
                else self.url_base
            )

            try:
                self.goto(page_url)

                # Get ads using the improved function
                ads = self.get_ads()
                if not ads:
                    logger.warning(f"No ads found on page {page_num}")
                    # Make new identity here if page is blocked
                    page_blocked = self.is_blocked_page()
                    if page_blocked:
                        logger.info(
                            f"Blocked page detected on page {page_num}, getting new identity..."
                        )
                        self.get_new_identity()
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
                    try:
                        article_info = self.handle_link(ad_link)
                    except Exception as e:
                        logger.error(f"Error handling link {ad_link}: {e}")

                        page_blocked = self.is_blocked_page()

                        if page_blocked:
                            logger.info(
                                f"Blocked/error page detected at {ad_link}, getting new identity..."
                            )
                            self.get_new_identity()
                            article_info = self.handle_link(ad_link)
                        else:
                            logger.info(
                                f"Continuing to next link after error on {ad_link}"
                            )
                            continue

                    if not saved_first_article:
                        # Save the timestamp of the first saved article so on next run we can end here
                        with self.ending_ad_timestamp_path.open("w") as f:
                            f.write(article_info[AdColumns.DATE_CREATED])
                        logger.info(
                            f"Created ending ad timestamp in {self.ending_ad_timestamp_path}"
                        )
                        saved_first_article = True

                    if last_scraped_ad_timestamp:
                        last_ad_timestamp = datetime.fromisoformat(
                            article_info[AdColumns.DATE_CREATED]
                        )
                        if last_ad_timestamp <= last_scraped_ad_timestamp:
                            logger.info(
                                f"Reached previously scraped ad from {last_scraped_ad_timestamp}, stopping scraper."
                            )
                            return

                    # delay = random.randint(1, 10)
                    # logger.info(
                    #     f"Waiting {delay:.2f} seconds before next link..."
                    # )
                    # time.sleep(delay)

            except Exception as e:
                logger.error(f"Error scraping page {page_num}: {e}")
                continue

            # Add delay between pages
            # delay = random.uniform(2, 5)
            # logger.info(
            #     f"Waiting {delay:.2f} seconds before next page..."
            # )
            # time.sleep(delay)

    def get_ad_columns(self) -> tuple[list[WebElement], list[WebElement]]:
        """Get the left and right columns of ad details"""
        if not self.driver:
            err = "WebDriver not initialized"
            logger.error(err)
            raise RuntimeError(err)

        ad_info = self.driver.find_element(
            By.CLASS_NAME, "ClassifiedDetailBasicDetails-list"
        )
        ad_left_column = ad_info.find_elements(
            By.CLASS_NAME, "ClassifiedDetailBasicDetails-listTerm"
        )
        ad_right_column = ad_info.find_elements(
            By.CLASS_NAME, "ClassifiedDetailBasicDetails-listDefinition"
        )
        return ad_left_column, ad_right_column

    def extract_article_info(self) -> dict[str, Any]:
        """Extract detailed information from a car ad page"""
        if not self.driver:
            err = "WebDriver not initialized"
            logger.error(err)
            raise RuntimeError(err)

        left_column, right_column = self.get_ad_columns()
        ad_details = get_ad_details(left_column, right_column)

        # Extract publication date
        try:
            published_elem = self.driver.find_element(
                By.CLASS_NAME, "ClassifiedDetailSystemDetails-listData"
            )
            date_time_format = "%d.%m.%Y. u %H:%M"
            date_time_obj = datetime.strptime(
                published_elem.text, date_time_format
            )
            ad_details[AdColumns.DATE_CREATED] = date_time_obj.isoformat()
        except Exception as e:
            logger.error(f"Error extracting publication date: {e}")
            raise

        # Extract price
        try:
            price_elem = self.driver.find_element(
                By.CLASS_NAME, "ClassifiedDetailSummary-priceDomestic"
            )
            price = price_elem.text.strip()
            ad_details[AdColumns.PRICE] = price
        except Exception as e:
            logger.error(f"Error extracting price: {e}")
            raise

        # Extract ad dates and duration
        try:
            ad_dates = self.driver.find_elements(
                By.CLASS_NAME, "ClassifiedDetailSystemDetails-listData"
            )
            if len(ad_dates) >= 2:
                ad_date_created = ad_dates[0].text.strip()
                ad_duration = ad_dates[1].text.strip()
                ad_expires = parse_date_string(
                    ad_duration,
                    datetime.strptime(ad_date_created, "%d.%m.%Y. u %H:%M"),
                )
                ad_details[AdColumns.AD_EXPIRES] = (
                    ad_expires.isoformat()
                    if ad_expires
                    else (
                        datetime.now() + timedelta(days=180)
                    ).isoformat()  # if expiry date is "do prodaje", set to 6 months from now
                )
        except Exception as e:
            logger.error(f"Error extracting ad duration: {e}")
            raise

        return transform_data(ad_details)
    
    def extract_image_urls(self) -> list[str]:
        """Extract image URLs from the ad page"""
        if not self.driver:
            err = "WebDriver not initialized"
            logger.error(err)
            raise RuntimeError(err)

        image_urls = []

        try:
            image_elements = self.driver.find_elements(
                By.CLASS_NAME, "ClassifiedDetailGallery-slideImage"
            )
            for img_elem in image_elements:
                img_url = img_elem.get_attribute("data-src")
                if img_url:
                    image_urls.append(img_url)
                else:
                    img_url = img_elem.get_attribute("src")
                    if img_url:
                        image_urls.append(img_url)
                    else:
                        logger.warning(
                            "Image element found without src or data-src attribute"
                        )
            logger.debug(f"Extracted {len(image_urls)} image URLs")

        except Exception as e:
            logger.error(f"Error extracting image URLs: {e}")

        return image_urls
    
    def save_image_urls(self, ad_id: int | None, image_urls: list[str]) -> None:
        """Save image URLs to database"""
        if not ad_id:
            logger.warning("No ad ID provided, skipping saving image URLs")
            return

        try:
            for idx, url in enumerate(image_urls):
                if db_id := self.database.insert_image_url(ad_id, url, idx):
                    logger.debug(f"Saved image URL with ID: {db_id}")
        except Exception as e:
            logger.error(f"Error saving image URLs to database: {e}")

    def handle_link(self, link: str) -> dict[str, Any]:
        """Handle individual ad link - extract info and save to database"""
        if not self.driver:
            err = "WebDriver not initialized"
            logger.error(err)
            raise RuntimeError(err)

        self.goto(link)

        try:
            article_info = self.extract_article_info()
        except Exception as e:
            logger.error(f"Error extracting article info from {link}: {e}")
            raise

        article_info[AdColumns.URL] = link
        logger.info(f"Extracted article info: {pprint.pformat(article_info)}")

        ad_id = self.save_article(article_info)

        image_urls = self.extract_image_urls()
        self.save_image_urls(ad_id, image_urls)

        return article_info

    def save_article(self, article_info: dict[str, Any]) -> int | None:
        """Save article information to database"""
        if not article_info:
            logger.warning("No article info to save")
            return None

        if not self.database:
            logger.error("Database not available for saving")
            return None

        try:
            ad_id = self.database.insert_ad(article_info)
            if ad_id:
                logger.info(
                    f"Successfully saved article to database with ID: {ad_id}"
                )
                return ad_id

            # Check if ad already exists
            criteria = {AdColumns.URL.value: article_info.get(AdColumns.URL)}
            try:
                existing_ad = self.database.get_by_criteria(
                    criteria, table_name=ADS_TABLE_NAME
                )
                if existing_ad:
                    logger.warning(
                        f"Tried to save article with url {article_info.get(AdColumns.URL)}, but it already exists in the database"
                    )
                else:
                    logger.error(
                        f"Failed to save article with url {article_info.get(AdColumns.URL)} to database for unknown reasons"
                    )
            except Exception as e:
                logger.error(f"Error checking for existing ad: {e}")

        except Exception as e:
            logger.error(f"Error saving article to database: {e}")

    def is_blocked_page(self) -> bool:
        """Check if the current page is a blocked/error page"""
        if not self.driver:
            err = "WebDriver not initialized"
            logger.error(err)
            raise RuntimeError(err)

        try:
            body_text = self.driver.find_element(
                By.TAG_NAME, "body"
            ).text.lower()
            blocked_phrases = [
                "i apologize for the inconvenience",
                "access denied",
                "captcha",
                "unusual traffic",
                "temporarily blocked",
            ]

            for phrase in blocked_phrases:
                if phrase in body_text:
                    logger.warning(f"Blocked page detected: '{phrase}' found")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking for blocked page: {e}")
            return False

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


def main():
    """Main function to run the scraper"""
    print("=== Tor + Firefox Selenium Scraper for Njuškalo ===\n")

    db = None  # Initialize db variable
    scraper = None  # Initialize scraper variable

    try:
        # Initialize and check database connection first
        print("Initializing database connection...")
        print(
            f"   Connecting to: {os.getenv('CARGPT_DB_HOST', 'localhost')}:{os.getenv('CARGPT_DB_PORT', '5432')}/{os.getenv('CARGPT_DB_NAME', 'ads_db')}"
        )
        try:
            db = Database()
            logger.info("Database connection established successfully")

            # Create ads table if it doesn't exist
            if db.create_ads_table() and db.create_images_table():
                logger.info("Database tables verified/created successfully")
                print("✅ Database initialized successfully!")
            else:
                logger.error("Failed to create/verify database table")
                print("\n" + "=" * 50)
                print("DATABASE TROUBLESHOOTING:")
                print("1. Start PostgreSQL database using Docker:")
                print("   make up-db")
                print("")
                print("2. Check if database is running:")
                print("   make status")
                print("")
                print("3. Environment variables (current values):")
                print(f"   - CARGPT_DB_NAME: {os.getenv('CARGPT_DB_NAME')}")
                print(f"   - CARGPT_DB_USER: {os.getenv('CARGPT_DB_USER')}")
                print(f"   - CARGPT_DB_HOST: {os.getenv('CARGPT_DB_HOST')}")
                print(f"   - CARGPT_DB_PORT: {os.getenv('CARGPT_DB_PORT')}")
                print("=" * 50)
                return

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return

        # Create scraper with database
        scraper = TorFirefoxScraper(database=db)

        # Start Tor
        print("Starting Tor...")
        if not scraper.start_tor():
            logger.error("Failed to start Tor.")
            return

        # Setup Firefox with Tor proxy
        print("Setting up Firefox with Tor proxy...")
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
        logger.info("Starting to scrape Njuškalo cars page...")
        scraper.scrape_njuskalo_cars(num_pages=100)

        # Show database statistics
        print("\n✅ Scraping completed!")
        total_ads = db.get_ads_count()
        print(f"📊 Total ads in database: {total_ads}")

    except KeyboardInterrupt:
        print("\n🛑 Scraping interrupted by user")
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
