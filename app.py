import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime

##############################################
# Utility Functions
##############################################

DATA_FILE = "construction_timeline.xlsx"

def load_data(file_path):
    if not os.path.exists(file_path):
        st.error(f"File {file_path} not found!")
        st.stop()
    df = pd.read_excel(file_path)
    # Clean column names and convert date columns
    df.columns = df.columns.str.strip()
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    # Ensure key text columns are strings
    for col in ["Status", "Activity", "Item", "Task", "Room"]:
        df[col] = df[col].astype(str)
    # If there is a "Notes" column, force it to string.
    if "Notes" in df.columns:
        df["Notes"] = df["Notes"].astype(str)
    # Add new columns if missing
    if "Order Status" not in df.columns:
        df["Order Status"] = "Not Ordered"
    if "Progress" not in df.columns:
        df["Progress"] = 0
    df["Progress"] = pd.to_numeric(df["Progress"], errors="coerce").fillna(0)
    return df

def save_data(df, file_path):
    try:
        df.to_excel(file_path, index=False)
        st.success("Data successfully saved!")
    except Exception as e:
        st.error(f"Error saving data: {e}")

##############################################
# Gantt Chart Generation (with refined grouping)
##############################################

def create_gantt_chart(df_input):
    if df_input.empty:
        return px.scatter(title="No data to display")
    
    # Build grouping columns based on sidebar checkboxes.
    group_cols = ["Activity"]
    if st.session_state.get("group_by_room", False):
        group_cols.append("Room")
    if st.session_state.get("group_by_item", False):
        group_cols.append("Item")
    if st.session_state.get("group_by_task", False):
        group_cols.append("Task")
    
    # Aggregate data: minimum Start Date, maximum End Date, average Progress.
    agg_dict = {"Start Date": "min", "End Date": "max", "Progress": "mean"}
    agg_df = df_input.groupby(group_cols).agg(agg_dict).reset_index()
    
    # For simplicity, compute an aggregated status:
    def compute_group_status(row):
        cond = True
        for col in group_cols:
            cond = cond & (df_input[col] == row[col])
        subset = df_input[cond]
        statuses = subset["Status"].str.strip().str.lower()
        if "in progress" in statuses.values:
            return "In Progress"
        if all(s in ["finished", "delivered"] for s in statuses):
            return "Finished"
        return "Not Started"
    
    agg_df["Aggregated Status"] = agg_df.apply(compute_group_status, axis=1)
    agg_df["Group Label"] = agg_df[group_cols].apply(lambda row: " | ".join(row.astype(str)), axis=1)
    
    # Build timeline segments.
    segments = []
    for _, row in agg_df.iterrows():
        seg = {}
        seg["Group Label"] = row["Group Label"]
        seg["Start"] = row["Start Date"]
        seg["End"] = row["End Date"]
        prog = row["Progress"]
        status = row["Aggregated Status"]
        # Simple logic: if not started or zero progress, mark as "Not Started"
        if status.lower() == "not started" or prog == 0:
            seg["Segment"] = "Not Started"
            seg["Progress"] = "0%"
        # For in-progress groups with partial progress, split the bar.
        elif status.lower() == "in progress" and 0 < prog < 100:
            total_sec = (row["End Date"] - row["Start Date"]).total_seconds()
            completed_sec = total_sec * (prog / 100.0)
            completed_end = row["Start Date"] + pd.Timedelta(seconds=completed_sec)
            segments.append({
                "Group Label": row["Group Label"],
                "Segment": "Completed (In Progress)",
                "Start": row["Start Date"],
                "End": completed_end,
                "Progress": f"{prog:.0f}%"
            })
            seg = {
                "Group Label": row["Group Label"],
                "Segment": "Remaining (In Progress)",
                "Start": completed_end,
                "End": row["End Date"],
                "Progress": f"{prog:.0f}%"
            }
        # If finished/delivered, force 100%
        elif status.lower() in ["finished", "delivered"]:
            seg["Segment"] = status
            seg["Progress"] = "100%"
        else:
            seg["Segment"] = status
            seg["Progress"] = f"{prog:.0f}%"
        segments.append(seg)
    seg_df = pd.DataFrame(segments)
    
    # Define color mapping.
    color_map = {
        "Not Started": "lightgray",
        "In Progress": "darkblue",
        "Completed (In Progress)": "darkblue",
        "Remaining (In Progress)": "lightgray",
        "Finished": "green",
        "Delivered": "green"
    }
    
    fig = px.timeline(
        seg_df,
        x_start="Start",
        x_end="End",
        y="Group Label",
        color="Segment",
        text="Progress",
        color_discrete_map=color_map,
        title="Project Timeline"
    )
    fig.for_each_trace(lambda t: t.update(name=t.name.split("=")[-1]))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Timeline", showlegend=True)
    return fig

##############################################
# App Initialization & Session State
##############################################

st.set_page_config(page_title="Construction Project Manager Dashboard", layout="wide")
st.title("Construction Project Manager Dashboard")

# Load data only once into session state.
if "df" not in st.session_state:
    st.session_state.df = load_data(DATA_FILE)

# Do NOT reassign st.session_state.df on every run—allow edits to persist.
# (The data editor below works on a local variable that is only committed when Save Updates is clicked.)

##############################################
# Data Editor Section
##############################################

st.subheader("Edit Task Information")
# Display the data editor using the current session state DataFrame.
# The editor's return value is stored in a local variable.
editor_value = st.data_editor("Edit Data", st.session_state.df, key="data_editor")

# Provide a Save Updates button. When clicked, commit the changes to session state
# and save the updated DataFrame to file.
if st.button("Save Updates"):
    st.session_state.df = editor_value.copy()
    save_data(st.session_state.df, DATA_FILE)
    st.experimental_rerun()  # Force a rerun so that all downstream components update

##############################################
# Sidebar – Filters and Management
##############################################

st.sidebar.header("Filter Options")
def norm_unique(col):
    return sorted(set(st.session_state.df[col].dropna().astype(str).str.lower().str.strip()))

selected_activities = st.sidebar.multiselect("Activity", options=norm_unique("Activity"), key="filter_activity")
selected_items = st.sidebar.multiselect("Item", options=norm_unique("Item"), key="filter_item")
selected_tasks = st.sidebar.multiselect("Task", options=norm_unique("Task"), key="filter_task")
selected_rooms = st.sidebar.multiselect("Room", options=norm_unique("Room"), key="filter_room")
selected_statuses = st.sidebar.multiselect("Status", options=norm_unique("Status"), key="filter_status")
selected_order_statuses = st.sidebar.multiselect("Order Status", options=norm_unique("Order Status"), key="filter_order_status")

if st.sidebar.button("Clear Filters"):
    for key in ["filter_activity", "filter_item", "filter_task", "filter_room", "filter_status", "filter_order_status"]:
        st.session_state[key] = []

st.sidebar.markdown("**Gantt Grouping Options**")
group_by_room = st.sidebar.checkbox("Group by Room", value=False)
group_by_item = st.sidebar.checkbox("Group by Item", value=False)
group_by_task = st.sidebar.checkbox("Group by Task", value=False)
st.session_state.group_by_room = group_by_room
st.session_state.group_by_item = group_by_item
st.session_state.group_by_task = group_by_task

min_date = st.session_state.df["Start Date"].min()
max_date = st.session_state.df["End Date"].max()
selected_dates = st.sidebar.date_input("Select Date Range", value=[min_date, max_date])

##############################################
# Sidebar – Manage Rows & Columns
##############################################

st.sidebar.header("Manage Rows & Columns")
with st.sidebar.expander("Rows"):
    if st.sidebar.button("Add New Row"):
        new_row = {
            "Activity": "",
            "Item": "",
            "Task": "",
            "Room": "",
            "Start Date": pd.NaT,
            "End Date": pd.NaT,
            "Status": "Not Started",
            "Order Status": "Not Ordered",
            "Progress": 0
        }
        new_row_df = pd.DataFrame([new_row])
        st.session_state.df = pd.concat([st.session_state.df, new_row_df], ignore_index=True)
    row_to_delete = st.sidebar.text_input("Row Number to Delete", value="")
    if st.sidebar.button("Delete Row") and row_to_delete.isdigit():
        row_num = int(row_to_delete)
        if 0 <= row_num < len(st.session_state.df):
            st.session_state.df = st.session_state.df.drop(st.session_state.df.index[row_num]).reset_index(drop=True)
        else:
            st.sidebar.error("Invalid row number.")

with st.sidebar.expander("Columns"):
    default_cols = {"Activity", "Item", "Task", "Room", "Start Date", "End Date", "Status", "Order Status", "Progress"}
    new_col_name = st.sidebar.text_input("New Column Name", key="new_col")
    default_value = st.sidebar.text_input("Default Value", key="def_val")
    if st.sidebar.button("Add Column"):
        if new_col_name and new_col_name not in st.session_state.df.columns:
            st.session_state.df[new_col_name] = default_value
        else:
            st.sidebar.error("Invalid or existing column name.")
    extra_cols = [col for col in st.session_state.df.columns if col not in default_cols]
    cols_to_delete = st.sidebar.multiselect("Delete Columns", options=extra_cols)
    if st.sidebar.button("Delete Selected Columns"):
        st.session_state.df.drop(columns=cols_to_delete, inplace=True)

##############################################
# Apply Filters to DataFrame for Dashboard
##############################################

df_filtered = st.session_state.df.copy()
for col in ["Activity", "Item", "Task", "Room", "Status", "Order Status"]:
    df_filtered[col + "_norm"] = df_filtered[col].astype(str).str.lower().str.strip()

if selected_activities:
    df_filtered = df_filtered[df_filtered["Activity_norm"].isin(selected_activities)]
if selected_items:
    df_filtered = df_filtered[df_filtered["Item_norm"].isin(selected_items)]
if selected_tasks:
    df_filtered = df_filtered[df_filtered["Task_norm"].isin(selected_tasks)]
if selected_rooms:
    df_filtered = df_filtered[df_filtered["Room_norm"].isin(selected_rooms)]
if selected_statuses:
    df_filtered = df_filtered[df_filtered["Status_norm"].isin(selected_statuses)]
if selected_order_statuses:
    df_filtered = df_filtered[df_filtered["Order Status_norm"].isin(selected_order_statuses)]
if len(selected_dates) == 2:
    start_range = pd.to_datetime(selected_dates[0])
    end_range = pd.to_datetime(selected_dates[1])
    df_filtered = df_filtered[(df_filtered["Start Date"] >= start_range) & (df_filtered["End Date"] <= end_range)]
df_filtered.drop(columns=[col for col in df_filtered.columns if col.endswith("_norm")], inplace=True)

##############################################
# Dashboard Overview
##############################################

st.header("Dashboard Overview")

# 1) Snapshot of Filtered Data
st.subheader("Current Tasks Snapshot")
st.dataframe(df_filtered)

# 2) Gantt Chart (regenerated from filtered data with refined grouping)
st.subheader("Project Timeline")
gantt_fig = create_gantt_chart(df_filtered)
st.plotly_chart(gantt_fig, use_container_width=True)

# 3) KPIs & Progress
total_tasks = st.session_state.df.shape[0]
finished_tasks = st.session_state.df[st.session_state.df["Status"].str.strip().str.lower().isin(["finished", "delivered"])].shape[0]
completion_percentage = (finished_tasks / total_tasks) * 100 if total_tasks > 0 else 0
in_progress_tasks = st.session_state.df[st.session_state.df["Status"].str.strip().str.lower() == "in progress"].shape[0]
not_declared = st.session_state.df[~st.session_state.df["Status"].str.strip().str.lower().isin(["finished", "in progress", "delivered", "not started"])].shape[0]

st.metric("Overall Completion", f"{completion_percentage:.1f}%")
st.progress(completion_percentage / 100)

st.markdown("#### Additional Insights")
today = pd.Timestamp(datetime.today().date())
overdue_df = df_filtered[(df_filtered["End Date"] < today) &
                         (~df_filtered["Status"].str.strip().str.lower().isin(["finished", "delivered"]))]
st.markdown(f"**Overdue Tasks:** {overdue_df.shape[0]}")
if not overdue_df.empty:
    st.dataframe(overdue_df[["Activity", "Room", "Task", "Status", "Order Status", "End Date"]])

task_dist = df_filtered.groupby("Activity").size().reset_index(name="Task Count")
dist_fig = px.bar(task_dist, x="Activity", y="Task Count", title="Task Distribution by Activity")
st.plotly_chart(dist_fig, use_container_width=True)

upcoming_df = df_filtered[(df_filtered["Start Date"] >= today) & (df_filtered["Start Date"] <= today + pd.Timedelta(days=7))]
st.markdown("**Upcoming Tasks (Next 7 Days):**")
if not upcoming_df.empty:
    st.dataframe(upcoming_df[["Activity", "Room", "Task", "Start Date", "Status", "Order Status"]])
else:
    st.info("No upcoming tasks in the next 7 days.")

active_filters = []
if selected_activities:
    active_filters.append("Activities: " + ", ".join(selected_activities))
if selected_items:
    active_filters.append("Items: " + ", ".join(selected_items))
if selected_tasks:
    active_filters.append("Tasks: " + ", ".join(selected_tasks))
if selected_rooms:
    active_filters.append("Rooms: " + ", ".join(selected_rooms))
if selected_statuses:
    active_filters.append("Status: " + ", ".join(selected_statuses))
if selected_order_statuses:
    active_filters.append("Order Status: " + ", ".join(selected_order_statuses))
if selected_dates:
    active_filters.append(f"Date Range: {selected_dates[0]} to {selected_dates[1]}")
st.markdown("**Active Filters:** " + ("; ".join(active_filters) if active_filters else "None"))

st.markdown("---")
st.markdown("CMBP Analytics Dashboard")
