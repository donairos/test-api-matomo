import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import logging
import os
from dotenv import load_dotenv
from PIL import Image
import io
import base64
import json

# Load environment variables
load_dotenv()

# Matomo API configuration
MATOMO_URL = os.getenv("MATOMO_URL")
TOKEN_AUTH = os.getenv("TOKEN_AUTH")
SITE_ID = os.getenv("SITE_ID")

logging.basicConfig(filename='matomo_extractor.log', level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_event_data(start_date, end_date):
    """Fetch event data from Matomo API"""
    events_data = []
    try:
        # Get event details
        name_params = {
            'module': 'API',
            'method': 'Events.getName',
            'idSite': SITE_ID,
            'period': 'range',
            'date': f"{start_date},{end_date}",
            'format': 'JSON',
            'token_auth': TOKEN_AUTH,
            'filter_limit': -1,
            'flat': 1
        }

        name_response = requests.post(MATOMO_URL, data=name_params)
        names_data = name_response.json()

        # Log response for debugging
        logging.info(f"Names Response: {name_response.text[:500]}")
        
        # Process the data
        for event in names_data:
            if isinstance(event, dict):
                event_data = {
                    'Event Name': event.get('label', ''),
                    'Event Count': event.get('nb_events', 0),
                    'Events With Value': event.get('nb_events_with_value', 0),
                    'Total Event Value': event.get('sum_event_value', 0)
                }
                events_data.append(event_data)
        
        df = pd.DataFrame(events_data)
        
        # Sort by Event Count in descending order
        if not df.empty:
            df = df.sort_values('Event Count', ascending=False)
            
            # Convert numeric columns to appropriate types
            numeric_columns = ['Event Count', 'Events With Value', 'Total Event Value']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
        return df
    
    except Exception as e:
        logging.error(f"Error in fetch_event_data: {str(e)}")
        st.error(f"Error fetching event data: {str(e)}")
        return pd.DataFrame()

def generate_comparison_summary(row):
    """Generate summary for category comparison using statistics"""
    period1_value = row['Event Count_period1']
    period2_value = row['Event Count_period2']
    percent_change = ((period2_value - period1_value) / period1_value * 100) if period1_value != 0 else float('inf')
    abs_change = period2_value - period1_value
    
    # Determine trend and magnitude
    if abs_change == 0:
        trend = "remained stable"
    else:
        trend = "increased" if abs_change > 0 else "decreased"
        
    # Determine magnitude description
    if abs(percent_change) < 10:
        magnitude = "slightly"
    elif abs(percent_change) < 30:
        magnitude = "moderately"
    elif abs(percent_change) < 50:
        magnitude = "significantly"
    else:
        magnitude = "dramatically"
    
    summary = (
        f"This category {trend} {magnitude} from {period1_value:,} to {period2_value:,} events "
        f"({percent_change:+.1f}% change)"
    )
    
    return summary

def compare_csv_data():
    """Function to handle CSV comparison in Streamlit"""
    st.subheader("Compare Event Data from CSV Files")
    
    # File uploaders for two CSV files
    st.write("Upload two CSV files to compare:")
    file1 = st.file_uploader("First Period CSV", type=['csv'], key='file1')
    file2 = st.file_uploader("Second Period CSV", type=['csv'], key='file2')
    
    if file1 and file2:
        try:
            # Read CSV files
            df1 = pd.read_csv(file1)
            df2 = pd.read_csv(file2)
            
            # Process each dataframe
            grouped1 = df1.groupby('Event Tag (IF)')['Event Count'].sum().reset_index()
            grouped2 = df2.groupby('Event Tag (IF)')['Event Count'].sum().reset_index()
            
            # Merge the datasets
            merged_df = pd.merge(
                grouped1, grouped2,
                on='Event Tag (IF)',
                how='outer',
                suffixes=('_period1', '_period2')
            ).fillna(0)
            
            # Calculate percent change
            merged_df['percent_change'] = ((merged_df['Event Count_period2'] - merged_df['Event Count_period1']) / 
                                         merged_df['Event Count_period1'] * 100).fillna(0)
            
            # Sort by absolute percent change
            merged_df = merged_df.sort_values('percent_change', key=abs, ascending=False)
            
            # Overall summary at the top
            st.subheader("Overall Summary")
            total_change = ((merged_df['Event Count_period2'].sum() - merged_df['Event Count_period1'].sum()) / 
                          merged_df['Event Count_period1'].sum() * 100)
            st.write(f"""
            - Total events changed by {total_change:+.1f}% between the two periods
            - {len(merged_df[merged_df['percent_change'] > 0])} categories increased
            - {len(merged_df[merged_df['percent_change'] < 0])} categories decreased
            - {len(merged_df[merged_df['percent_change'] == 0])} categories remained unchanged
            """)
            
            # Create main comparison visualization
            fig = go.Figure()
            
            # Add bars for period 1
            fig.add_trace(go.Bar(
                name=os.path.splitext(file1.name)[0],
                y=merged_df['Event Tag (IF)'],
                x=merged_df['Event Count_period1'],
                orientation='h',
                marker_color='rgba(54, 162, 235, 0.7)'
            ))
            
            # Add bars for period 2
            fig.add_trace(go.Bar(
                name=os.path.splitext(file2.name)[0],
                y=merged_df['Event Tag (IF)'],
                x=merged_df['Event Count_period2'],
                orientation='h',
                marker_color='rgba(255, 99, 132, 0.7)'
            ))
            
            # Update layout
            fig.update_layout(
                title="Event Tag Comparison",
                barmode='group',
                height=max(400, len(merged_df) * 30),
                margin=dict(l=200),
                yaxis={'categoryorder':'total ascending'},
                xaxis_title="Event Count",
                yaxis_title="Event Tag (IF)"
            )
            
            # Display the visualization
            st.plotly_chart(fig, use_container_width=True)
            
            # Display detailed analysis for each category
            st.subheader("Detailed Category Analysis")
            
            for _, row in merged_df.iterrows():
                with st.expander(f"{row['Event Tag (IF)']} (Change: {row['percent_change']:.1f}%)"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        # Create sparkline chart
                        sparkline = go.Figure()
                        sparkline.add_trace(go.Scatter(
                            x=['Period 1', 'Period 2'],
                            y=[row['Event Count_period1'], row['Event Count_period2']],
                            mode='lines+markers',
                            line=dict(color='blue'),
                            marker=dict(color=['blue', 'red'])
                        ))
                        sparkline.update_layout(
                            height=100,
                            margin=dict(l=0, r=0, t=0, b=0),
                            showlegend=False,
                            xaxis_showgrid=False,
                            yaxis_showgrid=False
                        )
                        st.plotly_chart(sparkline, use_container_width=True)
                    
                    with col2:
                        # Add metrics
                        st.metric(
                            "Change in Events",
                            f"{row['Event Count_period2'] - row['Event Count_period1']:,.0f}",
                            f"{row['percent_change']:.1f}%"
                        )
                    
                    # Generate and display summary
                    summary = generate_comparison_summary(row)
                    st.write("Analysis:", summary)
            
            # Display the data table
            st.subheader("Comparison Data")
            display_df = merged_df.copy()
            display_df['Percent Change'] = display_df['percent_change'].apply(lambda x: f"{x:.1f}%")
            display_df = display_df.drop('percent_change', axis=1)
            st.dataframe(display_df, use_container_width=True)
            
            # Add download button for the comparison data
            csv = merged_df.to_csv(index=False)
            st.download_button(
                "Download Comparison Data",
                csv,
                "event_comparison.csv",
                "text/csv",
                key='download-csv'
            )
            
        except Exception as e:
            st.error(f"Error processing CSV files: {str(e)}")
    else:
        st.info("Please upload both CSV files to see the comparison.")

def load_reports():
    """Load reports from JSON file"""
    try:
        with open('reports.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_reports(reports):
    """Save reports to JSON file"""
    with open('reports.json', 'w') as f:
        json.dump(reports, f)

def documentation_page():
    st.title("Analytics Documentation")
    
    # Initialize session state from file if it doesn't exist
    if 'reports' not in st.session_state:
        st.session_state.reports = load_reports()
    
    # Create a new report section
    st.subheader("Create New Report Section")
    
    # Date and Title
    col1, col2 = st.columns([1, 2])
    with col1:
        report_date = st.date_input("Report Date")
    with col2:
        report_title = st.text_input("Report Title")
    
    # Main report sections
    findings = st.text_area("Findings", height=150,
                           help="Document key findings from your analytics data")
    
    observations = st.text_area("Observations", height=150,
                              help="Note any patterns, trends, or interesting data points")
    
    recommendations = st.text_area("Recommendations", height=150,
                                 help="Suggest actionable improvements based on the data")
    
    conclusion = st.text_area("Conclusion", height=100,
                            help="Summarize key takeaways and next steps")
    
    # Screenshot upload section
    st.subheader("Upload Screenshots")
    uploaded_files = st.file_uploader("Upload screenshots or relevant images", 
                                    type=['png', 'jpg', 'jpeg'], 
                                    accept_multiple_files=True,
                                    key='doc_uploads')
    
    screenshots = []
    if uploaded_files:
        for uploaded_file in uploaded_files:
            # Convert uploaded image to base64 for storage
            image_bytes = uploaded_file.read()
            encoded_image = base64.b64encode(image_bytes).decode()
            screenshots.append({
                'name': uploaded_file.name,
                'data': encoded_image
            })
    
    # Save report button
    if st.button("Save Report Section"):
        if report_title:  # Ensure at least a title is provided
            new_report = {
                'date': report_date.strftime("%Y-%m-%d"),
                'title': report_title,
                'findings': findings,
                'observations': observations,
                'recommendations': recommendations,
                'conclusion': conclusion,
                'screenshots': screenshots
            }
            st.session_state.reports.append(new_report)
            save_reports(st.session_state.reports)  # Save to file
            st.success("Report section saved successfully!")
        else:
            st.error("Please provide at least a report title")
    
    # Display existing reports
    if st.session_state.reports:
        st.subheader("Existing Reports")
        for idx, report in enumerate(st.session_state.reports):
            with st.expander(f"{report['date']} - {report['title']}"):
                # Display report content
                st.write("### Findings")
                st.write(report['findings'])
                
                st.write("### Observations")
                st.write(report['observations'])
                
                st.write("### Recommendations")
                st.write(report['recommendations'])
                
                st.write("### Conclusion")
                st.write(report['conclusion'])
                
                # Display screenshots
                if report['screenshots']:
                    st.write("### Screenshots")
                    cols = st.columns(3)
                    for i, screenshot in enumerate(report['screenshots']):
                        with cols[i % 3]:
                            # Convert base64 back to image
                            image_data = base64.b64decode(screenshot['data'])
                            image = Image.open(io.BytesIO(image_data))
                            st.image(image, caption=screenshot['name'])
                
                # Delete report button
                if st.button(f"Delete Report", key=f"delete_{idx}"):
                    st.session_state.reports.pop(idx)
                    save_reports(st.session_state.reports)  # Save to file after deletion
                    st.rerun()
    
    # Export functionality
    if st.session_state.reports:
        st.subheader("Export Documentation")
        if st.button("Export as Markdown"):
            markdown_content = generate_markdown_report(st.session_state.reports)
            st.download_button(
                label="Download Markdown Report",
                data=markdown_content,
                file_name="analytics_documentation.md",
                mime="text/markdown"
            )       

def main():
    st.set_page_config(page_title="Matomo Data Extractor", layout="wide")
    st.title("Matomo Analytics")
    
    # Simplified sidebar with just two options
    page = st.sidebar.radio("Select Option", ["Extract & Export Events Data", "Compare Events Data", "Documentation"])
    
    if os.path.exists('matomo_extractor.log'):
        with open('matomo_extractor.log', 'r') as log_file:
            if st.sidebar.checkbox("Show Logs"):
                st.sidebar.text_area("Application Logs", log_file.read(), height=300)

    if page == "Documentation":
        documentation_page()
    elif page == "Extract & Export Events Data":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=datetime(2023, 1, 1))
        with col2:
            end_date = st.date_input("End Date", value=datetime.now().date())
            
        if st.button("Extract Events Data"):
            with st.spinner('Fetching events data...'):
                df = fetch_event_data(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
                if not df.empty:
                    # Display summary statistics
                    st.subheader("Events Summary")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Event Count", f"{df['Event Count'].sum():,}")
                    with col2:
                        st.metric("Total Events With Value", f"{df['Events With Value'].sum():,}")
                    with col3:
                        st.metric("Total Event Value", f"{df['Total Event Value'].sum():,}")
                    
                    # Add visualization for top 10 events
                    st.subheader("Top 10 Events")
                    top_10_events = df.head(10).iloc[::-1]  # Reverse the order for display
                    fig = go.Figure(data=[
                        go.Bar(
                            y=top_10_events['Event Name'],
                            x=top_10_events['Event Count'],
                            orientation='h',
                            text=top_10_events['Event Count'].apply(lambda x: f"{x:,}"),
                            textposition='auto',
                        )
                    ])
                    fig.update_layout(
                        yaxis_title="Event Name",
                        xaxis_title="Event Count",
                        height=400,
                        margin=dict(l=200),
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Display the full dataset
                    st.subheader("All Events")
                    st.dataframe(df, use_container_width=True)
                    
                    # Download button
                    st.download_button(
                        "Download CSV",
                        df.to_csv(index=False),
                        "events_data.csv",
                        "text/csv"
                    )
                else:
                    st.error("No events found")
    
    else:  # CSV Comparison
        compare_csv_data()

if __name__ == "__main__":
    main()