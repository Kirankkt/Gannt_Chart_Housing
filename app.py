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
activity_filter = st.sidebar.selectbox("Select Activity:", options=['All'] + list(df['Activity'].unique()), index=0)
room_filter = st.sidebar.selectbox("Select Room:", options=['All'] + list(df['Room'].unique()), index=0)

# Apply filters
if activity_filter != 'All':
    df = df[df['Activity'] == activity_filter]
if room_filter != 'All':
    df = df[df['Room'] == room_filter]

# Gantt Chart
st.subheader("📅 Gantt Chart - Construction Timeline")
df = df.sort_values(by='Start Date')
fig = px.timeline(df, x_start='Start Date', x_end='End Date', y='Task', color='Activity', title="Construction Schedule",
                  labels={'Task': 'Construction Task'}, hover_data=['Room', 'Location', 'Workdays', 'Status'])
fig.update_yaxes(categoryorder='total ascending')  # Improves readability
fig.update_layout(xaxis_title="Timeline", yaxis_title="Tasks", hovermode="x unified")
st.plotly_chart(fig)

# Task Progress Summary
st.subheader("📊 Task Progress Summary")
if 'Status' in df.columns:
    status_counts = df['Status'].value_counts().reset_index()
    status_counts.columns = ['Status', 'Count']
    st.dataframe(status_counts)
else:
    st.write("No status data available.")

# Workdays Summary
st.subheader("⏳ Workdays Analysis")
if 'Workdays' in df.columns:
    st.write(f"Total Workdays: {df['Workdays'].sum()} days")
    st.write(f"Average Workdays per Task: {df['Workdays'].mean():.2f} days")
else:
    st.write("No workdays data available.")

# Download CSV Option
st.sidebar.subheader("📥 Download Data")
st.sidebar.download_button("Download CSV", df.to_csv(index=False), file_name="Construction_Timeline.csv", mime="text/csv")

# Run: streamlit run <filename.py>
