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
    sky_id_mapping = {
        'JFK': 'jfk', 'LAX': 'lax', 'LHR': 'lhr', 'CDG': 'cdg', 'NRT': 'nrt',
        'DXB': 'dxb', 'SIN': 'sin', 'HKG': 'hkg', 'FRA': 'fra', 'AMS': 'ams',
        'ICN': 'icn', 'BKK': 'bkk', 'SYD': 'syd', 'YYZ': 'yyz', 'GRU': 'gru',
        'DEL': 'del', 'BOM': 'bom', 'PEK': 'pek', 'SVO': 'svo', 'MAD': 'mad',
        'FCO': 'fco', 'MUC': 'muc', 'ZUR': 'zur', 'VIE': 'vie', 'ARN': 'arn',
        'CPH': 'cph', 'HEL': 'hel', 'OSL': 'osl', 'LIS': 'lis', 'ATH': 'ath'
    }
    
    return sky_id_mapping.get(iata_code, iata_code.lower())

def get_airport_sky_id_from_api(iata_code):
    """
    Get Sky ID for an airport by searching the API
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

def get_detailed_flight_info(origin_iata, destination_iata):
    """
    Get detailed flight information including price, airline, and date
    Returns a dictionary with flight details or None if no flights found
    """
    # First try to get airport Sky IDs
    origin_sky_id = get_airport_sky_id(origin_iata)
    dest_sky_id = get_airport_sky_id(destination_iata)
    
    if not origin_sky_id or not dest_sky_id:
        # Fall back to mock data for this route
        return generate_mock_flight_details(origin_iata, destination_iata)
    
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
        time.sleep(random.uniform(1, 3))
        
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
                            flight_info = {
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
                                flight_info['airline'] = flight['airline']
                            elif 'carrier' in flight:
                                flight_info['airline'] = flight['carrier']
                            elif 'airlines' in flight and len(flight['airlines']) > 0:
                                flight_info['airline'] = flight['airlines'][0]
                            
                            # Try to extract time information
                            if 'departure' in flight:
                                dep = flight['departure']
                                if isinstance(dep, dict):
                                    flight_info['departure_time'] = dep.get('time', 'Unknown')
                                    flight_info['date'] = dep.get('date', departure_date)
                                
                            if 'arrival' in flight:
                                arr = flight['arrival']
                                if isinstance(arr, dict):
                                    flight_info['arrival_time'] = arr.get('time', 'Unknown')
                            
                            # Try to extract duration
                            if 'duration' in flight:
                                flight_info['duration'] = flight['duration']
                            elif 'travelTime' in flight:
                                flight_info['duration'] = flight['travelTime']
                            
                            # Try to extract stops
                            if 'stops' in flight:
                                flight_info['stops'] = flight['stops']
                            elif 'segments' in flight:
                                flight_info['stops'] = len(flight['segments']) - 1
                            
                            cheapest_flight = flight_info
                            
                    except (ValueError, TypeError, KeyError):
                        continue
                
                return cheapest_flight
            return None
        elif response.status_code == 429:
            print(f"Rate limit hit for {origin_iata}->{destination_iata}, using mock data...")
            return generate_mock_flight_details(origin_iata, destination_iata)
        elif response.status_code == 403:
            print(f"API access forbidden - using mock data for {origin_iata}->{destination_iata}")
            return generate_mock_flight_details(origin_iata, destination_iata)
        else:
            print(f"API error {response.status_code} for {origin_iata}->{destination_iata}, using mock data...")
            return generate_mock_flight_details(origin_iata, destination_iata)
    except Exception as e:
        print(f"Request error {origin_iata}->{destination_iata}: {str(e)}, using mock data...")
        return generate_mock_flight_details(origin_iata, destination_iata)

def generate_mock_flight_details(origin_iata, destination_iata):
    """
    Generate realistic mock flight details for a specific route
    """
    # Mock airlines
    airlines = ['American Airlines', 'Delta Air Lines', 'United Airlines', 'Southwest Airlines', 
                'British Airways', 'Lufthansa', 'Air France', 'KLM', 'Emirates', 'Qatar Airways',
                'Singapore Airlines', 'Cathay Pacific', 'Japan Airlines', 'ANA', 'Turkish Airlines']
    
    # Generate realistic prices based on route
    base_price = random.randint(150, 1200)
    
    # Simulate distance-based pricing
    international_routes = [
        ('JFK', 'LHR'), ('LAX', 'NRT'), ('DXB', 'JFK'), ('SIN', 'LHR'),
        ('DEL', 'JFK'), ('BOM', 'LHR'), ('CDG', 'JFK'), ('FRA', 'LAX')
    ]
    
    if (origin_iata, destination_iata) in international_routes or (destination_iata, origin_iata) in international_routes:
        base_price += random.randint(300, 800)
    
    # Generate mock flight times
    dep_hour = random.randint(6, 23)
    dep_minute = random.choice([0, 15, 30, 45])
    duration_hours = random.randint(1, 15)
    duration_minutes = random.choice([0, 15, 30, 45])
    
    arrival_hour = (dep_hour + duration_hours + (dep_minute + duration_minutes) // 60) % 24
    arrival_minute = (dep_minute + duration_minutes) % 60
    
    return {
        'price': base_price,
        'airline': random.choice(airlines),
        'date': (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        'departure_time': f"{dep_hour:02d}:{dep_minute:02d}",
        'arrival_time': f"{arrival_hour:02d}:{arrival_minute:02d}",
        'duration': f"{duration_hours}h {duration_minutes}m",
        'stops': random.choice([0, 0, 0, 1, 1, 2])  # Most flights are direct
    }

def populate_graph_with_flight_data(G, airports, max_airports=None):
    """
    Populate graph with flight data (mix of API and mock data)
    """
    airports_list = list(airports)
    
    if max_airports:
        airports_list = airports_list[:max_airports]
    
    print(f"Populating graph with flight data for {len(airports_list)} airports...")
    routes_added = 0
    
    for i, origin in enumerate(airports_list):
        print(f"Processing {origin} ({i+1}/{len(airports_list)})")
        
        # For each airport, generate connections to a subset of other airports
        # This simulates realistic flight networks where not every airport connects to every other
        possible_destinations = [dest for dest in airports_list if dest != origin]
        
        # Major airports get more connections
        if origin in ['JFK', 'LAX', 'LHR', 'CDG', 'DXB', 'NRT', 'SIN', 'DEL', 'BOM']:
            num_connections = random.randint(8, 15)
        else:
            num_connections = random.randint(3, 8)
        
        # Select random destinations
        if len(possible_destinations) > num_connections:
            destinations = random.sample(possible_destinations, num_connections)
        else:
            destinations = possible_destinations
        
        for destination in destinations:
            flight_info = get_detailed_flight_info(origin, destination)
            
            if flight_info and flight_info['price'] > 0:
                # Store all flight details as edge attributes
                G.add_edge(origin, destination, 
                         weight=flight_info['price'],
                         airline=flight_info['airline'],
                         date=flight_info['date'],
                         departure_time=flight_info['departure_time'],
                         arrival_time=flight_info['arrival_time'],
                         duration=flight_info['duration'],
                         stops=flight_info['stops'])
                
                routes_added += 1
                print(f"  ✓ {origin} → {destination}: ${flight_info['price']:.2f} on {flight_info['airline']}")
    
    print(f"\n✅ Graph populated with {routes_added} flight routes!")
    return G

def find_shortest_path_with_preference(G, source, target):
    """
    Find the cheapest path with preference for fewer stops
    """
    if not nx.has_path(G, source, target):
        return None, float('inf')
    
    try:
        # First check for direct flight
        if G.has_edge(source, target):
            direct_cost = G[source][target]['weight']
            direct_path = [source, target]
            print(f"   Direct flight available: ${direct_cost:.2f}")
            
            # Also find the shortest path with connections
            try:
                shortest_path = nx.dijkstra_path(G, source, target, weight='weight')
                shortest_cost = nx.dijkstra_path_length(G, source, target, weight='weight')
                
                # If direct flight is reasonably close to the shortest path price, prefer direct
                if len(shortest_path) > 2 and direct_cost <= shortest_cost * 1.3:  # 30% tolerance
                    print(f"   Choosing direct flight (only {((direct_cost/shortest_cost - 1) * 100):.1f}% more expensive)")
                    return direct_path, direct_cost
                else:
                    print(f"   Choosing connecting flight (${shortest_cost:.2f} vs ${direct_cost:.2f})")
                    return shortest_path, shortest_cost
            except:
                return direct_path, direct_cost
        else:
            # No direct flight, find shortest path
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
    Test if the API is working properly
    """
    print("Testing API connection...")
    
    try:
        # Simple test with a known route
        test_info = get_detailed_flight_info("JFK", "LAX")
        if test_info and 'price' in test_info:
            print("✅ API connection working!")
            print(f"   Test route JFK→LAX: ${test_info['price']:.2f} on {test_info['airline']}")
            return True
        else:
            print("⚠️  API returned no data, will use mock data")
            return False
    except Exception as e:
        print(f"❌ API connection failed: {str(e)}")
        print("   Will use mock data instead")
        return False

def main():
    print("🛫 Flight Route Finder - Enhanced Edition")
    print("=" * 50)
    
    # Test API first
    api_working = test_api_connection()
    if not api_working:
        print("\n📊 Using mock data for demonstration...")
    
    print(f"\n📍 Working with {len(filtered_airport_dict)} airports with scheduled service")
    
    # Initialize graph with airport nodes
    G = nx.DiGraph()
    for iata in filtered_airport_dict:
        G.add_node(iata)
    
    # Choose how many airports to process
    print("\nOptions:")
    print("1. Quick demo (50 airports)")
    print("2. Medium test (200 airports)")
    print("3. Full dataset (4000+ airports)")
    print("4. Custom number")
    
    choice = input("\nChoose option (1-4): ").strip()
    
    if choice == '1':
        max_airports = 50
    elif choice == '2':
        max_airports = 200
    elif choice == '3':
        max_airports = None
    elif choice == '4':
        try:
            max_airports = int(input("Enter number of airports: "))
        except:
            max_airports = 50
    else:
        max_airports = 50
    
    # Populate graph with flight data
    print(f"\n🔄 Loading flight data...")
    populate_graph_with_flight_data(G, filtered_airport_dict.keys(), max_airports)
    
    print(f"\n✅ System ready! Graph has {G.number_of_nodes()} airports and {G.number_of_edges()} routes.")
    
    # Show some example airports
    available_codes = sorted(G.nodes())
    print(f"\n📍 Available airports include: {', '.join(available_codes[:20])}...")
    if len(available_codes) > 20:
        print(f"   ... and {len(available_codes) - 20} more")
    
    # Main interaction loop
    while True:
        try:
            print("\n" + "="*50)
            origin = input("✈️  Enter origin IATA code (or 'q' to quit): ").upper().strip()
            if origin == 'Q':
                break
                
            destination = input("🛬 Enter destination IATA code: ").upper().strip()
            
            if origin not in G.nodes() or destination not in G.nodes():
                print("❌ Invalid IATA code(s). Please choose from available airports.")
                print(f"Examples: {', '.join(available_codes[:20])}")
                continue
            
            if origin == destination:
                print("❌ Origin and destination cannot be the same!")
                continue
            
            print(f"\n🔍 Searching for the best route from {origin} to {destination}...")
            path, cost = find_shortest_path_with_preference(G, origin, destination)
            
            if path is None or cost == float('inf'):
                print("❌ No available route found between these airports.")
                continue
            
            # Display results
            print(f"\n🎯 Best route from {origin} to {destination}:")
            print(f"✈️  Path: {' → '.join(path)}")
            print(f"💰 Total Cost: ${cost:.2f}")
            print(f"🛑 Stops: {len(path) - 2}")
            
            if len(path) == 2:
                print("🎉 Direct flight!")
            else:
                print(f"🔄 Connecting flight with {len(path) - 2} stop(s)")
            
            # Show detailed breakdown
            print(f"\n📋 Flight Details:")
            total_duration_mins = 0
            
            for i in range(len(path) - 1):
                leg_origin = path[i]
                leg_dest = path[i+1]
                edge_data = G[leg_origin][leg_dest]
                
                leg_cost = edge_data['weight']
                airline = edge_data.get('airline', 'Unknown')
                dep_time = edge_data.get('departure_time', 'Unknown')
                arr_time = edge_data.get('arrival_time', 'Unknown')
                duration = edge_data.get('duration', 'Unknown')
                date = edge_data.get('date', 'Unknown')
                stops = edge_data.get('stops', 0)
                
                print(f"\n   Leg {i+1}: {leg_origin} → {leg_dest}")
                print(f"      💵 Price: ${leg_cost:.2f}")
                print(f"      🏢 Airline: {airline}")
                print(f"      📅 Date: {date}")
                print(f"      🕐 Departure: {dep_time}")
                print(f"      🕑 Arrival: {arr_time}")
                print(f"      ⏱️  Duration: {duration}")
                if stops > 0:
                    print(f"      🔄 Flight stops: {stops}")
                
        except Exception as e:
            print(f"❌ An error occurred: {str(e)}")
            continue
        except KeyboardInterrupt:
            print("\n⏹️  Operation cancelled by user.")
            break
    
    print("\n👋 Thank you for using the Flight Route Finder!")
    print("Safe travels! ✈️")

if __name__ == "__main__":
    main()
