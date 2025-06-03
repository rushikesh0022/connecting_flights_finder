#!/usr/bin/env python3
"""
Enhanced Flight Route Finder with Real-time API Integration
- Uses ALL airports with scheduled service from OurAirports dataset
- Integrates with flight APIs for real-time pricing and airline information
- Prioritizes direct flights and minimizes connections
- Displays detailed flight information including airlines, dates, and times
"""

import pandas as pd
import networkx as nx
import requests
import http.client
from datetime import datetime, timedelta
import time
import random
import json

# Load airport data from the OurAirports dataset
print("📊 Loading airport dataset...")
airports_df = pd.read_csv('airports.csv')

# Filter for ALL airports with scheduled service and valid IATA codes
valid_airports = airports_df[
    (airports_df['iata_code'].notnull()) &
    (airports_df['iata_code'] != '') &  # Ensure IATA code is not empty
    (airports_df['scheduled_service'] == 'yes')  # ALL airports with scheduled service
].copy()

# Clean up IATA codes - remove any whitespace and ensure uppercase
valid_airports['iata_code'] = valid_airports['iata_code'].str.strip().str.upper()

print(f"✅ Loaded {len(airports_df):,} total airports from dataset")
print(f"✅ Found {len(valid_airports):,} airports with scheduled service and valid IATA codes")

# Create a dictionary of airports using the exact IATA codes from the dataset
airport_dict = {}
for _, airport in valid_airports.iterrows():
    iata_code = airport['iata_code']
    airport_dict[iata_code] = {
        'name': airport['name'],
        'municipality': airport['municipality'],
        'country': airport['iso_country'],
        'type': airport['type'],
        'latitude': airport['latitude_deg'],
        'longitude': airport['longitude_deg']
    }

# Display statistics about airport types
airport_types = valid_airports['type'].value_counts()
print(f"\n📊 Airport breakdown by type:")
for airport_type, count in airport_types.head(10).items():
    print(f"   {airport_type}: {count:,}")

# Show sample airports from different regions
print(f"\n🌍 Sample airports from different countries:")
sample_airports = valid_airports.groupby('iso_country').first().reset_index()
sample_display = sample_airports[['iata_code', 'name', 'municipality', 'iso_country', 'type']].head(15)
print(sample_display.to_string(index=False))

print(f"\n🎯 Total airports available for routing: {len(airport_dict):,}")

# Initialize directed graph for flight routes
G = nx.DiGraph()

# Add nodes for each airport
for iata in airport_dict:
    G.add_node(iata, **airport_dict[iata])

def get_detailed_flight_info(origin_iata, destination_iata):
    """
    Get detailed flight information from API including airlines, dates, and times
    Returns a dictionary with comprehensive flight details or None if no flights found
    """
    url = "https://fly-scraper.p.rapidapi.com/flights/search"
    
    # Search for flights 7 days from now
    departure_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    querystring = {
        "origin": origin_iata.lower(),  # Use IATA code directly from dataset
        "destination": destination_iata.lower(),
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
        # Add delay to respect rate limits
        time.sleep(random.uniform(1, 3))
        
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract flight information from API response
            if 'data' in data and 'flights' in data['data'] and len(data['data']['flights']) > 0:
                best_flight = None
                best_price = float('inf')
                
                for flight in data['data']['flights']:
                    try:
                        # Extract price from various possible fields
                        price = None
                        if 'price' in flight:
                            if isinstance(flight['price'], dict):
                                price = float(flight['price'].get('amount', 0))
                            else:
                                price = float(flight['price'])
                        elif 'totalPrice' in flight:
                            price = float(flight['totalPrice'])
                        elif 'cost' in flight:
                            price = float(flight['cost'])
                        
                        if price and price < best_price and price > 0:
                            best_price = price
                            
                            # Extract detailed flight information
                            flight_info = {
                                'price': price,
                                'airline': 'Unknown Airline',
                                'departure_time': 'Unknown',
                                'arrival_time': 'Unknown',
                                'date': departure_date,
                                'duration': 'Unknown',
                                'stops': 0,
                                'aircraft': 'Unknown'
                            }
                            
                            # Extract airline information
                            if 'airline' in flight:
                                flight_info['airline'] = flight['airline']
                            elif 'carrier' in flight:
                                flight_info['airline'] = flight['carrier']
                            elif 'airlines' in flight and len(flight['airlines']) > 0:
                                flight_info['airline'] = flight['airlines'][0]
                            elif 'operatingCarrier' in flight:
                                flight_info['airline'] = flight['operatingCarrier']
                            
                            # Extract departure information
                            if 'departure' in flight:
                                dep_info = flight['departure']
                                if isinstance(dep_info, dict):
                                    flight_info['departure_time'] = dep_info.get('time', 'Unknown')
                                    if 'date' in dep_info:
                                        flight_info['date'] = dep_info['date']
                            
                            # Extract arrival information
                            if 'arrival' in flight:
                                arr_info = flight['arrival']
                                if isinstance(arr_info, dict):
                                    flight_info['arrival_time'] = arr_info.get('time', 'Unknown')
                            
                            # Extract duration
                            if 'duration' in flight:
                                flight_info['duration'] = str(flight['duration'])
                            elif 'travelTime' in flight:
                                flight_info['duration'] = str(flight['travelTime'])
                            
                            # Extract number of stops
                            if 'stops' in flight:
                                flight_info['stops'] = int(flight['stops'])
                            elif 'segments' in flight:
                                flight_info['stops'] = max(0, len(flight['segments']) - 1)
                            elif 'layovers' in flight:
                                flight_info['stops'] = len(flight['layovers'])
                            
                            # Extract aircraft type
                            if 'aircraft' in flight:
                                flight_info['aircraft'] = flight['aircraft']
                            elif 'equipmentType' in flight:
                                flight_info['aircraft'] = flight['equipmentType']
                            
                            best_flight = flight_info
                            
                    except (ValueError, TypeError, KeyError) as e:
                        continue
                
                return best_flight
                
        elif response.status_code == 403:
            print(f"⚠️  API access issue for {origin_iata}→{destination_iata}")
            return None
        elif response.status_code == 429:
            print(f"⚠️  Rate limit hit, waiting...")
            time.sleep(30)
            return get_detailed_flight_info(origin_iata, destination_iata)
        else:
            print(f"⚠️  API error {response.status_code} for {origin_iata}→{destination_iata}")
            return None
            
    except Exception as e:
        print(f"⚠️  Request error for {origin_iata}→{destination_iata}: {str(e)}")
        return None

def generate_realistic_mock_flight_data(origin_iata, destination_iata):
    """
    Generate realistic mock flight data when API is not available
    Uses real airline names and realistic pricing based on distance estimation
    """
    # Real airline names for more realistic mock data
    major_airlines = [
        'American Airlines', 'Delta Air Lines', 'United Airlines', 'Southwest Airlines',
        'British Airways', 'Lufthansa', 'Air France', 'KLM Royal Dutch Airlines',
        'Emirates', 'Qatar Airways', 'Singapore Airlines', 'Cathay Pacific',
        'Japan Airlines', 'ANA All Nippon Airways', 'Turkish Airlines',
        'Iberia', 'Alitalia', 'Air Canada', 'Qantas', 'Korean Air'
    ]
    
    # Regional airlines for shorter routes
    regional_airlines = [
        'Alaska Airlines', 'JetBlue Airways', 'Frontier Airlines', 'Spirit Airlines',
        'Allegiant Air', 'Hawaiian Airlines', 'WestJet', 'Porter Airlines'
    ]
    
    # Estimate distance-based pricing (very rough approximation)
    base_price = random.randint(89, 299)  # Base domestic price
    
    # International route adjustments
    origin_country = airport_dict.get(origin_iata, {}).get('country', 'US')
    dest_country = airport_dict.get(destination_iata, {}).get('country', 'US')
    
    if origin_country != dest_country:
        base_price += random.randint(200, 800)  # International surcharge
        airline_pool = major_airlines  # International routes use major airlines
    else:
        airline_pool = major_airlines + regional_airlines  # Domestic can use any
    
    # Generate realistic flight times
    departure_hour = random.randint(6, 22)
    departure_minute = random.choice([0, 15, 30, 45])
    
    # Flight duration based on rough distance estimation
    if origin_country != dest_country:
        duration_hours = random.randint(6, 16)  # International flights
    else:
        duration_hours = random.randint(1, 6)   # Domestic flights
    
    duration_minutes = random.choice([0, 15, 30, 45])
    
    arrival_hour = (departure_hour + duration_hours + (departure_minute + duration_minutes) // 60) % 24
    arrival_minute = (departure_minute + duration_minutes) % 60
    
    # Determine if it's a direct flight or has stops
    stops = random.choices([0, 1, 2], weights=[70, 25, 5])[0]  # 70% direct flights
    
    return {
        'price': base_price,
        'airline': random.choice(airline_pool),
        'departure_time': f"{departure_hour:02d}:{departure_minute:02d}",
        'arrival_time': f"{arrival_hour:02d}:{arrival_minute:02d}",
        'date': (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        'duration': f"{duration_hours}h {duration_minutes}m",
        'stops': stops,
        'aircraft': random.choice(['Boeing 737', 'Airbus A320', 'Boeing 777', 'Airbus A350', 'Boeing 787'])
    }

def populate_flight_network(airports, use_api=True, max_airports=None):
    """
    Populate the flight network with routes between airports
    Prioritizes direct flights and uses real API data when available
    """
    airport_list = list(airports.keys())
    
    if max_airports:
        airport_list = airport_list[:max_airports]
        print(f"🔄 Processing {len(airport_list)} airports for testing...")
    else:
        print(f"🔄 Processing all {len(airport_list)} airports...")
    
    routes_added = 0
    api_calls = 0
    
    for i, origin in enumerate(airport_list):
        print(f"\n📍 Processing flights from {origin} ({i+1}/{len(airport_list)})")
        print(f"   {airports[origin]['name']}, {airports[origin]['municipality']}")
        
        # Process a subset of destinations to avoid too many API calls
        destinations = [dest for dest in airport_list if dest != origin]
        
        # For testing, limit destinations per origin
        if max_airports:
            destinations = random.sample(destinations, min(5, len(destinations)))
        else:
            destinations = random.sample(destinations, min(10, len(destinations)))
        
        for destination in destinations:
            print(f"   Checking {origin} → {destination}...", end=" ")
            
            if use_api:
                flight_info = get_detailed_flight_info(origin, destination)
                api_calls += 1
            else:
                flight_info = generate_realistic_mock_flight_data(origin, destination)
            
            if flight_info and flight_info['price'] > 0:
                # Add route to graph with all flight details
                G.add_edge(origin, destination, **flight_info)
                routes_added += 1
                
                print(f"✅ ${flight_info['price']:.0f} on {flight_info['airline']}")
            else:
                print("❌ No route")
        
        # Progress update
        if (i + 1) % 10 == 0:
            print(f"\n📊 Progress: {i+1}/{len(airport_list)} airports processed")
            print(f"📊 Routes added so far: {routes_added}")
            if use_api:
                print(f"📊 API calls made: {api_calls}")
    
    print(f"\n✅ Network populated with {routes_added} routes across {len(airport_list)} airports")
    if use_api:
        print(f"📊 Total API calls made: {api_calls}")
    
    return G

def find_optimal_route(G, origin, destination):
    """
    Find the optimal route prioritizing direct flights and minimizing connections
    Returns the best path with detailed route information
    """
    if origin not in G or destination not in G:
        return None, float('inf'), []
    
    # First check for direct flight
    if G.has_edge(origin, destination):
        direct_flight = G[origin][destination]
        print(f"🎯 Direct flight available!")
        return [origin, destination], direct_flight['price'], [direct_flight]
    
    # If no direct flight, find shortest path with minimum connections
    try:
        if not nx.has_path(G, origin, destination):
            return None, float('inf'), []
        
        # Use Dijkstra's algorithm to find cheapest path
        path = nx.dijkstra_path(G, origin, destination, weight='price')
        total_cost = nx.dijkstra_path_length(G, origin, destination, weight='price')
        
        # Extract detailed route information
        route_details = []
        for i in range(len(path) - 1):
            leg_origin = path[i]
            leg_dest = path[i + 1]
            flight_info = G[leg_origin][leg_dest]
            route_details.append(flight_info)
        
        return path, total_cost, route_details
        
    except nx.NetworkXNoPath:
        return None, float('inf'), []
    except Exception as e:
        print(f"❌ Error finding route: {str(e)}")
        return None, float('inf'), []

def display_route_details(path, total_cost, route_details, origin, destination):
    """
    Display detailed route information in a user-friendly format
    """
    if not path:
        print(f"❌ No route found from {origin} to {destination}")
        return
    
    origin_info = airport_dict[origin]
    dest_info = airport_dict[destination]
    
    print(f"\n🎯 Route: {origin} → {destination}")
    print(f"   From: {origin_info['name']}, {origin_info['municipality']}, {origin_info['country']}")
    print(f"   To: {dest_info['name']}, {dest_info['municipality']}, {dest_info['country']}")
    print(f"💰 Total Cost: ${total_cost:.2f}")
    print(f"🛑 Connections: {len(path) - 2}")
    
    if len(path) == 2:
        print("✈️  Type: Direct Flight")
    else:
        print(f"✈️  Type: Connecting Flight via {' → '.join(path[1:-1])}")
    
    print(f"\n📋 Detailed Flight Information:")
    print("=" * 80)
    
    for i, (leg_origin, leg_dest, flight_info) in enumerate(zip(path[:-1], path[1:], route_details)):
        leg_origin_info = airport_dict[leg_origin]
        leg_dest_info = airport_dict[leg_dest]
        
        print(f"\n✈️  FLIGHT {i+1}: {leg_origin} → {leg_dest}")
        print(f"   From: {leg_origin_info['name']}, {leg_origin_info['municipality']}")
        print(f"   To: {leg_dest_info['name']}, {leg_dest_info['municipality']}")
        print(f"   💵 Price: ${flight_info['price']:.2f}")
        print(f"   🏢 Airline: {flight_info['airline']}")
        print(f"   📅 Date: {flight_info['date']}")
        print(f"   🛫 Departure: {flight_info['departure_time']}")
        print(f"   🛬 Arrival: {flight_info['arrival_time']}")
        print(f"   ⏱️  Duration: {flight_info['duration']}")
        print(f"   ✈️  Aircraft: {flight_info.get('aircraft', 'Unknown')}")
        
        if flight_info['stops'] > 0:
            print(f"   🔄 Stops: {flight_info['stops']}")
        else:
            print(f"   🔄 Direct Flight")

def test_api_connectivity():
    """Test if the flight API is accessible"""
    print("🔍 Testing API connectivity...")
    
    # Test with a common route
    test_flight = get_detailed_flight_info("JFK", "LAX")
    
    if test_flight:
        print("✅ API is working!")
        print(f"   Test flight JFK→LAX: ${test_flight['price']:.2f} on {test_flight['airline']}")
        return True
    else:
        print("❌ API not accessible - will use mock data")
        return False

def main():
    """Main application function"""
    print("🚀 Enhanced Flight Route Finder")
    print("=" * 50)
    print("Features:")
    print("• Uses ALL airports with scheduled service from OurAirports dataset")
    print("• Real-time flight data with airline names and schedules")
    print("• Prioritizes direct flights and minimizes connections")
    print("• Comprehensive route information display")
    print("=" * 50)
    
    # Test API connectivity
    api_available = test_api_connectivity()
    
    print(f"\n📊 Available airports: {len(airport_dict):,}")
    print("Choose data source:")
    print("1. Real API data (slower, requires working API)")
    print("2. Mock data (faster, for testing)")
    print("3. Limited real data (10 airports, for testing)")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1" and api_available:
        print("\n🔄 Fetching real flight data for ALL airports...")
        print("⚠️  This will take a very long time due to API rate limits!")
        confirm = input("Continue? (y/N): ").strip().lower()
        if confirm == 'y':
            populate_flight_network(airport_dict, use_api=True)
        else:
            print("Using mock data instead...")
            populate_flight_network(airport_dict, use_api=False, max_airports=50)
    elif choice == "3":
        print("\n🔄 Fetching real data for limited airports...")
        populate_flight_network(airport_dict, use_api=api_available, max_airports=20)
    else:
        print("\n🔄 Generating mock flight data...")
        populate_flight_network(airport_dict, use_api=False, max_airports=100)
    
    print(f"\n✅ Flight network ready!")
    print(f"📊 Total routes: {G.number_of_edges():,}")
    print(f"📊 Connected airports: {G.number_of_nodes():,}")
    
    # Show available airports sample
    available_codes = sorted(airport_dict.keys())
    print(f"\n🎯 Available airports (sample): {', '.join(available_codes[:20])}")
    if len(available_codes) > 20:
        print(f"   ... and {len(available_codes) - 20:,} more airports")
    
    # Interactive flight search
    while True:
        try:
            print("\n" + "=" * 50)
            origin = input("✈️  Enter origin airport (IATA code) or 'q' to quit: ").upper().strip()
            
            if origin == 'Q':
                break
            
            if origin not in airport_dict:
                print(f"❌ Airport '{origin}' not found in dataset")
                print(f"💡 Available airports start with: {', '.join(sorted(set(code[0] for code in available_codes)))}")
                continue
            
            destination = input("🛬 Enter destination airport (IATA code): ").upper().strip()
            
            if destination not in airport_dict:
                print(f"❌ Airport '{destination}' not found in dataset")
                continue
            
            if origin == destination:
                print("❌ Origin and destination cannot be the same")
                continue
            
            print(f"\n🔍 Finding optimal route from {origin} to {destination}...")
            
            path, cost, route_details = find_optimal_route(G, origin, destination)
            
            display_route_details(path, cost, route_details, origin, destination)
            
        except KeyboardInterrupt:
            print("\n\n👋 Thank you for using the Enhanced Flight Route Finder!")
            break
        except Exception as e:
            print(f"❌ An error occurred: {str(e)}")
            continue

if __name__ == "__main__":
    main()
