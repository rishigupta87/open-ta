#!/usr/bin/env python3
"""Test script for debugging features in admin dashboard"""

import requests
import time

FRONTEND_URL = "http://localhost:8501"
BACKEND_URL = "http://localhost:8000"

def test_debugging_features():
    """Test the debugging capabilities"""
    print("🐛 Testing Admin Dashboard Debugging Features")
    print("=" * 60)
    
    # Test 1: Backend connectivity
    print("\n1. Testing Backend Connectivity...")
    try:
        response = requests.get(f"{BACKEND_URL}/", timeout=5)
        print(f"   ✅ Backend Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Backend Error: {e}")
    
    # Test 2: GraphQL endpoint
    print("\n2. Testing GraphQL Endpoint...")
    try:
        query = """
        query {
            getMarketStatus {
                success
                currentDay
                isTradingDay
            }
        }
        """
        
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/graphql",
            json={"query": query},
            timeout=10
        )
        end_time = time.time()
        
        print(f"   ✅ GraphQL Status: {response.status_code}")
        print(f"   ⏱️  Response Time: {(end_time - start_time):.2f}s")
        
        if response.status_code == 200:
            result = response.json()
            if "data" in result:
                print(f"   📊 Data Retrieved: {result['data']['getMarketStatus']['success']}")
            if "errors" in result:
                print(f"   ❌ GraphQL Errors: {result['errors']}")
                
    except Exception as e:
        print(f"   ❌ GraphQL Error: {e}")
    
    # Test 3: Frontend availability
    print("\n3. Testing Frontend Availability...")
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        print(f"   ✅ Frontend Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Frontend Error: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 Debugging Test Instructions:")
    print(f"   1. Open Admin Dashboard: {FRONTEND_URL}")
    print("   2. Select 'Admin Dashboard' from dropdown")
    print("   3. Enable '🐛 Debug Mode' checkbox in sidebar")
    print("   4. Observe debug information throughout the interface")
    print("   5. Use debugging controls in sidebar")
    print("\n🔧 Debug Features Available:")
    print("   • Function call tracing")
    print("   • Variable value inspection")
    print("   • Interactive breakpoints")
    print("   • GraphQL query/response debugging")
    print("   • Performance monitoring")
    print("   • Memory usage tracking")
    print("   • Error stack traces")

if __name__ == "__main__":
    test_debugging_features()
