import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os

# -----------------------------------------------
# App Configuration
# -----------------------------------------------
st.set_page_config(page_title="Construction Project Manager", layout="wide")
st.title("Construction Project Manager")
st.markdown("A robust ProjectManager-style construction tracking system built with Streamlit.")

# -----------------------------------------------
# 1. Data Loading
# -----------------------------------------------
@st.cache_data
def load_data(file_path):
    if not os.path.exists(file_path):
        st.error(f"File {file_path} not found!")
        st.stop()
    df = pd.read_excel(file_path)
    # Remove extra spaces from column names
    df.columns = df.columns.str.strip()
    # Convert date columns to datetime
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    return df

# Load dataset automatically (the file should be in the same directory)
data_file = "construction_timeline.xlsx"
df = load_data(data_file)

# -----------------------------------------------
# 2. Data Editing Option
# -----------------------------------------------
st.subheader("Edit Dataset")
# The data editor lets the user change values directly without file uploads
edited_df = st.data_editor(df, use_container_width=True)

# -----------------------------------------------
# 3. Sidebar Filters
# -----------------------------------------------
st.sidebar.header("Filter Options")

# Filter by Activity
activities = sorted(edited_df["Activity"].dropna().unique())
selected_activities = st.sidebar.multiselect("Select Activity", options=activities, default=activities)

# Filter by Room
rooms = sorted(edited_df["Room"].dropna().unique())
selected_rooms = st.sidebar.multiselect("Select Room", options=rooms, default=rooms)

# Filter by Status (if available, else show a default option)
if edited_df["Status"].notna().sum() > 0:
    statuses = sorted(edited_df["Status"].dropna().unique())
    selected_statuses = st.sidebar.multiselect("Select Status", options=statuses, default=statuses)
else:
    selected_statuses = []

# Filter by Date Range using the min and max dates from the dataset
min_date = edited_df["Start Date"].min()
max_date = edited_df["End Date"].max()
selected_date_range = st.sidebar.date_input("Select Date Range", value=[min_date, max_date])

# -----------------------------------------------
# 4. Filtering the DataFrame based on user input
# -----------------------------------------------
df_filtered = edited_df.copy()

if selected_activities:
    df_filtered = df_filtered[df_filtered["Activity"].isin(selected_activities)]
if selected_rooms:
    df_filtered = df_filtered[df_filtered["Room"].isin(selected_rooms)]
if selected_statuses:
    df_filtered = df_filtered[df_filtered["Status"].isin(selected_statuses)]

# Apply date filtering (ensure both Start and End dates are within the selected range)
if len(selected_date_range) == 2:
    start_range, end_range = pd.to_datetime(selected_date_range[0]), pd.to_datetime(selected_date_range[1])
    df_filtered = df_filtered[
        (df_filtered["Start Date"] >= start_range) & (df_filtered["End Date"] <= end_range)
    ]

# -----------------------------------------------
# 5. Detailed Interactive Gantt Chart using Plotly
# -----------------------------------------------
st.subheader("Gantt Chart Visualization")
if not df_filtered.empty:
    gantt_fig = px.timeline(
        df_filtered,
        x_start="Start Date",
        x_end="End Date",
        y="Task",
        color="Activity",
        hover_data=["Room", "Location", "Notes", "Workdays"],
        title="Construction Timeline Gantt Chart",
    )
    # Reverse y-axis to show tasks in natural top-to-bottom order
    gantt_fig.update_yaxes(autorange="reversed")
    gantt_fig.update_layout(xaxis_title="Timeline", yaxis_title="Tasks")
    st.plotly_chart(gantt_fig, use_container_width=True)
else:
    st.info("No data available for the selected filters. Please adjust your filter options.")

# -----------------------------------------------
# 6. Task Progress Tracker
# -----------------------------------------------
st.subheader("Task Progress Tracker")
if "Status" in edited_df.columns and edited_df["Status"].notna().any():
    progress_counts = edited_df["Status"].value_counts().reset_index()
    progress_counts.columns = ["Status", "Count"]
    st.dataframe(progress_counts, use_container_width=True)
else:
    st.info("No task status data available.")

# -----------------------------------------------
# 7. Workday & Budget Summaries
# -----------------------------------------------
st.subheader("Workday Summaries")
if "Workdays" in edited_df.columns and edited_df["Workdays"].notna().any():
    workday_summary = edited_df.groupby("Activity")["Workdays"].mean().reset_index()
    workday_summary.columns = ["Activity", "Average Workdays"]
    st.dataframe(workday_summary, use_container_width=True)
else:
    st.info("No workday information available.")

# -----------------------------------------------
# 8. Export Options for Filtered Data
# -----------------------------------------------
st.subheader("Export Filtered Data")

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="FilteredData")
    processed_data = output.getvalue()
    return processed_data

csv_data = convert_df_to_csv(df_filtered)
st.download_button(
    label="Download Filtered Data as CSV",
    data=csv_data,
    file_name="filtered_construction_data.csv",
    mime="text/csv",
)

excel_data = convert_df_to_excel(df_filtered)
st.download_button(
    label="Download Filtered Data as Excel",
    data=excel_data,
    file_name="filtered_construction_data.xlsx",
    mime="application/vnd.ms-excel",
)

st.markdown("---")
st.markdown("Developed with a forward-thinking, data-driven approach. Enjoy tracking your construction project!")
