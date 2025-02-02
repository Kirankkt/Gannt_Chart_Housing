import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# Load the dataset
file_path = "construction_timeline.xlsx"
df = pd.read_excel(file_path)

df.columns = df.columns.str.strip()
df['Start Date'] = pd.to_datetime(df['Start Date'], errors='coerce')
df['End Date'] = pd.to_datetime(df['End Date'], errors='coerce')
df['Workdays'] = pd.to_numeric(df['Workdays'], errors='coerce')

# Title
st.title("🏗️ Construction Project Tracker")

# Sidebar filters
st.sidebar.header("Filter Options")
activity_filter = st.sidebar.multiselect("Select Activities:", ['All'] + list(df['Activity'].unique()), default=['All'])
room_filter = st.sidebar.multiselect("Select Rooms:", ['All'] + list(df['Room'].unique()), default=['All'])

# Apply filters
if 'All' not in activity_filter:
    df = df[df['Activity'].isin(activity_filter)]
if 'All' not in room_filter:
    df = df[df['Room'].isin(room_filter)]

# Gantt Chart
st.subheader("📅 Gantt Chart - Construction Timeline")
if not df.empty:
    df = df.sort_values(by='Start Date')
    fig = px.timeline(df, x_start='Start Date', x_end='End Date', y='Task', color='Activity', title="Construction Schedule",
                      labels={'Task': 'Construction Task'}, hover_data=['Room', 'Location', 'Workdays', 'Status'])
    fig.update_yaxes(categoryorder='total ascending')  # Improves readability
    fig.update_layout(xaxis_title="Timeline", yaxis_title="Tasks", hovermode="x unified")
    st.plotly_chart(fig)
else:
    st.warning("No data available for the selected filters.")

# Task Progress Summary
st.subheader("📊 Task Progress Summary")
if 'Status' in df.columns and not df.empty:
    status_counts = df['Status'].value_counts().reset_index()
    status_counts.columns = ['Status', 'Count']
    st.dataframe(status_counts)
else:
    st.write("No status data available.")

# Workdays Summary
st.subheader("⏳ Workdays Analysis")
if 'Workdays' in df.columns and not df.empty:
    st.write(f"Total Workdays: {df['Workdays'].sum()} days")
    st.write(f"Average Workdays per Task: {df['Workdays'].mean():.2f} days")
else:
    st.write("No workdays data available.")

# Download CSV Option
st.sidebar.subheader("📥 Download Data")
st.sidebar.download_button("Download CSV", df.to_csv(index=False), file_name="Construction_Timeline.csv", mime="text/csv")

# Run: streamlit run <filename.py>
