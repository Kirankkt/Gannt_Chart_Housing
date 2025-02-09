import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from datetime import datetime
from docx import Document

# ---------------------------------------------------
# App Configuration
# ---------------------------------------------------
st.set_page_config(page_title="Construction Project Manager Dashboard", layout="wide")
st.title("Construction Project Manager Dashboard")
st.markdown(
    "This dashboard provides an overview of the construction project, including task snapshots, timeline visualization, and progress tracking. Use the sidebar to filter and update data."
)

# ---------------------------------------------------
# 1. Data Loading from Excel
# ---------------------------------------------------
@st.cache_data
def load_data(file_path):
    if not os.path.exists(file_path):
        st.error(f"File {file_path} not found!")
        st.stop()
    df = pd.read_excel(file_path)
    # Clean column names
    df.columns = df.columns.str.strip()
    # Convert date columns
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    # Ensure Status is a string
    df["Status"] = df["Status"].astype(str)
    # --- NEW COLUMNS ---
    # Add a new column "Order Status" if not present, defaulting to "Not Ordered"
    if "Order Status" not in df.columns:
        df["Order Status"] = "Not Ordered"
    # Add a new column "Progress" if not present, defaulting to 0
    if "Progress" not in df.columns:
        df["Progress"] = 0
    # Ensure "Progress" is numeric
    df["Progress"] = pd.to_numeric(df["Progress"], errors="coerce").fillna(0)
    return df

DATA_FILE = "construction_timeline.xlsx"
df = load_data(DATA_FILE)

# ---------------------------------------------------
# 2. Data Editing Section (Including New Rows)
# ---------------------------------------------------
st.subheader("Update Task Information")
st.markdown(
    """
    **Instructions:**
    - Update any field below.  
    - For **Status**, choose one of the following:  
      **Finished**, **In Progress**, **Not Started**, **Delivered**, **Not Delivered**.
    - For **Order Status**, select **Ordered** or **Not Ordered**.
    - For **Progress**, enter the completion percentage (0–100).
    - You can add new rows using the editor (the table will grow as needed).
    """
)

# Configure columns to use custom widgets
column_config = {
    "Status": st.column_config.SelectboxColumn(
        "Status",
        options=["Finished", "In Progress", "Not Started", "Delivered", "Not Delivered"],
        help="Select the current status of the task."
    ),
    "Order Status": st.column_config.SelectboxColumn(
        "Order Status",
        options=["Ordered", "Not Ordered"],
        help="Indicate if the task/material has been ordered."
    ),
    "Progress": st.column_config.NumberColumn(
        "Progress",
        help="Enter the progress percentage (0-100).",
        min_value=0,
        max_value=100,
        step=1
    )
}

# Enable dynamic rows to let users add new rows
edited_df = st.data_editor(
    df, 
    column_config=column_config, 
    use_container_width=True, 
    num_rows="dynamic"
)

# Fill missing values for the updated columns
edited_df["Status"] = edited_df["Status"].fillna("Not Started").replace("", "Not Started")
edited_df["Order Status"] = edited_df["Order Status"].fillna("Not Ordered").replace("", "Not Ordered")
edited_df["Progress"] = pd.to_numeric(edited_df["Progress"], errors="coerce").fillna(0)

# ---------------------------------------------------
# 2a. Save Updates Button
# ---------------------------------------------------
if st.button("Save Updates"):
    try:
        edited_df.to_excel(DATA_FILE, index=False)
        st.success("Data successfully saved!")
        load_data.clear()  # Clear cache so the next load uses updated data
    except Exception as e:
        st.error(f"Error saving data: {e}")

# ---------------------------------------------------
# 3. Sidebar Filters & Options
# ---------------------------------------------------
st.sidebar.header("Filter Options")

def norm_unique(col):
    return sorted(set(edited_df[col].dropna().astype(str).str.lower().str.strip()))

activity_options = norm_unique("Activity")
selected_activity_norm = st.sidebar.multiselect(
    "Select Activity (leave empty for all)",
    options=activity_options,
    default=[]
)

item_options = norm_unique("Item")
selected_item_norm = st.sidebar.multiselect(
    "Select Item (leave empty for all)",
    options=item_options,
    default=[]
)

task_options = norm_unique("Task")
selected_task_norm = st.sidebar.multiselect(
    "Select Task (leave empty for all)",
    options=task_options,
    default=[]
)

room_options = norm_unique("Room")
selected_room_norm = st.sidebar.multiselect(
    "Select Room (leave empty for all)",
    options=room_options,
    default=[]
)

status_options = norm_unique("Status")
selected_statuses = st.sidebar.multiselect(
    "Select Status (leave empty for all)",
    options=status_options,
    default=[]
)

order_status_options = norm_unique("Order Status")
selected_order_status = st.sidebar.multiselect(
    "Select Order Status (leave empty for all)",
    options=order_status_options,
    default=[]
)

show_finished = st.sidebar.checkbox("Show Finished/Delivered Tasks", value=True)
color_by_status = st.sidebar.checkbox("Color-code Gantt Chart by Activity Status", value=True)

st.sidebar.markdown("**Refine Gantt Grouping**")
group_by_room = st.sidebar.checkbox("Group by Room", value=False)
group_by_item = st.sidebar.checkbox("Group by Item", value=False)
group_by_task = st.sidebar.checkbox("Group by Task", value=False)

min_date = edited_df["Start Date"].min()
max_date = edited_df["End Date"].max()
selected_date_range = st.sidebar.date_input("Select Date Range", value=[min_date, max_date])

# ---------------------------------------------------
# 4. Filter the DataFrame Based on User Input
# ---------------------------------------------------
df_filtered = edited_df.copy()

# Create normalized columns for filtering
for col in ["Activity", "Item", "Task", "Room", "Status", "Order Status"]:
    df_filtered[col + "_norm"] = df_filtered[col].astype(str).str.lower().str.strip()

if selected_activity_norm:
    df_filtered = df_filtered[df_filtered["Activity_norm"].isin(selected_activity_norm)]
if selected_item_norm:
    df_filtered = df_filtered[df_filtered["Item_norm"].isin(selected_item_norm)]
if selected_task_norm:
    df_filtered = df_filtered[df_filtered["Task_norm"].isin(selected_task_norm)]
if selected_room_norm:
    df_filtered = df_filtered[df_filtered["Room_norm"].isin(selected_room_norm)]
if selected_statuses:
    df_filtered = df_filtered[df_filtered["Status_norm"].isin(selected_statuses)]
if selected_order_status:
    df_filtered = df_filtered[df_filtered["Order Status_norm"].isin(selected_order_status)]
if not show_finished:
    df_filtered = df_filtered[~df_filtered["Status_norm"].isin(["finished", "delivered"])]

if len(selected_date_range) == 2:
    start_range = pd.to_datetime(selected_date_range[0])
    end_range = pd.to_datetime(selected_date_range[1])
    df_filtered = df_filtered[
        (df_filtered["Start Date"] >= start_range) &
        (df_filtered["End Date"] <= end_range)
    ]

df_filtered.drop(columns=[c for c in df_filtered.columns if c.endswith("_norm")], inplace=True)

# ---------------------------------------------------
# 5. Gantt Chart Generation with Progress Display
# ---------------------------------------------------
def create_gantt_chart(df_input, color_by_status=False):
    """
    Build the grouping dynamically based on sidebar selections.
    Also aggregates the average progress for each group and displays it on the chart.
    """
    group_cols = ["Activity"]
    if group_by_room and "Room" in df_input.columns:
        group_cols.append("Room")
    if group_by_item and "Item" in df_input.columns:
        group_cols.append("Item")
    if group_by_task and "Task" in df_input.columns:
        group_cols.append("Task")
    
    if not group_cols:
        return px.scatter(title="No group columns selected")
    
    # Aggregate with the minimum start, maximum end, and average progress
    agg_dict = {
        "Start Date": "min",
        "End Date": "max",
        "Progress": "mean"
    }
    agg_df = df_input.groupby(group_cols).agg(agg_dict).reset_index()
    
    # Compute an aggregated status for the group (using custom logic)
    def compute_group_status(row):
        cond = True
        for g in group_cols:
            cond = cond & (df_input[g] == row[g])
        subset = df_input[cond]
        statuses = subset["Status"].str.strip().str.lower()
        now = pd.Timestamp(datetime.today().date())
        if "in progress" in statuses.values:
            return "In Progress"
        if all(status in ["finished", "delivered"] for status in statuses):
            max_end = subset["End Date"].dt.normalize().max()
            return "Finished On Time" if now <= max_end else "Finished Late"
        if all(status == "not started" for status in statuses):
            return "Not Started"
        min_start = subset["Start Date"].dt.normalize().min()
        return "Not Started" if now < min_start else "In Progress"
    
    if color_by_status:
        agg_df["Display Status"] = agg_df.apply(compute_group_status, axis=1)
        if len(group_cols) == 1:
            agg_df["Group Label"] = agg_df[group_cols[0]].astype(str)
        else:
            agg_df["Group Label"] = agg_df[group_cols].apply(lambda row: " | ".join(row.astype(str)), axis=1)
        color_discrete_map = {
            "Not Started": "lightgray",
            "In Progress": "blue",
            "Finished On Time": "green",
            "Finished Late": "orange"
        }
        fig = px.timeline(
            agg_df,
            x_start="Start Date",
            x_end="End Date",
            y="Group Label",
            color="Display Status",
            color_discrete_map=color_discrete_map,
            hover_data={"Progress": True},
            title="Project Timeline (Color-coded by Status)"
        )
    else:
        agg_df["Group Label"] = agg_df[group_cols].apply(lambda row: " | ".join(row.astype(str)), axis=1)
        fig = px.timeline(
            agg_df,
            x_start="Start Date",
            x_end="End Date",
            y="Group Label",
            color=group_cols[0],
            hover_data={"Progress": True},
            title="Project Timeline"
        )
    
    # Display the average progress (rounded to an integer percentage) on each bar
    fig.update_traces(text=agg_df["Progress"].round(0).astype(int).astype(str) + "%", textposition='inside')
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Timeline")
    return fig

gantt_fig = create_gantt_chart(df_filtered, color_by_status=color_by_status)

# ---------------------------------------------------
# 6. Overall Completion & Progress Calculation
# ---------------------------------------------------
total_tasks = edited_df.shape[0]
finished_tasks = edited_df[edited_df["Status"].str.strip().str.lower().isin(["finished", "delivered"])].shape[0]
completion_percentage = (finished_tasks / total_tasks) * 100 if total_tasks > 0 else 0

# Additional KPIs
tasks_in_progress = edited_df[edited_df["Status"].str.strip().str.lower() == "in progress"].shape[0]
not_declared = edited_df[~edited_df["Status"].str.strip().str.lower().isin(["finished", "in progress", "delivered", "not started"])].shape[0]

today = pd.Timestamp(datetime.today().date())
overdue_df = df_filtered[
    (df_filtered["End Date"] < today) & 
    (~df_filtered["Status"].str.strip().str.lower().isin(["finished", "delivered"]))
]
overdue_count = overdue_df.shape[0]

task_distribution = df_filtered.groupby("Activity").size().reset_index(name="Task Count")
dist_fig = px.bar(task_distribution, x="Activity", y="Task Count", title="Task Distribution by Activity")

upcoming_start = today
upcoming_end = today + pd.Timedelta(days=7)
upcoming_df = df_filtered[
    (df_filtered["Start Date"] >= upcoming_start) &
    (df_filtered["Start Date"] <= upcoming_end)
]

filter_summary = []
if selected_activity_norm:
    filter_summary.append("Activities: " + ", ".join([s.title() for s in selected_activity_norm]))
if selected_item_norm:
    filter_summary.append("Items: " + ", ".join([s.title() for s in selected_item_norm]))
if selected_task_norm:
    filter_summary.append("Tasks: " + ", ".join([s.title() for s in selected_task_norm]))
if selected_room_norm:
    filter_summary.append("Rooms: " + ", ".join([s.title() for s in selected_room_norm]))
if selected_statuses:
    filter_summary.append("Status: " + ", ".join(selected_statuses))
if selected_order_status:
    filter_summary.append("Order Status: " + ", ".join(selected_order_status))
if selected_date_range:
    filter_summary.append(f"Date Range: {selected_date_range[0]} to {selected_date_range[1]}")
filter_summary_text = "; ".join(filter_summary) if filter_summary else "No filters applied."

# ---------------------------------------------------
# 7. Dashboard Layout (Only Dashboard)
# ---------------------------------------------------
st.header("Dashboard Overview")

# Current Tasks Snapshot
st.subheader("Current Tasks Snapshot")
st.dataframe(df_filtered)

# Gantt Chart
st.subheader("Project Timeline")
st.plotly_chart(gantt_fig, use_container_width=True)

# KPI & Progress
st.metric("Overall Completion", f"{completion_percentage:.1f}%")
st.progress(completion_percentage / 100)

# Additional Insights
st.markdown("#### Additional Insights")
st.markdown(f"**Overdue Tasks:** {overdue_count}")
if not overdue_df.empty:
    st.dataframe(overdue_df[["Activity", "Room", "Task", "Status", "Order Status", "End Date"]])
st.markdown("**Task Distribution by Activity:**")
st.plotly_chart(dist_fig, use_container_width=True)
st.markdown("**Upcoming Tasks (Next 7 Days):**")
if not upcoming_df.empty:
    st.dataframe(upcoming_df[["Activity", "Room", "Task", "Start Date", "Status", "Order Status"]])
else:
    st.info("No upcoming tasks in the next 7 days.")
st.markdown("**Active Filters:**")
st.write(filter_summary_text)

col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
col_kpi1.metric("Total Tasks", total_tasks)
col_kpi2.metric("In Progress", tasks_in_progress)
col_kpi3.metric("Finished/Delivered", finished_tasks)
col_kpi4.metric("Not Declared", not_declared)

st.markdown("Use the filters on the sidebar to adjust the view.")
st.markdown("---")
st.markdown("CMBP Analytics Dashboard")
