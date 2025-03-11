import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment variable
API_KEY = os.getenv("AVIATION_STACK_API_KEY")
BASE_URL = "http://api.aviationstack.com/v1/flights"

# Define path for the request counter file
REQUEST_COUNTER_FILE = "api_request_counter.json"

def load_request_counter():
    """
    Load the API request counter from file
    """
    if os.path.exists(REQUEST_COUNTER_FILE):
        try:
            with open(REQUEST_COUNTER_FILE, "r") as file:
                counter_data = json.load(file)
                
                # Check if we need to reset the counter (new day)
                today = datetime.now().strftime("%Y-%m-%d")
                if counter_data.get("date") != today:
                    counter_data = {"date": today, "count": 0}
                    
                return counter_data
        except Exception as e:
            st.error(f"Error loading request counter: {str(e)}")
    
    # Initialize with today's date if file doesn't exist
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
    # Assuming 100 requests per day limit
    remaining = 100 - counter_data["count"]
    return max(0, remaining)

def get_flights(departure_date, departure_city, arrival_city):
    """
    Fetch flight details from Aviation Stack API
    """
    # Check remaining requests
    remaining_requests = get_remaining_requests()
    if remaining_requests <= 0:
        st.error("API request limit reached for today. Please try again tomorrow.")
        return []
    
    # Format date to YYYY-MM-DD for API
    formatted_date = departure_date.strftime("%Y-%m-%d")
    
    params = {
        'access_key': API_KEY,
        'flight_date': formatted_date,
        'dep_iata': departure_city,
        'arr_iata': arrival_city
    }
    
    try:
        # Make API request
        response = requests.get(BASE_URL, params=params)
        
        # Increment the counter for this request
        increment_request_counter(1)
        
        if response.status_code == 200:
            data = response.json()
            # Check if the API returned an error about limits
            if 'error' in data:
                st.error(f"API Error: {data['error']['info']}")
                # If it's specifically a usage limit error, update our counter
                if 'usage limit' in data['error']['info'].lower():
                    counter_data = load_request_counter()
                    counter_data["count"] = 100  # Set to limit
                    save_request_counter(counter_data)
                return []
            
            return data['data'] if 'data' in data else []
        else:
            st.error(f"Error fetching data: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return []

def format_flight_data(flights):
    """
    Format flight data for display
    """
    if not flights:
        return pd.DataFrame()
    
    formatted_data = []
    for flight in flights:
        try:
            flight_data = {
                "Airline": flight['airline']['name'] if 'airline' in flight and 'name' in flight['airline'] else "Unknown",
                "Flight Number": flight['flight']['number'] if 'flight' in flight and 'number' in flight['flight'] else "Unknown",
                "Departure": flight['departure']['airport'] if 'departure' in flight and 'airport' in flight['departure'] else "Unknown",
                "Departure Time": flight['departure']['scheduled'] if 'departure' in flight and 'scheduled' in flight['departure'] else "Unknown",
                "Arrival": flight['arrival']['airport'] if 'arrival' in flight and 'airport' in flight['arrival'] else "Unknown",
                "Arrival Time": flight['arrival']['scheduled'] if 'arrival' in flight and 'scheduled' in flight['arrival'] else "Unknown",
                "Status": flight['flight_status'] if 'flight_status' in flight else "Unknown"
            }
            formatted_data.append(flight_data)
        except Exception as e:
            st.warning(f"Error processing flight data: {str(e)}")
    
    return pd.DataFrame(formatted_data)

def main():
    st.title("Flight Search Chatbot 🛫")
    
    # Check if API key is available
    if not API_KEY:
        st.error("AviationStack API key not found. Please set the AVIATION_STACK_API_KEY environment variable.")
        st.info("You can get an API key from https://aviationstack.com/")
        return
    
    # Display remaining API requests
    remaining_requests = get_remaining_requests()
    request_status = st.empty()  # Create placeholder for dynamic updating
    request_status.info(f"Remaining API requests today: {remaining_requests}/100")
    
    # Sidebar for inputs
    st.sidebar.header("Search Flights")
    
    # Date selector
    st.sidebar.subheader("Select Travel Date")
    min_date = datetime.now().date()
    max_date = min_date + timedelta(days=365)
    departure_date = st.sidebar.date_input("Departure Date", min_value=min_date, max_value=max_date, value=min_date)
    
    # Airport inputs (using IATA codes)
    st.sidebar.subheader("Enter Airport IATA Codes")
    departure_city = st.sidebar.text_input("Departure City (IATA code, e.g., LAX)", "LAX")
    arrival_city = st.sidebar.text_input("Arrival City (IATA code, e.g., JFK)", "JFK")
    
    # Help info about IATA codes
    with st.sidebar.expander("Not sure about IATA codes?"):
        st.write("IATA codes are 3-letter airport codes. Examples:")
        st.write("- LAX: Los Angeles")
        st.write("- JFK: New York")
        st.write("- SFO: San Francisco")
        st.write("- LHR: London Heathrow")
        st.write("- CDG: Paris Charles de Gaulle")
        st.write("You can find more codes by searching online for 'IATA airport codes'.")
    
    # Search button (disabled if no requests remaining)
    search_button = st.sidebar.button("Search Flights", disabled=(remaining_requests <= 0))
    
    # Display results
    if search_button:
        with st.spinner("Searching for flights..."):
            st.subheader(f"Flights from {departure_city} to {arrival_city} on {departure_date}")
            
            flights = get_flights(departure_date, departure_city, arrival_city)
            
            # Update request counter display after API call
            request_status.info(f"Remaining API requests today: {get_remaining_requests()}/100")
            
            if not flights:
                st.info("No flights found for your search criteria. Try changing your search parameters.")
            else:
                flight_df = format_flight_data(flights)
                if not flight_df.empty:
                    st.dataframe(flight_df)
                    
                    # Download option
                    csv = flight_df.to_csv(index=False)
                    st.download_button(
                        label="Download flight data as CSV",
                        data=csv,
                        file_name=f"flights_{departure_city}_to_{arrival_city}_{departure_date}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No valid flight data found for your search criteria.")
    
    # Show welcome message on initial load
    if not search_button:
        st.write("👋 Welcome to the Flight Search Chatbot!")
        st.write("Please use the sidebar to search for flights.")
        st.write("1. Select your travel date")
        st.write("2. Enter departure and arrival airport codes")
        st.write("3. Click 'Search Flights' to see available options")
        
        # Show API limit info
        st.info("This application uses the AviationStack API which has a limit of 100 requests per day. Each search uses 1 request.")

    # Admin section for managing API usage (expandable)
    with st.expander("Admin: API Usage Information"):
        counter_data = load_request_counter()
        st.write(f"Date: {counter_data['date']}")
        st.write(f"Requests used today: {counter_data['count']}/100")
        
        if st.button("Reset Counter"):
            today = datetime.now().strftime("%Y-%m-%d")
            save_request_counter({"date": today, "count": 0})
            st.success("Counter reset successfully!")
            # Force reload to update displayed values
            st.experimental_rerun()

if __name__ == "__main__":
    main()
