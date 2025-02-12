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
# 1. Load Main Timeline Data (Excel)
# ---------------------------------------------------
@st.cache_data
def load_timeline_data(file_path):
    if not os.path.exists(file_path):
        st.error(f"File '{file_path}' not found!")
        st.stop()

    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()  # Clean column names

    # Convert date columns if they exist
    if "Start Date" in df.columns:
        df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    if "End Date" in df.columns:
        df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")

    # If "Progress" is missing, create it with default 0
    if "Progress" not in df.columns:
        df["Progress"] = 0.0

    # If "Status" is missing, create it with default "Not Started"
    if "Status" not in df.columns:
        df["Status"] = "Not Started"

    # Convert "Progress" to numeric
    df["Progress"] = pd.to_numeric(df["Progress"], errors="coerce").fillna(0)

    # Remove any "Order Status" from main table
    if "Order Status" in df.columns:
        df.drop(columns=["Order Status"], inplace=True)

    # Force "Status" to be one of ["Finished", "In Progress", "Not Started"] (case-insensitive)
    df["Status"] = df["Status"].astype(str).str.strip()
    valid_statuses = {"finished", "in progress", "not started"}
    df.loc[~df["Status"].str.lower().isin(valid_statuses), "Status"] = "Not Started"

    return df

DATA_FILE = "construction_timeline.xlsx"  # Main timeline Excel
df_main = load_timeline_data(DATA_FILE)

# ---------------------------------------------------
# 2. Update Task Information (Main Table)
# ---------------------------------------------------
st.subheader("Update Task Information (Main Timeline)")

with st.sidebar.expander("Row & Column Management (Main Timeline)"):
    st.markdown("**Delete a row by index**")
    delete_index = st.text_input("Enter row index to delete", value="")
    if st.button("Delete Row", key="delete_main_row"):
        if delete_index.isdigit():
            idx = int(delete_index)
            if 0 <= idx < len(df_main):
                df_main.drop(df_main.index[idx], inplace=True)
                try:
                    df_main.to_excel(DATA_FILE, index=False)
                    st.sidebar.success(f"Row {idx} deleted and saved.")
                except Exception as e:
                    st.sidebar.error(f"Error saving data: {e}")
            else:
                st.sidebar.error("Invalid index.")
        else:
            st.sidebar.error("Please enter a valid integer index.")

    st.markdown("**Add a new column**")
    new_col_name = st.text_input("New Column Name (main table)", value="")
    new_col_type = st.selectbox("Column Type (main table)", ["string", "integer", "float", "datetime"])
    if st.button("Add Column", key="add_main_col"):
        if new_col_name and new_col_name not in df_main.columns:
            if new_col_type == "string":
                df_main[new_col_name] = ""
            elif new_col_type == "integer":
                df_main[new_col_name] = 0
            elif new_col_type == "float":
                df_main[new_col_name] = 0.0
            elif new_col_type == "datetime":
                df_main[new_col_name] = pd.NaT
            try:
                df_main.to_excel(DATA_FILE, index=False)
                st.sidebar.success(f"Column '{new_col_name}' added and saved.")
            except Exception as e:
                st.sidebar.error(f"Error saving data: {e}")
        elif new_col_name in df_main.columns:
            st.sidebar.warning("Column already exists or invalid name.")
        else:
            st.sidebar.warning("Please enter a valid column name.")

    st.markdown("**Delete a column**")
    col_to_delete = st.selectbox(
        "Select Column to Delete (main table)",
        options=[""] + list(df_main.columns),
        index=0
    )
    if st.button("Delete Column", key="del_main_col"):
        if col_to_delete and col_to_delete in df_main.columns:
            df_main.drop(columns=[col_to_delete], inplace=True)
            try:
                df_main.to_excel(DATA_FILE, index=False)
                st.sidebar.success(f"Column '{col_to_delete}' deleted and saved.")
            except Exception as e:
                st.sidebar.error(f"Error saving data: {e}")
        else:
            st.sidebar.warning("Please select a valid column.")

# Configure main table columns in st.data_editor
column_config_main = {}
if "Activity" in df_main.columns:
    column_config_main["Activity"] = st.column_config.SelectboxColumn(
        "Activity",
        options=sorted(df_main["Activity"].dropna().unique()),
        help="Select an existing activity."
    )
if "Item" in df_main.columns:
    column_config_main["Item"] = st.column_config.SelectboxColumn(
        "Item",
        options=sorted(df_main["Item"].dropna().unique()),
        help="Select an existing item."
    )
if "Task" in df_main.columns:
    column_config_main["Task"] = st.column_config.SelectboxColumn(
        "Task",
        options=sorted(df_main["Task"].dropna().unique()),
        help="Select an existing task."
    )
if "Room" in df_main.columns:
    column_config_main["Room"] = st.column_config.SelectboxColumn(
        "Room",
        options=sorted(df_main["Room"].dropna().unique()),
        help="Select an existing room."
    )
if "Status" in df_main.columns:
    # Only allow 3 states in main table
    column_config_main["Status"] = st.column_config.SelectboxColumn(
        "Status",
        options=["Finished", "In Progress", "Not Started"],
        help="Set the status of the task."
    )
if "Progress" in df_main.columns:
    column_config_main["Progress"] = st.column_config.NumberColumn(
        "Progress",
        help="Enter the progress percentage (0-100).",
        min_value=0,
        max_value=100,
        step=1
    )

# Editable table for main timeline
edited_df_main = st.data_editor(
    df_main,
    column_config=column_config_main,
    use_container_width=True,
    num_rows="dynamic"
)

# Ensure valid defaults
if "Status" in edited_df_main.columns:
    valid_states = {"Finished", "In Progress", "Not Started"}
    # Fill any invalid status with "Not Started"
    edited_df_main.loc[~edited_df_main["Status"].isin(valid_states), "Status"] = "Not Started"
if "Progress" in edited_df_main.columns:
    edited_df_main["Progress"] = pd.to_numeric(edited_df_main["Progress"], errors="coerce").fillna(0)

# Save button for main timeline
st.markdown(
    "**Note:** Clicking 'Save Updates' overwrites the Excel file for the main timeline. "
    "Review changes carefully—there is no built-in undo."
)
if st.button("Save Updates (Main Timeline)"):
    try:
        edited_df_main.to_excel(DATA_FILE, index=False)
        st.success("Main timeline data successfully saved!")
        load_timeline_data.clear()  # Clear cache so next load refreshes
    except Exception as e:
        st.error(f"Error saving data: {e}")

# ---------------------------------------------------
# 3. Sidebar Filters & "Clear Filters" (Main)
# ---------------------------------------------------
st.sidebar.header("Filter Options (Main Timeline)")

def norm_unique(df_input, col):
    """Return sorted unique normalized (lower-stripped) values from a column."""
    if col not in df_input.columns:
        return []
    return sorted(set(df_input[col].dropna().astype(str).str.lower().str.strip()))

# Initialize session for filters
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
if "date_range" not in st.session_state:
    if "Start Date" in edited_df_main.columns:
        min_date = edited_df_main["Start Date"].min()
        max_date = edited_df_main["End Date"].max()
    else:
        min_date = datetime.today()
        max_date = datetime.today()
    st.session_state["date_range"] = [min_date, max_date]

# Clear filters button
if st.sidebar.button("Clear Filters (Main)"):
    st.session_state["activity_filter"] = []
    st.session_state["item_filter"] = []
    st.session_state["task_filter"] = []
    st.session_state["room_filter"] = []
    st.session_state["status_filter"] = []
    if "Start Date" in edited_df_main.columns:
        st.session_state["date_range"] = [
            edited_df_main["Start Date"].min(),
            edited_df_main["End Date"].max()
        ]
    else:
        st.session_state["date_range"] = [datetime.today(), datetime.today()]

# Build sidebars
activity_opts = norm_unique(edited_df_main, "Activity")
selected_activity_norm = st.sidebar.multiselect(
    "Filter by Activity",
    options=activity_opts,
    default=st.session_state["activity_filter"],
    key="activity_filter"
)
item_opts = norm_unique(edited_df_main, "Item")
selected_item_norm = st.sidebar.multiselect(
    "Filter by Item",
    options=item_opts,
    default=st.session_state["item_filter"],
    key="item_filter"
)
task_opts = norm_unique(edited_df_main, "Task")
selected_task_norm = st.sidebar.multiselect(
    "Filter by Task",
    options=task_opts,
    default=st.session_state["task_filter"],
    key="task_filter"
)
room_opts = norm_unique(edited_df_main, "Room")
selected_room_norm = st.sidebar.multiselect(
    "Filter by Room",
    options=room_opts,
    default=st.session_state["room_filter"],
    key="room_filter"
)
status_opts = norm_unique(edited_df_main, "Status")
selected_statuses = st.sidebar.multiselect(
    "Filter by Status",
    options=status_opts,
    default=st.session_state["status_filter"],
    key="status_filter"
)

show_finished = st.sidebar.checkbox("Show Finished Tasks", value=True)
color_by_status = st.sidebar.checkbox("Color-code Gantt Chart by Status", value=True)

st.sidebar.markdown("**Refine Gantt Grouping**")
group_by_room = st.sidebar.checkbox("Group by Room", value=False)
group_by_item = st.sidebar.checkbox("Group by Item", value=False)
group_by_task = st.sidebar.checkbox("Group by Task", value=False)

# Date range
default_min, default_max = st.session_state["date_range"]
selected_date_range = st.sidebar.date_input(
    "Filter Date Range",
    value=[default_min, default_max],
    key="date_range"
)

# ---------------------------------------------------
# 4. Filtering the DataFrame for the Gantt
# ---------------------------------------------------
df_filtered = edited_df_main.copy()

# Build normalized columns for filtering
for c in ["Activity", "Item", "Task", "Room", "Status"]:
    if c in df_filtered.columns:
        df_filtered[c + "_norm"] = df_filtered[c].astype(str).str.lower().str.strip()

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
if not show_finished:
    # Exclude tasks with status = "finished"
    df_filtered = df_filtered[~df_filtered["Status_norm"].isin(["finished"])]

# Filter by date range
if "Start Date" in df_filtered.columns and "End Date" in df_filtered.columns:
    if len(selected_date_range) == 2:
        start_range = pd.to_datetime(selected_date_range[0])
        end_range = pd.to_datetime(selected_date_range[1])
        df_filtered = df_filtered[
            (df_filtered["Start Date"] >= start_range) &
            (df_filtered["End Date"] <= end_range)
        ]

# Drop the temp norm columns
norm_cols = [x for x in df_filtered.columns if x.endswith("_norm")]
df_filtered.drop(columns=norm_cols, inplace=True, errors="ignore")

# ---------------------------------------------------
# 5. Gantt Chart Function
# ---------------------------------------------------
def create_gantt_chart(df_input, color_by_status=False):
    """
    Create a Gantt chart from df_input, requiring columns:
      'Start Date', 'End Date', 'Status', 'Progress' (float).
    Groups by Activity, plus optional (Room, Item, Task).
    """
    needed_cols = ["Start Date", "End Date", "Status", "Progress"]
    for ncol in needed_cols:
        if ncol not in df_input.columns:
            return px.scatter(title=f"Missing '{ncol}' for Gantt chart")

    if df_input.empty:
        return px.scatter(title="No data to display for Gantt")

    group_cols = ["Activity"]
    if group_by_room and "Room" in df_input.columns:
        group_cols.append("Room")
    if group_by_item and "Item" in df_input.columns:
        group_cols.append("Item")
    if group_by_task and "Task" in df_input.columns:
        group_cols.append("Task")

    if not group_cols:
        return px.scatter(title="No group columns selected for Gantt")

    grouped = (
        df_input
        .groupby(group_cols, dropna=False)
        .agg({
            "Start Date": "min",
            "End Date": "max",
            "Progress": "mean",
            "Status": lambda s: list(s)  # gather statuses
        })
        .reset_index()
    )
    grouped.rename(
        columns={
            "Start Date": "GroupStart",
            "End Date": "GroupEnd",
            "Progress": "AvgProgress",
            "Status": "AllStatuses"
        },
        inplace=True
    )

    now = pd.Timestamp(datetime.today().date())

    def aggregated_status(st_list, avg_prog, end_dt):
        all_lower = [x.lower().strip() for x in st_list]
        # If all tasks are "finished" => "Finished"
        # If end_dt < now & avg_prog < 100 => "Delayed"
        # If any "in progress" => "In Progress"
        # else => "Not Started"
        if all(s == "finished" for s in all_lower) or avg_prog >= 100:
            return "Finished"
        if end_dt < now and avg_prog < 100:
            return "Delayed"
        if "in progress" in all_lower:
            return "In Progress"
        return "Not Started"

    gantt_data = []
    for _, row in grouped.iterrows():
        group_label = " | ".join([str(row[g]) for g in group_cols])
        start = row["GroupStart"]
        end = row["GroupEnd"]
        avg_prog = row["AvgProgress"]
        st_list = row["AllStatuses"]

        agg_st = aggregated_status(st_list, avg_prog, end)
        if agg_st == "In Progress" and 0 < avg_prog < 100:
            total_secs = (end - start).total_seconds()
            done_secs = total_secs * (avg_prog / 100.0)
            done_end = start + pd.Timedelta(seconds=done_secs)

            # Completed part
            gantt_data.append({
                "Group Label": group_label,
                "Start": start,
                "End": done_end,
                "Display Status": "In Progress (Completed part)",
                "Progress": f"{avg_prog:.0f}%"
            })
            # Remaining
            remain_pct = 100 - avg_prog
            gantt_data.append({
                "Group Label": group_label,
                "Start": done_end,
                "End": end,
                "Display Status": "In Progress (Remaining part)",
                "Progress": f"{remain_pct:.0f}%"
            })
        else:
            gantt_data.append({
                "Group Label": group_label,
                "Start": start,
                "End": end,
                "Display Status": agg_st,
                "Progress": f"{avg_prog:.0f}%"
            })

    gantt_df = pd.DataFrame(gantt_data)
    if gantt_df.empty:
        return px.scatter(title="No data after grouping for Gantt")

    color_map = {
        "Not Started": "lightgray",
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
    fig.update_layout(
        xaxis_title="Timeline",
        showlegend=True
    )
    return fig

# Build the Gantt
gantt_fig = create_gantt_chart(df_filtered, color_by_status=color_by_status)

# ---------------------------------------------------
# 6. Overall Completion & Progress Calculation
# ---------------------------------------------------
total_tasks = len(edited_df_main)
finished_tasks = edited_df_main[edited_df_main["Status"].str.lower() == "finished"].shape[0]
completion_percentage = (finished_tasks / total_tasks * 100) if total_tasks else 0

in_progress_tasks = edited_df_main[edited_df_main["Status"].str.lower() == "in progress"].shape[0]
not_started_tasks = edited_df_main[edited_df_main["Status"].str.lower() == "not started"].shape[0]

today = pd.Timestamp(datetime.today().date())
if "End Date" in df_filtered.columns:
    overdue_df = df_filtered[
        (df_filtered["End Date"] < today)
        & (df_filtered["Status"].str.lower() != "finished")
    ]
    overdue_count = overdue_df.shape[0]
else:
    overdue_df = pd.DataFrame()
    overdue_count = 0

if "Activity" in df_filtered.columns:
    dist_table = df_filtered.groupby("Activity").size().reset_index(name="Task Count")
    dist_fig = px.bar(dist_table, x="Activity", y="Task Count", title="Task Distribution by Activity")
else:
    dist_fig = px.bar(title="No 'Activity' column to show distribution.")

# Next 7 Days
if "Start Date" in df_filtered.columns:
    upcoming_df = df_filtered[
        (df_filtered["Start Date"] >= today)
        & (df_filtered["Start Date"] <= today + pd.Timedelta(days=7))
    ]
else:
    upcoming_df = pd.DataFrame()

# Build filter summary text
filter_summary = []
if selected_activity_norm:
    filter_summary.append("Activities: " + ", ".join(selected_activity_norm))
if selected_item_norm:
    filter_summary.append("Items: " + ", ".join(selected_item_norm))
if selected_task_norm:
    filter_summary.append("Tasks: " + ", ".join(selected_task_norm))
if selected_room_norm:
    filter_summary.append("Rooms: " + ", ".join(selected_room_norm))
if selected_statuses:
    filter_summary.append("Status: " + ", ".join(selected_statuses))
if len(selected_date_range) == 2:
    filter_summary.append(f"Date Range: {selected_date_range[0]} to {selected_date_range[1]}")
filter_summary_text = "; ".join(filter_summary) if filter_summary else "No filters applied."

# ---------------------------------------------------
# 7. Dashboard Layout (Main Timeline)
# ---------------------------------------------------
st.header("Dashboard Overview (Main Timeline)")

st.subheader("Current Tasks Snapshot")
st.dataframe(df_filtered)

st.subheader("Project Timeline")
st.plotly_chart(gantt_fig, use_container_width=True)

# KPI & Progress
st.metric("Overall Completion (%)", f"{completion_percentage:.1f}%")
st.progress(completion_percentage / 100)

st.markdown("#### Additional Insights")
st.markdown(f"**Overdue Tasks:** {overdue_count}")
if not overdue_df.empty:
    st.dataframe(overdue_df[["Activity", "Room", "Task", "Status", "End Date"]])

st.markdown("**Task Distribution by Activity:**")
st.plotly_chart(dist_fig, use_container_width=True)

st.markdown("**Upcoming Tasks (Next 7 Days):**")
if not upcoming_df.empty:
    st.dataframe(upcoming_df[["Activity", "Room", "Task", "Start Date", "Status"]])
else:
    st.info("No upcoming tasks in the next 7 days.")

st.markdown("**Active Filters (Main Timeline):**")
st.write(filter_summary_text)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Tasks", total_tasks)
k2.metric("In Progress", in_progress_tasks)
k3.metric("Finished", finished_tasks)
k4.metric("Not Started", not_started_tasks)

st.markdown("Use the filters on the sidebar to adjust the view.")
st.markdown("---")

# ---------------------------------------------------
# 8. SECOND TABLE: Items to Order (CSV)
# ---------------------------------------------------
@st.cache_data
def load_items_data(file_path):
    if os.path.exists(file_path):
        df_items = pd.read_csv(file_path)
    else:
        # Create empty with needed columns
        df_items = pd.DataFrame(columns=["Item", "Quantity", "Order Status", "Delivery Status", "Notes"])
    return df_items

ITEMS_FILE = "Cleaned_Items_Table.csv"

st.header("Items to Order")

df_items = load_items_data(ITEMS_FILE)

# Configure columns for the items table
items_col_config = {}
if "Order Status" in df_items.columns:
    items_col_config["Order Status"] = st.column_config.SelectboxColumn(
        "Order Status",
        options=["Ordered", "Not Ordered"],
        help="Choose if this item is ordered or not."
    )
if "Delivery Status" in df_items.columns:
    items_col_config["Delivery Status"] = st.column_config.SelectboxColumn(
        "Delivery Status",
        options=["Delivered", "Not Delivered"],
        help="Is it delivered or not?"
    )
if "Quantity" in df_items.columns:
    items_col_config["Quantity"] = st.column_config.NumberColumn(
        "Quantity",
        min_value=0,
        step=1,
        help="Enter the quantity required."
    )

# Show the Items table in a data_editor
edited_df_items = st.data_editor(
    df_items,
    column_config=items_col_config,
    use_container_width=True,
    num_rows="dynamic"
)

# Save Items Table
if st.button("Save Items Table"):
    try:
        edited_df_items.to_csv(ITEMS_FILE, index=False)
        st.success("Items table successfully saved to Cleaned_Items_Table.csv!")
        load_items_data.clear()
    except Exception as e:
        st.error(f"Error saving items table: {e}")

# Optionally allow CSV download for the Items table
csv_buffer = io.StringIO()
edited_df_items.to_csv(csv_buffer, index=False)
st.download_button(
    label="Download Items Table as CSV",
    data=csv_buffer.getvalue(),
    file_name="Cleaned_Items_Table.csv",
    mime="text/csv"
)
