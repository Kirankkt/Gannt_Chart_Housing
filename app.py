import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os

# ---------------------------------------------------
# App Configuration
# ---------------------------------------------------
st.set_page_config(page_title="Construction Project Manager", layout="wide")
st.title("Construction Project Manager")
st.markdown("A robust ProjectManager-style construction tracking system built with Streamlit.")

# ---------------------------------------------------
# 1. Data Loading
# ---------------------------------------------------
DATA_FILE = "construction_timeline.xlsx"

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
    # Ensure Status is a string so that it can be edited
    df["Status"] = df["Status"].astype(str)
    return df

df = load_data(DATA_FILE)

# ---------------------------------------------------
# 2. Data Editing Option (Direct Editing)
# ---------------------------------------------------
st.subheader("Edit Dataset")
st.markdown(
    """
    **Instructions:**  
    You can edit any column below. For the **Status** column, please choose from the dropdown below – either **Finished** or **In Progress**.
    """
)
column_config = {
    "Status": st.column_config.SelectboxColumn(
        "Status",
        options=["Finished", "In Progress"],
        help="Select 'Finished' for completed tasks or 'In Progress' for ongoing tasks."
    )
}
edited_df = st.data_editor(df, column_config=column_config, use_container_width=True)

# ---------------------------------------------------
# 2a. Save Button to Persist Changes
# ---------------------------------------------------
if st.button("Save Updates"):
    try:
        # Write the updated DataFrame back to the same Excel file.
        edited_df.to_excel(DATA_FILE, index=False)
        st.success("Data successfully saved!")
        # Clear the cache so that the next load uses the updated file.
        load_data.clear()
    except Exception as e:
        st.error(f"Error saving data: {e}")

# ---------------------------------------------------
# 3. Sidebar Filters & Options (remains unchanged)
# ---------------------------------------------------
st.sidebar.header("Filter Options")

activities = sorted(edited_df["Activity"].dropna().unique())
selected_activities = st.sidebar.multiselect(
    "Select Activity (leave empty for all)",
    options=activities,
    default=[]
)

rooms = sorted(edited_df["Room"].dropna().unique())
selected_rooms = st.sidebar.multiselect(
    "Select Room (leave empty for all)",
    options=rooms,
    default=[]
)

if edited_df["Status"].notna().sum() > 0:
    statuses = sorted(edited_df["Status"].dropna().unique())
    selected_statuses = st.sidebar.multiselect(
        "Select Status (leave empty for all)",
        options=statuses,
        default=[]
    )
else:
    selected_statuses = []

show_finished = st.sidebar.checkbox("Show Finished Tasks", value=True)
min_date = edited_df["Start Date"].min()
max_date = edited_df["End Date"].max()
selected_date_range = st.sidebar.date_input("Select Date Range", value=[min_date, max_date])

# ---------------------------------------------------
# 4. Filtering the DataFrame Based on User Input
# ---------------------------------------------------
df_filtered = edited_df.copy()

if selected_activities:
    df_filtered = df_filtered[df_filtered["Activity"].isin(selected_activities)]
if selected_rooms:
    df_filtered = df_filtered[df_filtered["Room"].isin(selected_rooms)]
if selected_statuses:
    df_filtered = df_filtered[df_filtered["Status"].isin(selected_statuses)]
if not show_finished:
    df_filtered = df_filtered[~df_filtered["Status"].str.strip().str.lower().eq("finished")]
if len(selected_date_range) == 2:
    start_range = pd.to_datetime(selected_date_range[0])
    end_range = pd.to_datetime(selected_date_range[1])
    df_filtered = df_filtered[
        (df_filtered["Start Date"] >= start_range) & (df_filtered["End Date"] <= end_range)
    ]

# ---------------------------------------------------
# Helper Function: Group Status Aggregation
# ---------------------------------------------------
def group_status(status_series):
    statuses = status_series.dropna().astype(str).str.strip().str.lower()
    return "Finished" if len(statuses) > 0 and all(s == "finished" for s in statuses) else "In Progress"

# ---------------------------------------------------
# 5. Detailed Interactive Gantt Chart with Enhanced Hover Data
# ---------------------------------------------------
st.subheader("Gantt Chart Visualization")

if not df_filtered.empty:
    group_cols = ["Activity", "Room"] if selected_rooms else ["Activity"]
    agg_df = df_filtered.groupby(group_cols).agg({
        "Start Date": "min",
        "End Date": "max",
        "Task": lambda x: ", ".join(sorted(set(x.dropna()))),
        "Item": lambda x: ", ".join(sorted(set(x.dropna())))
    }).reset_index()
    agg_df.rename(columns={"Task": "Tasks", "Item": "Items"}, inplace=True)
    
    if "Room" in group_cols:
        agg_df["Activity_Room"] = agg_df["Activity"] + " (" + agg_df["Room"] + ")"
        gantt_fig = px.timeline(
            agg_df,
            x_start="Start Date",
            x_end="End Date",
            y="Activity_Room",
            color="Activity",
            hover_data=["Items", "Tasks"],
            title="Activity & Room Timeline Gantt Chart"
        )
        gantt_fig.update_layout(yaxis_title="Activity (Room)")
    else:
        gantt_fig = px.timeline(
            agg_df,
            x_start="Start Date",
            x_end="End Date",
            y="Activity",
            color="Activity",
            hover_data=["Items", "Tasks"],
            title="Activity Timeline Gantt Chart"
        )
        gantt_fig.update_layout(yaxis_title="Activity")
    
    gantt_fig.update_yaxes(autorange="reversed")
    gantt_fig.update_layout(xaxis_title="Timeline")
    st.plotly_chart(gantt_fig, use_container_width=True)
else:
    st.info("No data available for the selected filters. Please adjust your filter options.")

# ---------------------------------------------------
# 6. Task Progress Tracker with Real-Time Updates
# ---------------------------------------------------
st.subheader("Task Progress Tracker")
if "Status" in edited_df.columns and edited_df["Status"].notna().any():
    progress_counts = edited_df["Status"].value_counts().reset_index()
    progress_counts.columns = ["Status", "Count"]
    total_tasks = edited_df.shape[0]
    finished_tasks = edited_df[edited_df["Status"].str.strip().str.lower() == "finished"].shape[0]
    completion_percentage = (finished_tasks / total_tasks) * 100 if total_tasks > 0 else 0
    st.metric("Overall Completion", f"{completion_percentage:.1f}%")
    st.dataframe(progress_counts, use_container_width=True)
else:
    st.info("No task status data available.")

# ---------------------------------------------------
# 7. Workday Summaries
# ---------------------------------------------------
st.subheader("Workday Summaries")
if "Workdays" in edited_df.columns and edited_df["Workdays"].notna().any():
    workday_summary = edited_df.groupby("Activity")["Workdays"].mean().reset_index()
    workday_summary.columns = ["Activity", "Average Workdays"]
    st.dataframe(workday_summary, use_container_width=True)
else:
    st.info("No workday information available.")

# ---------------------------------------------------
# 8. Detailed Table View for Task & Item Information
# ---------------------------------------------------
st.subheader("Detailed Task Information")
if not df_filtered.empty:
    st.dataframe(df_filtered[["Activity", "Room", "Item", "Task", "Start Date", "End Date", "Status"]])
else:
    st.info("No detailed task data to display based on the current filters.")

# ---------------------------------------------------
# 9. Export Options for Filtered Data
# ---------------------------------------------------
st.subheader("Export Filtered Data")
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="FilteredData")
    return output.getvalue()
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
