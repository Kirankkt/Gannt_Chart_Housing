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

# Filter by Status (if available)
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

# Apply date filtering (ensuring the tasks fall within the selected range)
if len(selected_date_range) == 2:
    start_range, end_range = pd.to_datetime(selected_date_range[0]), pd.to_datetime(selected_date_range[1])
    df_filtered = df_filtered[
        (df_filtered["Start Date"] >= start_range) & (df_filtered["End Date"] <= end_range)
    ]

# -----------------------------------------------
# 5. Detailed Interactive Gantt Chart for Activities using Plotly
# -----------------------------------------------
st.subheader("Gantt Chart Visualization (by Activity)")
if not df_filtered.empty:
    # Aggregate data by Activity: get the earliest start date and latest end date
    agg_df = df_filtered.groupby("Activity").agg({
        "Start Date": "min",
        "End Date": "max",
        "Task": "count"  # Count number of tasks per activity as extra info
    }).reset_index()
    agg_df.rename(columns={"Task": "Task Count"}, inplace=True)

    # Create the timeline chart using Activity as the y-axis
    gantt_fig = px.timeline(
        agg_df,
        x_start="Start Date",
        x_end="End Date",
        y="Activity",
        color="Activity",
        hover_data=["Task Count"],
        title="Activity Timeline Gantt Chart",
    )
    # Reverse y-axis to display activities in a natural order
    gantt_fig.update_yaxes(autorange="reversed")
    gantt_fig.update_layout(xaxis_title="Timeline", yaxis_title="Activity")
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
