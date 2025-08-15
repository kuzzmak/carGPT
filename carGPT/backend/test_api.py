#!/usr/bin/env python3
"""
Simple test script to verify the FastAPI backend is working correctly.
"""

import requests
import json
from typing import Dict, Any, Optional

BASE_URL = "http://localhost:8000"

def test_endpoint(endpoint: str, method: str = "GET", data: Dict[Any, Any] | None = None) -> None:
    """Test a specific API endpoint."""
    url = f"{BASE_URL}{endpoint}"
    
    print(f"\n{'='*50}")
    print(f"Testing: {method} {endpoint}")
    print(f"{'='*50}")
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            print(f"❌ Unsupported method: {method}")
            return
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                json_response = response.json()
                print("✅ Success! Response:")
                print(json.dumps(json_response, indent=2, default=str))
            except json.JSONDecodeError:
                print(f"✅ Success! Text Response: {response.text}")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the FastAPI server is running on port 8000")
    except requests.exceptions.Timeout:
        print("❌ Timeout Error: Server took too long to respond")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def main():
    """Run all API tests."""
    print("🧪 Testing CarGPT Backend API")
    print(f"Base URL: {BASE_URL}")
    
    # Test health endpoint
    test_endpoint("/health")
    
    # Test stats endpoint
    test_endpoint("/stats")
    
    # Test getting all ads (limited to 2 for testing)
    test_endpoint("/ads?limit=2")
    
    # Test text search
    search_data = {
        "search_term": "Golf",
        "fields": ["make", "model", "type"]
    }
    test_endpoint("/ads/search/text", method="POST", data=search_data)
    
    # Test criteria search
    criteria_data = {
        "make": "Volkswagen"
    }
    test_endpoint("/ads/search", method="POST", data=criteria_data)
    
    print(f"\n{'='*50}")
    print("🎉 API testing completed!")
    print("📝 Visit http://localhost:8000/docs for interactive API documentation")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
