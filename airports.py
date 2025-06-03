import pandas as pd
import networkx as nx
import requests
import http.client
from datetime import datetime, timedelta
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random
import json

# Load airport data from the OurAirports dataset
airports_df = pd.read_csv('airports.csv')

# Filter for ALL airports with scheduled service and valid IATA codes
# This includes all airport types: large, medium, small airports, seaplane bases, etc.
valid_airports = airports_df[
    (airports_df['iata_code'].notnull()) &
    (airports_df['iata_code'] != '') &  # Ensure IATA code is not empty
    (airports_df['scheduled_service'] == 'yes')  # ALL airports with scheduled service
].copy()

# Clean up IATA codes - remove any whitespace and ensure uppercase
valid_airports['iata_code'] = valid_airports['iata_code'].str.strip().str.upper()

print(f"✅ Loaded {len(airports_df)} total airports from dataset")
print(f"✅ Found {len(valid_airports)} airports with scheduled service and valid IATA codes")

# Create a dictionary of airports using IATA codes from the dataset
airport_dict = valid_airports.set_index('iata_code').T.to_dict()

# Use ALL airports with scheduled service (no filtering by predefined list)
filtered_airport_dict = airport_dict.copy()

# Display statistics about airport types
airport_types = valid_airports['type'].value_counts()
print(f"\n📊 Airport breakdown by type:")
for airport_type, count in airport_types.items():
    print(f"   {airport_type}: {count}")

# Show sample airports from different regions to verify data quality
sample_airports = valid_airports.groupby('iso_country').head(2)[['iata_code', 'name', 'municipality', 'iso_country', 'type']]
print(f"\n🌍 Sample airports from different countries:")
print(sample_airports.head(15).to_string(index=False))

# Initialize directed graph
G = nx.DiGraph()

# Add nodes for each airport
for iata in filtered_airport_dict:
    G.add_node(iata)


# Real-time flight data fetcher using API
def get_airport_sky_id(iata_code):
    """
    Get Sky ID for an airport using IATA code
    First tries the API, then falls back to a mapping of common airports
    """
    # First try to get it from the API
    sky_id = get_airport_sky_id_from_api(iata_code)
    if sky_id:
        return sky_id
    
    # Fallback to hardcoded mapping for common airports
    # Note: These are placeholder Sky IDs and should be replaced with real ones
    # In a production system, you'd build this mapping by querying the airport search API
    sky_id_mapping = {
        'JFK': 'jfk',  # Will use IATA as fallback
        'LAX': 'lax',
        'LHR': 'lhr',
        'CDG': 'cdg',
        'NRT': 'nrt',
        'DXB': 'dxb',
        'SIN': 'sin',
        'HKG': 'hkg',
        'FRA': 'fra',
        'AMS': 'ams',
        'ICN': 'icn',
        'BKK': 'bkk',
        'SYD': 'syd',
        'YYZ': 'yyz',
        'GRU': 'gru',
        'DEL': 'del',
        'BOM': 'bom',
        'PEK': 'pek',
        'SVO': 'svo',
        'MAD': 'mad',
        'FCO': 'fco',
        'MUC': 'muc',
        'ZUR': 'zur',
        'VIE': 'vie',
        'ARN': 'arn',
        'CPH': 'cph',
        'HEL': 'hel',
        'OSL': 'osl',
        'LIS': 'lis',
        'ATH': 'ath'
    }
    
    return sky_id_mapping.get(iata_code, iata_code.lower())

def get_airport_sky_id_from_api(iata_code):
    """
    Get Sky ID for an airport by searching the API
    This is an alternative to the hardcoded mapping
    """
    url = "https://fly-scraper.p.rapidapi.com/airports/search"
    querystring = {"query": iata_code}
    headers = {
        "x-rapidapi-key": "613a06890fmsh4e0415ae052c1f1p148539jsn6c71e5245a82",
        "x-rapidapi-host": "fly-scraper.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                # Look for exact IATA match
                for airport in data['data']:
                    if airport.get('iata') == iata_code:
                        return airport.get('skyId')
                # If no exact match, return the first result
                return data['data'][0].get('skyId')
        return None
    except Exception as e:
        print(f"Error getting Sky ID for {iata_code}: {str(e)}")
        return None

# Real-time flight data fetcher using API
def get_flight_details(origin_iata, destination_iata, use_requests=True):
    """
    Get detailed flight information including price, airline, and date
    Returns a dictionary with flight details or None if no flights found
    """
    if use_requests:
        return get_flight_details_requests(origin_iata, destination_iata)
    else:
        return get_flight_details_http_client(origin_iata, destination_iata)

def get_flight_details_requests(origin_iata, destination_iata):
    """
    Get detailed flight information using requests library
    Returns: dict with {price, airline, date, departure_time, arrival_time} or None
    """
    # First try to get airport Sky IDs if we don't have them already
    origin_sky_id = get_airport_sky_id(origin_iata)
    dest_sky_id = get_airport_sky_id(destination_iata)
    
    if not origin_sky_id or not dest_sky_id:
        print(f"Could not resolve Sky IDs for {origin_iata} or {destination_iata}")
        return None
    
    # Use the search endpoint with Sky IDs
    url = "https://fly-scraper.p.rapidapi.com/flights/search"
    
    # Get date 7 days from now for the search
    departure_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    querystring = {
        "origin": origin_sky_id,
        "destination": dest_sky_id,
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
    
    try:
        # Add delay to avoid rate limiting
        time.sleep(random.uniform(2, 4))
        
        response = requests.get(url, headers=headers, params=querystring)
        
        if response.status_code == 200:
            data = response.json()
            # Extract the cheapest flight with details
            if 'data' in data and 'flights' in data['data'] and len(data['data']['flights']) > 0:
                # Find the cheapest flight and extract all details
                cheapest_flight = None
                cheapest_price = float('inf')
                
                for flight in data['data']['flights']:
                    try:
                        # Extract price
                        price = None
                        if 'price' in flight:
                            if isinstance(flight['price'], dict) and 'amount' in flight['price']:
                                price = float(flight['price']['amount'])
                            elif isinstance(flight['price'], (int, float)):
                                price = float(flight['price'])
                        elif 'totalPrice' in flight:
                            price = float(flight['totalPrice'])
                        elif 'cost' in flight:
                            price = float(flight['cost'])
                        
                        if price and price < cheapest_price:
                            cheapest_price = price
                            
                            # Extract additional details
                            flight_details = {
                                'price': price,
                                'airline': 'Unknown',
                                'date': departure_date,
                                'departure_time': 'Unknown',
                                'arrival_time': 'Unknown',
                                'duration': 'Unknown',
                                'stops': 0
                            }
                            
                            # Try to extract airline information
                            if 'airline' in flight:
                                flight_details['airline'] = flight['airline']
                            elif 'carrier' in flight:
                                flight_details['airline'] = flight['carrier']
                            elif 'airlines' in flight and len(flight['airlines']) > 0:
                                flight_details['airline'] = flight['airlines'][0]
                            
                            # Try to extract time information
                            if 'departure' in flight:
                                dep = flight['departure']
                                if isinstance(dep, dict):
                                    flight_details['departure_time'] = dep.get('time', 'Unknown')
                                    flight_details['date'] = dep.get('date', departure_date)
                                
                            if 'arrival' in flight:
                                arr = flight['arrival']
                                if isinstance(arr, dict):
                                    flight_details['arrival_time'] = arr.get('time', 'Unknown')
                            
                            # Try to extract duration
                            if 'duration' in flight:
                                flight_details['duration'] = flight['duration']
                            elif 'travelTime' in flight:
                                flight_details['duration'] = flight['travelTime']
                            
                            # Try to extract stops
                            if 'stops' in flight:
                                flight_details['stops'] = flight['stops']
                            elif 'segments' in flight:
                                flight_details['stops'] = len(flight['segments']) - 1
                            
                            cheapest_flight = flight_details
                            
                    except (ValueError, TypeError, KeyError):
                        continue
                
                return cheapest_flight
            return None
        elif response.status_code == 429:
            print(f"Rate limit hit for {origin_iata}->{destination_iata}, waiting...")
            time.sleep(60)
            return get_flight_details_requests(origin_iata, destination_iata)
        elif response.status_code == 403:
            print(f"API access forbidden for {origin_iata}->{destination_iata} - subscription issue")
            return None
        else:
            print(f"Error fetching price {origin_iata}->{destination_iata}: {response.status_code}")
            if response.text:
                print(f"Response: {response.text[:200]}...")
            return None
    except Exception as e:
        print(f"Request error {origin_iata}->{destination_iata}: {str(e)}")
        return None

# Backward compatibility - keep the old function for simple price lookup
def get_flight_price(origin_iata, destination_iata, use_requests=True):
    """
    Get real-time flight price between two airports using the Fly Scraper API
    Returns just the price (for backward compatibility)
    """
    flight_details = get_flight_details(origin_iata, destination_iata, use_requests)
    return flight_details['price'] if flight_details else None

def get_flight_price_requests(origin_iata, destination_iata):
    """
    Get flight price using requests library with the correct Fly Scraper API endpoints
    """
    # First try to get airport Sky IDs if we don't have them already
    origin_sky_id = get_airport_sky_id(origin_iata)
    dest_sky_id = get_airport_sky_id(destination_iata)
    
    if not origin_sky_id or not dest_sky_id:
        print(f"Could not resolve Sky IDs for {origin_iata} or {destination_iata}")
        return None
    
    # Use the search endpoint with Sky IDs
    url = "https://fly-scraper.p.rapidapi.com/flights/search"
    
    # Get date 7 days from now for the search
    departure_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    querystring = {
        "origin": origin_sky_id,
        "destination": dest_sky_id,
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
    
    try:
        # Add delay to avoid rate limiting
        time.sleep(random.uniform(2, 4))
        
        response = requests.get(url, headers=headers, params=querystring)
        
        if response.status_code == 200:
            data = response.json()
            # Extract the cheapest price from the response
            if 'data' in data and 'flights' in data['data'] and len(data['data']['flights']) > 0:
                # Find the cheapest flight
                cheapest_price = float('inf')
                for flight in data['data']['flights']:
                    try:
                        # The price structure might be different, try multiple paths
                        price = None
                        if 'price' in flight:
                            if isinstance(flight['price'], dict) and 'amount' in flight['price']:
                                price = float(flight['price']['amount'])
                            elif isinstance(flight['price'], (int, float)):
                                price = float(flight['price'])
                        elif 'totalPrice' in flight:
                            price = float(flight['totalPrice'])
                        elif 'cost' in flight:
                            price = float(flight['cost'])
                        
                        if price and price < cheapest_price:
                            cheapest_price = price
                    except (ValueError, TypeError, KeyError):
                        continue
                
                return cheapest_price if cheapest_price != float('inf') else None
            return None
        elif response.status_code == 429:
            print(f"Rate limit hit for {origin_iata}->{destination_iata}, waiting...")
            time.sleep(60)
            return get_flight_price_requests(origin_iata, destination_iata)
        elif response.status_code == 403:
            print(f"API access forbidden for {origin_iata}->{destination_iata} - subscription issue")
            return None
        else:
            print(f"Error fetching price {origin_iata}->{destination_iata}: {response.status_code}")
            if response.text:
                print(f"Response: {response.text[:200]}...")
            return None
    except Exception as e:
        print(f"Request error {origin_iata}->{destination_iata}: {str(e)}")
        return None

def get_flight_price_http_client(origin_iata, destination_iata):
    """
    Get flight price using http.client with the correct Fly Scraper API endpoints
    """
    # First try to get airport Sky IDs
    origin_sky_id = get_airport_sky_id(origin_iata)
    dest_sky_id = get_airport_sky_id(destination_iata)
    
    if not origin_sky_id or not dest_sky_id:
        print(f"Could not resolve Sky IDs for {origin_iata} or {destination_iata}")
        return None
    
    conn = http.client.HTTPSConnection("fly-scraper.p.rapidapi.com")
    
    headers = {
        'x-rapidapi-key': "613a06890fmsh4e0415ae052c1f1p148539jsn6c71e5245a82",
        'x-rapidapi-host': "fly-scraper.p.rapidapi.com"
    }
    
    try:
        # Add delay to avoid rate limiting
        time.sleep(random.uniform(2, 4))
        
        # Get date 7 days from now for the search
        departure_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Build the query string for the search endpoint
        query_params = f"origin={origin_sky_id}&destination={dest_sky_id}&date={departure_date}&adults=1&children=0&infants=0&cabinClass=economy&currency=USD"
        endpoint = f"/flights/search?{query_params}"
        
        conn.request("GET", endpoint, headers=headers)
        response = conn.getresponse()
        data = response.read()
        
        if response.status == 200:
            flight_data = json.loads(data.decode("utf-8"))
            # Extract the cheapest price from the response
            if 'data' in flight_data and 'flights' in flight_data['data'] and len(flight_data['data']['flights']) > 0:
                cheapest_price = float('inf')
                for flight in flight_data['data']['flights']:
                    try:
                        # The price structure might be different, try multiple paths
                        price = None
                        if 'price' in flight:
                            if isinstance(flight['price'], dict) and 'amount' in flight['price']:
                                price = float(flight['price']['amount'])
                            elif isinstance(flight['price'], (int, float)):
                                price = float(flight['price'])
                        elif 'totalPrice' in flight:
                            price = float(flight['totalPrice'])
                        elif 'cost' in flight:
                            price = float(flight['cost'])
                        
                        if price and price < cheapest_price:
                            cheapest_price = price
                    except (ValueError, TypeError, KeyError):
                        continue
                return cheapest_price if cheapest_price != float('inf') else None
            return None
        elif response.status == 429:
            print(f"Rate limit hit for {origin_iata}->{destination_iata}, waiting...")
            time.sleep(60)
            return get_flight_price_http_client(origin_iata, destination_iata)
        elif response.status == 403:
            print(f"API access forbidden for {origin_iata}->{destination_iata} - subscription issue")
            return None
        else:
            print(f"Error fetching price {origin_iata}->{destination_iata}: {response.status}")
            if data:
                print(f"Response: {data.decode('utf-8')[:200]}...")
            return None
    except Exception as e:
        print(f"Connection error {origin_iata}->{destination_iata}: {str(e)}")
        return None
    finally:
        conn.close()

def debug_api_response(response_data, origin_iata, destination_iata):
    """
    Debug helper to understand API response structure
    """
    print(f"\n--- DEBUG: API Response for {origin_iata} -> {destination_iata} ---")
    print(f"Response type: {type(response_data)}")
    
    if isinstance(response_data, dict):
        print(f"Top-level keys: {list(response_data.keys())}")
        
        if 'data' in response_data:
            data_section = response_data['data']
            print(f"Data section type: {type(data_section)}")
            print(f"Data section keys: {list(data_section.keys()) if isinstance(data_section, dict) else 'Not a dict'}")
            
            if isinstance(data_section, dict) and 'flights' in data_section:
                flights = data_section['flights']
                print(f"Flights count: {len(flights) if isinstance(flights, list) else 'Not a list'}")
                
                if isinstance(flights, list) and len(flights) > 0:
                    first_flight = flights[0]
                    print(f"First flight keys: {list(first_flight.keys()) if isinstance(first_flight, dict) else 'Not a dict'}")
                    
                    # Try to find price fields
                    price_fields = []
                    for key in first_flight.keys():
                        if 'price' in key.lower() or 'cost' in key.lower() or 'amount' in key.lower():
                            price_fields.append(key)
                    print(f"Potential price fields: {price_fields}")
    print("--- END DEBUG ---\n")

def get_flight_price_with_debug(origin_iata, destination_iata, use_requests=True):
    """
    Get flight price with detailed debugging information
    """
    print(f"\n🔍 DEBUG: Fetching detailed response for {origin_iata} -> {destination_iata}")
    
    # Get Sky IDs
    origin_sky_id = get_airport_sky_id(origin_iata)
    dest_sky_id = get_airport_sky_id(destination_iata)
    
    print(f"🔍 DEBUG: Sky IDs - Origin: {origin_sky_id}, Destination: {dest_sky_id}")
    
    if not origin_sky_id or not dest_sky_id:
        print("❌ DEBUG: Could not resolve Sky IDs")
        return None
    
    url = "https://fly-scraper.p.rapidapi.com/flights/search"
    departure_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    querystring = {
        "origin": origin_sky_id,
        "destination": dest_sky_id,
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
    
    print(f"🔍 DEBUG: Request URL: {url}")
    print(f"🔍 DEBUG: Query params: {querystring}")
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        print(f"🔍 DEBUG: Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            debug_api_response(data, origin_iata, destination_iata)
            
            # Try to extract price using the same logic as the main function
            if 'data' in data and 'flights' in data['data'] and len(data['data']['flights']) > 0:
                cheapest_price = float('inf')
                for i, flight in enumerate(data['data']['flights'][:3]):  # Only check first 3
                    print(f"🔍 DEBUG: Flight {i+1} structure: {list(flight.keys())}")
                    try:
                        price = None
                        if 'price' in flight:
                            if isinstance(flight['price'], dict) and 'amount' in flight['price']:
                                price = float(flight['price']['amount'])
                            elif isinstance(flight['price'], (int, float)):
                                price = float(flight['price'])
                        elif 'totalPrice' in flight:
                            price = float(flight['totalPrice'])
                        elif 'cost' in flight:
                            price = float(flight['cost'])
                        
                        print(f"🔍 DEBUG: Flight {i+1} extracted price: {price}")
                        
                        if price and price < cheapest_price:
                            cheapest_price = price
                    except (ValueError, TypeError, KeyError) as e:
                        print(f"🔍 DEBUG: Error parsing flight {i+1}: {e}")
                        continue
                
                final_price = cheapest_price if cheapest_price != float('inf') else None
                print(f"🔍 DEBUG: Final cheapest price: {final_price}")
                return final_price
            else:
                print("🔍 DEBUG: No flights found in response")
                return None
        else:
            print(f"🔍 DEBUG: Error response: {response.text[:500]}...")
            return None
    except Exception as e:
        print(f"🔍 DEBUG: Exception occurred: {str(e)}")
        return None

def populate_graph_with_real_data(G, airports, use_requests=True, batch_size=3, debug_mode=False):
    """
    Populate graph with real flight data from API
    """
    airports_list = list(airports)
    total_pairs = len(airports_list) * (len(airports_list) - 1)
    processed = 0
    
    print(f"Fetching real-time flight data for {len(airports_list)} airports...")
    print(f"This will make approximately {total_pairs} API calls. Please be patient...")
    
    for i, origin in enumerate(airports_list):
        print(f"\nProcessing flights from {origin} ({i+1}/{len(airports_list)})")
        
        # Process destinations in batches to avoid overwhelming the API
        destinations = [dest for dest in airports_list if dest != origin]
        
        for j in range(0, len(destinations), batch_size):
            batch = destinations[j:j+batch_size]
            
            for destination in batch:
                processed += 1
                print(f"  Checking {origin} -> {destination} ({processed}/{total_pairs})")
                
                # Get detailed flight information
                flight_details = get_flight_details(origin, destination, use_requests)
                
                if flight_details and flight_details['price'] > 0:
                    # Store all flight details as edge attributes
                    G.add_edge(origin, destination, 
                             weight=flight_details['price'],
                             airline=flight_details['airline'],
                             date=flight_details['date'],
                             departure_time=flight_details['departure_time'],
                             arrival_time=flight_details['arrival_time'],
                             duration=flight_details['duration'],
                             stops=flight_details['stops'])
                    
                    print(f"    ✓ Added route: ${flight_details['price']:.2f} on {flight_details['airline']} "
                          f"({flight_details['departure_time']} - {flight_details['arrival_time']})")
                else:
                    print(f"    ✗ No direct flight found")
            
            # Add delay between batches to respect rate limits
            if j + batch_size < len(destinations):
                delay = random.uniform(5, 10)
                print(f"    Waiting {delay:.1f}s before next batch...")
                time.sleep(delay)
        
        # Longer delay between origins
        if i + 1 < len(airports_list):
            delay = random.uniform(10, 15)
            print(f"  Waiting {delay:.1f}s before next origin...")
            time.sleep(delay)
    
    print(f"\nGraph populated with {G.number_of_edges()} real flight routes")
    return G

def find_cheapest_path(G, source, target):
    """
    Find the single cheapest path using Dijkstra's algorithm
    """
    if not nx.has_path(G, source, target):
        return None, float('inf')
    
    try:
        # Use Dijkstra's algorithm to find the shortest path
        path = nx.dijkstra_path(G, source, target, weight='weight')
        cost = nx.dijkstra_path_length(G, source, target, weight='weight')
        return path, cost
    except nx.NetworkXNoPath:
        return None, float('inf')
    except Exception as e:
        print(f"Error finding path: {str(e)}")
        return None, float('inf')

def test_api_connection():
    """
    Test if the API is working properly with the correct endpoints
    """
    print("Testing API connection...")
    
    # Test with JFK to LAX route
    origin_sky_id = get_airport_sky_id("JFK")
    dest_sky_id = get_airport_sky_id("LAX")
    
    if not origin_sky_id or not dest_sky_id:
        print("❌ Could not resolve Sky IDs for test airports")
        return False
    
    url = "https://fly-scraper.p.rapidapi.com/flights/search"
    departure_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    querystring = {
        "origin": origin_sky_id,
        "destination": dest_sky_id,
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
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                print("✅ API is working!")
                print(f"   Test search returned data structure: {list(data.keys())}")
                if 'flights' in data['data']:
                    print(f"   Found {len(data['data']['flights'])} flights in test search")
                return True
            else:
                print("⚠️  API responded but with unexpected data structure")
                print(f"   Response keys: {list(data.keys())}")
                return False
        elif response.status_code == 403:
            print("❌ API Error: You are not subscribed to this API.")
            print("   Please check your RapidAPI subscription for the Fly Scraper API.")
            return False
        elif response.status_code == 429:
            print("⚠️  API Rate limit hit. Please wait before making requests.")
            return False
        else:
            print(f"❌ API Error: Status code {response.status_code}")
            print(f"   Response: {response.text[:300]}...")
            return False
    except Exception as e:
        print(f"❌ Connection Error: {str(e)}")
        return False

# Mock data fallback for when API is not available
def generate_mock_flight_data(origin_iata, airports_list):
    """
    Generate realistic mock flight data for testing the routing system
    (Fallback when API is not available)
    """
    flights = []
    
    # Mock airlines
    airlines = ['American Airlines', 'Delta Air Lines', 'United Airlines', 'Southwest Airlines', 
                'British Airways', 'Lufthansa', 'Air France', 'KLM', 'Emirates', 'Qatar Airways',
                'Singapore Airlines', 'Cathay Pacific', 'Japan Airlines', 'ANA', 'Turkish Airlines']
    
    # Simulate that major airports have more connections
    num_connections = random.randint(3, 8)
    
    # Select random destinations from the airports list
    possible_destinations = [airport for airport in airports_list if airport != origin_iata]
    destinations = random.sample(possible_destinations, min(num_connections, len(possible_destinations)))
    
    for dest in destinations:
        # Generate realistic prices based on some factors
        base_price = random.randint(100, 1500)
        
        # Simulate distance-based pricing (very rough approximation)
        if dest in ['LHR', 'CDG', 'FRA', 'AMS'] and origin_iata in ['JFK', 'LAX']:
            base_price += random.randint(200, 800)  # Transatlantic
        elif dest in ['NRT', 'ICN', 'HKG'] and origin_iata in ['LAX', 'JFK']:
            base_price += random.randint(400, 1000)  # Transpacific
        
        # Generate mock flight times
        dep_hour = random.randint(6, 23)
        dep_minute = random.choice([0, 15, 30, 45])
        duration_hours = random.randint(1, 15)
        duration_minutes = random.choice([0, 15, 30, 45])
        
        arrival_hour = (dep_hour + duration_hours + (dep_minute + duration_minutes) // 60) % 24
        arrival_minute = (dep_minute + duration_minutes) % 60
        
        flights.append({
            'destination': {'iataCode': dest},
            'price': {'amount': base_price},
            'airline': random.choice(airlines),
            'date': (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
            'departure_time': f"{dep_hour:02d}:{dep_minute:02d}",
            'arrival_time': f"{arrival_hour:02d}:{arrival_minute:02d}",
            'duration': f"{duration_hours}h {duration_minutes}m",
            'stops': random.choice([0, 0, 0, 1, 1, 2])  # Most flights are direct
        })
    
    return flights

def populate_graph_with_mock_data(G, airports):
    """
    Populate graph with mock flight data for testing
    (Fallback when API is not available)
    """
    airports_list = list(airports)
    
    print("Generating mock flight data for testing...")
    for i, origin in enumerate(airports_list):
        print(f"Processing {origin} ({i+1}/{len(airports_list)})")
        
        flights = generate_mock_flight_data(origin, airports_list)
        
        for flight in flights:
            try:
                destination = flight['destination']['iataCode']
                price = float(flight['price']['amount'])
                
                if destination in airports and price > 0:
                    # Store all flight details as edge attributes
                    G.add_edge(origin, destination, 
                             weight=price,
                             airline=flight['airline'],
                             date=flight['date'],
                             departure_time=flight['departure_time'],
                             arrival_time=flight['arrival_time'],
                             duration=flight['duration'],
                             stops=flight['stops'])
                    
                    print(f"  Added route: {origin} -> {destination} (${price:.2f}) "
                          f"on {flight['airline']} ({flight['departure_time']} - {flight['arrival_time']})")
            except (KeyError, TypeError, ValueError) as e:
                print(f"  Error processing flight: {str(e)}")
    
    print(f"\nGraph populated with {G.number_of_edges()} flight routes")
    return G

def main():
    print("Initializing flight route finder...")
    print("Enhanced with real-time API integration!")
    G = nx.DiGraph()
    
    # Add nodes for each airport
    for iata in filtered_airport_dict:
        G.add_node(iata)
    
    # Test API connection first
    if not test_api_connection():
        print("\n" + "="*50)
        print("API NOT AVAILABLE - Using Mock Data for Testing")
        print("="*50)
        print("The real-time flight API is not accessible.")
        print("To use real data, you need to:")
        print("1. Subscribe to the Fly Scraper API on RapidAPI")
        print("2. Make sure your subscription is active")
        print("3. Update the API key if needed")
        print("\nFor now, using mock data to demonstrate the routing system...")
        print("="*50)
        
        populate_graph_with_mock_data(G, filtered_airport_dict.keys())
        print("\nMock data populated. You can now use the routing system with simulated flight data.")
    else:
        # Populate graph with real flight data from API
        print("\n🚀 API is working! Ready to fetch real-time flight data...")
        print("⚠️  Warning: This will take a while due to API rate limits!")
        print("\nOptions:")
        print("1. Full data fetch (recommended for complete route coverage)")
        print("2. Limited fetch (faster, fewer routes)")
        print("3. Debug mode (single route with detailed logging)")
        print("4. Use mock data instead")
        
        choice = input("\nChoose option (1-4): ").strip()
        
        if choice == '1':
            print("\n🔄 Starting full data fetch...")
            populate_graph_with_real_data(G, filtered_airport_dict.keys(), use_requests=True, batch_size=3)
        elif choice == '2':
            # Limited to first 10 airports for faster testing
            limited_airports = list(filtered_airport_dict.keys())[:10]
            print(f"\n🔄 Starting limited fetch for {len(limited_airports)} airports...")
            populate_graph_with_real_data(G, limited_airports, use_requests=True, batch_size=5)
        elif choice == '3':
            print("\n🔍 Debug mode: Testing single route JFK -> LAX...")
            debug_airports = ['JFK', 'LAX']
            populate_graph_with_real_data(G, debug_airports, use_requests=True, batch_size=1, debug_mode=True)
        else:
            print("\n📊 Using mock data instead...")
            populate_graph_with_mock_data(G, filtered_airport_dict.keys())
            populate_graph_with_mock_data(G, filtered_airport_dict.keys())
    
    print(f"\n✅ Flight data loaded! Graph has {G.number_of_nodes()} airports and {G.number_of_edges()} routes.")
    print(f"📍 Available airports: {', '.join(sorted(filtered_airport_dict.keys()))}")
    
    while True:
        try:
            origin = input("\n✈️  Enter origin IATA code (or 'q' to quit): ").upper()
            if origin == 'Q':
                break
                
            destination = input("🛬 Enter destination IATA code: ").upper()
            
            if origin not in filtered_airport_dict or destination not in filtered_airport_dict:
                print("❌ Invalid IATA code(s). Please choose from available airports:")
                # Show first 50 airports as examples
                available_codes = sorted(filtered_airport_dict.keys())
                print(f"Examples: {', '.join(available_codes[:50])}")
                if len(available_codes) > 50:
                    print(f"... and {len(available_codes) - 50} more airports")
                continue
            
            print("\n🔍 Searching for the cheapest route...")
            path, cost = find_cheapest_path(G, origin, destination)
            
            if path is None or cost == float('inf'):
                print("❌ No available path found.")
                continue
            
            print(f"\n🎯 Cheapest route from {origin} to {destination}:")
            print("✈️  Path:", ' → '.join(path))
            print(f"💰 Total Cost: ${cost:.2f}")
            print(f"🛑 Stops: {len(path) - 2}")
            
            # Add details about each leg with airline and flight information
            print("\n📋 Detailed route breakdown:")
            for j in range(len(path) - 1):
                leg_origin = path[j]
                leg_dest = path[j+1]
                edge_data = G[leg_origin][leg_dest]
                
                leg_cost = edge_data['weight']
                airline = edge_data.get('airline', 'Unknown')
                dep_time = edge_data.get('departure_time', 'Unknown')
                arr_time = edge_data.get('arrival_time', 'Unknown')
                duration = edge_data.get('duration', 'Unknown')
                date = edge_data.get('date', 'Unknown')
                stops = edge_data.get('stops', 0)
                
                print(f"   Leg {j+1}: {leg_origin} → {leg_dest}")
                print(f"      💵 Price: ${leg_cost:.2f}")
                print(f"      🏢 Airline: {airline}")
                print(f"      📅 Date: {date}")
                print(f"      🕐 Departure: {dep_time} | Arrival: {arr_time}")
                print(f"      ⏱️  Duration: {duration}")
                if stops > 0:
                    print(f"      🔄 Stops: {stops}")
                print()
                
        except Exception as e:
            print(f"❌ An error occurred: {str(e)}")
            continue
        except KeyboardInterrupt:
            print("\n⏹️  Operation cancelled by user.")
            break
    
    print("\n👋 Thank you for using the flight route finder!")

if __name__ == "__main__":
    main()
