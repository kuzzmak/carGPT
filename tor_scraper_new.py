import time
import random
import socket
import subprocess
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Configuration
TOR_BROWSER_PATH = r"..."
TOR_PATH = r"..."
USE_PRIVOXY = False  # Set to True if you're using Privoxy as a bridge

def is_tor_running():
    """Check if Tor is running on the default port"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(('127.0.0.1', 9050))
        s.close()
        return True
    except:
        return False

def start_tor_process():
    """Start the Tor process"""
    if not is_tor_running():
        print("Starting Tor process...")
        if os.path.exists(TOR_PATH):
            subprocess.Popen([TOR_PATH], creationflags=subprocess.CREATE_NO_WINDOW)
            # Wait for Tor to initialize
            attempts = 0
            while attempts < 10 and not is_tor_running():
                time.sleep(2)
                attempts += 1
            
            if is_tor_running():
                print("Tor process started successfully")
                return True
            else:
                print("Failed to start Tor process")
                return False
        else:
            print(f"Tor executable not found at {TOR_PATH}")
            return False
    return True  # Tor was already running

def create_browser():
    """Create a Chrome WebDriver configured to use Tor"""
    if not is_tor_running() and not start_tor_process():
        print("Cannot create browser without Tor running")
        return None
    
    options = Options()
    
    # Configure proxy settings
    if USE_PRIVOXY:
        # If using Privoxy as a middle layer (recommended)
        options.add_argument('--proxy-server=http://127.0.0.1:8118')
    else:
        # Direct SOCKS5 configuration
        options.add_argument('--proxy-server=socks5://127.0.0.1:9050')
    
    # Anti-detection measures
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Other settings
    options.add_argument('--disable-extensions')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # Random user agent
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36'
    ]
    options.add_argument(f'user-agent={random.choice(user_agents)}')
    
    # Create driver
    try:
        driver = webdriver.Chrome(options)
        
        # Check if proxy is working
        driver.set_page_load_timeout(30)
        driver.get('https://check.torproject.org')
        
        if "Congratulations. This browser is configured to use Tor" in driver.page_source:
            print("Tor connection successful!")
        else:
            print("Connected, but not through Tor. Check your configuration.")
        
        return driver
    except Exception as e:
        print(f"Error creating browser: {e}")
        return None

def scrape_with_rotating_identity(urls, max_requests_per_identity=3):
    """Scrape URLs with rotating Tor identities"""
    driver = create_browser()
    if not driver:
        print("Failed to create browser. Exiting.")
        return
    
    try:
        request_count = 0
        
        for url in urls:
            # Check if we need to rotate identity
            if request_count >= max_requests_per_identity:
                print(f"Made {request_count} requests. Restarting browser for new identity...")
                driver.quit()
                
                # Add a delay before restarting
                time.sleep(random.uniform(3, 7))
                
                # Restart the browser (which gets a new Tor circuit)
                driver = create_browser()
                if not driver:
                    print("Failed to create browser. Exiting.")
                    return
                
                request_count = 0
            
            # Perform the scraping
            print(f"Scraping {url}")
            try:
                driver.get(url)
                
                # Your scraping logic here
                # Example: content = driver.page_source
                
                # Add random delay between requests to be less detectable
                time.sleep(random.uniform(1, 5))
                
                request_count += 1
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                
    finally:
        if driver:
            driver.quit()

# Example usage
if __name__ == "__main__":
    urls_to_scrape = [
        "https://www.njuskalo.hr/auti?page=1",
        "https://www.njuskalo.hr/auti?page=2",
        # Add more URLs
    ]
    
    scrape_with_rotating_identity(urls_to_scrape, max_requests_per_identity=3)