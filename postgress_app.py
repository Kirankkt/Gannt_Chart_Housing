import streamlit as st
import pandas as pd
import plotly.express as px
import io
from datetime import datetime
from sqlalchemy import create_engine

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
# HIDE TOOLTIP IN st.data_editor
# ---------------------------------------------------------------------
hide_stdataeditor_bug_tooltip = """
<style>
[data-testid="stDataEditor"] [role="tooltip"] {
    visibility: hidden !important;
}
</style>
"""
st.markdown(hide_stdataeditor_bug_tooltip, unsafe_allow_html=True)

# =====================================================================
# 1. CREATE A POSTGRES ENGINE (SINGLE CONNECTION STRING)
# =====================================================================
@st.cache_resource
def get_sql_engine():
    """
    Create a SQLAlchemy engine for PostgreSQL using a single connection string
    from .streamlit/secrets.toml (under [postgresql] section).
    """
    connection_string = st.secrets["postgresql"]["connection_string"]
    return create_engine(connection_string)

engine = get_sql_engine()

# Table names
MAIN_TIMELINE_TABLE = "construction_timeline_3"
ITEMS_TABLE = "cleaned_items"

# =====================================================================
# 2. HELPER FUNCTIONS TO LOAD/SAVE DATA
# =====================================================================
@st.cache_data
def load_main_timeline() -> pd.DataFrame:
    """
    Load the main timeline DataFrame from the Postgres table 'construction_timeline'.
    If the table doesn't exist, return an empty DataFrame with the known columns:
      activity, item, task, room, location, notes, start_date, end_date, status, workdays, progress
    """
    # Check if table exists
    check_q = f"""
    SELECT * FROM information_schema.tables
    WHERE table_name = '{MAIN_TIMELINE_TABLE}'
    """
    exists_df = pd.read_sql(check_q, engine)
    if exists_df.empty:
        # Return an empty DataFrame with the known columns
        cols = [
            "activity", "item", "task", "room", "location",
            "notes", "start_date", "end_date", "status",
            "workdays", "progress"
        ]
        return pd.DataFrame(columns=cols)

    # If table exists, load it
    try:
        df = pd.read_sql(f"SELECT * FROM {MAIN_TIMELINE_TABLE}", engine)
    except Exception as e:
        st.error(f"Error loading main timeline from DB: {e}")
        cols = [
            "activity", "item", "task", "room", "location",
            "notes", "start_date", "end_date", "status",
            "workdays", "progress"
        ]
        return pd.DataFrame(columns=cols)

    # Convert date columns
    if "start_date" in df.columns:
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    if "end_date" in df.columns:
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    # Force "status" to string
    if "status" not in df.columns:
        df["status"] = "Not Started"
    df["status"] = df["status"].astype(str).fillna("Not Started")

    # Ensure "workdays" is integer
    if "workdays" in df.columns:
        df["workdays"] = pd.to_numeric(df["workdays"], errors="coerce").fillna(0).astype(int)

    # Ensure "progress" is numeric
    if "progress" in df.columns:
        df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0).astype(float)
    else:
        df["progress"] = 0.0

    return df


def save_main_timeline(df: pd.DataFrame):
    """
    Overwrite the entire 'construction_timeline' table in Postgres
    with the given DataFrame (if_exists="replace").
    """
    # Convert start/end_date
    if "start_date" in df.columns:
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    if "end_date" in df.columns:
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    # status to string
    if "status" in df.columns:
        df["status"] = df["status"].astype(str)

    # workdays to int
    if "workdays" in df.columns:
        df["workdays"] = pd.to_numeric(df["workdays"], errors="coerce").fillna(0).astype(int)

    # progress to float
    if "progress" in df.columns:
        df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0).astype(float)

    df.to_sql(MAIN_TIMELINE_TABLE, engine, index=False, if_exists="replace")


@st.cache_data
def load_items_table() -> pd.DataFrame:
    """
    Load or create the 'cleaned_items' table from Postgres.
    Columns: item, quantity, order_status, delivery_status, notes
    """
    # Check if table exists
    check_q = f"""
    SELECT * FROM information_schema.tables
    WHERE table_name = '{ITEMS_TABLE}'
    """
    exists_df = pd.read_sql(check_q, engine)
    if exists_df.empty:
        # Return an empty DF with known columns
        cols = ["item", "quantity", "order_status", "delivery_status", "notes"]
        return pd.DataFrame(columns=cols)

    # If table exists, load it
    try:
        df = pd.read_sql(f"SELECT * FROM {ITEMS_TABLE}", engine)
    except Exception as e:
        st.error(f"Error loading items from DB: {e}")
        cols = ["item", "quantity", "order_status", "delivery_status", "notes"]
        return pd.DataFrame(columns=cols)

    # Force dtypes
    if "quantity" in df.columns:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    for c in ["item", "order_status", "delivery_status", "notes"]:
        if c in df.columns:
            df[c] = df[c].astype(str)

    return df


def save_items_table(df: pd.DataFrame):
    """
    Overwrite the entire 'cleaned_items' table in Postgres
    with the given DataFrame (if_exists="replace").
    """
    if "quantity" in df.columns:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)

    df.to_sql(ITEMS_TABLE, engine, index=False, if_exists="replace")

# ---------------------------------------------------------------------
# Load data into DataFrames
# ---------------------------------------------------------------------
df_main = load_main_timeline()
df_items = load_items_table()

# ---------------------------------------------------------------------
# MAIN TIMELINE: EDIT & SAVE
# ---------------------------------------------------------------------
st.subheader("Update Task Information (construction_timeline)")

with st.sidebar.expander("Row & Column Management (Main Timeline)"):
    st.markdown("*Delete a row by index*")
    delete_index = st.text_input("Enter row index to delete (main table)", value="")
    if st.button("Delete Row (Main)"):
        if delete_index.isdigit():
            idx = int(delete_index)
            if 0 <= idx < len(df_main):
                df_main.drop(df_main.index[idx], inplace=True)
                try:
                    save_main_timeline(df_main)
                    st.sidebar.success(f"Row {idx} deleted and saved to Postgres.")
                    load_main_timeline.clear()  # clear cache_data
                    df_main = load_main_timeline()  # reload
                except Exception as e:
                    st.sidebar.error(f"Error saving data: {e}")
            else:
                st.sidebar.error("Invalid index.")
        else:
            st.sidebar.error("Please enter a valid integer index.")

    st.markdown("*Add a new column*")
    new_col_name = st.text_input("New Column Name (main table)", value="")
    new_col_type = st.selectbox("Column Type (main table)", ["string", "integer", "datetime", "float"])
    if st.button("Add Column (Main)"):
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
                save_main_timeline(df_main)
                st.sidebar.success(f"Column '{new_col_name}' added and saved.")
                load_main_timeline.clear()
                df_main = load_main_timeline()
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
                save_main_timeline(df_main)
                st.sidebar.success(f"Column '{col_to_delete}' deleted and saved.")
                load_main_timeline.clear()
                df_main = load_main_timeline()
            except Exception as e:
                st.sidebar.error(f"Error saving data: {e}")
        else:
            st.sidebar.warning("Please select a valid column.")

# Set up st.data_editor column configs
column_config_main = {}
if "status" in df_main.columns:
    column_config_main["status"] = st.column_config.SelectboxColumn(
        "status",
        options=["Finished", "In Progress", "Not Started"],
        help="Status of the task"
    )
if "workdays" in df_main.columns:
    column_config_main["workdays"] = st.column_config.NumberColumn(
        "workdays",
        min_value=0,
        help="Number of workdays allocated to this item."
    )
if "progress" in df_main.columns:
    column_config_main["progress"] = st.column_config.NumberColumn(
        "progress",
        min_value=0,
        max_value=100,
        step=1,
        help="Progress %"
    )

# For text columns
for text_col in ["activity", "item", "task", "room", "location", "notes"]:
    if text_col in df_main.columns:
        column_config_main[text_col] = st.column_config.TextColumn(
            text_col, help=f"{text_col.title()}"
        )

# For start_date / end_date, we can treat them as text columns or let them remain default
if "start_date" in df_main.columns:
    column_config_main["start_date"] = st.column_config.TextColumn(
        "start_date", help="Start date (YYYY-MM-DD)", max_chars=10
    )
if "end_date" in df_main.columns:
    column_config_main["end_date"] = st.column_config.TextColumn(
        "end_date", help="End date (YYYY-MM-DD)", max_chars=10
    )

# Edit the main timeline
edited_df_main = st.data_editor(
    df_main,
    column_config=column_config_main,
    use_container_width=True,
    num_rows="dynamic"
)

# If user sets status to "Finished", we can auto-set progress=100
if "status" in edited_df_main.columns and "progress" in edited_df_main.columns:
    finished_mask = edited_df_main["status"].str.lower() == "finished"
    edited_df_main.loc[finished_mask, "progress"] = 100

if st.button("Save Updates (Main Timeline)"):
    try:
        save_main_timeline(edited_df_main)
        st.success("Main timeline data successfully saved to Postgres!")
        load_main_timeline.clear()
    except Exception as e:
        st.error(f"Error saving main timeline: {e}")

# =====================================================================
# SIDEBAR FILTERS (MAIN TIMELINE)
# =====================================================================
st.sidebar.header("Filter Options (Main Timeline)")

def norm_unique(df_input: pd.DataFrame, col: str):
    """Return sorted unique normalized (lower-stripped) values from a column."""
    if col not in df_input.columns:
        return []
    return sorted(set(df_input[col].dropna().astype(str).str.lower().str.strip()))

# Initialize session state for multi-select filters
for key in ["activity_filter", "item_filter", "task_filter", "room_filter", "status_filter"]:
    if key not in st.session_state:
        st.session_state[key] = []

# Date range defaults
if "start_date" in edited_df_main.columns and not edited_df_main["start_date"].isnull().all():
    try:
        start_min = edited_df_main["start_date"].dropna().min()
        min_start = pd.to_datetime(start_min)
    except:
        min_start = datetime.today()
else:
    min_start = datetime.today()

if "end_date" in edited_df_main.columns and not edited_df_main["end_date"].isnull().all():
    try:
        end_max = edited_df_main["end_date"].dropna().max()
        max_end = pd.to_datetime(end_max)
    except:
        max_end = datetime.today()
else:
    max_end = datetime.today()

default_date_range = (min_start, max_end)
selected_date_range = st.sidebar.date_input("Filter Date Range", value=default_date_range, key="date_range")

if st.sidebar.button("Clear Filters (Main)"):
    st.session_state["activity_filter"] = []
    st.session_state["item_filter"] = []
    st.session_state["task_filter"] = []
    st.session_state["room_filter"] = []
    st.session_state["status_filter"] = []

# Multi-select filters
a_opts = norm_unique(edited_df_main, "activity")
st.sidebar.multiselect(
    "Filter by activity",
    options=a_opts,
    default=st.session_state["activity_filter"],
    key="activity_filter"
)
i_opts = norm_unique(edited_df_main, "item")
st.sidebar.multiselect(
    "Filter by item",
    options=i_opts,
    default=st.session_state["item_filter"],
    key="item_filter"
)
t_opts = norm_unique(edited_df_main, "task")
st.sidebar.multiselect(
    "Filter by task",
    options=t_opts,
    default=st.session_state["task_filter"],
    key="task_filter"
)
r_opts = norm_unique(edited_df_main, "room")
st.sidebar.multiselect(
    "Filter by room",
    options=r_opts,
    default=st.session_state["room_filter"],
    key="room_filter"
)
s_opts = norm_unique(edited_df_main, "status")
st.sidebar.multiselect(
    "Filter by status",
    options=s_opts,
    default=st.session_state["status_filter"],
    key="status_filter"
)

show_finished = st.sidebar.checkbox("Show Finished Tasks", value=True)
color_by_status = st.sidebar.checkbox("Color-code Gantt Chart by Status", value=True)

st.sidebar.markdown("*Refine Gantt Grouping*")
group_by_room = st.sidebar.checkbox("Group by Room", value=False)
group_by_item = st.sidebar.checkbox("Group by Item", value=False)
group_by_task = st.sidebar.checkbox("Group by Task", value=False)
group_by_location = st.sidebar.checkbox("Group by Location", value=False)

# =====================================================================
# FILTER MAIN TABLE FOR GANTT
# =====================================================================
df_filtered = edited_df_main.copy()

# Force status to string
if "status" in df_filtered.columns:
    df_filtered["status"] = df_filtered["status"].astype(str).fillna("Not Started")

# Normalize columns for filter
for col in ["activity", "item", "task", "room", "status"]:
    if col in df_filtered.columns:
        df_filtered[col + "_norm"] = df_filtered[col].astype(str).str.lower().str.strip()

# Apply multi-select filters
if st.session_state["activity_filter"]:
    df_filtered = df_filtered[df_filtered["activity_norm"].isin(st.session_state["activity_filter"])]
if st.session_state["item_filter"]:
    df_filtered = df_filtered[df_filtered["item_norm"].isin(st.session_state["item_filter"])]
if st.session_state["task_filter"]:
    df_filtered = df_filtered[df_filtered["task_norm"].isin(st.session_state["task_filter"])]
if st.session_state["room_filter"]:
    df_filtered = df_filtered[df_filtered["room_norm"].isin(st.session_state["room_filter"])]
if st.session_state["status_filter"]:
    df_filtered = df_filtered[df_filtered["status_norm"].isin(st.session_state["status_filter"])]

if not show_finished:
    # Exclude tasks where status_norm == "finished"
    df_filtered = df_filtered[df_filtered["status_norm"] != "finished"]

# Date filter
if "start_date" in df_filtered.columns and "end_date" in df_filtered.columns:
    try:
        srange, erange = selected_date_range
        srange = pd.to_datetime(srange)
        erange = pd.to_datetime(erange)
        df_filtered = df_filtered[
            (pd.to_datetime(df_filtered["start_date"], errors="coerce") >= srange) &
            (pd.to_datetime(df_filtered["end_date"], errors="coerce") <= erange)
        ]
    except:
        pass

# Remove the normalized columns
normcols = [c for c in df_filtered.columns if c.endswith("_norm")]
df_filtered.drop(columns=normcols, inplace=True, errors="ignore")

# =====================================================================
# GANTT CHART FUNCTION with PARTIAL PROGRESS
# =====================================================================
def create_gantt_chart(df_input: pd.DataFrame, color_by_status: bool = True):
    """
    Create a Gantt chart with partial segments for 'progress'.
    We assume columns: start_date, end_date, status, progress.
    """
    needed = ["start_date", "end_date", "status", "progress"]
    missing = [c for c in needed if c not in df_input.columns]
    if missing:
        return px.scatter(title=f"Cannot build Gantt: missing {missing}")

    if df_input.empty:
        return px.scatter(title="No data to display for Gantt")

    # Decide grouping columns
    group_cols = ["activity"]
    if group_by_room and "room" in df_input.columns:
        group_cols.append("room")
    if group_by_item and "item" in df_input.columns:
        group_cols.append("item")
    if group_by_task and "task" in df_input.columns:
        group_cols.append("task")
    if group_by_location and "location" in df_input.columns:
        group_cols.append("location")

    if not group_cols:
        return px.scatter(title="No group columns selected for Gantt")

    # aggregator
    grouped = (
        df_input
        .groupby(group_cols, dropna=False)
        .agg({
            "start_date": "min",
            "end_date": "max",
            "progress": "mean",
            "status": lambda s: list(s.dropna().astype(str))
        })
        .reset_index()
    )
    grouped.rename(columns={
        "start_date": "GroupStart",
        "end_date": "GroupEnd",
        "progress": "AvgProgress",
        "status": "AllStatuses"
    }, inplace=True)

    now = pd.Timestamp(datetime.today().date())

    def aggregated_status(st_list, avg_prog, start_dt, end_dt):
        """Return a single overall status for the group, used for color logic."""
        all_lower = [str(x).lower().strip() for x in st_list]
        if all(s == "finished" for s in all_lower) or avg_prog >= 100:
            return "Finished"
        if end_dt < now and avg_prog < 100:
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

        # partial progress logic
        if final_st == "In Progress" and 0 < avgp < 100:
            total_s = (end - start).total_seconds() if end > start else 0
            done_s = total_s * (avgp / 100.0)
            done_end = start + pd.Timedelta(seconds=done_s)
            # completed part
            segments.append({
                "Group Label": label,
                "Start": start,
                "End": done_end,
                "Display Status": "In Progress (Completed)",
                "Progress": f"{avgp:.0f}%"
            })
            # remaining part
            remain_pct = 100 - avgp
            segments.append({
                "Group Label": label,
                "Start": done_end,
                "End": end,
                "Display Status": "In Progress (Remaining)",
                "Progress": f"{remain_pct:.0f}%"
            })
        else:
            # single segment
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
        "In Progress (Completed)": "blue",
        "In Progress (Remaining)": "lightblue",
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
# KPI & CALCULATIONS
# =====================================================================
total_tasks = len(edited_df_main)

if "status" in edited_df_main.columns:
    edited_df_main["status"] = edited_df_main["status"].astype(str).fillna("Not Started")

finished_count = edited_df_main[edited_df_main["status"].str.lower() == "finished"].shape[0]
completion_pct = (finished_count / total_tasks * 100) if total_tasks else 0
inprogress_count = edited_df_main[edited_df_main["status"].str.lower() == "in progress"].shape[0]
notstart_count = edited_df_main[edited_df_main["status"].str.lower() == "not started"].shape[0]

today_dt = pd.Timestamp(datetime.today().date())
if "end_date" in df_filtered.columns:
    overdue_df = df_filtered[
        (df_filtered["end_date"] < today_dt)
        & (df_filtered["status"].str.lower() != "finished")
    ]
    overdue_count = overdue_df.shape[0]
else:
    overdue_df = pd.DataFrame()
    overdue_count = 0

if "activity" in df_filtered.columns:
    dist_table = df_filtered.groupby("activity").size().reset_index(name="Task Count")
    dist_fig = px.bar(dist_table, x="activity", y="Task Count", title="Task Distribution by Activity")
else:
    dist_fig = px.bar(title="No 'activity' column to show distribution.")

if "start_date" in df_filtered.columns:
    next7_df = df_filtered[
        (df_filtered["start_date"] >= today_dt)
        & (df_filtered["start_date"] <= today_dt + pd.Timedelta(days=7))
    ]
else:
    next7_df = pd.DataFrame()

# Summarize filter choices
filt_summ = []
if st.session_state["activity_filter"]:
    filt_summ.append("Activities: " + ", ".join(st.session_state["activity_filter"]))
if st.session_state["item_filter"]:
    filt_summ.append("Items: " + ", ".join(st.session_state["item_filter"]))
if st.session_state["task_filter"]:
    filt_summ.append("Tasks: " + ", ".join(st.session_state["task_filter"]))
if st.session_state["room_filter"]:
    filt_summ.append("Rooms: " + ", ".join(st.session_state["room_filter"]))
if st.session_state["status_filter"]:
    filt_summ.append("Status: " + ", ".join(st.session_state["status_filter"]))
if selected_date_range:
    d0, d1 = selected_date_range
    filt_summ.append(f"Date Range: {d0} to {d1}")

filt_text = "; ".join(filt_summ) if filt_summ else "No filters applied."

# =====================================================================
# DISPLAY MAIN TIMELINE DASHBOARD
# =====================================================================
st.header("Dashboard Overview (construction_timeline)")

st.subheader("Current Tasks Snapshot")
st.dataframe(df_filtered)

st.subheader("Project Timeline")
st.plotly_chart(gantt_fig, use_container_width=True)

st.metric("Overall Completion (%)", f"{completion_pct:.1f}%")
st.progress(completion_pct / 100)

st.markdown("#### Additional Insights")
st.markdown(f"*Overdue Tasks:* {overdue_count}")
if not overdue_df.empty:
    st.dataframe(overdue_df[["activity", "room", "task", "status", "end_date"]])

st.markdown("*Task Distribution by Activity:*")
st.plotly_chart(dist_fig, use_container_width=True)

st.markdown("*Upcoming Tasks (Next 7 Days):*")
if not next7_df.empty:
    st.dataframe(next7_df[["activity", "room", "task", "start_date", "status"]])
else:
    st.info("No upcoming tasks in the next 7 days.")

st.markdown("*Active Filters (Main Timeline):*")
st.write(filt_text)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Tasks", total_tasks)
col2.metric("In Progress", inprogress_count)
col3.metric("Finished", finished_count)
col4.metric("Not Started", notstart_count)

st.markdown("---")

# =====================================================================
# SECOND TABLE: CLEANED_ITEMS
# =====================================================================
st.header("Items to Order (cleaned_items)")

# Ensure columns exist
for needed_col in ["item", "quantity", "order_status", "delivery_status", "notes"]:
    if needed_col not in df_items.columns:
        df_items[needed_col] = ""

# Force dtypes again
df_items["item"] = df_items["item"].astype(str)
df_items["quantity"] = pd.to_numeric(df_items["quantity"], errors="coerce").fillna(0).astype(int)
df_items["order_status"] = df_items["order_status"].astype(str)
df_items["delivery_status"] = df_items["delivery_status"].astype(str)
df_items["notes"] = df_items["notes"].astype(str)

# Configure st.data_editor columns
items_col_config = {
    "item": st.column_config.TextColumn("item", help="Name of the item"),
    "quantity": st.column_config.NumberColumn(
        "quantity",
        min_value=0,
        step=1,
        help="Enter the quantity required."
    ),
    "order_status": st.column_config.SelectboxColumn(
        "order_status",
        options=["ordered", "not ordered"],
        help="Ordered or not?"
    ),
    "delivery_status": st.column_config.SelectboxColumn(
        "delivery_status",
        options=["delivered", "not delivered", "delayed"],
        help="Delivery status?"
    ),
    "notes": st.column_config.TextColumn("notes", help="Any notes?")
}

edited_df_items = st.data_editor(
    df_items,
    column_config=items_col_config,
    use_container_width=True,
    num_rows="dynamic"
)

if st.button("Save Items Table"):
    try:
        edited_df_items["quantity"] = pd.to_numeric(edited_df_items["quantity"], errors="coerce").fillna(0).astype(int)
        save_items_table(edited_df_items)
        st.success("Items table successfully saved to Postgres!")
        load_items_table.clear()
    except Exception as e:
        st.error(f"Error saving items table: {e}")

# Optionally add a download button for the items table as CSV
csv_buffer = io.StringIO()
edited_df_items.to_csv(csv_buffer, index=False)
st.download_button(
    label="Download Items Table as CSV",
    data=csv_buffer.getvalue(),
    file_name="cleaned_items_export.csv",
    mime="text/csv"
)
