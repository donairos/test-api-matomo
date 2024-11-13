import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# Matomo API configuration
MATOMO_URL = "https://wa.chop.edu/index.php"  # Replace with your Matomo URL
TOKEN_AUTH = "a80e73fafbfdf79815af9b75ff54f4c2"    # Replace with your API token
SITE_ID = "21"                   # Replace with your site ID

# Function to connect to Matomo API
def connect_to_matomo():
    """Test connection to Matomo API"""
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
        st.error(f"Error connecting to Matomo API: {e}")
        return False

# Function to extract data from Matomo
def fetch_data(period, date, end_date=None):
    """Fetch Matomo data for a specific period and date range"""
    if period == "range" and end_date:
        date_param = f"{date},{end_date}"
    else:
        date_param = date

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
    return data


# Add this new function after the existing API functions
def fetch_event_evolution(event_name, period, date, end_date=None):
    """Fetch evolution data for a specific event"""
    if period == "range" and end_date:
        date_param = f"{date},{end_date}"
    else:
        date_param = date

    params = {
        'module': 'API',
        'method': 'Events.getAction',
        'idSite': SITE_ID,
        'period': period,
        'date': date_param,
        'format': 'JSON',
        'token_auth': TOKEN_AUTH,
        'eventName': event_name,
        'flat': 0
    }

    response = requests.post(MATOMO_URL, data=params)
    response.raise_for_status()
    return response.json()

# Initialize the Streamlit app
st.title("Matomo Data Extractor")

# Date selection
st.sidebar.header("Select Parameters")
period = st.sidebar.selectbox("Select Period", options=["day", "week", "month", "year", "range"])
date = st.sidebar.date_input("Start Date", value=datetime.now().date())
end_date = None

if period == "range":
    end_date = st.sidebar.date_input("End Date")

# Check connection to Matomo
if connect_to_matomo():
    # Button to trigger data extraction
    if st.sidebar.button("Fetch Data"):
        try:
            data = fetch_data(period, date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d") if end_date else None)

            # Convert JSON data to DataFrame
            df = pd.json_normalize(data)
            if not df.empty:
                columns_to_keep = ['label', 'nb_events', 'nb_events_with_value', 'sum_event_value']
                existing_columns = [col for col in columns_to_keep if col in df.columns]
                df = df[existing_columns]

                column_mapping = {
                    'label': 'Event Name',
                    'nb_events': 'Event Count',
                    'nb_events_with_value': 'Events With Value',
                    'sum_event_value': 'Total Event Value'
                }
                df.rename(columns=column_mapping, inplace=True)

# Replace the DataFrame display section with this updated code
                # Display the DataFrame as a table with row evolution
                st.subheader("Event Data")
                
                # Add selection column to DataFrame
                df['View Evolution'] = False
                edited_df = st.data_editor(
                    df,
                    hide_index=True,
                    column_config={
                        "View Evolution": st.column_config.CheckboxColumn(
                            "View Evolution",
                            help="Click to view evolution",
                            default=False,
                        )
                    }
                )

                # Handle row evolution display
                selected_events = edited_df[edited_df['View Evolution']]['Event Name'].tolist()
                
                if selected_events:
                    for event_name in selected_events:
                        with st.expander(f"Evolution for: {event_name}", expanded=True):
                            try:
                                evolution_data = fetch_event_evolution(
                                    event_name,
                                    period,
                                    date.strftime("%Y-%m-%d"),
                                    end_date.strftime("%Y-%m-%d") if end_date else None
                                )
                                
                                # Create evolution graph
                                fig = go.Figure()
                                dates = list(evolution_data.keys())
                                values = [d.get('nb_events', 0) for d in evolution_data.values()]
                                
                                fig.add_trace(go.Scatter(
                                    x=pd.to_datetime(dates),
                                    y=values,
                                    mode='lines+markers',
                                    name=event_name
                                ))
                                
                                fig.update_layout(
                                    title=f"Evolution for {event_name}",
                                    xaxis_title="Date",
                                    yaxis_title="Number of Events",
                                    height=300,
                                    showlegend=False
                                )
                                
                                st.plotly_chart(fig, use_container_width=True)
                                
                            except Exception as e:
                                st.error(f"Error fetching evolution data for {event_name}: {str(e)}")

                # Keep the original trend graph
                st.subheader("Overall Event Count Trend")
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=df['Event Name'],
                        y=df['Event Count'],
                        mode="lines+markers",
                        name="Event Count"
                    )
                )
                fig.update_layout(
                    title="Event Count Trend",
                    xaxis_title="Event Name",
                    yaxis_title="Event Count",
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)

        except requests.exceptions.RequestException as e:
            st.error(f"Failed to fetch data: {str(e)}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
