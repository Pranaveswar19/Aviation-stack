# app.py
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
            "New York": [
                {"iata": "JFK", "name": "John F. Kennedy International"},
                {"iata": "LGA", "name": "LaGuardia Airport"}
            ],
            "London": [
                {"iata": "LHR", "name": "Heathrow Airport"},
                {"iata": "LGW", "name": "Gatwick Airport"}
            ],
            "Tokyo": [
                {"iata": "HND", "name": "Haneda Airport"},
                {"iata": "NRT", "name": "Narita International"}
            ],
            "Dubai": [
                {"iata": "DXB", "name": "Dubai International"}
            ],
            "Singapore": [
                {"iata": "SIN", "name": "Changi Airport"}
            ]
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
    def get_city_airports(self, city: str) -> List[Dict]:
        """Get airports for a city with caching"""
        if self.use_mock:
            return self.mock_airports.get(city, [])
        
        if st.session_state.api_calls >= 95:  # API limit safety
            self.use_mock = True
            return self.mock_airports.get(city, [])
        
        try:
            st.session_state.api_calls += 1
            sleep(1)  # Rate limiting
            
            response = requests.get(
                "http://api.aviationstack.com/v1/airports",
                params={
                    "access_key": self.aviation_api_key,
                    "city": city
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "iata": airport["iata_code"],
                        "name": airport["airport_name"]
                    }
                    for airport in data.get("data", [])
                    if airport.get("iata_code")
                ]
            return []
        except Exception as e:
            st.warning(f"Using mock data due to API error: {str(e)}")
            return self.mock_airports.get(city, [])

    @st.cache_data(ttl=3600)
    def search_flights(self, departure_city: str, arrival_city: str, 
                      departure_date: str) -> List[Dict]:
        """Search flights with caching"""
        if self.use_mock:
            route_key = (departure_city, arrival_city)
            return self.mock_routes.get(route_key, [])
        
        if st.session_state.api_calls >= 95:
            self.use_mock = True
            return self.mock_routes.get((departure_city, arrival_city), [])
        
        try:
            st.session_state.api_calls += 1
            sleep(1)  # Rate limiting
            
            response = requests.get(
                "http://api.aviationstack.com/v1/flights",
                params={
                    "access_key": self.aviation_api_key,
                    "dep_iata": departure_city,
                    "arr_iata": arrival_city,
                    "flight_date": departure_date
                }
            )
            
            if response.status_code == 200:
                return response.json().get("data", [])
            return []
        except Exception as e:
            st.warning(f"Using mock data due to API error: {str(e)}")
            return self.mock_routes.get((departure_city, arrival_city), [])

    def get_flight_price_estimate(self, departure_city: str, 
                                arrival_city: str) -> Optional[Dict]:
        """Get price estimates"""
        if self.use_mock:
            route_key = (departure_city, arrival_city)
            return self.mock_prices.get(route_key, {
                "min_price": 500,
                "max_price": 1000,
                "currency": "USD"
            })
        
        try:
            client = openai.OpenAI(api_key=self.openai_api_key)
            
            prompt = f"""Estimate price range for a flight from {departure_city} to {arrival_city}.
            Format response as JSON with min_price, max_price, and currency fields."""
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=[
                    {"role": "system", "content": "You are a flight pricing expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            st.warning(f"Using mock price data due to API error: {str(e)}")
            return self.mock_prices.get((departure_city, arrival_city), {
                "min_price": 500,
                "max_price": 1000,
                "currency": "USD"
            })

def main():
    st.title("✈️ Flight Information Tracker")
    
    # Initialize data provider
    data_provider = FlightDataProvider(use_mock=USE_MOCK_DATA)
    
    # Show API call counter in sidebar
    st.sidebar.metric("API Calls Made", st.session_state.api_calls)
    
    if USE_MOCK_DATA:
        st.info("""
        ℹ️ Currently using demo data due to API limits. 
        Available demo routes: 
        - New York (JFK) ↔️ London (LHR)
        - London (LHR) ↔️ Tokyo (HND)
        - Tokyo (HND) ↔️ Dubai (DXB)
        - Dubai (DXB) ↔️ Singapore (SIN)
        """)
    
    # Search form
    with st.form("flight_search_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            departure_city = st.text_input("Departure City")
            departure_date = st.date_input("Departure Date", 
                min_value=datetime.today())
            
        with col2:
            arrival_city = st.text_input("Arrival City")
            budget_range = st.slider("Budget Range (USD)", 
                0, 5000, (200, 2000))
        
        search_button = st.form_submit_button("Search Flights")
        
        if search_button:
            if not (departure_city and arrival_city):
                st.error("Please enter both departure and arrival cities.")
                return
            
            # Get airports
            with st.spinner("Finding airports..."):
                departure_airports = data_provider.get_city_airports(departure_city)
                arrival_airports = data_provider.get_city_airports(arrival_city)
            
            if not departure_airports or not arrival_airports:
                st.error(f"No airports found for one or both cities. Available cities in demo mode: {', '.join(data_provider.mock_airports.keys())}")
                return
            
            # Search flights
            flights = []
            with st.spinner("Searching flights..."):
                for dep_airport in departure_airports:
                    for arr_airport in arrival_airports:
                        results = data_provider.search_flights(
                            dep_airport["iata"],
                            arr_airport["iata"],
                            departure_date.strftime("%Y-%m-%d")
                        )
                        flights.extend(results)
            
            # Display results
            if flights:
                st.subheader("📊 Flight Information")
                
                # Get and display price estimate
                with st.spinner("Estimating prices..."):
                    price_estimate = data_provider.get_flight_price_estimate(
                        departure_city, arrival_city)
                
                if price_estimate:
                    with st.expander("💰 Estimated Price Range", expanded=True):
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Minimum Price", 
                            f"${price_estimate['min_price']}")
                        col2.metric("Maximum Price", 
                            f"${price_estimate['max_price']}")
                        col3.metric("Currency", price_estimate['currency'])
                
                # Display flights table
                flight_data = []
                for flight in flights:
                    flight_data.append({
                        "Flight Number": flight["flight"]["number"],
                        "Airline": flight["airline"]["name"],
                        "Departure": flight["departure"]["scheduled"],
                        "Arrival": flight["arrival"]["scheduled"],
                        "Status": flight["flight_status"].title()
                    })
                
                if flight_data:
                    st.dataframe(
                        pd.DataFrame(flight_data),
                        use_container_width=True,
                        hide_index=True
                    )
            else:
                st.warning("No flights found for the specified route and date.")

if __name__ == "__main__":
    main()
