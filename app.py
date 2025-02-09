import streamlit as st
import pandas as pd
import plotly.express as px
import io, os
from datetime import datetime

# ---------------------------------------------------
# Utility functions
# ---------------------------------------------------
def load_data(file_path):
    if not os.path.exists(file_path):
        st.error(f"File {file_path} not found!")
        st.stop()
    df = pd.read_excel(file_path)
    # Clean column names and convert dates
    df.columns = df.columns.str.strip()
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    # Ensure key columns are strings
    for col in ["Status", "Activity", "Item", "Task", "Room"]:
        df[col] = df[col].astype(str)
    # Add new columns if not present
    if "Order Status" not in df.columns:
        df["Order Status"] = "Not Ordered"
    if "Progress" not in df.columns:
        df["Progress"] = 0
    df["Progress"] = pd.to_numeric(df["Progress"], errors="coerce").fillna(0)
    return df

def enforce_logic(df):
    # Enforce that if Order Status is "Not Ordered", then status must be "Not Started" and progress 0.
    # And if Order Status is "Ordered" but status is "Not Started", force progress to 0.
    for idx, row in df.iterrows():
        order = row["Order Status"].strip().lower()
        status = row["Status"].strip().lower()
        if order == "not ordered":
            df.at[idx, "Status"] = "Not Started"
            df.at[idx, "Progress"] = 0
        elif order == "ordered" and status == "not started":
            df.at[idx, "Progress"] = 0
        # Optionally: if status is finished/delivered, force progress to 100
        if status in ["finished", "delivered"]:
            df.at[idx, "Progress"] = 100
    return df

def save_data(df, file_path):
    try:
        df.to_excel(file_path, index=False)
        st.success("Data successfully saved!")
    except Exception as e:
        st.error(f"Error saving data: {e}")

# ---------------------------------------------------
# Gantt Chart Generation
# ---------------------------------------------------
def create_gantt_chart(df_input):
    # If no data is available, return an empty figure with a message.
    if df_input.empty:
        fig = px.scatter(title="No data to display")
        return fig

    # Define grouping columns based on sidebar options (set in session_state)
    group_cols = ["Activity"]
    if st.session_state.get("group_by_room", False):
        group_cols.append("Room")
    if st.session_state.get("group_by_item", False):
        group_cols.append("Item")
    if st.session_state.get("group_by_task", False):
        group_cols.append("Task")
    if not group_cols:
        return px.scatter(title="No group columns selected")

    # Aggregate: minimum start, maximum end, average progress
    agg_dict = {"Start Date": "min", "End Date": "max", "Progress": "mean"}
    agg_df = df_input.groupby(group_cols).agg(agg_dict).reset_index()

    # Compute aggregated status (simple logic: if any row is in progress then overall "In Progress", etc.)
    def compute_group_status(row):
        cond = True
        for col in group_cols:
            cond = cond & (df_input[col] == row[col])
        subset = df_input[cond]
        statuses = subset["Status"].str.strip().str.lower()
        now = pd.Timestamp(datetime.today().date())
        # If any task is in progress, overall status is In Progress.
        if "in progress" in statuses.values:
            return "In Progress"
        # If all tasks are finished/delivered, decide based on end date.
        if all(status in ["finished", "delivered"] for status in statuses):
            max_end = subset["End Date"].max()
            return "Finished On Time" if now <= max_end else "Finished Late"
        # If all tasks are not started, then "Not Started"
        if all(status == "not started" for status in statuses):
            return "Not Started"
        # Otherwise, default to In Progress.
        return "In Progress"
    
    agg_df["Aggregated Status"] = agg_df.apply(compute_group_status, axis=1)
    if len(group_cols) == 1:
        agg_df["Group Label"] = agg_df[group_cols[0]].astype(str)
    else:
        agg_df["Group Label"] = agg_df[group_cols].apply(lambda row: " | ".join(row.astype(str)), axis=1)

    # Build Gantt segments. For in-progress groups with partial progress (0<progress<100), split the bar.
    segments = []
    for idx, row in agg_df.iterrows():
        start = row["Start Date"]
        end = row["End Date"]
        prog = row["Progress"]
        status = row["Aggregated Status"]
        label = row["Group Label"]
        total_sec = (end - start).total_seconds()
        # For in-progress tasks with partial progress, split into two segments.
        if status == "In Progress" and 0 < prog < 100 and total_sec > 0:
            completed_sec = total_sec * (prog / 100.0)
            completed_end = start + pd.Timedelta(seconds=completed_sec)
            segments.append({
                "Group Label": label,
                "Segment": "Completed (In Progress)",
                "Start": start,
                "End": completed_end,
                "Progress": f"{prog:.0f}%"
            })
            segments.append({
                "Group Label": label,
                "Segment": "Remaining (In Progress)",
                "Start": completed_end,
                "End": end,
                "Progress": f"{prog:.0f}%"
            })
        else:
            # For full segments, use the aggregated status as the label.
            seg_label = status
            segments.append({
                "Group Label": label,
                "Segment": seg_label,
                "Start": start,
                "End": end,
                "Progress": f"{prog:.0f}%"
            })
    seg_df = pd.DataFrame(segments)

    # Define color mapping for the segments:
    color_map = {
        "Not Started": "lightgray",
        "Finished On Time": "green",
        "Finished Late": "red",
        "Completed (In Progress)": "darkblue",
        "Remaining (In Progress)": "lightgray",
        "In Progress": "darkblue"  # fallback if not split
    }
    seg_df["Color"] = seg_df["Segment"].apply(lambda x: color_map.get(x, "blue"))

    # Create timeline plot
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

# ---------------------------------------------------
# App Initialization & Session State Management
# ---------------------------------------------------
DATA_FILE = "construction_timeline.xlsx"
if "df" not in st.session_state:
    st.session_state.df = load_data(DATA_FILE)

# For filter grouping (default to False if not set)
for key in ["group_by_room", "group_by_item", "group_by_task"]:
    if key not in st.session_state:
        st.session_state[key] = False

# ---------------------------------------------------
# Sidebar – Filter Options & Clear Filters Button
# ---------------------------------------------------
st.sidebar.header("Filter Options")
# Get unique normalized filter values from the current data
def norm_unique(col):
    return sorted(set(st.session_state.df[col].dropna().astype(str).str.lower().str.strip()))

activity_options = norm_unique("Activity")
selected_activities = st.sidebar.multiselect("Activity", options=activity_options, key="filter_activity")
item_options = norm_unique("Item")
selected_items = st.sidebar.multiselect("Item", options=item_options, key="filter_item")
task_options = norm_unique("Task")
selected_tasks = st.sidebar.multiselect("Task", options=task_options, key="filter_task")
room_options = norm_unique("Room")
selected_rooms = st.sidebar.multiselect("Room", options=room_options, key="filter_room")
status_options = norm_unique("Status")
selected_statuses = st.sidebar.multiselect("Status", options=status_options, key="filter_status")
order_status_options = norm_unique("Order Status")
selected_order_statuses = st.sidebar.multiselect("Order Status", options=order_status_options, key="filter_order_status")

if st.sidebar.button("Clear Filters"):
    st.session_state.filter_activity = []
    st.session_state.filter_item = []
    st.session_state.filter_task = []
    st.session_state.filter_room = []
    st.session_state.filter_status = []
    st.session_state.filter_order_status = []

# Sidebar grouping options for Gantt chart
st.sidebar.markdown("**Gantt Grouping Options**")
st.session_state.group_by_room = st.sidebar.checkbox("Group by Room", value=st.session_state.get("group_by_room", False))
st.session_state.group_by_item = st.sidebar.checkbox("Group by Item", value=st.session_state.get("group_by_item", False))
st.session_state.group_by_task = st.sidebar.checkbox("Group by Task", value=st.session_state.get("group_by_task", False))

# Date range filter
min_date = st.session_state.df["Start Date"].min()
max_date = st.session_state.df["End Date"].max()
selected_dates = st.sidebar.date_input("Select Date Range", value=[min_date, max_date])

# ---------------------------------------------------
# Sidebar – Manage Rows & Columns
# ---------------------------------------------------
st.sidebar.header("Manage Rows & Columns")

with st.sidebar.expander("Rows"):
    if st.sidebar.button("Add New Row"):
        # Append a new row with default values to the session_state DataFrame.
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
        st.session_state.df = st.session_state.df.append(new_row, ignore_index=True)
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
    # Allow deletion only of non-default columns.
    extra_cols = [col for col in st.session_state.df.columns if col not in default_cols]
    cols_to_delete = st.sidebar.multiselect("Delete Columns", options=extra_cols)
    if st.sidebar.button("Delete Selected Columns"):
        st.session_state.df.drop(columns=cols_to_delete, inplace=True)

# ---------------------------------------------------
# Apply Filters to DataFrame
# ---------------------------------------------------
df_filtered = st.session_state.df.copy()

# Normalize for filtering
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

# Drop helper columns
df_filtered.drop(columns=[col for col in df_filtered.columns if col.endswith("_norm")], inplace=True)

# ---------------------------------------------------
# Data Editing Section (Show current data for editing)
# ---------------------------------------------------
st.subheader("Update Task Information")
st.markdown("""
- Edit the table below. (New rows can be added using the sidebar “Add New Row” button.)
- **Status** must be one of: Finished, In Progress, Not Started, Delivered, Not Delivered.
- **Order Status** must be either Ordered or Not Ordered.
- **Progress** should be between 0 and 100.
""")
# Show the editable table using the current number of rows
edited_df = st.data_editor(st.session_state.df, use_container_width=True, num_rows=st.session_state.df.shape[0])
st.session_state.df = edited_df  # update session state with edits

# ---------------------------------------------------
# Save Updates Button – Enforce logical rules and save
# ---------------------------------------------------
if st.button("Save Updates"):
    st.session_state.df = enforce_logic(st.session_state.df)
    save_data(st.session_state.df, DATA_FILE)
    # No rerun command is used here

# ---------------------------------------------------
# Dashboard Overview
# ---------------------------------------------------
st.header("Dashboard Overview")

# 1) Snapshot of filtered data
st.subheader("Current Tasks Snapshot")
st.dataframe(df_filtered)

# 2) Gantt Chart
st.subheader("Project Timeline")
gantt_fig = create_gantt_chart(df_filtered)
st.plotly_chart(gantt_fig, use_container_width=True)

# 3) KPIs & Progress
total_tasks = st.session_state.df.shape[0]
finished_tasks = st.session_state.df[st.session_state.df["Status"].str.strip().str.lower().isin(["finished", "delivered"])].shape[0]
completion_percentage = (finished_tasks / total_tasks) * 100 if total_tasks > 0 else 0
in_progress_tasks = st.session_state.df[st.session_state.df["Status"].str.strip().str.lower() == "in progress"].shape[0]
not_declared = st.session_state.df[~st.session_state.df["Status"].str.strip().str.lower().isin(
    ["finished", "in progress", "delivered", "not started"]
)].shape[0]

st.metric("Overall Completion", f"{completion_percentage:.1f}%")
st.progress(completion_percentage / 100)

# 4) Additional Insights
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

# Active Filters Summary
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
