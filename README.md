# Flight Route Finder

A Python application that finds optimal flight routes between airports worldwide using graph theory and real-time flight data.

## Overview

Flight Route Finder helps travelers discover the most cost-effective routes between airports, intelligently balancing price with convenience. The application uses the Fly Scraper API to fetch real flight data and falls back to realistic mock data when necessary.

## Features

- **Smart Route Finding**: Uses Dijkstra's algorithm to find the cheapest path between airports
- **Direct vs. Connecting Flight Analysis**: Compares direct flights against connecting options, preferring direct flights when they're within 30% of the price of connecting flights
- **Comprehensive Airport Database**: Works with 4000+ airports with scheduled service worldwide
- **Detailed Flight Information**: Shows complete route breakdowns with pricing, airlines, times, and durations
- **Graceful API Fallbacks**: Automatically switches to realistic mock data when API limits are reached

## How It Works

1. **Airport Data Loading**: Loads and filters airport data from a comprehensive CSV dataset
2. **Graph Construction**: Builds a directed graph where nodes are airports and edges are flights
3. **Flight Data Population**: Populates the graph with real flight data (or mock data when needed)
4. **Route Optimization**: Applies Dijkstra's algorithm with custom heuristics to find optimal routes
5. **Itinerary Display**: Shows detailed flight information for each leg of the journey

## Usage

1. Run the script: `python airports_fixed.py`
2. Choose dataset size (quick demo, medium test, or full dataset)
3. Enter origin airport IATA code (e.g., "JFK")
4. Enter destination airport IATA code (e.g., "LAX")
5. View the optimal route and detailed flight information

## Requirements

- Python 3.6+
- NetworkX
- Pandas
- Requests

## Data Sources

- Airport data from OurAirports dataset
- Flight information from Fly Scraper API or realistic mock data generator

## Example

```
✈️  Enter origin IATA code (or 'q' to quit): JFK
🛬 Enter destination IATA code: LHR

🔍 Searching for the best route from JFK to LHR...
   Direct flight available: $542.00
   Choosing direct flight

🎯 Best route from JFK to LHR:
✈️  Path: JFK → LHR
💰 Total Cost: $542.00
🛑 Stops: 0
🎉 Direct flight!

📋 Flight Details:

   Leg 1: JFK → LHR
      💵 Price: $542.00
      🏢 Airline: British Airways
      📅 Date: 2025-06-11
      🕐 Departure: 19:45
      🕑 Arrival: 07:55
      ⏱️  Duration: 7h 10m
```
