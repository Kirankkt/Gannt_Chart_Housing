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
# HIDE THE BUG TOOLTIP IN st.data_editor
# ---------------------------------------------------------------------
hide_stdataeditor_bug_tooltip = """
<style>
[data-testid="stDataEditor"] [role="tooltip"] {
    visibility: hidden !important;
}
</style>
"""
st.markdown(hide_stdataeditor_bug_tooltip, unsafe_allow_html=True)

# ---------------------------------------------------------------------
# POSTGRESQL SETUP
# ---------------------------------------------------------------------
@st.cache_resource
def get_sql_engine():
    connection_string = st.secrets["postgresql"]["connection_string"]
    return create_engine(connection_string)

engine = get_sql_engine()

# Table names for our two datasets:
TIMELINE_TABLE = "construction_timeline_2"
ITEMS_TABLE = "cleaned_items"

# ---------------------------------------------------------------------
# HELPER FUNCTIONS: LOAD & SAVE DATA FROM/TO POSTGRESQL
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_timeline_data_sql() -> pd.DataFrame:
    """
    Load the main timeline DataFrame from PostgreSQL.
    Expects columns: activity, task, room, location, start_date, end_date, status
    We'll also add a 'progress' column if it doesn't exist.
    """
    try:
        df = pd.read_sql(f"SELECT * FROM {TIMELINE_TABLE}", engine)
    except Exception as e:
        st.error(f"Error loading table '{TIMELINE_TABLE}': {e}")
        st.stop()

    df.columns = df.columns.str.lower().str.strip()
    if "start_date" in df.columns:
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    if "end_date" in df.columns:
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
    if "progress" not in df.columns:
        df["progress"] = 0.0
    if "status" not in df.columns:
        df["status"] = "Not Started"

    df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)
    df["status"] = df["status"].astype(str).fillna("Not Started")
    return df

def save_timeline_data_sql(df: pd.DataFrame):
    """Save the timeline DataFrame back to PostgreSQL."""
    try:
        df.to_sql(TIMELINE_TABLE, engine, if_exists="replace", index=False)
        st.sidebar.success("Timeline data saved to PostgreSQL successfully!")
    except Exception as e:
        st.sidebar.error(f"Error saving timeline data: {e}")

@st.cache_data(show_spinner=False)
def load_items_data_sql() -> pd.DataFrame:
    """
    Load the 'Items to Order' DataFrame from PostgreSQL.
    Expects columns: item, quantity, order_status, delivery_status, notes
    """
    try:
        df_i = pd.read_sql(f"SELECT * FROM {ITEMS_TABLE}", engine)
    except Exception:
        df_i = pd.DataFrame(columns=["item", "quantity", "order_status", "delivery_status", "notes"])
    df_i.columns = df_i.columns.str.lower().str.strip()
    return df_i

def save_items_data_sql(df: pd.DataFrame):
    """Save the items DataFrame back to PostgreSQL."""
    try:
        df.to_sql(ITEMS_TABLE, engine, if_exists="replace", index=False)
        st.success("Items table saved to PostgreSQL successfully!")
    except Exception as e:
        st.error(f"Error saving items table: {e}")

# ---------------------------------------------------------------------
# 1. LOAD MAIN TIMELINE DATA
# ---------------------------------------------------------------------
df_main = load_timeline_data_sql()

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
                save_timeline_data_sql(df_main)
                st.sidebar.success(f"Row {idx} deleted and saved.")
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
                df_main[new_col_name] = ""
                df_main[new_col_name] = df_main[new_col_name].astype(object)
            elif new_col_type == "integer":
                df_main[new_col_name] = 0
            elif new_col_type == "float":
                df_main[new_col_name] = 0.0
            elif new_col_type == "datetime":
                df_main[new_col_name] = pd.NaT
            save_timeline_data_sql(df_main)
            st.sidebar.success(f"Column '{new_col_name}' added and saved.")
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
            save_timeline_data_sql(df_main)
            st.sidebar.success(f"Column '{col_to_delete}' deleted and saved.")
        else:
            st.sidebar.warning("Please select a valid column.")

# Use TextColumn for free text entry with suggestions
column_config_main = {}
for col in ["activity", "item", "task", "room", "location"]:
    if col in df_main.columns:
        placeholder = ", ".join(sorted(df_main[col].dropna().unique()))
        column_config_main[col] = st.column_config.TextColumn(
            col, placeholder=placeholder, help=f"{col.capitalize()} (type new value if needed)"
        )
if "status" in df_main.columns:
    column_config_main["status"] = st.column_config.SelectboxColumn(
        "status", options=["Finished", "In Progress", "Not Started"], help="Status"
    )
if "progress" in df_main.columns:
    column_config_main["progress"] = st.column_config.NumberColumn(
        "progress", min_value=0, max_value=100, step=1, help="Progress %"
    )

edited_df_main = st.data_editor(
    df_main,
    column_config=column_config_main,
    use_container_width=True,
    num_rows="dynamic"
)

if "status" in edited_df_main.columns:
    edited_df_main["status"] = edited_df_main["status"].astype(str).fillna("Not Started")
    mask_finished = edited_df_main["status"].str.lower() == "finished"
    if "progress" in edited_df_main.columns:
        edited_df_main.loc[mask_finished, "progress"] = 100

if st.button("Save Updates (Main Timeline)"):
    try:
        save_timeline_data_sql(edited_df_main)
        st.success("Main timeline data successfully saved!")
        st.experimental_rerun()  # Refresh the page so new data is reloaded in snapshot & Gantt chart
    except Exception as e:
        st.error(f"Error saving main timeline: {e}")

# ---------------------------------------------------------------------
# 3. SIDEBAR FILTERS FOR MAIN TIMELINE
# ---------------------------------------------------------------------
st.sidebar.header("Filter Options (Main Timeline)")

def norm_unique(df_input: pd.DataFrame, col: str):
    if col not in df_input.columns:
        return []
    return sorted(set(df_input[col].dropna().astype(str).str.lower().str.strip()))

for key in ["activity_filter", "item_filter", "task_filter", "room_filter", "location_filter", "status_filter"]:
    if key not in st.session_state:
        st.session_state[key] = []

default_date_range = (
    edited_df_main["start_date"].min() if "start_date" in edited_df_main.columns and not edited_df_main["start_date"].isnull().all() else datetime.today(),
    edited_df_main["end_date"].max() if "end_date" in edited_df_main.columns and not edited_df_main["end_date"].isnull().all() else datetime.today()
)
selected_date_range = st.sidebar.date_input("Filter Date Range", value=default_date_range, key="date_range")

if st.sidebar.button("Clear Filters (Main)"):
    for key in ["activity_filter", "item_filter", "task_filter", "room_filter", "location_filter", "status_filter"]:
        st.session_state[key] = []

if "activity" in edited_df_main.columns:
    a_opts = norm_unique(edited_df_main, "activity")
    selected_activity_norm = st.sidebar.multiselect(
        "Filter by Activity", options=a_opts,
        default=st.session_state["activity_filter"], key="activity_filter"
    )
else:
    selected_activity_norm = []

if "item" in edited_df_main.columns:
    i_opts = norm_unique(edited_df_main, "item")
    selected_item_norm = st.sidebar.multiselect(
        "Filter by Item", options=i_opts,
        default=st.session_state["item_filter"], key="item_filter"
    )
else:
    selected_item_norm = []

if "task" in edited_df_main.columns:
    t_opts = norm_unique(edited_df_main, "task")
    selected_task_norm = st.sidebar.multiselect(
        "Filter by Task", options=t_opts,
        default=st.session_state["task_filter"], key="task_filter"
    )
else:
    selected_task_norm = []

if "room" in edited_df_main.columns:
    r_opts = norm_unique(edited_df_main, "room")
    selected_room_norm = st.sidebar.multiselect(
        "Filter by Room", options=r_opts,
        default=st.session_state["room_filter"], key="room_filter"
    )
else:
    selected_room_norm = []

if "location" in edited_df_main.columns:
    loc_opts = norm_unique(edited_df_main, "location")
    selected_location_norm = st.sidebar.multiselect(
        "Filter by Location", options=loc_opts,
        default=st.session_state["location_filter"], key="location_filter"
    )
else:
    selected_location_norm = []

if "status" in edited_df_main.columns:
    s_opts = norm_unique(edited_df_main, "status")
    selected_statuses = st.sidebar.multiselect(
        "Filter by Status", options=s_opts,
        default=st.session_state["status_filter"], key="status_filter"
    )
else:
    selected_statuses = []

show_finished = st.sidebar.checkbox("Show Finished Tasks", value=True)
color_by_status = st.sidebar.checkbox("Color-code Gantt Chart by Status", value=True)

st.sidebar.markdown("*Refine Gantt Grouping*")
group_by_room = st.sidebar.checkbox("Group by Room", value=False)
group_by_task = st.sidebar.checkbox("Group by Task", value=False)
group_by_location = st.sidebar.checkbox("Group by Location", value=False)

df_filtered = edited_df_main.copy()
for col in ["activity", "item", "task", "room", "location", "status"]:
    if col in df_filtered.columns:
        df_filtered[col + "_norm"] = df_filtered[col].astype(str).str.lower().str.strip()

if selected_activity_norm and "activity_norm" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["activity_norm"].isin(selected_activity_norm)]
if selected_item_norm and "item_norm" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["item_norm"].isin(selected_item_norm)]
if selected_task_norm and "task_norm" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["task_norm"].isin(selected_task_norm)]
if selected_room_norm and "room_norm" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["room_norm"].isin(selected_room_norm)]
if selected_location_norm and "location_norm" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["location_norm"].isin(selected_location_norm)]
if selected_statuses and "status_norm" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["status_norm"].isin(selected_statuses)]

if not show_finished and "status_norm" in df_filtered.columns:
    df_filtered = df_filtered[~df_filtered["status_norm"].isin(["finished"])]

if "start_date" in df_filtered.columns and "end_date" in df_filtered.columns:
    srange, erange = selected_date_range
    srange = pd.to_datetime(srange)
    erange = pd.to_datetime(erange)
    df_filtered = df_filtered[
        (df_filtered["start_date"] >= srange) &
        (df_filtered["end_date"] <= erange)
    ]

normcols = [c for c in df_filtered.columns if c.endswith("_norm")]
df_filtered.drop(columns=normcols, inplace=True, errors="ignore")

# ---------------------------------------------------------------------
# 5. GANTT CHART FUNCTION
# ---------------------------------------------------------------------
def create_gantt_chart(df_input: pd.DataFrame, color_by_status: bool = True):
    """
    Build a Gantt chart using columns: start_date, end_date, status, progress.
    We'll group by activity + optional user checkboxes (room, task, location).
    """
    needed = ["start_date", "end_date", "status", "progress"]
    missing = [c for c in needed if c not in df_input.columns]
    if missing:
        return px.scatter(title=f"Cannot build Gantt: missing {missing}")
    if df_input.empty:
        return px.scatter(title="No data to display for Gantt")

    group_cols = []
    if "activity" in df_input.columns:
        group_cols.append("activity")
    if group_by_room and "room" in df_input.columns:
        group_cols.append("room")
    if group_by_task and "task" in df_input.columns:
        group_cols.append("task")
    if group_by_location and "location" in df_input.columns:
        group_cols.append("location")

    if not group_cols:
        return px.scatter(title="No valid columns to group by for Gantt")

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
        "start_date": "group_start",
        "end_date": "group_end",
        "progress": "avg_progress",
        "status": "all_statuses"
    }, inplace=True)
    now = pd.Timestamp(datetime.today().date())

    def aggregated_status(st_list, avg_prog, start_dt, end_dt):
        all_lower = [str(x).lower().strip() for x in st_list]
        if all(s == "finished" for s in all_lower) or avg_prog >= 100:
            return "Finished"
        if end_dt < now and avg_prog < 100:
            return "Delayed"
        total_duration = (end_dt - start_dt).total_seconds() or 1
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
        label_parts = [str(row[g]) for g in group_cols]
        label = " | ".join(label_parts)
        st_list = row["all_statuses"]
        start = row["group_start"]
        end = row["group_end"]
        avgp = row["avg_progress"]
        final_st = aggregated_status(st_list, avgp, start, end)
        if final_st == "In Progress" and 0 < avgp < 100:
            total_s = (end - start).total_seconds()
            done_s = total_s * (avgp / 100.0)
            done_end = start + pd.Timedelta(seconds=done_s)
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
        color="Display Status" if color_by_status else None,
        color_discrete_map=color_map if color_by_status else {}
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Timeline", showlegend=True)
    return fig

gantt_fig = create_gantt_chart(df_filtered, color_by_status=color_by_status)

# ---------------------------------------------------------------------
# 6. KPI & CALCULATIONS
# ---------------------------------------------------------------------
total_tasks = len(edited_df_main)
if "status" in edited_df_main.columns:
    edited_df_main["status"] = edited_df_main["status"].astype(str).fillna("Not Started")
finished_count = edited_df_main[edited_df_main["status"].str.lower() == "finished"].shape[0]
completion_pct = (finished_count / total_tasks * 100) if total_tasks else 0
inprogress_count = edited_df_main[edited_df_main["status"].str.lower() == "in progress"].shape[0]
notstart_count = edited_df_main[edited_df_main["status"].str.lower() == "not started"].shape[0]
today_dt = pd.Timestamp(datetime.today().date())
if "end_date" in df_filtered.columns and "status" in df_filtered.columns:
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
filt_summ = []
if "activity_filter" in st.session_state and st.session_state["activity_filter"]:
    filt_summ.append("Activities: " + ", ".join(st.session_state["activity_filter"]))
if "item_filter" in st.session_state and st.session_state["item_filter"]:
    filt_summ.append("Items: " + ", ".join(st.session_state["item_filter"]))
if "task_filter" in st.session_state and st.session_state["task_filter"]:
    filt_summ.append("Tasks: " + ", ".join(st.session_state["task_filter"]))
if "room_filter" in st.session_state and st.session_state["room_filter"]:
    filt_summ.append("Rooms: " + ", ".join(st.session_state["room_filter"]))
if "location_filter" in st.session_state and st.session_state["location_filter"]:
    filt_summ.append("Locations: " + ", ".join(st.session_state["location_filter"]))
if "status_filter" in st.session_state and st.session_state["status_filter"]:
    filt_summ.append("Status: " + ", ".join(st.session_state["status_filter"]))
if selected_date_range:
    d0, d1 = selected_date_range
    filt_summ.append(f"Date Range: {d0} to {d1}")
filt_text = "; ".join(filt_summ) if filt_summ else "No filters applied."

# ---------------------------------------------------------------------
# 7. DISPLAY MAIN TIMELINE DASHBOARD
# ---------------------------------------------------------------------
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
mcol1, mcol2, mcol3, mcol4 = st.columns(4)
mcol1.metric("Total Tasks", total_tasks)
mcol2.metric("In Progress", inprogress_count)
mcol3.metric("Finished", finished_count)
mcol4.metric("Not Started", notstart_count)
st.markdown("Use the filters on the sidebar to adjust the view.")
st.markdown("---")

# ---------------------------------------------------------------------
# 8. SECOND TABLE: ITEMS TO ORDER
# ---------------------------------------------------------------------
st.header("Items to Order")
df_items = load_items_data_sql()
for needed_col in ["item", "quantity", "order_status", "delivery_status", "notes"]:
    if needed_col not in df_items.columns:
        df_items[needed_col] = ""
df_items["item"] = df_items["item"].astype(str)
df_items["quantity"] = pd.to_numeric(df_items["quantity"], errors="coerce").fillna(0).astype(int)
df_items["order_status"] = df_items["order_status"].astype(str)
df_items["delivery_status"] = df_items["delivery_status"].astype(str)
df_items["notes"] = df_items["notes"].astype(str)
items_col_config = {}
if "item" in df_items.columns:
    placeholder = ", ".join(sorted(df_items["item"].dropna().unique()))
    items_col_config["item"] = st.column_config.TextColumn(
        "item", placeholder=placeholder, help="Name of the item (type new value if needed)"
    )
items_col_config["quantity"] = st.column_config.NumberColumn("quantity", min_value=0, step=1, help="Enter the quantity required.")
items_col_config["order_status"] = st.column_config.SelectboxColumn(
    "order_status",
    options=["Ordered", "Not Ordered"],
    help="Choose if this item is ordered or not ordered."
)
items_col_config["delivery_status"] = st.column_config.SelectboxColumn(
    "delivery_status",
    options=["Delivered", "Not Delivered", "Delayed"],
    help="Has it been delivered, not delivered, or delayed?"
)
items_col_config["notes"] = st.column_config.TextColumn("notes", help="Type any notes or remarks here.")
edited_df_items = st.data_editor(
    df_items,
    column_config=items_col_config,
    use_container_width=True,
    num_rows="dynamic"
)
if st.button("Save Items Table"):
    try:
        edited_df_items["quantity"] = pd.to_numeric(edited_df_items["quantity"], errors="coerce").fillna(0).astype(int)
        save_items_data_sql(edited_df_items)
        st.success("Items table successfully saved to PostgreSQL!")
    except Exception as e:
        st.error(f"Error saving items table: {e}")
csv_buffer = io.StringIO()
edited_df_items.to_csv(csv_buffer, index=False)
st.download_button(
    label="Download Items Table as CSV",
    data=csv_buffer.getvalue(),
    file_name="cleaned_items.csv",
    mime="text/csv"
)
