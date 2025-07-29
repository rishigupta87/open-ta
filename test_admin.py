#!/usr/bin/env python3
"""Test script for admin dashboard functionality"""

import requests
import json

# Test GraphQL endpoints
GRAPHQL_ENDPOINT = "http://localhost:8000/graphql"

def test_graphql_query(query, description):
    """Test a GraphQL query"""
    print(f"\n🧪 Testing: {description}")
    try:
        response = requests.post(
            GRAPHQL_ENDPOINT,
            json={"query": query},
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        if "errors" in result:
            print(f"❌ GraphQL Errors: {result['errors']}")
            return False
        
        print(f"✅ Success: {result.get('data', {})}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("🎯 Open-TA Admin Dashboard Test")
    print("=" * 50)
    
    # Test 1: Market Status
    test_graphql_query("""
        query {
            getMarketStatus {
                success
                message
                activeExchanges
                isAnyMarketOpen
                currentTimeIst
                currentDay
                isTradingDay
                statusReason
                nextTradingDay
                daysUntilNextTrading
            }
        }
    """, "Market Status")
    
    # Test 2: Signal Engine Status
    test_graphql_query("""
        query {
            getSignalEngineStatus {
                success
                message
                status {
                    isRunning
                    activeExchanges
                    currentSignalsCount
                }
            }
        }
    """, "Signal Engine Status")
    
    # Test 3: Current Signals
    test_graphql_query("""
        query {
            getCurrentSignals(limit: 5) {
                success
                message
                signals {
                    symbol
                    underlying
                    signalStrength
                    signalType
                }
                totalCount
            }
        }
    """, "Current Signals")
    
    # Test 4: OI Analytics
    test_graphql_query("""
        query {
            getOiAnalytics(limit: 5) {
                success
                message
                analytics {
                    underlying
                    marketSentiment
                    avgIv
                }
                totalCount
            }
        }
    """, "OI Analytics")
    
    print("\n" + "=" * 50)
    print("✅ All GraphQL endpoints tested!")
    print("\n📊 Admin Dashboard should be accessible at:")
    print("   http://localhost:8501")
    print("   Select 'Admin Dashboard' from the dropdown")

if __name__ == "__main__":
    main()
