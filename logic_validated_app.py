import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
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
# DATABASE INITIALIZATION
# ---------------------------------------------------------------------
DB_FILE = "dashboard.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Create timeline table if it does not exist.
    c.execute("""CREATE TABLE IF NOT EXISTS timeline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Activity TEXT,
        Item TEXT,
        Task TEXT,
        Room TEXT,
        Location TEXT,
        Notes TEXT,
        "Start Date" DATETIME,
        "End Date" DATETIME,
        Status TEXT,
        Progress REAL,
        Workdays INTEGER
    )""")
    # Create items table if it does not exist.
    c.execute("""CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Item TEXT,
        Quantity INTEGER,
        "Order Status" TEXT,
        "Delivery Status" TEXT,
        Notes TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------------------
# HELPER FUNCTIONS FOR TIMELINE TABLE
# ---------------------------------------------------------------------
def load_timeline_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM timeline", conn)
    conn.close()
    # If table is empty, create an empty DataFrame with the expected columns.
    if df.empty:
        cols = ["Activity", "Item", "Task", "Room", "Location", "Notes", "Start Date", "End Date", "Status", "Progress", "Workdays"]
        df = pd.DataFrame(columns=cols)
    # Drop the 'id' column for editing purposes.
    df = df.drop(columns=["id"], errors="ignore")
    # Ensure date columns are in datetime format.
    if "Start Date" in df.columns:
        df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    if "End Date" in df.columns:
        df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    # Ensure Progress and Status exist.
    if "Progress" not in df.columns:
        df["Progress"] = 0.0
    if "Status" not in df.columns:
        df["Status"] = "Not Started"
    df["Progress"] = pd.to_numeric(df["Progress"], errors="coerce").fillna(0)
    df["Status"] = df["Status"].astype(str).fillna("Not Started")
    return df

def save_timeline_data(df: pd.DataFrame):
    conn = sqlite3.connect(DB_FILE)
    # Replace the timeline table with the new DataFrame.
    df.to_sql("timeline", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------
# HELPER FUNCTIONS FOR ITEMS TABLE
# ---------------------------------------------------------------------
def load_items_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM items", conn)
    conn.close()
    if df.empty:
        cols = ["Item", "Quantity", "Order Status", "Delivery Status", "Notes"]
        df = pd.DataFrame(columns=cols)
    # Drop the 'id' column for editing.
    df = df.drop(columns=["id"], errors="ignore")
    return df

def save_items_data(df: pd.DataFrame):
    conn = sqlite3.connect(DB_FILE)
    df.to_sql("items", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------
# 1. LOAD TIMELINE DATA
# ---------------------------------------------------------------------
df_main = load_timeline_data()

# ---------------------------------------------------------------------
# 2. MAIN TIMELINE: EDIT & SAVE
# ---------------------------------------------------------------------
st.subheader("Update Task Information (Main Timeline)")

with st.sidebar.expander("Row & Column Management (Main Timeline)"):
    # ----- Delete Row -----
    st.markdown("*Delete a row by index*")
    delete_index = st.text_input("Enter row index to delete (main table)", value="")
    if st.button("Delete Row (Main)"):
        if delete_index.isdigit():
            idx = int(delete_index)
            if 0 <= idx < len(df_main):
                df_main = df_main.drop(df_main.index[idx]).reset_index(drop=True)
                save_timeline_data(df_main)
                st.sidebar.success(f"Row {idx} deleted and saved.")
                df_main = load_timeline_data()
            else:
                st.sidebar.error("Invalid index.")
        else:
            st.sidebar.error("Please enter a valid integer index.")
    # ----- Add Column -----
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
            save_timeline_data(df_main)
            st.sidebar.success(f"Column '{new_col_name}' added and saved.")
            df_main = load_timeline_data()
        elif new_col_name in df_main.columns:
            st.sidebar.warning("Column already exists or invalid name.")
        else:
            st.sidebar.warning("Please enter a valid column name.")
    # ----- Delete Column -----
    st.markdown("*Delete a column*")
    col_to_delete = st.selectbox("Select Column to Delete (main table)", options=[""] + list(df_main.columns), index=0)
    if st.button("Delete Column (Main)"):
        if col_to_delete and col_to_delete in df_main.columns:
            df_main = df_main.drop(columns=[col_to_delete])
            save_timeline_data(df_main)
            st.sidebar.success(f"Column '{col_to_delete}' deleted and saved.")
            df_main = load_timeline_data()
        else:
            st.sidebar.warning("Please select a valid column.")

# Configure columns for st.data_editor
column_config_main = {}
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

# Use st.data_editor to allow editing
edited_df_main = st.data_editor(
    df_main,
    column_config=column_config_main,
    use_container_width=True,
    num_rows="dynamic"
)

# Force Status to string
if "Status" in edited_df_main.columns:
    edited_df_main["Status"] = edited_df_main["Status"].astype(str).fillna("Not Started")

# --- Auto-update Progress when Status is Finished ---
if "Status" in edited_df_main.columns and "Progress" in edited_df_main.columns:
    mask_finished = edited_df_main["Status"].str.lower() == "finished"
    if mask_finished.any() and not edited_df_main.loc[mask_finished, "Progress"].eq(100).all():
        edited_df_main.loc[mask_finished, "Progress"] = 100
        # If supported, force a rerun to update the UI immediately.
        try:
            st.experimental_rerun()
        except AttributeError:
            st.warning("Auto-refresh is not available in your Streamlit version. Please consider upgrading.")

# Save Updates button (write the updated DataFrame to SQLite)
if st.button("Save Updates (Main Timeline)"):
    edited_df_main.loc[edited_df_main["Status"].str.lower() == "finished", "Progress"] = 100
    try:
        save_timeline_data(edited_df_main)
        st.success("Main timeline data successfully saved!")
        df_main = load_timeline_data()
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

# Initialize filter session states if not already present.
for key in ["activity_filter", "item_filter", "task_filter", "room_filter", "status_filter"]:
    if key not in st.session_state:
        st.session_state[key] = []

default_date_range = (
    edited_df_main["Start Date"].min() if "Start Date" in edited_df_main.columns and not edited_df_main["Start Date"].isnull().all() else datetime.today(),
    edited_df_main["End Date"].max() if "End Date" in edited_df_main.columns and not edited_df_main["End Date"].isnull().all() else datetime.today()
)
selected_date_range = st.sidebar.date_input("Filter Date Range", value=default_date_range, key="date_range")

if st.sidebar.button("Clear Filters (Main)"):
    for key in ["activity_filter", "item_filter", "task_filter", "room_filter", "status_filter"]:
        st.session_state[key] = []

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

# ---------------------------------------------------------------------
# 4. FILTER MAIN TABLE FOR GANTT
# ---------------------------------------------------------------------
df_filtered = edited_df_main.copy()
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
if "Start Date" in df_filtered.columns and "End Date" in df_filtered.columns:
    srange, erange = selected_date_range
    srange = pd.to_datetime(srange)
    erange = pd.to_datetime(erange)
    df_filtered = df_filtered[(df_filtered["Start Date"] >= srange) & (df_filtered["End Date"] <= erange)]
normcols = [c for c in df_filtered.columns if c.endswith("_norm")]
df_filtered.drop(columns=normcols, inplace=True, errors="ignore")

# ---------------------------------------------------------------------
# 5. GANTT CHART FUNCTION
# ---------------------------------------------------------------------
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
        df_input.groupby(group_cols, dropna=False)
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

# ---------------------------------------------------------------------
# 6. KPI & CALCULATIONS
# ---------------------------------------------------------------------
total_tasks = len(edited_df_main)
if "Status" in edited_df_main.columns:
    edited_df_main["Status"] = edited_df_main["Status"].astype(str).fillna("Not Started")
finished_count = edited_df_main[edited_df_main["Status"].str.lower() == "finished"].shape[0]
completion_pct = (finished_count / total_tasks * 100) if total_tasks else 0
inprogress_count = edited_df_main[edited_df_main["Status"].str.lower() == "in progress"].shape[0]
notstart_count = edited_df_main[edited_df_main["Status"].str.lower() == "not started"].shape[0]
today_dt = pd.Timestamp(datetime.today().date())
if "End Date" in df_filtered.columns:
    overdue_df = df_filtered[(df_filtered["End Date"] < today_dt) & (df_filtered["Status"].str.lower() != "finished")]
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
    next7_df = df_filtered[(df_filtered["Start Date"] >= today_dt) & (df_filtered["Start Date"] <= today_dt + pd.Timedelta(days=7))]
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

# ---------------------------------------------------------------------
# 8. SECOND TABLE: ITEMS TO ORDER
# ---------------------------------------------------------------------
st.header("Items to Order")
df_items = load_items_data()
# Ensure all needed columns exist.
for col in ["Item", "Quantity", "Order Status", "Delivery Status", "Notes"]:
    if col not in df_items.columns:
        df_items[col] = ""
df_items["Item"] = df_items["Item"].astype(str)
df_items["Quantity"] = pd.to_numeric(df_items["Quantity"], errors="coerce").fillna(0).astype(int)
df_items["Order Status"] = df_items["Order Status"].astype(str)
df_items["Delivery Status"] = df_items["Delivery Status"].astype(str)
df_items["Notes"] = df_items["Notes"].astype(str)
items_col_config = {}
items_col_config["Item"] = st.column_config.TextColumn("Item", help="Name of the item")
items_col_config["Quantity"] = st.column_config.NumberColumn("Quantity", min_value=0, step=1, help="Enter the quantity required.")
items_col_config["Order Status"] = st.column_config.SelectboxColumn("Order Status", options=["Ordered", "Not Ordered"], help="Choose if this item is ordered or not ordered.")
items_col_config["Delivery Status"] = st.column_config.SelectboxColumn("Delivery Status", options=["Delivered", "Not Delivered", "Delayed"], help="Has it been delivered, not delivered, or delayed?")
items_col_config["Notes"] = st.column_config.TextColumn("Notes", help="Type any notes or remarks here.")
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
        st.success("Items table successfully saved!")
    except Exception as e:
        st.error(f"Error saving items table: {e}")
csv_buffer = io.StringIO()
edited_df_items.to_csv(csv_buffer, index=False)
st.download_button(
    label="Download Items Table as CSV",
    data=csv_buffer.getvalue(),
    file_name="Cleaned_Items_Table.csv",
    mime="text/csv"
)
