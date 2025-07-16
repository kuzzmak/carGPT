import requests
import time
import random
import subprocess
import os
import socket

def is_tor_running():
    """Check if the Tor SOCKS proxy is accessible"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(('127.0.0.1', 9050))
        s.close()
        return True
    except:
        return False

def start_tor_browser():
    """Start the Tor Browser to initialize the Tor service"""
    # Update this path to your actual Tor Browser path
    tor_browser_path = r"..."
    
    if os.path.exists(tor_browser_path):
        print("Starting Tor Browser to initialize Tor network...")
        process = subprocess.Popen([tor_browser_path])
        
        # Wait for Tor to connect
        attempts = 0
        while attempts < 30 and not is_tor_running():
            print("Waiting for Tor to initialize...")
            time.sleep(2)
            attempts += 1
        
        if is_tor_running():
            print("Tor is running!")
            return True
        else:
            print("Failed to start Tor")
            return False
    else:
        print(f"Tor Browser not found at: {tor_browser_path}")
        print("Please install Tor Browser or update the path")
        return False

def get_tor_session():
    """Create a requests session that routes through Tor"""
    session = requests.session()
    # Use Tor's SOCKS proxy
    session.proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
    }
    return session

def verify_tor_connection():
    """Verify that we're connected through Tor"""
    try:
        session = get_tor_session()
        # Check if we're using Tor
        response = session.get('https://check.torproject.org', timeout=15)
        
        if 'Congratulations. This browser is configured to use Tor' in response.text:
            print("Successfully connected through Tor!")
            
            # Get current IP to confirm
            ip_response = session.get('https://api.ipify.org', timeout=10)
            print(f"Current Tor exit node IP: {ip_response.text}")
            
            return True
        else:
            print("Warning: Not connected through Tor")
            return False
    except Exception as e:
        print(f"Error checking Tor connection: {e}")
        return False

def restart_tor_identity():
    """Get a new Tor identity by restarting the Tor Browser"""
    # Close any existing Tor Browser instances
    try:
        subprocess.run("taskkill /f /im firefox.exe", shell=True)
        time.sleep(1)
        subprocess.run("taskkill /f /im tor.exe", shell=True)
        time.sleep(2)
    except:
        pass
    
    # Restart Tor
    return start_tor_browser()

def scrape_with_tor(urls, max_requests_per_identity=3):
    """Scrape URLs using requests through Tor"""
    # Make sure we have requests and the SOCKS library
    try:
        import requests
        import socks
        print("Required libraries found")
    except ImportError:
        print("Please install required packages: pip install requests[socks]")
        return
    
    # Initialize Tor
    if not is_tor_running():
        if not start_tor_browser():
            print("Failed to start Tor. Exiting.")
            return
    
    # Verify Tor connection
    if not verify_tor_connection():
        print("Not properly connected through Tor. Exiting.")
        return
    
    request_count = 0
    session = get_tor_session()
    
    # Set a fake user agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    for i, url in enumerate(urls):
        # Check if we need to rotate identity
        if request_count >= max_requests_per_identity:
            print(f"Made {request_count} requests. Rotating Tor identity...")
            
            # Get a new identity
            if restart_tor_identity():
                print("Tor identity rotated successfully")
                session = get_tor_session()  # Create new session
                verify_tor_connection()  # Verify the connection
                request_count = 0
            else:
                print("Failed to rotate Tor identity")
        
        # Perform the scraping
        try:
            print(f"Scraping {url}")
            response = session.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                print(f"Successfully scraped {url} ({len(response.text)} bytes)")
                
                # Example: Parse with BeautifulSoup (uncomment if needed)
                # soup = BeautifulSoup(response.text, 'html.parser')
                # items = soup.select('.your-selector')
                # for item in items:
                #     print(item.text.strip())
                
                # Save the page for verification if needed
                with open(f"page_{i+1}.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"Saved response to page_{i+1}.html")
                
            else:
                print(f"Failed to scrape {url}: Status code {response.status_code}")
            
            # Add random delay between requests
            delay = random.uniform(2, 5)
            print(f"Waiting {delay:.2f} seconds before next request...")
            time.sleep(delay)
            
            request_count += 1
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
    
    print("Scraping completed")

# Example usage
if __name__ == "__main__":
    urls_to_scrape = [
        "https://www.njuskalo.hr/auti?page=1",
        "https://www.njuskalo.hr/auti?page=2",
        "https://www.njuskalo.hr/auti?page=3",
        "https://www.njuskalo.hr/auti?page=4",
        "https://www.njuskalo.hr/auti?page=5",
        # Add more URLs
    ]
   
    scrape_with_tor(urls_to_scrape, max_requests_per_identity=2)