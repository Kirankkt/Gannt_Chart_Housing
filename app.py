import streamlit as st
import pandas as pd
import plotly.express as px
import io, os
from datetime import datetime

# ---------------------------------------------------------------------
# APP CONFIG & TITLE
# ---------------------------------------------------------------------
st.set_page_config(page_title="Construction Project Manager Dashboard", layout="wide")
st.title("Construction Project Manager Dashboard")
st.markdown(
    "This dashboard provides an overview of the construction project, including task snapshots, "
    "timeline visualization, and progress tracking. Use the sidebar to filter and update data."
)

# ---------------------------------------------------------------------
# HIDE THE BUG TOOLTIP IN st.data_editor
# ---------------------------------------------------------------------
hide_stdataeditor_bug_tooltip = """
<style>
/* Hide all tooltips within the data editor */
[data-testid="stDataEditor"] [role="tooltip"] {
    visibility: hidden !important;
}
</style>
"""
st.markdown(hide_stdataeditor_bug_tooltip, unsafe_allow_html=True)

# =====================================================================
# 1. HELPER: LOAD MAIN TIMELINE DATA
# =====================================================================
@st.cache_data
def load_timeline_data(file_path: str) -> pd.DataFrame:
    """Load or create the main timeline DataFrame from Excel."""
    if not os.path.exists(file_path):
        st.error(f"File '{file_path}' not found! Please upload or create it.")
        st.stop()

    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()

    # Convert Start/End Dates if present
    if "Start Date" in df.columns:
        df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    if "End Date" in df.columns:
        df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")

    # Ensure "Progress" column
    if "Progress" not in df.columns:
        df["Progress"] = 0.0

    # Ensure "Status" column
    if "Status" not in df.columns:
        df["Status"] = "Not Started"

    # Convert "Progress" to numeric
    df["Progress"] = pd.to_numeric(df["Progress"], errors="coerce").fillna(0)

    # Remove "Order Status" from main timeline if present
    if "Order Status" in df.columns:
        df.drop(columns=["Order Status"], inplace=True)

    # Type‐check: "Status" must be string
    df["Status"] = df["Status"].astype(str).fillna("Not Started")

    return df

DATA_FILE = "construction_timeline.xlsx"
df_main = load_timeline_data(DATA_FILE)

# ---------------------------------------------------------------------
# 2. MAIN TIMELINE: EDIT & SAVE
# ---------------------------------------------------------------------
st.subheader("Update Task Information (Main Timeline)")

with st.sidebar.expander("Row & Column Management (Main Timeline)"):
    st.markdown("*Delete a row by index*")
    delete_index = st.text_input("Enter row index to delete (main table)", value="")
    if st.button("Delete Row (Main)"):
        if delete_index.isdigit():
            idx = int(delete_index)
            if 0 <= idx < len(df_main):
                df_main.drop(df_main.index[idx], inplace=True)
                try:
                    df_main.to_excel(DATA_FILE, index=False)
                    st.sidebar.success(f"Row {idx} deleted and saved.")
                    load_timeline_data.clear()  # clear cache and reload data
                    df_main = load_timeline_data(DATA_FILE)
                except Exception as e:
                    st.sidebar.error(f"Error saving data: {e}")
            else:
                st.sidebar.error("Invalid index.")
        else:
            st.sidebar.error("Please enter a valid integer index.")

    st.markdown("*Add a new column*")
    new_col_name = st.text_input("New Column Name (main table)", value="")
    new_col_type = st.selectbox("Column Type (main table)", ["string", "integer", "float", "datetime"])
    if st.button("Add Column (Main)"):
        if new_col_name and new_col_name not in df_main.columns:
            if new_col_type == "string":
                # Create column of empty strings (makes them text-editable)
                df_main[new_col_name] = ["" for _ in range(len(df_main))]
                df_main[new_col_name] = df_main[new_col_name].astype(str)
            elif new_col_type == "integer":
                df_main[new_col_name] = 0
            elif new_col_type == "float":
                df_main[new_col_name] = 0.0
            elif new_col_type == "datetime":
                df_main[new_col_name] = pd.NaT

            try:
                df_main.to_excel(DATA_FILE, index=False)
                st.sidebar.success(f"Column '{new_col_name}' added and saved.")
                load_timeline_data.clear()  # clear cache and reload data
                df_main = load_timeline_data(DATA_FILE)
            except Exception as e:
                st.sidebar.error(f"Error saving data: {e}")
        elif new_col_name in df_main.columns:
            st.sidebar.warning("Column already exists or invalid name.")
        else:
            st.sidebar.warning("Please enter a valid column name.")

    st.markdown("*Delete a column*")
    col_to_delete = st.selectbox(
        "Select Column to Delete (main table)",
        options=[""] + list(df_main.columns),
        index=0
    )
    if st.button("Delete Column (Main)"):
        if col_to_delete and col_to_delete in df_main.columns:
            df_main.drop(columns=[col_to_delete], inplace=True)
            try:
                df_main.to_excel(DATA_FILE, index=False)
                st.sidebar.success(f"Column '{col_to_delete}' deleted and saved.")
                load_timeline_data.clear()
                df_main = load_timeline_data(DATA_FILE)
            except Exception as e:
                st.sidebar.error(f"Error saving data: {e}")
        else:
            st.sidebar.warning("Please select a valid column.")

# Configure columns for st.data_editor in the main timeline
column_config_main = {}

# Pre‐set known columns as selectboxes, etc.
if "Activity" in df_main.columns:
    column_config_main["Activity"] = st.column_config.SelectboxColumn(
        "Activity", options=sorted(df_main["Activity"].dropna().unique()), help="Activity"
    )
if "Item" in df_main.columns:
    column_config_main["Item"] = st.column_config.SelectboxColumn(
        "Item", options=sorted(df_main["Item"].dropna().unique()), help="Item"
    )
if "Task" in df_main.columns:
    column_config_main["Task"] = st.column_config.SelectboxColumn(
        "Task", options=sorted(df_main["Task"].dropna().unique()), help="Task"
    )
if "Room" in df_main.columns:
    column_config_main["Room"] = st.column_config.SelectboxColumn(
        "Room", options=sorted(df_main["Room"].dropna().unique()), help="Room"
    )
if "Status" in df_main.columns:
    column_config_main["Status"] = st.column_config.SelectboxColumn(
        "Status", options=["Finished", "In Progress", "Not Started"], help="Status"
    )
if "Progress" in df_main.columns:
    column_config_main["Progress"] = st.column_config.NumberColumn(
        "Progress", min_value=0, max_value=100, step=1, help="Progress %"
    )

# Any other columns not in the known config get a default config based on dtype:
for col in df_main.columns:
    if col not in column_config_main:  # not yet configured
        col_dtype = df_main[col].dtype
        if pd.api.types.is_datetime64_any_dtype(col_dtype):
            column_config_main[col] = st.column_config.DateColumn(
                label=col,
                help=f"Date column: {col}"
            )
        elif pd.api.types.is_numeric_dtype(col_dtype):
            column_config_main[col] = st.column_config.NumberColumn(
                label=col,
                help=f"Numeric column: {col}"
            )
        else:
            # default to free‐text
            column_config_main[col] = st.column_config.TextColumn(
                label=col,
                help=f"Text column: {col}"
            )

# Edit the main timeline
edited_df_main = st.data_editor(
    df_main,
    column_config=column_config_main,
    use_container_width=True,
    num_rows="dynamic"
)

# Force Status to string once user is done editing
if "Status" in edited_df_main.columns:
    edited_df_main["Status"] = edited_df_main["Status"].astype(str).fillna("Not Started")

# ---------------------------------------------------------------------
# Immediately set progress = 100 if status = Finished (in memory)
# So that Gantt chart and metrics update automatically
# ---------------------------------------------------------------------
if "Status" in edited_df_main.columns and "Progress" in edited_df_main.columns:
    mask_finished = edited_df_main["Status"].str.lower() == "finished"
    edited_df_main.loc[mask_finished, "Progress"] = 100

if st.button("Save Updates (Main Timeline)"):
    # Repeat the same logic at save just to ensure consistency
    if "Status" in edited_df_main.columns and "Progress" in edited_df_main.columns:
        mask_finished = edited_df_main["Status"].str.lower() == "finished"
        edited_df_main.loc[mask_finished, "Progress"] = 100

    try:
        edited_df_main.to_excel(DATA_FILE, index=False)
        st.success("Main timeline data successfully saved!")
        load_timeline_data.clear()
    except Exception as e:
        st.error(f"Error saving main timeline: {e}")

# =====================================================================
# 3. SIDEBAR FILTERS FOR MAIN TIMELINE
# =====================================================================
st.sidebar.header("Filter Options (Main Timeline)")

def norm_unique(df_input: pd.DataFrame, col: str):
    """Return sorted unique normalized (lower-stripped) values from a column."""
    if col not in df_input.columns:
        return []
    return sorted(set(df_input[col].dropna().astype(str).str.lower().str.strip()))

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

# --- Date Range: use a default computed once, but allow the widget to be edited ---
default_date_range = (
    edited_df_main["Start Date"].min() if "Start Date" in edited_df_main.columns and not edited_df_main["Start Date"].isnull().all() else datetime.today(),
    edited_df_main["End Date"].max() if "End Date" in edited_df_main.columns and not edited_df_main["End Date"].isnull().all() else datetime.today()
)
selected_date_range = st.sidebar.date_input("Filter Date Range", value=default_date_range, key="date_range")

if st.sidebar.button("Clear Filters (Main)"):
    st.session_state["activity_filter"] = []
    st.session_state["item_filter"] = []
    st.session_state["task_filter"] = []
    st.session_state["room_filter"] = []
    st.session_state["status_filter"] = []
    # (We intentionally do not reset the date range widget to original default)

# Multi‐select filters
a_opts = norm_unique(edited_df_main, "Activity")
selected_activity_norm = st.sidebar.multiselect("Filter by Activity", options=a_opts,
    default=st.session_state["activity_filter"], key="activity_filter")
i_opts = norm_unique(edited_df_main, "Item")
selected_item_norm = st.sidebar.multiselect("Filter by Item", options=i_opts,
    default=st.session_state["item_filter"], key="item_filter")
t_opts = norm_unique(edited_df_main, "Task")
selected_task_norm = st.sidebar.multiselect("Filter by Task", options=t_opts,
    default=st.session_state["task_filter"], key="task_filter")
r_opts = norm_unique(edited_df_main, "Room")
selected_room_norm = st.sidebar.multiselect("Filter by Room", options=r_opts,
    default=st.session_state["room_filter"], key="room_filter")
s_opts = norm_unique(edited_df_main, "Status")
selected_statuses = st.sidebar.multiselect("Filter by Status", options=s_opts,
    default=st.session_state["status_filter"], key="status_filter")

show_finished = st.sidebar.checkbox("Show Finished Tasks", value=True)
color_by_status = st.sidebar.checkbox("Color-code Gantt Chart by Status", value=True)

st.sidebar.markdown("*Refine Gantt Grouping*")
group_by_room = st.sidebar.checkbox("Group by Room", value=False)
group_by_item = st.sidebar.checkbox("Group by Item", value=False)
group_by_task = st.sidebar.checkbox("Group by Task", value=False)

# =====================================================================
# 4. FILTER MAIN TABLE FOR GANTT
# =====================================================================
df_filtered = edited_df_main.copy()

# Force status to string
if "Status" in df_filtered.columns:
    df_filtered["Status"] = df_filtered["Status"].astype(str).fillna("Not Started")

for col in ["Activity", "Item", "Task", "Room", "Status"]:
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

if not show_finished:
    df_filtered = df_filtered[~df_filtered["Status_norm"].isin(["finished"])]

# Use the user‐selected date range from the date_input widget
if "Start Date" in df_filtered.columns and "End Date" in df_filtered.columns:
    srange, erange = selected_date_range  # get the dates from the widget
    srange = pd.to_datetime(srange)
    erange = pd.to_datetime(erange)
    df_filtered = df_filtered[
        (df_filtered["Start Date"] >= srange) &
        (df_filtered["End Date"] <= erange)
    ]

normcols = [c for c in df_filtered.columns if c.endswith("_norm")]
df_filtered.drop(columns=normcols, inplace=True, errors="ignore")

# =====================================================================
# 5. GANTT CHART FUNCTION
# =====================================================================
def create_gantt_chart(df_input: pd.DataFrame, color_by_status: bool = True):
    needed = ["Start Date", "End Date", "Status", "Progress"]
    missing = [c for c in needed if c not in df_input.columns]
    if missing:
        return px.scatter(title=f"Cannot build Gantt: missing {missing}")

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
            "Status": lambda s: list(s.dropna().astype(str))
        })
        .reset_index()
    )
    grouped.rename(columns={
        "Start Date": "GroupStart",
        "End Date": "GroupEnd",
        "Progress": "AvgProgress",
        "Status": "AllStatuses"
    }, inplace=True)

    now = pd.Timestamp(datetime.today().date())

    def aggregated_status(st_list, avg_prog, start_dt, end_dt):
        # treat unknown statuses as "Not Started"
        all_lower = [str(x).lower().strip() for x in st_list]
        if all(s == "finished" for s in all_lower) or avg_prog >= 100:
            return "Finished"
        if end_dt < now and avg_prog < 100:
            return "Delayed"
        total_duration = (end_dt - start_dt).total_seconds()
        if total_duration <= 0:
            total_duration = 1
        delay_threshold = start_dt + pd.Timedelta(seconds=total_duration * 0.5)
        if now > delay_threshold and avg_prog == 0:
            return "Delayed"
        if "in progress" in all_lower:
            if avg_prog == 0:
                return "Just Started"
            return "In Progress"
        return "Not Started"

    segments = []
    for _, row in grouped.iterrows():
        label = " | ".join(str(row[g]) for g in group_cols)
        st_list = row["AllStatuses"]
        start = row["GroupStart"]
        end = row["GroupEnd"]
        avgp = row["AvgProgress"]
        final_st = aggregated_status(st_list, avgp, start, end)

        if final_st == "In Progress" and 0 < avgp < 100:
            total_s = (end - start).total_seconds()
            done_s = total_s * (avgp / 100.0)
            done_end = start + pd.Timedelta(seconds=done_s)
            # completed portion
            segments.append({
                "Group Label": label,
                "Start": start,
                "End": done_end,
                "Display Status": "In Progress (Completed part)",
                "Progress": f"{avgp:.0f}%"
            })
            remain_pct = 100 - avgp
            segments.append({
                "Group Label": label,
                "Start": done_end,
                "End": end,
                "Display Status": "In Progress (Remaining part)",
                "Progress": f"{remain_pct:.0f}%"
            })
        else:
            segments.append({
                "Group Label": label,
                "Start": start,
                "End": end,
                "Display Status": final_st,
                "Progress": f"{avgp:.0f}%"
            })

    gantt_df = pd.DataFrame(segments)
    if gantt_df.empty:
        return px.scatter(title="No data after grouping for Gantt")

    color_map = {
        "Not Started": "lightgray",
        "Just Started": "lightgreen",
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

# =====================================================================
# 6. KPI & CALCULATIONS
# =====================================================================
total_tasks = len(edited_df_main)
if total_tasks == 0:
    total_tasks = 1  # to avoid zero-division

if "Status" in edited_df_main.columns:
    edited_df_main["Status"] = edited_df_main["Status"].astype(str).fillna("Not Started")

finished_count = edited_df_main[edited_df_main["Status"].str.lower() == "finished"].shape[0]
completion_pct = (finished_count / total_tasks * 100)
inprogress_count = edited_df_main[edited_df_main["Status"].str.lower() == "in progress"].shape[0]
notstart_count = edited_df_main[edited_df_main["Status"].str.lower() == "not started"].shape[0]

today_dt = pd.Timestamp(datetime.today().date())
if "End Date" in df_filtered.columns:
    overdue_df = df_filtered[
        (df_filtered["End Date"] < today_dt)
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

if "Start Date" in df_filtered.columns:
    next7_df = df_filtered[
        (df_filtered["Start Date"] >= today_dt)
        & (df_filtered["Start Date"] <= today_dt + pd.Timedelta(days=7))
    ]
else:
    next7_df = pd.DataFrame()

filt_summ = []
if selected_activity_norm:
    filt_summ.append("Activities: " + ", ".join(selected_activity_norm))
if selected_item_norm:
    filt_summ.append("Items: " + ", ".join(selected_item_norm))
if selected_task_norm:
    filt_summ.append("Tasks: " + ", ".join(selected_task_norm))
if selected_room_norm:
    filt_summ.append("Rooms: " + ", ".join(selected_room_norm))
if selected_statuses:
    filt_summ.append("Status: " + ", ".join(selected_statuses))
if selected_date_range:
    d0, d1 = selected_date_range
    filt_summ.append(f"Date Range: {d0} to {d1}")
filt_text = "; ".join(filt_summ) if filt_summ else "No filters applied."

# =====================================================================
# 7. DISPLAY MAIN TIMELINE DASHBOARD
# =====================================================================
st.header("Dashboard Overview (Main Timeline)")

st.subheader("Current Tasks Snapshot")
st.dataframe(df_filtered)

st.subheader("Project Timeline")
st.plotly_chart(gantt_fig, use_container_width=True)

st.metric("Overall Completion (%)", f"{completion_pct:.1f}%")
st.progress(completion_pct / 100)

st.markdown("#### Additional Insights")
st.markdown(f"*Overdue Tasks:* {overdue_count}")
if not overdue_df.empty:
    st.dataframe(overdue_df[["Activity", "Room", "Task", "Status", "End Date"]])

st.markdown("*Task Distribution by Activity:*")
st.plotly_chart(dist_fig, use_container_width=True)

st.markdown("*Upcoming Tasks (Next 7 Days):*")
if not next7_df.empty:
    st.dataframe(next7_df[["Activity", "Room", "Task", "Start Date", "Status"]])
else:
    st.info("No upcoming tasks in the next 7 days.")

st.markdown("*Active Filters (Main Timeline):*")
st.write(filt_text)

mcol1, mcol2, mcol3, mcol4 = st.columns(4)
mcol1.metric("Total Tasks", total_tasks)
mcol2.metric("In Progress", inprogress_count)
mcol3.metric("Finished", finished_count)
mcol4.metric("Not Started", notstart_count)

st.markdown("Use the filters on the sidebar to adjust the view.")
st.markdown("---")

# =====================================================================
# 8. SECOND TABLE: ITEMS TO ORDER (CSV)
# =====================================================================
@st.cache_data
def load_items_data(file_path: str) -> pd.DataFrame:
    """Load or create the 'Items to Order' table from CSV."""
    if os.path.exists(file_path):
        df_i = pd.read_csv(file_path)
    else:
        df_i = pd.DataFrame(columns=["Item", "Quantity", "Order Status", "Delivery Status", "Notes"])
    return df_i

ITEMS_FILE = "Cleaned_Items_Table.csv"
st.header("Items to Order")
df_items = load_items_data(ITEMS_FILE)

# Ensure all needed columns exist & correct dtypes
for needed_col in ["Item", "Quantity", "Order Status", "Delivery Status", "Notes"]:
    if needed_col not in df_items.columns:
        df_items[needed_col] = ""

df_items["Item"] = df_items["Item"].astype(str)
df_items["Quantity"] = pd.to_numeric(df_items["Quantity"], errors="coerce").fillna(0).astype(int)
df_items["Order Status"] = df_items["Order Status"].astype(str)
df_items["Delivery Status"] = df_items["Delivery Status"].astype(str)
df_items["Notes"] = df_items["Notes"].astype(str)

# Configure columns for Items
items_col_config = {
    "Item": st.column_config.TextColumn(
        "Item",
        help="Name of the item"
    ),
    "Quantity": st.column_config.NumberColumn(
        "Quantity",
        min_value=0,
        step=1,
        help="Enter the quantity required."
    ),
    "Order Status": st.column_config.SelectboxColumn(
        "Order Status",
        options=["Ordered", "Not Ordered"],
        help="Choose if this item is ordered or not ordered."
    ),
    "Delivery Status": st.column_config.SelectboxColumn(
        "Delivery Status",
        options=["Delivered", "Not Delivered", "Delayed"],
        help="Has it been delivered, not delivered, or delayed?"
    ),
    "Notes": st.column_config.TextColumn(
        "Notes",
        help="Type any notes or remarks here."
    ),
}

edited_df_items = st.data_editor(
    df_items,
    column_config=items_col_config,
    use_container_width=True,
    num_rows="dynamic"
)

if st.button("Save Items Table"):
    try:
        edited_df_items["Quantity"] = pd.to_numeric(edited_df_items["Quantity"], errors="coerce").fillna(0).astype(int)
        edited_df_items.to_csv(ITEMS_FILE, index=False)
        st.success("Items table successfully saved to Cleaned_Items_Table.csv!")
        load_items_data.clear()
    except Exception as e:
        st.error(f"Error saving items table: {e}")

# Download button for the items table
csv_buffer = io.StringIO()
edited_df_items.to_csv(csv_buffer, index=False)
st.download_button(
    label="Download Items Table as CSV",
    data=csv_buffer.getvalue(),
    file_name="Cleaned_Items_Table.csv",
    mime="text/csv"
)
