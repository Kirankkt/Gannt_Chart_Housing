import streamlit as st
import pandas as pd
import plotly.express as px
import io
from datetime import datetime
import psycopg2
from sqlalchemy import create_engine, text

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
# 0. POSTGRES CONNECTION SETUP
# =====================================================================
@st.cache_resource
def get_db_engine():
    """Create and return a SQLAlchemy engine using secrets.toml credentials."""
    # Replace "postgres" with the key you used in secrets.toml
    conn_data = st.secrets["postgres"]
    # Example connection string:
    # postgresql://user:password@host:port/database
    conn_str = (
        f"postgresql://{conn_data['user']}:{conn_data['password']}"
        f"@{conn_data['host']}:{conn_data['port']}/{conn_data['database']}"
    )
    engine = create_engine(conn_str)
    return engine

engine = get_db_engine()


# =====================================================================
# 1. HELPER: LOAD MAIN TIMELINE DATA FROM POSTGRES
# =====================================================================
TIMELINE_TABLE = "construction_timeline_3"  # your table name in Postgres
@st.cache_data
def load_timeline_data() -> pd.DataFrame:
    """
    Load or create the main timeline DataFrame from the Postgres table `construction_timeline_3`.
    We then rename columns in-memory so they match the older Excel-based code logic.
    Also ensure that 'Progress' column exists, etc.
    """
    with engine.connect() as conn:
        df = pd.read_sql(f"SELECT * FROM {TIMELINE_TABLE}", conn)

    # -- Because your original code uses specific column names, rename them:
    # DB columns → In-app columns
    rename_map = {
        "activity": "Activity",
        "item": "Item",
        "task": "Task",
        "room": "Room",
        "location": "Location",
        "notes": "Notes",
        "start_date": "Start Date",
        "end_date": "End Date",
        "status": "Status",
        "workdays": "Workdays",
    }
    # If your DB columns have trailing spaces (like "activity " / "end_date "), adjust accordingly:
    # rename_map = {"activity ": "Activity", "end_date ": "End Date", ...}

    # Apply rename if they exist
    for dbcol, appcol in rename_map.items():
        if dbcol in df.columns:
            df.rename(columns={dbcol: appcol}, inplace=True)

    # Force datetime
    if "Start Date" in df.columns:
        df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    if "End Date" in df.columns:
        df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")

    # Ensure we have a "Progress" column in the DataFrame
    if "Progress" not in df.columns:
        df["Progress"] = 0.0

    # Force "Status" to string for the Gantt logic (in your provided DB, 'status' was double precision—this code expects text).
    df["Status"] = df["Status"].astype(str).fillna("Not Started")

    # Convert "Progress" to numeric
    df["Progress"] = pd.to_numeric(df["Progress"], errors="coerce").fillna(0)

    return df


def save_timeline_data(df: pd.DataFrame):
    """
    Overwrite the entire `construction_timeline_3` table with the given dataframe.
    1) We'll rename columns back to DB format,
    2) TRUNCATE or DELETE existing rows,
    3) Re-insert all rows from df.
    """
    # Create a copy so we don't modify the argument in place
    df_to_save = df.copy()

    # Reverse of rename_map:
    rename_map_back = {
        "Activity": "activity",
        "Item": "item",
        "Task": "task",
        "Room": "room",
        "Location": "location",
        "Notes": "notes",
        "Start Date": "start_date",
        "End Date": "end_date",
        "Status": "status",
        "Workdays": "workdays",
        "Progress": "progress",
    }
    for appcol, dbcol in rename_map_back.items():
        if appcol in df_to_save.columns:
            df_to_save.rename(columns={appcol: dbcol}, inplace=True)

    # Convert columns to suitable dtypes if needed
    # - Example: ensure "status" is text, "workdays" is numeric, "progress" is double, etc.
    if "status" in df_to_save.columns:
        df_to_save["status"] = df_to_save["status"].astype(str)
    if "workdays" in df_to_save.columns:
        df_to_save["workdays"] = pd.to_numeric(df_to_save["workdays"], errors="coerce").fillna(0).astype("Int64")
    if "progress" in df_to_save.columns:
        df_to_save["progress"] = pd.to_numeric(df_to_save["progress"], errors="coerce").fillna(0).astype(float)

    # Now overwrite the table in Postgres. We'll do a TRUNCATE + batch insert:
    with engine.begin() as conn:
        # 1) Clear out the table
        conn.execute(text(f"TRUNCATE TABLE {TIMELINE_TABLE}"))
        # 2) Insert everything from the DataFrame
        df_to_save.to_sql(TIMELINE_TABLE, conn, if_exists="append", index=False)


def alter_table_add_column(table_name: str, new_col_name: str, new_col_type: str):
    """
    Adds a new column to the specified Postgres table with the chosen type.
    We interpret "string", "integer", "float", "datetime" → appropriate PostgreSQL type.
    """
    # Map UI choices → Postgres data types
    type_map = {
        "string": "TEXT",
        "integer": "BIGINT",
        "float": "DOUBLE PRECISION",
        "datetime": "TIMESTAMP WITHOUT TIME ZONE"
    }
    pg_type = type_map.get(new_col_type, "TEXT")  # default to TEXT

    with engine.begin() as conn:
        # Build and execute an ALTER TABLE statement
        sql = text(f"ALTER TABLE {table_name} ADD COLUMN {new_col_name} {pg_type}")
        conn.execute(sql)


def alter_table_drop_column(table_name: str, col_name: str):
    """Drops a column from the specified Postgres table."""
    with engine.begin() as conn:
        sql = text(f"ALTER TABLE {table_name} DROP COLUMN {col_name}")
        conn.execute(sql)


# =====================================================================
# 2. MAIN TIMELINE: LOAD & EDIT
# =====================================================================
df_main = load_timeline_data()

st.subheader("Update Task Information (Main Timeline)")

# -- Sidebar for row/column management
with st.sidebar.expander("Row & Column Management (Main Timeline)"):
    st.markdown("*Delete a row by index*")
    delete_index = st.text_input("Enter row index to delete (main table)", value="")
    if st.button("Delete Row (Main)"):
        if delete_index.isdigit():
            idx = int(delete_index)
            if 0 <= idx < len(df_main):
                df_main.drop(df_main.index[idx], inplace=True)
                try:
                    save_timeline_data(df_main)
                    st.sidebar.success(f"Row {idx} deleted and saved.")
                    load_timeline_data.clear()  # clear cache
                    df_main = load_timeline_data()
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
            try:
                # 1) Alter the actual table in Postgres
                alter_table_add_column(TIMELINE_TABLE, new_col_name, new_col_type)
                # 2) Reload data so df_main has that column
                load_timeline_data.clear()
                df_main = load_timeline_data()
                st.sidebar.success(f"Column '{new_col_name}' added and saved.")
            except Exception as e:
                st.sidebar.error(f"Error adding column: {e}")
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
            try:
                # 1) Alter the actual table in Postgres
                alter_table_drop_column(TIMELINE_TABLE, col_to_delete)
                # 2) Reload
                load_timeline_data.clear()
                df_main = load_timeline_data()
                st.sidebar.success(f"Column '{col_to_delete}' deleted and saved.")
            except Exception as e:
                st.sidebar.error(f"Error deleting column: {e}")
        else:
            st.sidebar.warning("Please select a valid column.")


# Configure columns for st.data_editor
column_config_main = {}
if "Activity" in df_main.columns:
    # Let user select from existing or type new
    existing_activities = sorted(set(df_main["Activity"].dropna().unique()))
    column_config_main["Activity"] = st.column_config.SelectboxColumn(
        "Activity",
        options=existing_activities,
        help="Activity (select or type new)",
        allow_custom_value=True
    )
if "Item" in df_main.columns:
    existing_items = sorted(set(df_main["Item"].dropna().unique()))
    column_config_main["Item"] = st.column_config.SelectboxColumn(
        "Item",
        options=existing_items,
        help="Item (select or type new)",
        allow_custom_value=True
    )
if "Task" in df_main.columns:
    existing_tasks = sorted(set(df_main["Task"].dropna().unique()))
    column_config_main["Task"] = st.column_config.SelectboxColumn(
        "Task",
        options=existing_tasks,
        help="Task (select or type new)",
        allow_custom_value=True
    )
if "Room" in df_main.columns:
    existing_rooms = sorted(set(df_main["Room"].dropna().unique()))
    column_config_main["Room"] = st.column_config.SelectboxColumn(
        "Room",
        options=existing_rooms,
        help="Room (select or type new)",
        allow_custom_value=True
    )
if "Status" in df_main.columns:
    column_config_main["Status"] = st.column_config.SelectboxColumn(
        "Status",
        options=["Finished", "In Progress", "Not Started"],
        help="Status",
        allow_custom_value=True
    )
if "Progress" in df_main.columns:
    column_config_main["Progress"] = st.column_config.NumberColumn(
        "Progress", min_value=0, max_value=100, step=1, help="Progress %"
    )

edited_df_main = st.data_editor(
    df_main,
    column_config=column_config_main,
    use_container_width=True,
    num_rows="dynamic"
)

# Force "Status" to string once user is done editing
if "Status" in edited_df_main.columns:
    edited_df_main["Status"] = edited_df_main["Status"].astype(str).fillna("Not Started")

# --- Auto-update Progress if status is "Finished" ---
if st.button("Save Updates (Main Timeline)"):
    # If Status is "Finished", set Progress = 100
    if "Status" in edited_df_main.columns and "Progress" in edited_df_main.columns:
        finished_mask = edited_df_main["Status"].str.lower() == "finished"
        edited_df_main.loc[finished_mask, "Progress"] = 100

    try:
        save_timeline_data(edited_df_main)
        st.success("Main timeline data successfully saved!")
        load_timeline_data.clear()
    except Exception as e:
        st.error(f"Error saving main timeline: {e}")


# =====================================================================
# 3. SIDEBAR FILTERS FOR MAIN TIMELINE
# =====================================================================
st.sidebar.header("Filter Options (Main Timeline)")

def norm_unique(df_input: pd.DataFrame, col: str):
    """Return sorted unique lower-stripped values from a column."""
    if col not in df_input.columns:
        return []
    return sorted(set(df_input[col].dropna().astype(str).str.lower().str.strip()))

# Session-state to remember multi-select filters
for key_ in ["activity_filter", "item_filter", "task_filter", "room_filter", "status_filter"]:
    if key_ not in st.session_state:
        st.session_state[key_] = []

df_main_latest = load_timeline_data()
# We'll filter using the already-edited data if it hasn't been saved, so let's just use 'edited_df_main'
all_data_for_filter = edited_df_main.copy()

# Build the default date range
default_date_range = (
    all_data_for_filter["Start Date"].min() if "Start Date" in all_data_for_filter.columns and not all_data_for_filter["Start Date"].isnull().all() else datetime.today(),
    all_data_for_filter["End Date"].max() if "End Date" in all_data_for_filter.columns and not all_data_for_filter["End Date"].isnull().all() else datetime.today()
)
selected_date_range = st.sidebar.date_input("Filter Date Range", value=default_date_range, key="date_range")

if st.sidebar.button("Clear Filters (Main)"):
    st.session_state["activity_filter"] = []
    st.session_state["item_filter"] = []
    st.session_state["task_filter"] = []
    st.session_state["room_filter"] = []
    st.session_state["status_filter"] = []
    # We'll not reset date range to keep user control

# Multi-select filters
a_opts = norm_unique(all_data_for_filter, "Activity")
selected_activity_norm = st.sidebar.multiselect(
    "Filter by Activity", 
    options=a_opts,
    default=st.session_state["activity_filter"], 
    key="activity_filter"
)

i_opts = norm_unique(all_data_for_filter, "Item")
selected_item_norm = st.sidebar.multiselect(
    "Filter by Item",
    options=i_opts,
    default=st.session_state["item_filter"],
    key="item_filter"
)

t_opts = norm_unique(all_data_for_filter, "Task")
selected_task_norm = st.sidebar.multiselect(
    "Filter by Task",
    options=t_opts,
    default=st.session_state["task_filter"],
    key="task_filter"
)

r_opts = norm_unique(all_data_for_filter, "Room")
selected_room_norm = st.sidebar.multiselect(
    "Filter by Room",
    options=r_opts,
    default=st.session_state["room_filter"],
    key="room_filter"
)

s_opts = norm_unique(all_data_for_filter, "Status")
selected_statuses = st.sidebar.multiselect(
    "Filter by Status",
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

# =====================================================================
# 4. FILTER MAIN TABLE FOR GANTT
# =====================================================================
df_filtered = all_data_for_filter.copy()

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

# Date range filter
if "Start Date" in df_filtered.columns and "End Date" in df_filtered.columns:
    srange, erange = selected_date_range
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

    # aggregator
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
        """Return a single 'display' status for the aggregated row."""
        all_lower = [str(x).lower().strip() for x in st_list if x]
        if all_lower and all(s == "finished" for s in all_lower):
            return "Finished"
        if avg_prog >= 100:
            return "Finished"

        # Overdue logic
        if pd.notnull(end_dt) and end_dt < now and avg_prog < 100:
            return "Delayed"

        # Some partial progress logic
        if "in progress" in all_lower and 0 < avg_prog < 100:
            return "In Progress"
        if "in progress" in all_lower and avg_prog == 0:
            return "Just Started"

        # If we didn't match any of the above:
        return "Not Started"

    segments = []
    for _, row in grouped.iterrows():
        label = " | ".join(str(row[g]) for g in group_cols)
        st_list = row["AllStatuses"]
        start = row["GroupStart"]
        end = row["GroupEnd"]
        avgp = row["AvgProgress"] if pd.notnull(row["AvgProgress"]) else 0
        final_st = aggregated_status(st_list, avgp, start, end)

        if final_st.startswith("In Progress") and 0 < avgp < 100 and pd.notnull(start) and pd.notnull(end):
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
total_tasks = len(all_data_for_filter)

if "Status" in all_data_for_filter.columns:
    all_data_for_filter["Status"] = all_data_for_filter["Status"].astype(str).fillna("Not Started")

finished_count = all_data_for_filter[all_data_for_filter["Status"].str.lower() == "finished"].shape[0]
completion_pct = (finished_count / total_tasks * 100) if total_tasks else 0

inprogress_count = all_data_for_filter[all_data_for_filter["Status"].str.lower() == "in progress"].shape[0]
notstart_count = all_data_for_filter[all_data_for_filter["Status"].str.lower() == "not started"].shape[0]

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
# 8. SECOND TABLE: ITEMS TO ORDER (FROM Postgres)
# =====================================================================
ITEMS_TABLE = "cleaned_items"

@st.cache_data
def load_items_data() -> pd.DataFrame:
    """Load or create the 'Items to Order' table from Postgres `cleaned_items`."""
    with engine.connect() as conn:
        # If the table doesn't exist or is empty, we can handle that by creating an empty DF:
        try:
            df_i = pd.read_sql(f"SELECT * FROM {ITEMS_TABLE}", conn)
        except:
            # If table doesn't exist, create an empty DF with required columns
            df_i = pd.DataFrame(columns=["item","quantity","order_status","delivery_status","notes"])
    # Rename columns to match old code references:
    rename_map = {
        "item": "Item",
        "quantity": "Quantity",
        "order_status": "Order Status",
        "delivery_status": "Delivery Status",
        "notes": "Notes",
    }
    df_i.rename(columns=rename_map, inplace=True)
    # Ensure types
    if "Quantity" in df_i.columns:
        df_i["Quantity"] = pd.to_numeric(df_i["Quantity"], errors="coerce").fillna(0).astype(int)
    for c in ["Item","Order Status","Delivery Status","Notes"]:
        if c in df_i.columns:
            df_i[c] = df_i[c].astype(str)
    return df_i

def save_items_data(df: pd.DataFrame):
    """Overwrite the entire 'cleaned_items' table with the given DataFrame."""
    df_save = df.copy()
    # Reverse rename
    rename_map_back = {
        "Item": "item",
        "Quantity": "quantity",
        "Order Status": "order_status",
        "Delivery Status": "delivery_status",
        "Notes": "notes",
    }
    df_save.rename(columns=rename_map_back, inplace=True)

    # Ensure data types before writing
    df_save["quantity"] = pd.to_numeric(df_save["quantity"], errors="coerce").fillna(0).astype(int)

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {ITEMS_TABLE}"))
        df_save.to_sql(ITEMS_TABLE, conn, if_exists="append", index=False)


st.header("Items to Order")
df_items = load_items_data()

# Ensure columns exist
for needed_col in ["Item","Quantity","Order Status","Delivery Status","Notes"]:
    if needed_col not in df_items.columns:
        df_items[needed_col] = ""

items_col_config = {}

if "Item" in df_items.columns:
    existing_items_2 = sorted(set(df_items["Item"].dropna().unique()))
    items_col_config["Item"] = st.column_config.SelectboxColumn(
        "Item",
        options=existing_items_2,
        help="Name of the item (select or type new)",
        allow_custom_value=True
    )

if "Quantity" in df_items.columns:
    items_col_config["Quantity"] = st.column_config.NumberColumn(
        "Quantity", min_value=0, step=1, help="Enter the quantity required."
    )

# For "Order Status" → remove "Delayed" from possible options
if "Order Status" in df_items.columns:
    items_col_config["Order Status"] = st.column_config.SelectboxColumn(
        "Order Status",
        options=["Ordered", "Not Ordered"],
        help="Choose if item is ordered or not.",
        allow_custom_value=True
    )

# For "Delivery Status" → add "Delayed" as an option
if "Delivery Status" in df_items.columns:
    items_col_config["Delivery Status"] = st.column_config.SelectboxColumn(
        "Delivery Status",
        options=["Delivered", "Not Delivered", "Delayed"],
        help="Delivery status of this item.",
        allow_custom_value=True
    )

if "Notes" in df_items.columns:
    items_col_config["Notes"] = st.column_config.TextColumn(
        "Notes",
        help="Any notes or remarks."
    )

edited_df_items = st.data_editor(
    df_items,
    column_config=items_col_config,
    use_container_width=True,
    num_rows="dynamic"
)

if st.button("Save Items Table"):
    try:
        edited_df_items["Quantity"] = pd.to_numeric(edited_df_items["Quantity"], errors="coerce").fillna(0).astype(int)
        save_items_data(edited_df_items)
        st.success("Items table successfully saved to DB!")
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
