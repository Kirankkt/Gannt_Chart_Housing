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
activity_filter = st.sidebar.multiselect("Select Activities:", df['Activity'].unique(), default=df['Activity'].unique())
room_filter = st.sidebar.multiselect("Select Room:", df['Room'].unique(), default=df['Room'].unique())

# Apply filters
df_filtered = df[(df['Activity'].isin(activity_filter)) & (df['Room'].isin(room_filter))]

# Gantt Chart
df_filtered = df_filtered.sort_values(by='Start Date')
st.subheader("📅 Gantt Chart - Construction Timeline")
fig = px.timeline(df_filtered, x_start='Start Date', x_end='End Date', y='Task', color='Activity', title="Construction Schedule",
                  labels={'Task': 'Construction Task'}, hover_data=['Room', 'Location', 'Workdays'])
st.plotly_chart(fig)

# Task Progress Summary
st.subheader("📊 Task Progress Summary")
if 'Status' in df_filtered.columns:
    status_counts = df_filtered['Status'].value_counts().reset_index()
    status_counts.columns = ['Status', 'Count']
    st.dataframe(status_counts)
else:
    st.write("No status data available.")

# Workdays Summary
st.subheader("⏳ Workdays Analysis")
if 'Workdays' in df_filtered.columns:
    st.write(f"Total Workdays: {df_filtered['Workdays'].sum()} days")
    st.write(f"Average Workdays per Task: {df_filtered['Workdays'].mean():.2f} days")
else:
    st.write("No workdays data available.")

# Download CSV Option
st.sidebar.subheader("📥 Download Data")
st.sidebar.download_button("Download CSV", df_filtered.to_csv(index=False), file_name="Construction_Timeline.csv", mime="text/csv")

# Run: streamlit run <filename.py>
