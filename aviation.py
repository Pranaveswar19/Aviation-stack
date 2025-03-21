import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import os
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AVIATION_STACK_API_KEY")
BASE_URL = "http://api.aviationstack.com/v1/flights"

REQUEST_COUNTER_FILE = "api_request_counter.json"

def load_request_counter():
    """
    Load the API request counter from file
    """
    if os.path.exists(REQUEST_COUNTER_FILE):
        try:
            with open(REQUEST_COUNTER_FILE, "r") as file:
                counter_data = json.load(file)
                
                today = datetime.now().strftime("%Y-%m-%d")
                if counter_data.get("date") != today:
                    counter_data = {"date": today, "count": 0}
                    
                return counter_data
        except Exception as e:
            st.error(f"Error loading request counter: {str(e)}")
    
    today = datetime.now().strftime("%Y-%m-%d")
    return {"date": today, "count": 0}

def save_request_counter(counter_data):
    """
    Save the API request counter to file
    """
    try:
        with open(REQUEST_COUNTER_FILE, "w") as file:
            json.dump(counter_data, file)
    except Exception as e:
        st.error(f"Error saving request counter: {str(e)}")

def increment_request_counter(increment=1):
    """
    Increment the API request counter
    """
    counter_data = load_request_counter()
    counter_data["count"] += increment
    save_request_counter(counter_data)
    return counter_data

def get_remaining_requests():
    """
    Get the number of remaining API requests for the day
    """
    counter_data = load_request_counter()
    remaining = 3 - counter_data["count"]
    return max(0, remaining)

def test_api_connection():
    """
    Test the API connection and key validity
    """
    if not API_KEY:
        return False, "API key is missing. Please check your .env file."
    
    params = {
        'access_key': API_KEY,
        'limit': 1  
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            return True, "Connection successful"
        elif response.status_code == 401:
            return False, "Authentication failed: Invalid API key"
        elif response.status_code == 403:
            return False, "Access forbidden: Free tier limitations may apply"
        else:
            try:
                error_data = response.json()
                if 'error' in error_data:
                    return False, f"API Error: {error_data['error']['info']}"
            except:
                pass
            return False, f"API returned status code: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, "Request timed out. API service may be slow or unavailable."
    except requests.exceptions.ConnectionError:
        return False, "Connection error. Please check your internet connection."
    except Exception as e:
        return False, f"Error testing API connection: {str(e)}"

def get_flights(departure_city=None, arrival_city=None):
    """
    Fetch flight details from Aviation Stack API
    Adapted for free tier limitations
    """
    remaining_requests = get_remaining_requests()
    if remaining_requests <= 0:
        st.error("API request limit reached for today. Please try again tomorrow.")
        return []
    
    params = {
        'access_key': API_KEY,
        'limit': 100  
    }
    
    if departure_city:
        params['dep_iata'] = departure_city
    
    if arrival_city:
        params['arr_iata'] = arrival_city
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=15)
        
        increment_request_counter(1)
        
        if response.status_code == 200:
            data = response.json()
            if 'error' in data:
                error_message = data['error']['info'] if 'info' in data['error'] else "Unknown API error"
                st.error(f"API Error: {error_message}")
                return []
            
            return data['data'] if 'data' in data else []
        elif response.status_code == 401:
            st.error("Authentication failed: Invalid API key. Please check your API key in the .env file.")
            return []
        elif response.status_code == 403:
            st.error("Access forbidden: The free tier has limitations on what data you can access.")
            st.info("The free tier only allows basic flight data without date filtering and has restricted parameters.")
            return []
        else:
            st.error(f"Error fetching data: {response.status_code}")
            return []
    except requests.exceptions.Timeout:
        st.error("Request timed out. The API service may be slow or unavailable.")
        return []
    except requests.exceptions.ConnectionError:
        st.error("Connection error. Please check your internet connection.")
        return []
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return []

def format_flight_data(flights):
    """
    Format flight data for display
    Adapted for free tier which might have limited fields
    """
    if not flights:
        return pd.DataFrame()
    
    formatted_data = []
    for flight in flights:
        try:
            flight_data = {}
            
            if 'flight' in flight:
                flight_data["Flight Number"] = flight['flight'].get('number', 'Unknown')
                flight_data["Flight IATA"] = flight['flight'].get('iata', 'Unknown')
            
            if 'airline' in flight:
                flight_data["Airline"] = flight['airline'].get('name', 'Unknown')
                flight_data["Airline IATA"] = flight['airline'].get('iata', 'Unknown')
            
            if 'departure' in flight:
                flight_data["Departure Airport"] = flight['departure'].get('airport', 'Unknown')
                flight_data["Departure IATA"] = flight['departure'].get('iata', 'Unknown')
                if 'scheduled' in flight['departure']:
                    flight_data["Scheduled Departure"] = flight['departure']['scheduled']
            
            if 'arrival' in flight:
                flight_data["Arrival Airport"] = flight['arrival'].get('airport', 'Unknown')
                flight_data["Arrival IATA"] = flight['arrival'].get('iata', 'Unknown')
                if 'scheduled' in flight['arrival']:
                    flight_data["Scheduled Arrival"] = flight['arrival']['scheduled']
            
            flight_data["Status"] = flight.get('flight_status', 'Unknown')
            
            formatted_data.append(flight_data)
        except Exception as e:
            st.warning(f"Error processing flight data: {str(e)}")
    
    return pd.DataFrame(formatted_data)

def main():
    st.title("Flight Search Chatbot 🛫")
    st.caption("Using Aviation Stack API (Free Tier)")
    
    if not API_KEY:
        st.error("AviationStack API key not found. Please set the AVIATION_STACK_API_KEY environment variable.")
        st.info("You can get an API key from https://aviationstack.com/")
        
        with st.expander("How to set up your API key"):
            st.code("""
# Create a file named .env in the same directory as your app.py
# Add this line to the file:
AVIATION_STACK_API_KEY=your_api_key_here
            """)
        return
        
    remaining_requests = get_remaining_requests()
    request_status = st.empty()  
    request_status.info(f"Remaining API requests today: {remaining_requests}/3 (Free Tier)")
    
    st.warning("""
    ⚠️ Free Tier Limitations:
    - Limited to 100 requests per month (~3 per day)
    - No date filtering capability
    - Only real-time flight data
    - Limited response fields
    - HTTP only (not HTTPS)
    """)
    
    st.sidebar.header("Search Flights")
    
    st.sidebar.subheader("Enter Airport IATA Codes")
    departure_city = st.sidebar.text_input("Departure City (IATA code, e.g., LAX)", "LAX")
    arrival_city = st.sidebar.text_input("Arrival City (IATA code, e.g., JFK)", "JFK")
    
    with st.sidebar.expander("Not sure about IATA codes?"):
        st.write("IATA codes are 3-letter airport codes. Examples:")
        st.write("- LAX: Los Angeles")
        st.write("- JFK: New York")
        st.write("- SFO: San Francisco")
        st.write("- LHR: London Heathrow")
        st.write("- CDG: Paris Charles de Gaulle")
        st.write("You can find more codes by searching online for 'IATA airport codes'.")
    
    search_button = st.sidebar.button("Search Real-time Flights", disabled=(remaining_requests <= 0))
    
    if search_button:
        with st.spinner("Searching for flights..."):
            st.subheader(f"Real-time Flights from {departure_city} to {arrival_city}")
            st.caption("Note: Free tier only provides current flight data, not future flights")
            
            flights = get_flights(departure_city, arrival_city)
            
            request_status.info(f"Remaining API requests today: {get_remaining_requests()}/3 (Free Tier)")
            
            if not flights:
                st.info("No flights found for your search criteria or API limitations encountered.")
                st.info("The free tier only provides current flights in real-time.")
            else:
                flight_df = format_flight_data(flights)
                if not flight_df.empty:
                    st.dataframe(flight_df)
                    
                    st.success(f"Found {len(flight_df)} flights matching your criteria.")
                    
                    csv = flight_df.to_csv(index=False)
                    st.download_button(
                        label="Download flight data as CSV",
                        data=csv,
                        file_name=f"flights_{departure_city}_to_{arrival_city}_realtime.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No valid flight data found for your search criteria.")
    
    if not search_button:
        st.write("👋 Welcome to the Flight Search Chatbot!")
        st.write("This application uses the Aviation Stack API **free tier** which has certain limitations.")
        st.write("1. Enter departure and arrival airport codes")
        st.write("2. Click 'Search Real-time Flights' to see current flights")
        st.write("3. Please note that the free tier only provides real-time flight data and not future flights")
        
        with st.expander("Test API Connection"):
            if st.button("Test Connection"):
                success, message = test_api_connection()
                if success:
                    st.success(message)
                else:
                    st.error(message)

    with st.expander("Admin: API Usage Information"):
        counter_data = load_request_counter()
        st.write(f"Date: {counter_data['date']}")
        st.write(f"Requests used today: {counter_data['count']}/3")
        st.write(f"Monthly estimate: {counter_data['count'] * 30}/100 (Free tier limit)")
        
        if st.button("Reset Counter"):
            today = datetime.now().strftime("%Y-%m-%d")
            save_request_counter({"date": today, "count": 0})
            st.success("Counter reset successfully!")
            st.experimental_rerun()

if __name__ == "__main__":
    main()
