#!/usr/bin/env python3
"""
Tor + Firefox Selenium scraper for Njuškalo cars page
"""

import os
import time
import signal
import subprocess
import requests
import logging
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TorFirefoxScraper:
    def __init__(self, tor_browser_path="/home/tonkec/Downloads/tor-browser-linux-x86_64-14.5.5/tor-browser"):
        self.tor_browser_path = tor_browser_path
        self.tor_executable_path = os.path.join(tor_browser_path, "Browser/start-tor-browser")
        self.tor_binary_path = os.path.join(tor_browser_path, "Browser/TorBrowser/Tor/tor")
        self.tor_process = None
        self.driver = None
        self.tor_proxy_port = 9150  # Tor Browser uses 9150, standalone Tor uses 9050
        self.tor_control_port = 9151
        
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
            # Check if Tor Browser directory exists
            if not os.path.exists(self.tor_browser_path):
                logger.error(f"Tor Browser directory not found: {self.tor_browser_path}")
                return False
            
            # Start Tor browser in detached mode
            env = os.environ.copy()
            env['DISPLAY'] = os.environ.get('DISPLAY', ':0')
            
            self.tor_process = subprocess.Popen(
                [self.tor_executable_path, '--detach'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=os.setsid
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
                    logger.info(f"Tor Browser started successfully after {elapsed_time} seconds")
                    return True
                    
                logger.info(f"Waiting for Tor Browser... ({elapsed_time}/{max_wait_time} seconds)")
            
            logger.error("Tor Browser failed to start within the timeout period")
            return False
                
        except Exception as e:
            logger.error(f"Error starting Tor Browser: {e}")
            return False
    
    def start_tor_alternative(self):
        """Alternative method: try to start standalone Tor if available"""
        try:
            logger.info("Trying to start standalone Tor...")
            
            # Check if tor is installed system-wide
            result = subprocess.run(['which', 'tor'], capture_output=True, text=True)
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
            os.makedirs('/tmp/tor_data_selenium', exist_ok=True)
            
            with open('/tmp/tor_selenium.conf', 'w') as f:
                f.write(torrc_content)
            
            # Start Tor with custom config
            self.tor_process = subprocess.Popen(
                [tor_binary, '-f', '/tmp/tor_selenium.conf'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
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
                        'http': f'socks5://127.0.0.1:{port}',
                        'https': f'socks5://127.0.0.1:{port}'
                    }
                    
                    # Test connection to check IP
                    response = requests.get('http://httpbin.org/ip', proxies=proxies, timeout=10)
                    if response.status_code == 200:
                        ip_info = response.json()
                        logger.info(f"Tor connection successful on port {port}. Current IP: {ip_info.get('origin')}")
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
                "/opt/firefox/firefox"
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
            firefox_options.set_preference("network.proxy.type", 1)  # Manual proxy configuration
            firefox_options.set_preference("network.proxy.socks", "127.0.0.1")
            firefox_options.set_preference("network.proxy.socks_port", self.tor_proxy_port)
            firefox_options.set_preference("network.proxy.socks_version", 5)
            firefox_options.set_preference("network.proxy.socks_remote_dns", True)
            
            # Additional privacy settings and anti-detection measures
            firefox_options.set_preference("dom.webdriver.enabled", False)
            firefox_options.set_preference("useAutomationExtension", False)
            firefox_options.set_preference("general.useragent.override", 
                "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0")
            
            # More anti-detection settings
            firefox_options.set_preference("dom.webnotifications.enabled", False)
            firefox_options.set_preference("media.navigator.enabled", False)
            firefox_options.set_preference("webgl.disabled", True)
            firefox_options.set_preference("dom.battery.enabled", False)
            firefox_options.set_preference("dom.webdriver.enabled", False)
            
            # Disable images and other resources to speed up loading (optional)
            # firefox_options.set_preference("permissions.default.image", 2)
            firefox_options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", False)
            
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
    
    def scrape_njuskalo_cars(self, url="https://www.njuskalo.hr/auti"):
        """Scrape the Njuškalo cars page"""
        if not self.driver:
            logger.error("WebDriver not initialized")
            return []
            
        try:
            logger.info(f"Navigating to {url}")
            self.driver.get(url)
            
            # Wait for page to load
            wait = WebDriverWait(self.driver, 20)
            
            # Wait for car listings to load
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "EntityList-item")))
                logger.info("Page loaded successfully")
            except TimeoutException:
                logger.warning("Timeout waiting for car listings, proceeding anyway...")
            
            # Get page title
            page_title = self.driver.title
            logger.info(f"Page title: {page_title}")
            
            # Extract car listings
            car_listings = []
            
            try:
                # Find car listing elements (adjust selectors based on actual page structure)
                listings = self.driver.find_elements(By.CSS_SELECTOR, ".EntityList-item")
                logger.info(f"Found {len(listings)} car listings")
                
                for i, listing in enumerate(listings[:10]):  # Limit to first 10 for demo
                    try:
                        car_data = {}
                        
                        # Extract car title
                        title_element = listing.find_element(By.CSS_SELECTOR, ".entity-title a")
                        car_data['title'] = title_element.text.strip()
                        car_data['url'] = title_element.get_attribute('href')
                        
                        # Extract price
                        try:
                            price_element = listing.find_element(By.CSS_SELECTOR, ".price")
                            car_data['price'] = price_element.text.strip()
                        except Exception:
                            car_data['price'] = "N/A"
                        
                        # Extract location
                        try:
                            location_element = listing.find_element(By.CSS_SELECTOR, ".entity-pub-info")
                            car_data['location'] = location_element.text.strip()
                        except Exception:
                            car_data['location'] = "N/A"
                        
                        # Extract description
                        try:
                            desc_element = listing.find_element(By.CSS_SELECTOR, ".entity-description")
                            car_data['description'] = desc_element.text.strip()
                        except Exception:
                            car_data['description'] = "N/A"
                        
                        car_listings.append(car_data)
                        logger.info(f"Extracted data for listing {i+1}: {car_data['title']}")
                        
                    except Exception as e:
                        logger.warning(f"Error extracting data from listing {i+1}: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"Error finding car listings: {e}")
                # Fallback: get page source for manual inspection
                page_source = self.driver.page_source
                logger.info(f"Page source length: {len(page_source)} characters")
                
                # Save page source to file for debugging
                with open("njuskalo_page_source.html", "w", encoding="utf-8") as f:
                    f.write(page_source)
                logger.info("Page source saved to njuskalo_page_source.html")
            
            return car_listings
            
        except Exception as e:
            logger.error(f"Error scraping Njuškalo: {e}")
            return []
    
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
    
    scraper = TorFirefoxScraper()
    
    try:
        # Start Tor
        print("Step 1: Starting Tor...")
        if not scraper.start_tor():
            logger.error("Failed to start Tor.")
            print("\n" + "="*50)
            print("TROUBLESHOOTING:")
            print("1. Make sure Tor Browser is downloaded and extracted")
            print("2. Or install Tor system-wide: sudo apt install tor")
            print("3. Or manually start Tor Browser and run this script again")
            print("="*50)
            return
        
        # Setup Firefox with Tor proxy
        print("Step 2: Setting up Firefox with Tor proxy...")
        if not scraper.setup_firefox_with_tor():
            logger.error("Failed to setup Firefox with Tor.")
            print("\n" + "="*50)
            print("TROUBLESHOOTING:")
            print("1. Make sure Firefox is installed: sudo apt install firefox")
            print("2. Make sure geckodriver is in PATH")
            print("3. Install geckodriver: sudo apt install firefox-geckodriver")
            print("="*50)
            return
        
        # Scrape Njuškalo cars page
        print("Step 3: Scraping Njuškalo cars page...")
        logger.info("Starting to scrape Njuškalo cars page...")
        car_listings = scraper.scrape_njuskalo_cars()
        
        # Display results
        if car_listings:
            print(f"\n✅ SUCCESS! Scraped {len(car_listings)} car listings:")
            print("="*80)
            for i, car in enumerate(car_listings, 1):
                print(f"\n--- Car {i} ---")
                print(f"Title: {car.get('title', 'N/A')}")
                print(f"Price: {car.get('price', 'N/A')}")
                print(f"Location: {car.get('location', 'N/A')}")
                print(f"URL: {car.get('url', 'N/A')}")
                print(f"Description: {car.get('description', 'N/A')[:100]}...")
        else:
            print("\n⚠️  No car listings were extracted")
            print("The page structure might have changed or there were loading issues")
        
    except KeyboardInterrupt:
        print("\n🛑 Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\n❌ Unexpected error: {e}")
    finally:
        print("\nCleaning up...")
        scraper.cleanup()
        print("Done!")

if __name__ == "__main__":
    main()