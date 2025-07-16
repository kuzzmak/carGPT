import os
import platform
import pprint
import random
import re
import socket
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Optional

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from carGPT.scraper.scraper.translations import TRANSLATIONS

# Configuration
TOR_BROWSER_PATH = (
    r"..."
)
SOCKS_PORT = 9050
CONTROL_PORT = 9051


def prepare_environment(tor_path: str | Path):
    if not isinstance(tor_path, Path):
        tor_path = Path(tor_path)
    # Download tor locally
    if not tor_path.exists():
        current_os = platform.system()
        # Check os and download the Tor Browser
        if current_os == "Windows":
            print("Downloading Tor Browser for Windows...")
            # Download logic for Windows
            # You can use requests or any other method to download the Tor Browser
            # For example, you can use a direct link to the Tor Browser installer
            # Example: requests.get("https://example.com/tor-browser.exe").content
        elif current_os == "Linux":
            print("Downloading Tor Browser for Linux...")
            # Download logic for Linux
            # Example: requests.get("https://example.com/tor-browser.tar.xz").content
        else:
            print(
                f"Unsupported OS: {current_os}. Please download Tor Browser manually."
            )
            return False


def is_tor_running():
    """Check if Tor SOCKS proxy is accessible"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", SOCKS_PORT))
        s.close()
        return True
    except Exception:
        return False


def start_tor_browser():
    """Start the Tor Browser to initialize Tor service"""
    if os.path.exists(TOR_BROWSER_PATH):
        print("Starting Tor Browser to initialize Tor network...")
        process = subprocess.Popen([TOR_BROWSER_PATH])

        # Wait for Tor to connect
        attempts = 0
        while attempts < 30 and not is_tor_running():
            print("Waiting for Tor to initialize...")
            time.sleep(2)
            attempts += 1

        if is_tor_running():
            print("Tor is running!")
            # Kill Firefox but keep Tor running
            time.sleep(5)  # Give it time to fully connect
            kill_firefox_processes()
            return True
        else:
            print("Failed to start Tor")
            return False
    else:
        print(f"Tor Browser not found at: {TOR_BROWSER_PATH}")
        print("Please install Tor Browser or update the path")
        return False


def verify_tor_connection_with_requests():
    """Verify Tor connection using requests"""
    try:
        session = requests.session()
        session.proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050",
        }

        response = session.get("https://check.torproject.org", timeout=15)

        if (
            "Congratulations. This browser is configured to use Tor"
            in response.text
        ):
            ip_response = session.get("https://api.ipify.org", timeout=10)
            print(f"Verified Tor connection! Exit node IP: {ip_response.text}")
            return True
        else:
            print("Warning: Not properly connected through Tor")
            return False
    except Exception as e:
        print(f"Error verifying Tor connection: {e}")
        return False


def create_selenium_with_tor():
    """Create Firefox WebDriver configured to use Tor"""
    options = Options()

    # Configure Tor SOCKS proxy for Firefox
    profile = webdriver.FirefoxProfile()
    profile.set_preference("network.proxy.type", 1)
    profile.set_preference("network.proxy.socks", "127.0.0.1")
    profile.set_preference("network.proxy.socks_port", SOCKS_PORT)
    profile.set_preference("network.proxy.socks_version", 5)
    profile.set_preference("network.proxy.socks_remote_dns", True)
    profile.update_preferences()

    # Anti-fingerprinting measures (limited for Firefox)
    profile.set_preference("dom.webdriver.enabled", False)
    profile.set_preference("useAutomationExtension", False)
    profile.set_preference(
        "general.useragent.override",
        random.choice(
            [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0",
            ]
        ),
    )

    options.set_preference("browser.privatebrowsing.autostart", True)

    options.profile = profile
    # Create the WebDriver
    try:
        driver = webdriver.Firefox(options=options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        print(f"Error creating Firefox driver: {e}")
        return None


def verify_tor_with_selenium(driver):
    """Verify Tor connection using Selenium"""
    try:
        driver.get("https://check.torproject.org")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        if (
            "Congratulations. This browser is configured to use Tor"
            in driver.page_source
        ):
            print("Selenium is successfully using Tor!")
            return True
        else:
            print(
                "Selenium is NOT using Tor. Please check your configuration."
            )
            return False
    except Exception as e:
        print(f"Error verifying Tor with Selenium: {e}")
        return False


def kill_tor_processes():
    """Kill any existing Tor processes"""
    try:
        subprocess.run(
            "taskkill /f /im tor.exe", shell=True, stdout=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"Error killing Tor processes: {e}")


def kill_firefox_processes():
    """Kill any existing Firefox processes if they exist"""
    try:
        # Check if firefox.exe is running
        result = subprocess.run(
            'tasklist /FI "IMAGENAME eq firefox.exe"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if "firefox.exe" in result.stdout:
            subprocess.run(
                "taskkill /f /im firefox.exe",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("Killed firefox.exe process.")
        else:
            print("No firefox.exe process found.")
    except Exception as e:
        print(f"Error killing Firefox processes: {e}")


def restart_tor_identity():
    """Restart Tor to get a new identity"""
    print("Restarting Tor to obtain new identity...")

    # Kill existing processes
    kill_tor_processes()
    kill_firefox_processes()

    time.sleep(2)

    # Start Tor again
    return start_tor_browser()


def get_ad_links(page_ads: list[WebElement]) -> list[str]:
    ad_links = []
    for ad in page_ads:
        try:
            ad_class = ad.get_attribute("class")
            if (
                ad_class is not None
                and "EntityList-bannerContainer" in ad_class
            ):
                print("Skipping something that is not an add")
                continue
            article = ad.find_element(By.TAG_NAME, "article")
            article_title = article.find_element(By.CLASS_NAME, "entity-title")
            article_link = article_title.find_element(By.TAG_NAME, "a")
            article_link_url = article_link.get_attribute("href")
            ad_links.append(article_link_url)
        except Exception as e:
            print(f"Error happened: {e}")
    return ad_links


def get_ads(driver: WebDriver):
    ads = (
        driver.find_element(By.CSS_SELECTOR, ".EntityList--ListItemRegularAd")
        .find_element(By.CLASS_NAME, "EntityList-items")
        .find_elements(By.CLASS_NAME, "EntityList-item")
    )
    print(f"Found {len(ads)} ads on the page")
    return ads


def round_up_to_next_hour(dt: datetime) -> datetime:
    """Rounds a datetime up to the next full hour."""
    if dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        return dt
    return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def parse_date_string(date_str: str, base_time: Optional[datetime] = None):
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
    pattern = r"(\d+)\s*dana?\s*i\s*(\d+)\s*sat[ai]?"
    pattern = r"(\d+)\s*dana?(?:\s*i\s*(\d+)\s*sat[ai]?)?"

    match = re.match(pattern, date_str)

    if not match:
        raise ValueError(f"Unrecognized date format: '{date_str}'")

    days = int(match.group(1))
    hours = int(match.group(2))

    result = base_time + timedelta(days=days, hours=hours)
    return round_up_to_next_hour(result)


def get_ad_columns(
    driver: WebDriver,
) -> tuple[list[WebElement], list[WebElement]]:
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
    for prop_name, prop_value in zip(left_column, right_column):
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
    def year_transform(year: str):
        return int(year.split(".")[0]) if "." in year else int(year)

    def boolean_transform(value: str):
        return value.lower() == "da"

    def price_transform(price: str):
        price = price.replace(".", "")
        price = price.replace(",", ".")
        price = price.replace("€", "").strip()
        price = float(price)
        return price

    transformations = {
        "manufacture_year": lambda x: year_transform(x),
        "model_year": lambda x: year_transform(x),
        "mileage": lambda x: int(x.split()[0].replace(".", "")),
        "power": lambda x: int(x.split()[0]),
        "service_book": lambda x: boolean_transform(x),
        "fuel_consumption": lambda x: float(x.split()[0].replace(",", ".")),
        "average_CO2_emission": lambda x: float(
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
                print(f"Error transforming {key}: {e}")
                transformed_data[key] = value  # fallback to original value
        else:
            transformed_data[key] = value  # no transformation needed

    return transformed_data


def extract_article_info(driver: WebDriver) -> dict[str, Any]:
    left_column, right_column = get_ad_columns(driver)
    ad_details = get_ad_details(left_column, right_column)

    published_elem = driver.find_element(
        By.CLASS_NAME, "ClassifiedDetailSystemDetails-listData"
    )
    date_time_format = "%d.%m.%Y. u %H:%M"
    date_time_obj = datetime.strptime(published_elem.text, date_time_format)
    ad_details["date_created"] = date_time_obj.isoformat()

    price_elem = driver.find_element(
        By.CLASS_NAME, "ClassifiedDetailSummary-priceDomestic"
    )
    price = price_elem.text.strip()
    ad_details["price"] = price

    ad_dates = driver.find_elements(
        By.CLASS_NAME, "ClassifiedDetailSystemDetails-listData"
    )
    ad_date_created = ad_dates[0].text.strip()
    ad_duration = ad_dates[1].text.strip()
    ad_duration_parsed = parse_date_string(
        ad_duration, datetime.strptime(ad_date_created, "%d.%m.%Y. u %H:%M")
    )
    ad_details["ad_duration"] = (
        ad_duration_parsed.isoformat() if ad_duration_parsed else ""
    )
    ad_details = transform_data(ad_details)
    return ad_details


def handle_link(link: str, driver: WebDriver) -> None:
    driver.get(link)
    print(f"Went to page {link}")
    article_info = extract_article_info(driver)
    print(f"Extracted article info: {pprint.pformat(article_info)}")
    # save_article(article_info)


def scrape_with_selenium_tor(num_pages: int = 20):
    """Scrape URLs using Selenium with Tor identity rotation"""
    # Ensure Tor is running
    if not is_tor_running():
        if not start_tor_browser():
            print("Could not start Tor. Exiting.")
            return

    # Verify Tor connection with requests first (more reliable check)
    if not verify_tor_connection_with_requests():
        print("Tor connection verification failed. Proceeding with caution...")

    driver = None

    urls_to_scrape = Queue[str]()
    base_url = "https://www.njuskalo.hr/auti?page={page}"
    for i in range(1, num_pages + 1):
        urls_to_scrape.put(base_url.format(page=i))

    ads_file = open("urls.txt", "w")

    while True:
        if driver is None:
            print("Creating browser")

            # Create new WebDriver
            driver = create_selenium_with_tor()
            if not driver:
                print("Failed to create WebDriver. Exiting.")
                return

            # Verify Tor connection with Selenium
            if not verify_tor_with_selenium(driver):
                print("Warning: Selenium may not be using Tor correctly")

        try:
            url = urls_to_scrape.get(timeout=5)
        except Empty:
            print("No more URLs to scrape (queue is empty). Exiting loop.")
            break

        print(f"Scraping {url}")

        try:
            driver.get(url)
        except TimeoutException:
            print(f"Timeout while loading {url}. Skipping to next URL.")
            urls_to_scrape.put(url)  # Re-add the URL to the queue
            continue
        except Exception as e:
            print(f"Error loading {url}: {e}")
            continue

        # Wait for the page to load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        print(f"Successfully loaded {url}")

        # Find text "Auti - osobni automobili" on page
        # if "Auti - osobni automobili" not in driver.page_source:
        ads = get_ads(driver)
        if not ads:
            print(f"No ads found on {url}. Skipping to next URL.")
            continue

        ad_links = get_ad_links(ads)
        if not ad_links:
            print(f"No ad links found on {url}. Skipping to next URL.")
            continue

        print(f"Found {len(ad_links)} ad links on {url}.")

        for ad_link in ad_links:
            ads_file.write(ad_link + "\n")
        ads_file.flush()

        for ad_link in ad_links:
            try:
                handle_link(ad_link, driver)
                sleep_time = random.randint(1, 10)
                print(f"Sleeping for {sleep_time}s")
                time.sleep(sleep_time)
            except Exception as e:
                print(f"Error handling link {ad_link}: {e}")
                continue

        print(f"Saved {len(ad_links)} ad links to urls.txt")

        delay = random.uniform(1, 7)
        print(f"Waiting {delay:.2f} seconds before next request...")
        time.sleep(delay)

    # Clean up
    if driver:
        driver.quit()

    kill_tor_processes()
    kill_firefox_processes()

    ads_file.close()

    # try:
    #     for i, url in enumerate(urls):
    #         # Check if we need to rotate identity
    #         if driver is None or request_count >= max_requests_per_identity:
    #             print(
    #                 f"{'Creating initial browser' if driver is None else 'Rotating identity after ' + str(request_count) + ' requests'}"
    #             )

    #             # Close previous driver if it exists
    #             if driver:
    #                 driver.quit()

    #             # Get new identity if not the first run
    #             if driver is not None:
    #                 if not restart_tor_identity():
    #                     print("Failed to restart Tor. Exiting.")
    #                     return

    #             # Create new WebDriver
    #             driver = create_selenium_with_tor()
    #             if not driver:
    #                 print("Failed to create WebDriver. Exiting.")
    #                 return

    #             # Verify Tor connection with Selenium
    #             if not verify_tor_with_selenium(driver):
    #                 print("Warning: Selenium may not be using Tor correctly")

    #             request_count = 0

    #         # Perform the scraping
    #         try:
    #             print(f"Scraping {url}")
    #             driver.get(url)

    #             # Wait for the page to load
    #             WebDriverWait(driver, 20).until(
    #                 EC.presence_of_element_located((By.TAG_NAME, "body"))
    #             )

    #             print(f"Successfully loaded {url}")

    #             # YOUR SELENIUM SCRAPING LOGIC HERE
    #             # Example:
    #             # elements = driver.find_elements(By.CSS_SELECTOR, ".your-selector")
    #             # for element in elements:
    #             #     print(element.text)

    #             # Save screenshot for verification
    #             screenshot_path = f"page_{i+1}_screenshot.png"
    #             driver.save_screenshot(screenshot_path)
    #             print(f"Saved screenshot to {screenshot_path}")

    #             # Add random delay between requests
    #             delay = random.uniform(2, 5)
    #             print(f"Waiting {delay:.2f} seconds before next request...")
    #             time.sleep(delay)

    #             request_count += 1

    #         except Exception as e:
    #             print(f"Error scraping {url}: {e}")

    # finally:
    #     # Clean up
    #     if driver:
    #         driver.quit()
    #     kill_tor_processes()
    #     kill_firefox_processes()
    #     print("Scraping completed")


# Example usage
if __name__ == "__main__":
    scrape_with_selenium_tor(num_pages=200)
