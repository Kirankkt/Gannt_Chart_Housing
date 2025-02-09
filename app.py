import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from datetime import datetime, date, timedelta

##############################################
# Database Functions (SQLite Backend)
##############################################

DB_FILE = "tasks.db"

def init_db():
    """Initialize the SQLite database and create the tasks table if it does not exist."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
      CREATE TABLE IF NOT EXISTS tasks (
        Activity TEXT,
        Item TEXT,
        Task TEXT,
        Room TEXT,
        "Start Date" TEXT,
        "End Date" TEXT,
        Status TEXT,
        "Order Status" TEXT,
        Progress INTEGER,
        Notes TEXT
      )
    """)
    conn.commit()
    return conn

def load_data_from_db(conn):
    """Load tasks from the database into a DataFrame."""
    df = pd.read_sql_query("SELECT * FROM tasks", conn)
    if not df.empty:
        # Convert ISO date strings to datetime objects; if conversion fails, they become NaT.
        df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
        df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    return df

def save_data_to_db(df, conn):
    """Save the DataFrame to the tasks table in the database (replacing the table)."""
    df_copy = df.copy()
    # Convert datetime columns to ISO date strings (or None if missing)
    if "Start Date" in df_copy.columns:
        df_copy["Start Date"] = df_copy["Start Date"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None)
    if "End Date" in df_copy.columns:
        df_copy["End Date"] = df_copy["End Date"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None)
    df_copy.to_sql("tasks", conn, if_exists="replace", index=False)

##############################################
# Gantt Chart Generation (with Refined Grouping)
##############################################

def create_gantt_chart(df_input):
    if df_input.empty:
        return px.scatter(title="No data to display")
    
    # Determine grouping columns based on sidebar checkboxes.
    group_cols = ["Activity"]
    if st.session_state.get("group_by_room", False):
        group_cols.append("Room")
    if st.session_state.get("group_by_item", False):
        group_cols.append("Item")
    if st.session_state.get("group_by_task", False):
        group_cols.append("Task")
    
    # Aggregate data: get min Start Date, max End Date, and average Progress.
    agg_dict = {"Start Date": "min", "End Date": "max", "Progress": "mean"}
    agg_df = df_input.groupby(group_cols).agg(agg_dict).reset_index()
    
    # Compute an aggregated status per group (simple logic).
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
        seg = {"Group Label": row["Group Label"], "Start": row["Start Date"], "End": row["End Date"]}
        prog = row["Progress"]
        status = row["Aggregated Status"]
        if status.lower() == "not started" or prog == 0:
            seg["Segment"] = "Not Started"
            seg["Progress"] = "0%"
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

# Initialize the SQLite database connection.
conn = init_db()

# Load data from the database into session state only once.
if "df" not in st.session_state:
    st.session_state.df = load_data_from_db(conn)
    if st.session_state.df.empty:
        # If no data exists, create an empty DataFrame with the expected columns.
        st.session_state.df = pd.DataFrame(columns=["Activity", "Item", "Task", "Room", "Start Date", "End Date", "Status", "Order Status", "Progress", "Notes"])

# Do not reassign st.session_state.df on every run so that edits persist.

##############################################
# Data Editor Section
##############################################

st.subheader("Edit Task Information")
# The data editor shows the current DataFrame.
editor_df = st.data_editor(st.session_state.df, key="data_editor")
if st.button("Save Updates"):
    st.session_state.df = editor_df.copy()
    save_data_to_db(st.session_state.df, conn)
    st.success("Your changes have been saved.")
    # Note: st.experimental_rerun() is not used because your version doesn't support it.
    # You may need to manually refresh the page for dashboard components to update.

##############################################
# Sidebar – Filters and Grouping Options
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

# Date range filter – ensure valid default dates.
if not st.session_state.df.empty and pd.notnull(st.session_state.df["Start Date"].min()):
    min_date_val = st.session_state.df["Start Date"].min().date()
else:
    min_date_val = date.today()
if not st.session_state.df.empty and pd.notnull(st.session_state.df["End Date"].max()):
    max_date_val = st.session_state.df["End Date"].max().date()
else:
    max_date_val = date.today()

selected_dates = st.sidebar.date_input("Select Date Range", value=[min_date_val, max_date_val])

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
            "Start Date": None,
            "End Date": None,
            "Status": "",
            "Order Status": "",
            "Progress": 0,
            "Notes": ""
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
    default_cols = {"Activity", "Item", "Task", "Room", "Start Date", "End Date", "Status", "Order Status", "Progress", "Notes"}
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
# Apply Filters for Dashboard
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
if isinstance(selected_dates, list) and len(selected_dates) == 2:
    start_range = pd.to_datetime(selected_dates[0])
    end_range = pd.to_datetime(selected_dates[1])
    df_filtered = df_filtered[(df_filtered["Start Date"] >= start_range) & (df_filtered["End Date"] <= end_range)]
df_filtered.drop(columns=[col for col in df_filtered.columns if col.endswith("_norm")], inplace=True)

##############################################
# Dashboard Overview
##############################################

st.header("Dashboard Overview")

st.subheader("Current Tasks Snapshot")
st.dataframe(df_filtered)

st.subheader("Project Timeline")
gantt_fig = create_gantt_chart(df_filtered)
st.plotly_chart(gantt_fig, use_container_width=True)

total_tasks = st.session_state.df.shape[0]
finished_tasks = st.session_state.df[st.session_state.df["Status"].str.strip().str.lower().isin(["finished", "delivered"])].shape[0]
completion_percentage = (finished_tasks / total_tasks) * 100 if total_tasks > 0 else 0
in_progress_tasks = st.session_state.df[st.session_state.df["Status"].str.strip().str.lower() == "in progress"].shape[0]
not_declared = st.session_state.df[~st.session_state.df["Status"].str.strip().str.lower().isin(["finished", "in progress", "delivered", "not started"])].shape[0]

st.metric("Overall Completion", f"{completion_percentage:.1f}%")
st.progress(completion_percentage / 100)

st.markdown("#### Additional Insights")
today_val = pd.Timestamp(datetime.today().date())
overdue_df = df_filtered[(df_filtered["End Date"] < today_val) &
                         (~df_filtered["Status"].str.strip().str.lower().isin(["finished", "delivered"]))]
st.markdown(f"**Overdue Tasks:** {overdue_df.shape[0]}")
if not overdue_df.empty:
    st.dataframe(overdue_df[["Activity", "Room", "Task", "Status", "Order Status", "End Date"]])

task_dist = df_filtered.groupby("Activity").size().reset_index(name="Task Count")
dist_fig = px.bar(task_dist, x="Activity", y="Task Count", title="Task Distribution by Activity")
st.plotly_chart(dist_fig, use_container_width=True)

upcoming_df = df_filtered[(df_filtered["Start Date"] >= today_val) & (df_filtered["Start Date"] <= today_val + timedelta(days=7))]
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
