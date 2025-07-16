import time
import os
import random
import subprocess
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Path to Tor Browser - update this to your actual path
TOR_BROWSER_PATH = r"..."
TOR_PROFILE_PATH = r"..."  # Update this!

def setup_tor_driver():
    """Set up a Firefox driver using the Tor Browser"""
    options = FirefoxOptions()
    options.binary_location = TOR_BROWSER_PATH
    
    # Use the Tor Browser's profile
    options.profile = TOR_PROFILE_PATH
    
    # Additional settings
    options.set_preference("network.proxy.type", 1)
    options.set_preference("network.proxy.socks", "127.0.0.1")
    options.set_preference("network.proxy.socks_port", 9050)
    options.set_preference("network.proxy.socks_remote_dns", True)
    
    # Create the driver
    driver = webdriver.Firefox(options=options)
    
    # Set a reasonable page load timeout
    driver.set_page_load_timeout(30)
    
    return driver

def restart_tor_browser():
    """Kill any existing Tor Browser processes and restart the Tor service"""
    # Kill Firefox processes (on Windows)
    try:
        subprocess.run("taskkill /f /im firefox.exe", shell=True)
        time.sleep(2)
    except:
        pass
    
    # Kill Tor processes (on Windows)
    try:
        subprocess.run("taskkill /f /im tor.exe", shell=True)
        time.sleep(2)
    except:
        pass
    
    # Start Tor Browser in the background (just to initialize Tor)
    subprocess.Popen([TOR_BROWSER_PATH], 
                     creationflags=subprocess.CREATE_NO_WINDOW)
    
    # Give it time to start up
    time.sleep(10)
    
    # Kill the browser again, keeping just the Tor service running
    try:
        subprocess.run("taskkill /f /im firefox.exe", shell=True)
        time.sleep(2)
    except:
        pass

def scrape_with_rotating_identity(urls, max_requests_per_identity=3):
    """Scrape URLs with rotating Tor identities using Tor Browser's Firefox"""
    request_count = 0
    
    for i, url in enumerate(urls):
        # Check if we need to rotate identity
        if request_count == 0 or request_count >= max_requests_per_identity:
            print(f"Setting up new Tor identity...")
            
            # Restart Tor completely to get a new identity
            restart_tor_browser()
            
            # Create a new driver
            driver = setup_tor_driver()
            
            # Test the connection to verify we're using Tor
            try:
                print("Testing Tor connection...")
                driver.get("https://check.torproject.org")
                time.sleep(5)
                
                if "Congratulations" in driver.page_source:
                    print("Successfully connected through Tor!")
                else:
                    print("Warning: Connected but not through Tor")
            except Exception as e:
                print(f"Error testing Tor connection: {e}")
                driver.quit()
                continue
                
            request_count = 0
        
        # Perform the scraping
        try:
            print(f"Scraping {url}")
            driver.get(url)
            
            # Wait for the page to load
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Your scraping logic here
            # Example:
            # data = driver.find_elements(By.CSS_SELECTOR, ".your-css-selector")
            
            print(f"Successfully loaded {url}")
            
            # Add random delay between requests
            time.sleep(random.uniform(2, 5))
            
            request_count += 1
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
        
        # After processing the last URL or when it's time to rotate
        if i == len(urls) - 1 or request_count >= max_requests_per_identity:
            print("Closing browser")
            driver.quit()

# Example usage
if __name__ == "__main__":
    urls_to_scrape = [
        "https://www.njuskalo.hr/auti?page=1",
        "https://www.njuskalo.hr/auti?page=2",
        "https://www.njuskalo.hr/auti?page=3",
        # Add more URLs
    ]
    
    scrape_with_rotating_identity(urls_to_scrape, max_requests_per_identity=2)