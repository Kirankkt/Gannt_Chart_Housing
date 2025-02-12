import streamlit as st
import pandas as pd
import plotly.express as px
import io, os
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
# Hide the “This error should never happen” tooltip in st.data_editor
# (Known Streamlit bug)
# ---------------------------------------------------
hide_stdataeditor_bug_tooltip = """
<style>
/* Hide all tooltips within the data editor */
[data-testid="stDataEditor"] [role="tooltip"] {
    visibility: hidden !important;
}
</style>
"""
st.markdown(hide_stdataeditor_bug_tooltip, unsafe_allow_html=True)

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
    if "Start Date" in df.columns:
        df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    if "End Date" in df.columns:
        df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")

    # Ensure string columns
    for col in ["Status", "Activity", "Item", "Task", "Room"]:
        if col in df.columns:
            df[col] = df[col].astype(str)

    # Ensure these columns exist
    if "Order Status" not in df.columns:
        df["Order Status"] = "Not Ordered"
    if "Progress" not in df.columns:
        df["Progress"] = 0

    # Convert Progress to numeric safely
    df["Progress"] = pd.to_numeric(df["Progress"], errors="coerce").fillna(0)

    return df

DATA_FILE = "construction_timeline.xlsx"
df = load_data(DATA_FILE)

# ---------------------------------------------------
# 2. Data Editing Section (Allowing New Rows)
# ---------------------------------------------------
st.subheader("Update Task Information")

# --- Simple row/column management in the sidebar ---
with st.sidebar.expander("Row & Column Management"):
    st.markdown("**Delete a row by index**")
    delete_index = st.text_input("Enter row index to delete", value="")
    if st.button("Delete Row"):
        if delete_index.isdigit():
            idx = int(delete_index)
            if 0 <= idx < len(df):
                df.drop(df.index[idx], inplace=True)
                try:
                    df.to_excel(DATA_FILE, index=False)
                    st.sidebar.success(f"Row {idx} deleted and saved.")
                except Exception as e:
                    st.sidebar.error(f"Error saving data: {e}")
            else:
                st.sidebar.error("Invalid index.")
        else:
            st.sidebar.error("Please enter a valid integer index.")

    st.markdown("**Add a new column**")
    new_col_name = st.text_input("New Column Name", value="")
    new_col_type = st.selectbox("Column Type", ["string", "integer", "float", "datetime"])
    if st.button("Add Column"):
        if new_col_name and new_col_name not in df.columns:
            if new_col_type == "string":
                df[new_col_name] = ""
            elif new_col_type == "integer":
                df[new_col_name] = 0
            elif new_col_type == "float":
                df[new_col_name] = 0.0
            elif new_col_type == "datetime":
                df[new_col_name] = pd.NaT
            # Save the change:
            try:
                df.to_excel(DATA_FILE, index=False)
                st.sidebar.success(f"Column '{new_col_name}' added and saved.")
            except Exception as e:
                st.sidebar.error(f"Error saving data: {e}")
        elif new_col_name in df.columns:
            st.sidebar.warning("Column already exists or invalid name.")
        else:
            st.sidebar.warning("Please enter a valid column name.")

    st.markdown("**Delete a column**")
    col_to_delete = st.selectbox("Select Column to Delete", options=[""] + list(df.columns), index=0)
    if st.button("Delete Column"):
        if col_to_delete and col_to_delete in df.columns:
            df.drop(columns=[col_to_delete], inplace=True)
            try:
                df.to_excel(DATA_FILE, index=False)
                st.sidebar.success(f"Column '{col_to_delete}' deleted and saved.")
            except Exception as e:
                st.sidebar.error(f"Error saving data: {e}")
        else:
            st.sidebar.warning("Please select a valid column.")

# Configure column editors.
column_config = {}
if "Activity" in df.columns:
    column_config["Activity"] = st.column_config.SelectboxColumn(
        "Activity",
        options=sorted(df["Activity"].dropna().unique()),
        help="Select an existing activity."
    )
if "Item" in df.columns:
    column_config["Item"] = st.column_config.SelectboxColumn(
        "Item",
        options=sorted(df["Item"].dropna().unique()),
        help="Select an existing item."
    )
if "Task" in df.columns:
    column_config["Task"] = st.column_config.SelectboxColumn(
        "Task",
        options=sorted(df["Task"].dropna().unique()),
        help="Select an existing task."
    )
if "Room" in df.columns:
    column_config["Room"] = st.column_config.SelectboxColumn(
        "Room",
        options=sorted(df["Room"].dropna().unique()),
        help="Select an existing room."
    )
if "Status" in df.columns:
    column_config["Status"] = st.column_config.SelectboxColumn(
        "Status",
        options=["Finished", "In Progress", "Not Started", "Delivered", "Not Delivered"],
        help="Select the current status of the task."
    )
if "Order Status" in df.columns:
    column_config["Order Status"] = st.column_config.SelectboxColumn(
        "Order Status",
        options=["Ordered", "Not Ordered"],
        help="Indicate if the task/material has been ordered."
    )
if "Progress" in df.columns:
    column_config["Progress"] = st.column_config.NumberColumn(
        "Progress",
        help="Enter the progress percentage (0-100).",
        min_value=0,
        max_value=100,
        step=1
    )

# Render editable data table
edited_df = st.data_editor(
    df,
    column_config=column_config,
    use_container_width=True,
    num_rows="dynamic"
)

# Make sure newly-added rows have default status/order/progress
if "Status" in edited_df.columns:
    edited_df["Status"] = edited_df["Status"].fillna("Not Started").replace("", "Not Started")
if "Order Status" in edited_df.columns:
    edited_df["Order Status"] = edited_df["Order Status"].fillna("Not Ordered").replace("", "Not Ordered")
if "Progress" in edited_df.columns:
    edited_df["Progress"] = pd.to_numeric(edited_df["Progress"], errors="coerce").fillna(0)

# ---------------------------------------------------
# 2a. Save Updates Button
# ---------------------------------------------------
st.markdown(
    "**Note:** Once you click 'Save Updates', the Excel file is overwritten. "
    "Make sure you have reviewed your changes, as there's no built-in undo."
)
if st.button("Save Updates"):
    try:
        edited_df.to_excel(DATA_FILE, index=False)
        st.success("Data successfully saved!")
        load_data.clear()  # Clear cache so that new data is reloaded
    except Exception as e:
        st.error(f"Error saving data: {e}")

# ---------------------------------------------------
# 3. Sidebar Filters & "Clear Filters" Option
# ---------------------------------------------------
st.sidebar.header("Filter Options")

def norm_unique(df_input, col):
    """Return sorted unique normalized (lower-stripped) values from a column."""
    if col not in df_input.columns:
        return []
    return sorted(set(df_input[col].dropna().astype(str).str.lower().str.strip()))

# Initialize session state for filters
if "activity_filter" not in st.session_state:
    st.session_state["activity_filter"] = []
if "item_filter" not in st.session_state:
    st.session_state["item_filter"] = []
if "task_filter" not in st.session_state:
    st.session_state["task_filter"] = []
if "room_filter" not in st.session_state:
    st.session_state["room_filter"] = []
if "status_filter" not in st.session_state:
    st.session_state["status_filter"] = []
if "order_filter" not in st.session_state:
    st.session_state["order_filter"] = []
if "date_range" not in st.session_state:
    min_date = edited_df["Start Date"].min() if "Start Date" in edited_df.columns else datetime.today()
    max_date = edited_df["End Date"].max() if "End Date" in edited_df.columns else datetime.today()
    st.session_state["date_range"] = [min_date, max_date]

# Clear filters button
if st.sidebar.button("Clear Filters"):
    st.session_state["activity_filter"] = []
    st.session_state["item_filter"] = []
    st.session_state["task_filter"] = []
    st.session_state["room_filter"] = []
    st.session_state["status_filter"] = []
    st.session_state["order_filter"] = []
    min_date = edited_df["Start Date"].min() if "Start Date" in edited_df.columns else datetime.today()
    max_date = edited_df["End Date"].max() if "End Date" in edited_df.columns else datetime.today()
    st.session_state["date_range"] = [min_date, max_date]

activity_options = norm_unique(edited_df, "Activity")
selected_activity_norm = st.sidebar.multiselect(
    "Select Activity (leave empty for all)",
    options=activity_options,
    default=st.session_state["activity_filter"],
    key="activity_filter"
)

item_options = norm_unique(edited_df, "Item")
selected_item_norm = st.sidebar.multiselect(
    "Select Item (leave empty for all)",
    options=item_options,
    default=st.session_state["item_filter"],
    key="item_filter"
)

task_options = norm_unique(edited_df, "Task")
selected_task_norm = st.sidebar.multiselect(
    "Select Task (leave empty for all)",
    options=task_options,
    default=st.session_state["task_filter"],
    key="task_filter"
)

room_options = norm_unique(edited_df, "Room")
selected_room_norm = st.sidebar.multiselect(
    "Select Room (leave empty for all)",
    options=room_options,
    default=st.session_state["room_filter"],
    key="room_filter"
)

status_options = norm_unique(edited_df, "Status")
selected_statuses = st.sidebar.multiselect(
    "Select Status (leave empty for all)",
    options=status_options,
    default=st.session_state["status_filter"],
    key="status_filter"
)

order_status_options = norm_unique(edited_df, "Order Status")
selected_order_status = st.sidebar.multiselect(
    "Select Order Status (leave empty for all)",
    options=order_status_options,
    default=st.session_state["order_filter"],
    key="order_filter"
)

show_finished = st.sidebar.checkbox("Show Finished/Delivered Tasks", value=True)
color_by_status = st.sidebar.checkbox("Color-code Gantt Chart by Status", value=True)

st.sidebar.markdown("**Refine Gantt Grouping**")
group_by_room = st.sidebar.checkbox("Group by Room", value=False)
group_by_item = st.sidebar.checkbox("Group by Item", value=False)
group_by_task = st.sidebar.checkbox("Group by Task", value=False)

# Date range
default_min, default_max = st.session_state["date_range"]
selected_date_range = st.sidebar.date_input(
    "Select Date Range",
    value=[default_min, default_max],
    key="date_range"
)

# ---------------------------------------------------
# 4. Filtering the DataFrame Based on User Input
# ---------------------------------------------------
df_filtered = edited_df.copy()

# Only proceed if the necessary columns exist
necessary_cols = {"Start Date", "End Date", "Status", "Order Status", "Progress"}
if not necessary_cols.issubset(df_filtered.columns):
    st.warning("Your data is missing some necessary columns for the Gantt chart. Please ensure it has Start Date, End Date, Status, Order Status, Progress, etc.")
    st.stop()

# Create normalized columns for filtering
for col in ["Activity", "Item", "Task", "Room", "Status", "Order Status"]:
    if col in df_filtered.columns:
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
    # Exclude tasks with status in ["finished", "delivered"]
    df_filtered = df_filtered[~df_filtered["Status_norm"].isin(["finished", "delivered"])]

# Filter by date range
if len(selected_date_range) == 2:
    start_range = pd.to_datetime(selected_date_range[0])
    end_range = pd.to_datetime(selected_date_range[1])
    df_filtered = df_filtered[
        (df_filtered["Start Date"] >= start_range) &
        (df_filtered["End Date"] <= end_range)
    ]

# Drop the temp normalized columns
to_drop_norm = [c for c in df_filtered.columns if c.endswith("_norm")]
df_filtered.drop(columns=to_drop_norm, inplace=True, errors="ignore")

# ---------------------------------------------------
# 5. Revised Gantt Chart Generation with Enhanced Color Logic
# ---------------------------------------------------
def create_gantt_chart(df_input, color_by_status=False):
    """
    Create a Gantt chart from df_input, aggregating by selected grouping columns.
    - If df_input is empty, return an empty figure (no error).
    - Aggregates (min Start, max End, mean Progress) by group.
    - Derives an 'Aggregated Status' for color coding.
    """

    if df_input.empty:
        return px.scatter(title="No data to display for Gantt")

    # Build grouping columns dynamically
    group_cols = ["Activity"]  # base group by Activity
    if group_by_room and "Room" in df_input.columns:
        group_cols.append("Room")
    if group_by_item and "Item" in df_input.columns:
        group_cols.append("Item")
    if group_by_task and "Task" in df_input.columns:
        group_cols.append("Task")

    if not group_cols:
        return px.scatter(title="No group columns selected.")

    # Aggregate
    agg_dict = {
        "Start Date": "min",
        "End Date": "max",
        "Progress": "mean"
    }
    grouped = df_input.groupby(group_cols, dropna=False).agg(agg_dict).reset_index()
    grouped.rename(columns={
        "Start Date":"GroupStart",
        "End Date":"GroupEnd",
        "Progress":"AvgProgress"
    }, inplace=True)

    # Determine an aggregated status for each group
    now = pd.Timestamp(datetime.today().date())

    def get_aggregated_status(subset_df, avg_progress, end_date):
        # Only "finished" → "Finished" (green)
        # end_date < now and progress < 100 → "Delayed" (red)
        # any "in progress" → "In Progress" (splitting bar)
        # else → "Not Started / Delivered / Not Delivered" (gray)
        statuses = subset_df["Status"].str.strip().str.lower()
        # all tasks are strictly "finished"?
        all_finished = all(s == "finished" for s in statuses)

        if all_finished or avg_progress >= 100:
            return "Finished"
        if end_date < now and avg_progress < 100:
            return "Delayed"
        if "in progress" in statuses.values:
            return "In Progress"
        return "Not Started / Delivered / Not Delivered"

    # Build timeline segments
    gantt_segments = []
    for idx, row in grouped.iterrows():
        # Subset the original DF to see if any tasks are "in progress", etc.
        cond = True
        for gcol in group_cols:
            cond &= (df_input[gcol] == row[gcol])
        subset = df_input[cond]

        group_status = get_aggregated_status(
            subset_df=subset,
            avg_progress=row["AvgProgress"],
            end_date=row["GroupEnd"]
        )
        group_label = " | ".join([str(row[g]) for g in group_cols])
        start = row["GroupStart"]
        end = row["GroupEnd"]
        avg_prog = row["AvgProgress"]

        if group_status == "In Progress" and 0 < avg_prog < 100:
            total_duration = (end - start).total_seconds()
            completed_duration = total_duration * (avg_prog / 100.0)
            completed_end = start + pd.Timedelta(seconds=completed_duration)

            # Segment 1: Completed portion (darkblue), show e.g. "7%"
            gantt_segments.append({
                "Group Label": group_label,
                "Start": start,
                "End": completed_end,
                "Display Status": "In Progress (Completed part)",
                "Progress": f"{avg_prog:.0f}%"
            })

            # Segment 2: Remaining portion (lightgray), e.g. "93%"
            remain_pct = 100 - avg_prog
            gantt_segments.append({
                "Group Label": group_label,
                "Start": completed_end,
                "End": end,
                "Display Status": "In Progress (Remaining part)",
                "Progress": f"{remain_pct:.0f}%"
            })
        else:
            # Single segment for Finished, Delayed, Not Started, Delivered, etc.
            gantt_segments.append({
                "Group Label": group_label,
                "Start": start,
                "End": end,
                "Display Status": group_status,
                "Progress": f"{avg_prog:.0f}%"
            })

    gantt_df = pd.DataFrame(gantt_segments)
    if gantt_df.empty:
        return px.scatter(title="No data after grouping.")

    # Define final color mapping
    color_map = {
        "Not Started / Delivered / Not Delivered": "lightgray",
        "In Progress (Completed part)": "darkblue",
        "In Progress (Remaining part)": "lightgray",
        "Finished": "green",
        "Delayed": "red"
    }

    fig = px.timeline(
        gantt_df,
        x_start="Start",
        x_end="End",
        y="Group Label",
        text="Progress",
        color="Display Status",
        color_discrete_map=color_map
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Timeline", showlegend=True)

    return fig

gantt_fig = create_gantt_chart(df_filtered, color_by_status=color_by_status)

# ---------------------------------------------------
# 6. Overall Completion & Progress Calculation
# ---------------------------------------------------
total_tasks = edited_df.shape[0]
finished_tasks = edited_df[
    edited_df["Status"].str.strip().str.lower() == "finished"
].shape[0]
completion_percentage = (finished_tasks / total_tasks) * 100 if total_tasks > 0 else 0

tasks_in_progress = edited_df[
    edited_df["Status"].str.strip().str.lower() == "in progress"
].shape[0]

not_declared = edited_df[
    ~edited_df["Status"].str.strip().str.lower().isin(
        ["finished", "in progress", "delivered", "not started"]
    )
].shape[0]

today = pd.Timestamp(datetime.today().date())
overdue_df = df_filtered[
    (df_filtered["End Date"] < today)
    & (~df_filtered["Status"].str.strip().str.lower().isin(["finished"]))
]
overdue_count = overdue_df.shape[0]

if "Activity" in df_filtered.columns:
    task_distribution = df_filtered.groupby("Activity").size().reset_index(name="Task Count")
    dist_fig = px.bar(task_distribution, x="Activity", y="Task Count", title="Task Distribution by Activity")
else:
    dist_fig = px.bar(title="No 'Activity' column to show distribution.")

# Next 7 days
upcoming_start = today
upcoming_end = today + pd.Timedelta(days=7)
upcoming_df = df_filtered[
    (df_filtered["Start Date"] >= upcoming_start)
    & (df_filtered["Start Date"] <= upcoming_end)
] if "Start Date" in df_filtered.columns else pd.DataFrame()

# Build filter summary text
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
if len(selected_date_range) == 2:
    filter_summary.append(f"Date Range: {selected_date_range[0]} to {selected_date_range[1]}")

filter_summary_text = "; ".join(filter_summary) if filter_summary else "No filters applied."

# ---------------------------------------------------
# 7. Dashboard Layout
# ---------------------------------------------------
st.header("Dashboard Overview")

# 1) Current Tasks Snapshot
st.subheader("Current Tasks Snapshot")
st.dataframe(df_filtered)

# 2) Gantt Chart
st.subheader("Project Timeline")
st.plotly_chart(gantt_fig, use_container_width=True)

# 3) KPI & Progress
st.metric("Overall Completion", f"{completion_percentage:.1f}%")
st.progress(completion_percentage / 100)

# 4) Additional Insights
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
col_kpi3.metric("Finished", finished_tasks)
col_kpi4.metric("Not Declared", not_declared)

st.markdown("Use the filters on the sidebar to adjust the view.")
st.markdown("---")
st.markdown("CMBP Analytics Dashboard")
