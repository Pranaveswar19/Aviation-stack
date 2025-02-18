# aviation.py
import streamlit as st
import requests
import openai
from datetime import datetime, timedelta
import pandas as pd
import json
import os
from time import sleep
from typing import Dict, List, Optional

# Configuration and Settings
st.set_page_config(
    page_title="Flight Info Tracker",
    page_icon="✈️",
    layout="wide"
)

# Initialize session state
if 'api_calls' not in st.session_state:
    st.session_state.api_calls = 0
    
if 'flight_search_done' not in st.session_state:
    st.session_state.flight_search_done = False

# Toggle this to True when API limit is reached
USE_MOCK_DATA = True

class FlightDataProvider:
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.aviation_api_key = st.secrets.get("aviation_api_key", "")
        self.openai_api_key = st.secrets.get("openai_api_key", "")
        
        # Initialize mock data
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock data for demo mode"""
        self.mock_airports = {
            "New York": [("JFK", "John F. Kennedy International"), ("LGA", "LaGuardia Airport")],
            "London": [("LHR", "Heathrow Airport"), ("LGW", "Gatwick Airport")],
            "Tokyo": [("HND", "Haneda Airport"), ("NRT", "Narita International")],
            "Dubai": [("DXB", "Dubai International")],
            "Singapore": [("SIN", "Changi Airport")]
        }
        
        # Generate mock flight schedules
        current_date = datetime.now()
        self.mock_routes = {}
        
        route_pairs = [
            ("JFK", "LHR"), ("LHR", "HND"), 
            ("HND", "DXB"), ("DXB", "SIN")
        ]
        
        airlines = [
            ("BA", "British Airways"), 
            ("AA", "American Airlines"),
            ("EK", "Emirates"),
            ("SQ", "Singapore Airlines")
        ]
        
        for dep, arr in route_pairs:
            flights = []
            for airline_code, airline_name in airlines:
                # Morning flight
                flight_num = f"{airline_code}{100 + len(flights)}"
                dep_time = current_date.replace(hour=8, minute=0)
                arr_time = dep_time + timedelta(hours=8)
                
                flights.append({
                    "flight": {"number": flight_num},
                    "airline": {"name": airline_name},
                    "departure": {"scheduled": dep_time.strftime("%Y-%m-%dT%H:%M:%SZ")},
                    "arrival": {"scheduled": arr_time.strftime("%Y-%m-%dT%H:%M:%SZ")},
                    "flight_status": "scheduled"
                })
                
                # Evening flight
                flight_num = f"{airline_code}{200 + len(flights)}"
                dep_time = current_date.replace(hour=18, minute=0)
                arr_time = dep_time + timedelta(hours=8)
                
                flights.append({
                    "flight": {"number": flight_num},
                    "airline": {"name": airline_name},
                    "departure": {"scheduled": dep_time.strftime("%Y-%m-%dT%H:%M:%SZ")},
                    "arrival": {"scheduled": arr_time.strftime("%Y-%m-%dT%H:%M:%SZ")},
                    "flight_status": "scheduled"
                })
            
            self.mock_routes[(dep, arr)] = flights
        
        # Mock price ranges
        self.mock_prices = {
            ("New York", "London"): {"min_price": 450, "max_price": 800, "currency": "USD"},
            ("London", "Tokyo"): {"min_price": 700, "max_price": 1200, "currency": "USD"},
            ("Tokyo", "Dubai"): {"min_price": 600, "max_price": 900, "currency": "USD"},
            ("Dubai", "Singapore"): {"min_price": 400, "max_price": 700, "currency": "USD"}
        }

    @st.cache_data(ttl=3600)
    def get_city_airports(self, city: str):
        """Get airports for a city with caching - Fixed unhashable type error"""
        city = str(city)  # Ensure city is always a string (hashable)

        if self.use_mock:
            return tuple(self.mock_airports.get(city, []))  # Convert list to tuple

        if st.session_state.api_calls >= 95:  # API limit safety
            self.use_mock = True
            return tuple(self.mock_airports.get(city, []))

        try:
            st.session_state.api_calls += 1
            sleep(1)  # Rate limiting
            
            response = requests.get(
                "http://api.aviationstack.com/v1/airports",
                params={"access_key": self.aviation_api_key, "city": city}
            )
            
            if response.status_code == 200:
                data = response.json()
                return tuple((airport["iata_code"], airport["airport_name"]) 
                             for airport in data.get("data", []) 
                             if airport.get("iata_code"))

        except Exception as e:
            st.warning(f"Using mock data due to API error: {str(e)}")
            return tuple(self.mock_airports.get(city, []))
        return ()

def main():
    st.title("✈️ Flight Information Tracker")
    
    # Initialize data provider
    data_provider = FlightDataProvider(use_mock=USE_MOCK_DATA)
    
    st.sidebar.metric("API Calls Made", st.session_state.api_calls)
    
    if USE_MOCK_DATA:
        st.info("ℹ️ Currently using demo data due to API limits.")

    with st.form("flight_search_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            departure_city = st.text_input("Departure City")
            departure_date = st.date_input("Departure Date", min_value=datetime.today())
            
        with col2:
            arrival_city = st.text_input("Arrival City")

        search_button = st.form_submit_button("Search Flights")
        
        if search_button:
            if not (departure_city and arrival_city):
                st.error("Please enter both departure and arrival cities.")
                return
            
            with st.spinner("Finding airports..."):
                departure_airports = data_provider.get_city_airports(departure_city)
                arrival_airports = data_provider.get_city_airports(arrival_city)
            
            if not departure_airports or not arrival_airports:
                st.error(f"No airports found for one or both cities.")
                return
            
            st.success(f"Found {len(departure_airports)} departure airports and {len(arrival_airports)} arrival airports.")

if __name__ == "__main__":
    main()
