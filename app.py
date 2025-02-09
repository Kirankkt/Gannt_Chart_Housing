import streamlit as st
import pandas as pd
import plotly.express as px
import io, os
from datetime import datetime

##############################################
# Utility Functions
##############################################

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
    # Add new columns if missing
    if "Order Status" not in df.columns:
        df["Order Status"] = "Not Ordered"
    if "Progress" not in df.columns:
        df["Progress"] = 0
    df["Progress"] = pd.to_numeric(df["Progress"], errors="coerce").fillna(0)
    return df

def enforce_logic(df):
    # For each row, enforce:
    # 1. If Order Status is "Not Ordered", force Status to "Not Started" and Progress to 0.
    # 2. If Order Status is "Ordered" but Status is "Not Started", force Progress to 0.
    # 3. If Status is Finished or Delivered, force Progress to 100.
    for idx, row in df.iterrows():
        order = row["Order Status"].strip().lower()
        status = row["Status"].strip().lower()
        if order == "not ordered":
            df.at[idx, "Status"] = "Not Started"
            df.at[idx, "Progress"] = 0
        elif order == "ordered" and status == "not started":
            df.at[idx, "Progress"] = 0
        if status in ["finished", "delivered"]:
            df.at[idx, "Progress"] = 100
    return df

def save_data(df, file_path):
    try:
        df.to_excel(file_path, index=False)
        st.success("Data successfully saved!")
    except Exception as e:
        st.error(f"Error saving data: {e}")

##############################################
# Gantt Chart Generation
##############################################

def create_gantt_chart(df_input):
    # If no data is available, return an empty figure.
    if df_input.empty:
        fig = px.scatter(title="No data to display")
        return fig

    # Determine grouping columns based on sidebar options stored in session_state.
    group_cols = ["Activity"]
    if st.session_state.get("group_by_room", False):
        group_cols.append("Room")
    if st.session_state.get("group_by_item", False):
        group_cols.append("Item")
    if st.session_state.get("group_by_task", False):
        group_cols.append("Task")
    if not group_cols:
        return px.scatter(title="No group columns selected")

    # Aggregate by group: minimum Start Date, maximum End Date, average Progress.
    agg_dict = {"Start Date": "min", "End Date": "max", "Progress": "mean"}
    agg_df = df_input.groupby(group_cols).agg(agg_dict).reset_index()

    # Compute an aggregated status per group.
    def compute_group_status(row):
        cond = True
        for col in group_cols:
            cond = cond & (df_input[col] == row[col])
        subset = df_input[cond]
        statuses = subset["Status"].str.strip().str.lower()
        now = pd.Timestamp(datetime.today().date())
        if "in progress" in statuses.values:
            return "In Progress"
        if all(status in ["finished", "delivered"] for status in statuses):
            max_end = subset["End Date"].max()
            return "Finished On Time" if now <= max_end else "Finished Late"
        if all(status == "not started" for status in statuses):
            return "Not Started"
        return "In Progress"
    
    agg_df["Aggregated Status"] = agg_df.apply(compute_group_status, axis=1)
    if len(group_cols) == 1:
        agg_df["Group Label"] = agg_df[group_cols[0]].astype(str)
    else:
        agg_df["Group Label"] = agg_df[group_cols].apply(lambda row: " | ".join(row.astype(str)), axis=1)

    # Build Gantt segments.
    segments = []
    for idx, row in agg_df.iterrows():
        start = row["Start Date"]
        end = row["End Date"]
        prog = row["Progress"]
        status = row["Aggregated Status"]
        label = row["Group Label"]
        total_sec = (end - start).total_seconds()
        # For tasks with Order Status "Not Ordered" (or 0 progress) treat as "Not Started".
        if status.lower() in ["delivered", "not delivered"] or prog == 0:
            segments.append({
                "Group Label": label,
                "Segment": "Not Started",
                "Start": start,
                "End": end,
                "Progress": "0%"
            })
        # For In Progress groups with partial progress, split the bar.
        elif status == "In Progress":
            if prog > 0 and prog < 100 and total_sec > 0:
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
                segments.append({
                    "Group Label": label,
                    "Segment": "In Progress",
                    "Start": start,
                    "End": end,
                    "Progress": f"{prog:.0f}%"
                })
        else:
            # For finished tasks.
            segments.append({
                "Group Label": label,
                "Segment": status,
                "Start": start,
                "End": end,
                "Progress": f"{prog:.0f}%"
            })
    seg_df = pd.DataFrame(segments)

    # Define color mapping for segments (descriptive labels).
    color_map = {
        "Not Started": "lightgray",
        "Finished On Time": "green",
        "Finished Late": "red",
        "Completed (In Progress)": "darkblue",
        "Remaining (In Progress)": "lightgray",
        "In Progress": "darkblue"
    }
    seg_df["Color"] = seg_df["Segment"].apply(lambda x: color_map.get(x, "blue"))

    # Create the timeline plot.
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

DATA_FILE = "construction_timeline.xlsx"
if "df" not in st.session_state:
    st.session_state.df = load_data(DATA_FILE)

# Ensure filter keys exist.
for key in ["filter_activity", "filter_item", "filter_task", "filter_room", "filter_status", "filter_order_status"]:
    if key not in st.session_state:
        st.session_state[key] = []

# Grouping options defaults.
for key in ["group_by_room", "group_by_item", "group_by_task"]:
    if key not in st.session_state:
        st.session_state[key] = False

##############################################
# Sidebar – Filter Options & Clear Filters
##############################################

st.sidebar.header("Filter Options")

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
    for key in ["filter_activity", "filter_item", "filter_task", "filter_room", "filter_status", "filter_order_status"]:
        st.session_state[key] = []

# Sidebar grouping options.
st.sidebar.markdown("**Gantt Grouping Options**")
st.session_state.group_by_room = st.sidebar.checkbox("Group by Room", value=st.session_state.get("group_by_room", False))
st.session_state.group_by_item = st.sidebar.checkbox("Group by Item", value=st.session_state.get("group_by_item", False))
st.session_state.group_by_task = st.sidebar.checkbox("Group by Task", value=st.session_state.get("group_by_task", False))

# Date range filter.
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
        # Use pd.concat to add a new row.
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
# Apply Filters to DataFrame
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
# Data Editing Section
##############################################

st.subheader("Update Task Information")
st.markdown("""
- Edit the table below. (Use the sidebar “Add New Row” button to add rows.)
- **Status** (dropdown): If **Order Status** is “Not Ordered”, please select only “Not Started”.
- **Order Status** (dropdown): Choose “Ordered” if materials have been ordered.
- **Progress** (number): Enter a percentage (0–100). (If **Order Status** is “Not Ordered” or **Status** is “Not Started”, progress will be forced to 0.)
""")
# Configure column editors with tooltips.
column_config = {
    "Activity": st.column_config.SelectboxColumn(
         "Activity",
         options=sorted(st.session_state.df["Activity"].dropna().unique()),
         help="Select an activity. You may type a new value if needed."
    ),
    "Item": st.column_config.SelectboxColumn(
         "Item",
         options=sorted(st.session_state.df["Item"].dropna().unique()),
         help="Select an item. You may type a new value if needed."
    ),
    "Task": st.column_config.SelectboxColumn(
         "Task",
         options=sorted(st.session_state.df["Task"].dropna().unique()),
         help="Select a task. You may type a new value if needed."
    ),
    "Room": st.column_config.SelectboxColumn(
         "Room",
         options=sorted(st.session_state.df["Room"].dropna().unique()),
         help="Select a room. You may type a new value if needed."
    ),
    "Status": st.column_config.SelectboxColumn(
         "Status",
         options=["Finished", "In Progress", "Not Started", "Delivered", "Not Delivered"],
         help="If Order Status is 'Not Ordered', only 'Not Started' is allowed."
    ),
    "Order Status": st.column_config.SelectboxColumn(
         "Order Status",
         options=["Ordered", "Not Ordered"],
         help="Select 'Ordered' if materials have been ordered, otherwise 'Not Ordered'."
    ),
    "Progress": st.column_config.NumberColumn(
         "Progress",
         help="Enter progress as a percentage (0-100).",
         min_value=0,
         max_value=100,
         step=1
    )
}

edited_df = st.data_editor(st.session_state.df, use_container_width=True, num_rows=st.session_state.df.shape[0], column_config=column_config)
st.session_state.df = edited_df  # update session state with latest edits

##############################################
# Save Updates Button – Enforce Logic and Save
##############################################

if st.button("Save Updates"):
    st.session_state.df = enforce_logic(st.session_state.df)
    save_data(st.session_state.df, DATA_FILE)
    # Note: The app does not call st.experimental_rerun; refresh the page if needed.

##############################################
# Dashboard Overview
##############################################

st.header("Dashboard Overview")

# 1) Snapshot of Filtered Data
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
not_declared = st.session_state.df[~st.session_state.df["Status"].str.strip().str.lower().isin(["finished", "in progress", "delivered", "not started"])].shape[0]

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
