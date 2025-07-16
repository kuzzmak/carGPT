import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
import requests
import random
import socket
import socks
import os
import subprocess

# Tor configuration
TOR_PORT = 9050  # Default Tor SOCKS port
TOR_CONTROL_PORT = 9051  # Default Tor control port
TOR_PASSWORD = "your_password"  # Set this in your torrc file


# Check if Tor is running
def is_tor_running():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', 9050))
        s.close()
        return True
    except:
        return False

# Start Tor if it's not running (Windows specific)
def ensure_tor_is_running():
    if not is_tor_running():
        print("Tor is not running. Attempting to start Tor...")
        # Path to your Tor executable - update this to your actual path
        tor_path = r"..."
        
        if os.path.exists(tor_path):
            # Start Tor in the background
            subprocess.Popen([tor_path], 
                             creationflags=subprocess.CREATE_NO_WINDOW)
            # Wait for Tor to start up
            time.sleep(10)
            if is_tor_running():
                print("Successfully started Tor service")
            else:
                print("Failed to start Tor service")
        else:
            print(f"Tor executable not found at {tor_path}")
            print("Please install Tor or update the path")


def create_tor_browser_with_stem():
    """Create a Chrome WebDriver configured to use Tor with Stem for control"""
    from stem import Signal
    from stem.control import Controller
    
    # Make sure Tor is running
    ensure_tor_is_running()
    
    # Configure Chrome to use Tor
    options = Options()
    options.add_argument('--proxy-server=socks5://127.0.0.1:9050')
    
    # Additional settings to make browser less detectable
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-extensions')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-browser-side-navigation')
    options.add_argument('--disable-gpu')
    
    # Use a random user agent
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15',
    ]
    options.add_argument(f'user-agent={random.choice(user_agents)}')
    
    # Create and return the WebDriver
    driver = driver = webdriver.Chrome(options)
    return driver


def get_current_ip(driver):
    """Check the current IP address"""
    driver.get('https://check.torproject.org')
    return driver.page_source

def renew_tor_identity_with_stem():
    """Request a new identity from Tor using Stem"""
    try:
        from stem import Signal
        from stem.control import Controller
        
        with Controller.from_port(port=9051) as controller:
            controller.authenticate(password="your_tor_password")  # Use your Tor password
            controller.signal(Signal.NEWNYM)
            print("Successfully renewed Tor identity")
            # Wait a moment for the new circuit to be established
            time.sleep(5)
            return True
    except Exception as e:
        print(f"Error renewing Tor identity with Stem: {e}")
        return False

def scrape_with_rotating_identity(urls, max_requests_per_identity=3):
    """Scrape URLs with rotating Tor identities"""
    driver = create_tor_browser()
    
    try:
        request_count = 0
        
        for url in urls:
            # Check if we need to rotate identity
            if request_count >= max_requests_per_identity:
                print(f"Made {request_count} requests. Rotating identity...")
                renew_tor_identity()
                
                # Add a delay after rotating identity
                time.sleep(random.uniform(3, 7))
                
                # Restart the browser with new identity
                driver.quit()
                driver = create_tor_browser()
                request_count = 0
            
            # Perform the scraping
            print(f"Scraping {url}")
            driver.get(url)
            
            # Your scraping logic here
            # Example: content = driver.page_source
            
            # Add random delay between requests to be less detectable
            time.sleep(random.uniform(1, 5))
            
            request_count += 1
            
    finally:
        driver.quit()

# Example usage
if __name__ == "__main__":
    # Configuration for the Tor control port in torrc file:
    # ControlPort 9051
    # HashedControlPassword YOUR_HASHED_PASSWORD
    
    # Example URLs to scrape
    urls_to_scrape = [
        "https://www.njuskalo.hr/auti?page=1",
        # "http://your-local-webpage-2.com",
        # Add more URLs
    ]
    
    # Start scraping with identity rotation
    scrape_with_rotating_identity(urls_to_scrape, max_requests_per_identity=5)