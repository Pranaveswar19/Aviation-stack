import streamlit as st
import requests
import openai
from datetime import datetime, timedelta
import pandas as pd
import json
import os

# Configure page settings
st.set_page_config(
    page_title="Flight Info Tracker",
    page_icon="✈️",
    layout="wide"
)

# Initialize session state
if 'flight_search_done' not in st.session_state:
    st.session_state.flight_search_done = False

if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []

# API Configuration
AVIATION_API_KEY = st.secrets["aviation_api_key"]
OPENAI_API_KEY = st.secrets["openai_api_key"]
AVIATION_API_BASE = "http://api.aviationstack.com/v1"

def get_city_airports(city):
    """Fetch airports for a given city using Aviation Stack API"""
    endpoint = f"{AVIATION_API_BASE}/airports"
    params = {
        "access_key": AVIATION_API_KEY,
        "city": city
    }
    
    try:
        response = requests.get(endpoint, params=params)
        data = response.json()
        
        if response.status_code == 200 and "data" in data:
            return [{"iata": airport["iata_code"], 
                    "name": airport["airport_name"]} 
                    for airport in data["data"] 
                    if airport["iata_code"]]
        return []
    except Exception as e:
        st.error(f"Error fetching airports: {str(e)}")
        return []

def search_flights(departure_city, arrival_city, departure_date):
    """Search for flights using Aviation Stack API"""
    endpoint = f"{AVIATION_API_BASE}/flights"
    params = {
        "access_key": AVIATION_API_KEY,
        "dep_iata": departure_city,
        "arr_iata": arrival_city,
        "flight_date": departure_date
    }
    
    try:
        response = requests.get(endpoint, params=params)
        data = response.json()
        
        if response.status_code == 200 and "data" in data:
            return data["data"]
        return []
    except Exception as e:
        st.error(f"Error searching flights: {str(e)}")
        return []

def get_flight_price_estimate(departure_city, arrival_city, class_type="economy"):
    """Get estimated flight price using OpenAI API"""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""Based on current market trends, estimate the price range for a flight from {departure_city} to {arrival_city} in {class_type} class.
    Provide the estimate in USD with a reasonable range. Consider factors like:
    - Average prices for this route
    - Seasonal variations
    - Class of travel
    
    Format your response as a JSON object with:
    - min_price
    - max_price
    - currency
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "You are a flight pricing expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        price_data = json.loads(response.choices[0].message.content)
        return price_data
    except Exception as e:
        st.error(f"Error estimating price: {str(e)}")
        return None

def format_flight_duration(departure_time, arrival_time):
    """Calculate and format flight duration"""
    try:
        dep_time = datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
        arr_time = datetime.fromisoformat(arrival_time.replace('Z', '+00:00'))
        duration = arr_time - dep_time
        hours = duration.total_seconds() // 3600
        minutes = (duration.total_seconds() % 3600) // 60
        return f"{int(hours)}h {int(minutes)}m"
    except:
        return "Duration unavailable"

def main():
    st.title("✈️ Flight Information Tracker")
    st.markdown("""
    <style>
    .flight-header {
        color: #1E88E5;
        font-size: 20px;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Input form
    with st.form("flight_search_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            departure_city = st.text_input("Departure City", 
                placeholder="Enter city name")
            departure_date = st.date_input("Departure Date", 
                min_value=datetime.today())
            
        with col2:
            arrival_city = st.text_input("Arrival City", 
                placeholder="Enter city name")
            budget_range = st.slider("Budget Range (USD)", 
                0, 5000, (200, 2000))
        
        search_button = st.form_submit_button("Search Flights")
        
        if search_button:
            if not (departure_city and arrival_city):
                st.error("Please enter both departure and arrival cities.")
                return
            
            st.session_state.flight_search_done = True
            
            # Get airports for both cities
            departure_airports = get_city_airports(departure_city)
            arrival_airports = get_city_airports(arrival_city)
            
            if not departure_airports or not arrival_airports:
                st.error("Could not find airports for one or both cities.")
                return
            
            # Search flights
            flights = []
            for dep_airport in departure_airports:
                for arr_airport in arrival_airports:
                    results = search_flights(
                        dep_airport["iata"],
                        arr_airport["iata"],
                        departure_date.strftime("%Y-%m-%d")
                    )
                    flights.extend(results)
            
            if not flights:
                st.warning("No flights found for the specified route and date.")
                return
            
            # Get price estimate
            price_estimate = get_flight_price_estimate(departure_city, arrival_city)
            
            # Display results
            st.subheader("📊 Flight Information")
            
            # Price estimate card
            if price_estimate:
                with st.expander("💰 Estimated Price Range", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Minimum Price", f"${price_estimate['min_price']}")
                    col2.metric("Maximum Price", f"${price_estimate['max_price']}")
                    col3.metric("Currency", price_estimate['currency'])
            
            # Flights table
            flight_data = []
            for flight in flights:
                flight_data.append({
                    "Flight Number": flight.get("flight", {}).get("number", "N/A"),
                    "Airline": flight.get("airline", {}).get("name", "N/A"),
                    "Departure": flight.get("departure", {}).get("scheduled", "N/A"),
                    "Arrival": flight.get("arrival", {}).get("scheduled", "N/A"),
                    "Duration": format_flight_duration(
                        flight.get("departure", {}).get("scheduled", ""),
                        flight.get("arrival", {}).get("scheduled", "")
                    ),
                    "Status": flight.get("flight_status", "N/A").title()
                })
            
            if flight_data:
                st.dataframe(
                    pd.DataFrame(flight_data),
                    use_container_width=True,
                    hide_index=True
                )
            
            # Save search to history
            st.session_state.conversation_history.append({
                "departure": departure_city,
                "arrival": arrival_city,
                "date": departure_date.strftime("%Y-%m-%d"),
                "budget": budget_range
            })
    
    # Show search history
    if st.session_state.conversation_history:
        with st.expander("🕒 Search History"):
            for idx, search in enumerate(st.session_state.conversation_history):
                st.write(f"Search {idx + 1}: {search['departure']} to {search['arrival']} on {search['date']}")

if __name__ == "__main__":
    main()
