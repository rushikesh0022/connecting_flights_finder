#!/usr/bin/env python3
"""
Simple API tester for the Fly Scraper API
This script tests the API connection without running the full flight finder
"""

import requests
import json
from datetime import datetime, timedelta

def test_api_basic():
    """Test basic API connectivity"""
    print("🔍 Testing Fly Scraper API connectivity...")
    print("=" * 50)
    
    # Test with a simple flight search
    url = "https://fly-scraper.p.rapidapi.com/flights/search"
    
    # Get date 7 days from now
    departure_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    querystring = {
        "origin": "jfk",  # JFK Airport
        "destination": "lax",  # LAX Airport
        "date": departure_date,
        "adults": "1",
        "children": "0", 
        "infants": "0",
        "cabinClass": "economy",
        "currency": "USD"
    }
    
    headers = {
        "x-rapidapi-key": "613a06890fmsh4e0415ae052c1f1p148539jsn6c71e5245a82",
        "x-rapidapi-host": "fly-scraper.p.rapidapi.com"
    }
    
    print(f"🚀 Testing API endpoint: {url}")
    print(f"📅 Search date: {departure_date}")
    print(f"✈️  Route: JFK → LAX")
    print("-" * 50)
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"⏱️  Response Time: {response.elapsed.total_seconds():.2f}s")
        
        if response.status_code == 200:
            print("✅ SUCCESS: API is working!")
            try:
                data = response.json()
                print(f"📦 Response Structure: {list(data.keys())}")
                
                if 'data' in data:
                    data_section = data['data']
                    if isinstance(data_section, dict):
                        print(f"📋 Data Keys: {list(data_section.keys())}")
                        
                        if 'flights' in data_section:
                            flights = data_section['flights']
                            print(f"✈️  Flights Found: {len(flights) if isinstance(flights, list) else 'Unknown'}")
                            
                            if isinstance(flights, list) and len(flights) > 0:
                                print(f"🎯 First Flight Keys: {list(flights[0].keys())}")
                                
                                # Find the best routes (cheapest, fastest, and direct/connecting flights)
                                print("\n🔍 ANALYZING FLIGHT OPTIONS...")
                                print("-" * 50)
                                
                                # Sort flights by price
                                try:
                                    cheapest_flights = sorted(flights, key=lambda f: float(f.get('price', {}).get('amount', float('inf'))))
                                    if cheapest_flights:
                                        cheapest = cheapest_flights[0]
                                        price = cheapest.get('price', {}).get('amount')
                                        currency = cheapest.get('price', {}).get('currency', querystring['currency'])
                                        print(f"💰 CHEAPEST FLIGHT: {price} {currency}")
                                        
                                        # Check if it's direct or has connections
                                        segments = cheapest.get('segments', [])
                                        stops = len(segments) - 1 if segments else 0
                                        if stops == 0:
                                            print("✅ This is a DIRECT flight")
                                        else:
                                            print(f"🔄 This flight has {stops} stops/connections")
                                            
                                        # Show route details
                                        if segments:
                                            print("\n📍 ROUTE DETAILS:")
                                            for i, segment in enumerate(segments):
                                                departure = segment.get('departure', {})
                                                arrival = segment.get('arrival', {})
                                                airline = segment.get('airline', {}).get('name', 'Unknown Airline')
                                                
                                                dept_airport = departure.get('airport', {}).get('code', 'N/A')
                                                dept_time = departure.get('time', 'N/A')
                                                
                                                arr_airport = arrival.get('airport', {}).get('code', 'N/A')
                                                arr_time = arrival.get('time', 'N/A')
                                                
                                                print(f"  Leg {i+1}: {dept_airport} ({dept_time}) → {arr_airport} ({arr_time}) - {airline}")
                                                
                                    # Find fastest direct flight
                                    direct_flights = [f for f in flights if len(f.get('segments', [])) == 1]
                                    if direct_flights:
                                        fastest_direct = min(direct_flights, 
                                                         key=lambda f: f.get('duration', {}).get('total', float('inf')))
                                        duration = fastest_direct.get('duration', {}).get('total', 'N/A')
                                        price = fastest_direct.get('price', {}).get('amount')
                                        print(f"\n⚡ FASTEST DIRECT FLIGHT: {duration} minutes, {price} {currency}")
                                    
                                    # Find best connecting flight (balance of price and duration)
                                    connecting_flights = [f for f in flights if len(f.get('segments', [])) > 1]
                                    if connecting_flights and len(connecting_flights) > 0:
                                        # Simple scoring: lower is better
                                        best_connecting = min(connecting_flights, 
                                            key=lambda f: (
                                                float(f.get('price', {}).get('amount', float('inf'))) * 0.7 + 
                                                float(f.get('duration', {}).get('total', float('inf'))) * 0.3
                                            )
                                        )
                                        duration = best_connecting.get('duration', {}).get('total', 'N/A')
                                        price = best_connecting.get('price', {}).get('amount')
                                        stops = len(best_connecting.get('segments', [])) - 1
                                        print(f"\n🌟 BEST CONNECTING FLIGHT: {stops} stops, {duration} minutes, {price} {currency}")
                                except Exception as e:
                                    print(f"⚠️ Error analyzing flights: {str(e)}")
                        else:
                            print("⚠️  No 'flights' key in data section")
                    else:
                        print(f"⚠️  Data section is not a dict: {type(data_section)}")
                else:
                    print("⚠️  No 'data' key in response")
                    
            except json.JSONDecodeError:
                print("❌ Response is not valid JSON")
                print(f"📄 Raw response: {response.text[:200]}...")
                
        elif response.status_code == 403:
            print("❌ FORBIDDEN: API key not authorized")
            print("   This usually means:")
            print("   • You're not subscribed to this API on RapidAPI")
            print("   • Your subscription has expired")
            print("   • The API key is invalid")
            
        elif response.status_code == 429:
            print("⚠️  RATE LIMITED: Too many requests")
            print("   Wait a moment and try again")
            
        elif response.status_code == 404:
            print("❌ NOT FOUND: Invalid endpoint or parameters")
            
        else:
            print(f"❌ ERROR: Unexpected status code {response.status_code}")
            
        if response.text:
            print(f"\n📄 Response preview: {response.text[:300]}...")
            
    except requests.exceptions.Timeout:
        print("⏰ TIMEOUT: Request took too long")
    except requests.exceptions.ConnectionError:
        print("🔌 CONNECTION ERROR: Unable to connect to API")
    except Exception as e:
        print(f"💥 UNEXPECTED ERROR: {str(e)}")
    
    print("\n" + "=" * 50)

def test_airport_search():
    """Test the airport search endpoint"""
    print("🔍 Testing Airport Search API...")
    print("=" * 50)
    
    url = "https://fly-scraper.p.rapidapi.com/airports/search"
    querystring = {"query": "JFK"}
    headers = {
        "x-rapidapi-key": "613a06890fmsh4e0415ae052c1f1p148539jsn6c71e5245a82",
        "x-rapidapi-host": "fly-scraper.p.rapidapi.com"
    }
    
    print(f"🚀 Testing endpoint: {url}")
    print(f"🔎 Searching for: JFK")
    print("-" * 50)
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Airport search working!")
            try:
                data = response.json()
                print(f"📦 Response Keys: {list(data.keys())}")
                
                if 'data' in data and isinstance(data['data'], list):
                    airports = data['data']
                    print(f"✈️  Airports Found: {len(airports)}")
                    
                    if len(airports) > 0:
                        first_airport = airports[0]
                        print(f"🏢 First Airport Keys: {list(first_airport.keys())}")
                        if 'skyId' in first_airport:
                            print(f"🆔 JFK Sky ID: {first_airport['skyId']}")
                
            except json.JSONDecodeError:
                print("❌ Invalid JSON response")
                
        else:
            print(f"❌ Error: {response.status_code}")
            
        if response.text:
            print(f"\n📄 Response preview: {response.text[:300]}...")
            
    except Exception as e:
        print(f"💥 Error: {str(e)}")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    print("🧪 Fly Scraper API Test Suite")
    print("=" * 50)
    
    # Test basic flight search
    test_api_basic()
    
    print("\n")
    
    # Test airport search
    test_airport_search()
    
    print("🏁 Testing complete!")
