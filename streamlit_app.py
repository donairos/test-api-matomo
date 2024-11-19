import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

# Matomo API configuration
MATOMO_URL = "https://wa.chop.edu/index.php"
TOKEN_AUTH = "a80e73fafbfdf79815af9b75ff54f4c2"
SITE_ID = "21"

def connect_to_matomo():
    try:
        params = {
            'module': 'API',
            'method': 'SitesManager.getSiteFromId',
            'idSite': SITE_ID,
            'format': 'JSON',
            'token_auth': TOKEN_AUTH
        }
        response = requests.post(MATOMO_URL, data=params)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to Matomo API: {str(e)}")
        return False

def fetch_event_names(period, start_date, end_date=None):
    if period == "range" and end_date:
        date_param = f"{start_date},{end_date}"
    else:
        date_param = start_date

    params = {
        'module': 'API',
        'method': 'Events.getName',
        'idSite': SITE_ID,
        'period': period,
        'date': date_param,
        'format': 'JSON',
        'token_auth': TOKEN_AUTH,
        'flat': 1,
        'filter_limit': -1
    }

    response = requests.post(MATOMO_URL, data=params)
    response.raise_for_status()
    data = response.json()
    return pd.json_normalize(data)

# Initialize the Streamlit app
st.title("Matomo Data Extractor")

# Date selection
st.sidebar.header("Select Parameters")

old_start_date = st.sidebar.date_input("Old Site Start Date", value=datetime(2021, 1, 1))
old_end_date = st.sidebar.date_input("Old Site End Date", value=datetime(2022, 12, 31))

new_start_date = st.sidebar.date_input("New Site Start Date", value=datetime(2023, 1, 1))
new_end_date = st.sidebar.date_input("New Site End Date", value=datetime.now().date())

if connect_to_matomo():
    if st.sidebar.button("Fetch Data"):
        try:
            old_event_data = fetch_event_names("range", old_start_date.strftime("%Y-%m-%d"), old_end_date.strftime("%Y-%m-%d"))
            new_event_data = fetch_event_names("range", new_start_date.strftime("%Y-%m-%d"), new_end_date.strftime("%Y-%m-%d"))

            # Combine old and new event data
            combined_data = pd.concat([old_event_data, new_event_data], ignore_index=True)

            # Create event name comparison plot
            fig = go.Figure()
            fig.add_trace(go.Bar(x=combined_data[combined_data['label'].isin(old_event_data['label'])]['label'], y=combined_data[combined_data['label'].isin(old_event_data['label'])]['nb_events'], name='Old Site'))
            fig.add_trace(go.Bar(x=combined_data[combined_data['label'].isin(new_event_data['label'])]['label'], y=combined_data[combined_data['label'].isin(new_event_data['label'])]['nb_events'], name='New Site'))
            fig.update_layout(
                title="Event Name Comparison",
                xaxis_title="Event Name",
                yaxis_title="Event Count",
                barmode='group'
            )
            st.plotly_chart(fig, use_container_width=True)

            # Display event data
            st.subheader("Old Site Event Data")
            st.dataframe(old_event_data)

            st.subheader("New Site Event Data")
            st.dataframe(new_event_data)

        except requests.exceptions.RequestException as e:
            st.error(f"Failed to fetch data: {str(e)}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")