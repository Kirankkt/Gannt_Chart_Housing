import streamlit as st
import sqlite3
import os
import json
import pandas as pd
import plotly.express as px
from datetime import datetime

#################################
# DATABASE SETUP & HELPER FUNCTIONS
#################################

DB_FILE = "tasks.db"  # SQLite database file

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

def init_db():
    """Creates the tasks table if it does not exist."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity TEXT,
        item TEXT,
        task TEXT,
        room TEXT,
        status TEXT,
        order_status TEXT,
        delivery_status TEXT,
        progress INTEGER,
        start_date TEXT,
        end_date TEXT,
        notes TEXT,
        image_links TEXT
    )
    """)
    conn.commit()
    conn.close()

def insert_task(task_data):
    """Inserts a new task into the database."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO tasks (
            activity, item, task, room, status, order_status, delivery_status, progress,
            start_date, end_date, notes, image_links
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_data["activity"],
        task_data["item"],
        task_data["task"],
        task_data["room"],
        task_data["status"],
        task_data["order_status"],
        task_data["delivery_status"],
        task_data["progress"],
        task_data["start_date"].isoformat(),
        task_data["end_date"].isoformat(),
        task_data["notes"],
        json.dumps(task_data["image_links"])  # Store as JSON string
    ))
    conn.commit()
    conn.close()

def update_task_row(task_row):
    """Updates an entire task row (used by the data editor)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE tasks
        SET activity=?, item=?, task=?, room=?, status=?, order_status=?, delivery_status=?, progress=?,
            start_date=?, end_date=?, notes=?, image_links=?
        WHERE id=?
    """, (
        task_row["activity"],
        task_row["item"],
        task_row["task"],
        task_row["room"],
        task_row["status"],
        task_row["order_status"],
        task_row["delivery_status"],
        int(task_row["progress"]),
        pd.to_datetime(task_row["start_date"]).isoformat(),
        pd.to_datetime(task_row["end_date"]).isoformat(),
        task_row["notes"],
        task_row["image_links"],
        int(task_row["id"])
    ))
    conn.commit()
    conn.close()

def update_task_images(task_id, new_image_links):
    """Replaces the image_links for a given task with new_image_links (a list)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE tasks SET image_links = ? WHERE id = ?", (json.dumps(new_image_links), task_id))
    conn.commit()
    conn.close()

def fetch_tasks():
    """Fetches all tasks from the database and returns a pandas DataFrame."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks")
    rows = c.fetchall()
    columns = [desc[0] for desc in c.description]
    conn.close()
    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
        # Convert image_links JSON string back to a list
        df["image_links"] = df["image_links"].apply(lambda x: json.loads(x) if x else [])
    return df

# Initialize the database on app start
init_db()

# Helper: Force app rerun
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.info("Please refresh the page to see updated changes.")

#################################
# STREAMLIT APP LAYOUT & FUNCTIONALITY
#################################

st.set_page_config(page_title="Task Dashboard", layout="wide")
st.title("Task Dashboard")
st.markdown("""
This dashboard stores tasks in a SQLite database.  
• **Add New Task:** Enter details, select dropdown values, and upload one or more images (saved as clickable links).  
• **Data Editor:** Edit existing tasks (dropdowns for Status, Order Status, Delivery Status, and a numeric Progress field).  
• **Update Images:** Replace images for a selected task.  
• **Gantt Chart:** Displays tasks by timeline (updates automatically).  
• **Download Data:** Export the current data as an Excel file.
""")

# DOWNLOAD DATA AS EXCEL
if st.button("Download Data as Excel"):
    df_all = fetch_tasks()
    towrite = pd.ExcelWriter("download.xlsx", engine="openpyxl")
    df_all.to_excel(towrite, index=False)
    towrite.save()
    with open("download.xlsx", "rb") as f:
        st.download_button("Download Excel File", f,
                           file_name="tasks.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

#################################
# 1) DATA EDITOR FOR EXISTING TASKS
#################################
st.subheader("Data Editor: Existing Tasks")
df_tasks = fetch_tasks()
if df_tasks.empty:
    st.info("No tasks available.")
else:
    # Configure dropdowns for editing
    column_config = {
        "status": st.column_config.SelectboxColumn(
            "Status",
            options=["Not Started", "In Progress", "Finished"],
            help="Select the task status."
        ),
        "order_status": st.column_config.SelectboxColumn(
            "Order Status",
            options=["Not Ordered", "Ordered"],
            help="Select the order status."
        ),
        "delivery_status": st.column_config.SelectboxColumn(
            "Delivery Status",
            options=["Not Delivered", "Delivered"],
            help="Select the delivery status."
        ),
        "progress": st.column_config.NumberColumn(
            "Progress (%)",
            help="Task progress percentage.",
            min_value=0,
            max_value=100,
            step=1
        )
    }
    # Show the data editor
    edited_df = st.data_editor(
        df_tasks,
        column_config=column_config,
        use_container_width=True,
        key="data_editor"
    )
    if st.button("Save Changes (Data Editor)"):
        for idx, row in edited_df.iterrows():
            # For the image_links column, if the user has edited it as text, try to load it as JSON.
            try:
                imglinks = row["image_links"]
                if isinstance(imglinks, list):
                    new_links = imglinks
                else:
                    new_links = json.loads(imglinks) if imglinks else []
            except Exception:
                new_links = []
            row["image_links"] = json.dumps(new_links)
            update_task_row(row)
        st.success("Changes saved!")
        safe_rerun()

#################################
# 2) ADD NEW TASK FORM
#################################
st.subheader("Add New Task")
with st.form("new_task_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        new_activity = st.text_input("Activity")
        new_item = st.text_input("Item")
        new_task = st.text_input("Task")
        new_room = st.text_input("Room")
    with col2:
        new_status = st.selectbox("Status", ["Not Started", "In Progress", "Finished"])
        new_order_status = st.selectbox("Order Status", ["Not Ordered", "Ordered"])
        new_delivery_status = st.selectbox("Delivery Status", ["Not Delivered", "Delivered"])
        new_progress = st.slider("Progress (%)", 0, 100, 0, step=1)
    with col3:
        new_start_date = st.date_input("Start Date", value=datetime.today())
        new_end_date = st.date_input("End Date", value=datetime.today())
        new_notes = st.text_area("Notes")
    st.write("**Upload one or more images:**")
    # Allow multiple file uploads
    uploaded_files = st.file_uploader("Select image files", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="new_task_images")
    submitted = st.form_submit_button("Add Task")
    if submitted:
        image_links = []
        if uploaded_files:
            img_folder = "uploaded_images"
            os.makedirs(img_folder, exist_ok=True)
            for uploaded_file in uploaded_files:
                img_filename = uploaded_file.name
                img_path = os.path.join(img_folder, img_filename)
                with open(img_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                # Create a Markdown clickable link (assumes relative path access)
                link = f"[{img_filename}]({img_path})"
                image_links.append(link)
        task_data = {
            "activity": new_activity,
            "item": new_item,
            "task": new_task,
            "room": new_room,
            "status": new_status,
            "order_status": new_order_status,
            "delivery_status": new_delivery_status,
            "progress": new_progress,
            "start_date": new_start_date,
            "end_date": new_end_date,
            "notes": new_notes,
            "image_links": image_links
        }
        insert_task(task_data)
        st.success("New task added!")
        safe_rerun()

#################################
# 3) UPDATE IMAGES FOR EXISTING TASK
#################################
st.subheader("Update Images for Existing Task")
df_tasks = fetch_tasks()
if df_tasks.empty:
    st.info("No tasks available to update images.")
else:
    # List tasks by ID with brief info for selection
    task_options = df_tasks[['id', 'activity', 'task']].apply(
        lambda row: f"ID {row['id']}: {row['activity']} - {row['task']}", axis=1
    ).tolist()
    task_choice = st.selectbox("Select a task to update its images", options=task_options)
    selected_id = int(task_choice.split(":")[0].replace("ID", "").strip())
    st.write("**Upload one or more new images (these will replace the existing ones):**")
    new_uploaded_files = st.file_uploader("Select new images", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="update_task_images")
    if st.button("Update Images"):
        if new_uploaded_files:
            new_image_links = []
            img_folder = "uploaded_images"
            os.makedirs(img_folder, exist_ok=True)
            for uploaded_file in new_uploaded_files:
                img_filename = uploaded_file.name
                img_path = os.path.join(img_folder, img_filename)
                with open(img_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                link = f"[{img_filename}]({img_path})"
                new_image_links.append(link)
            update_task_images(selected_id, new_image_links)
            st.success(f"Images updated for task ID {selected_id}.")
            safe_rerun()
        else:
            st.warning("Please upload images to update.")

#################################
# 4) SIDEBAR FILTERS & OPTIONS
#################################
st.sidebar.header("Filter Options")
def norm_unique(df, col_name: str):
    return sorted(set(df[col_name].dropna().astype(str).str.strip()))
df_filter = fetch_tasks()
activity_opts = norm_unique(df_filter, "activity")
selected_activity = st.sidebar.multiselect("Select Activity", activity_opts, default=[])
item_opts = norm_unique(df_filter, "item")
selected_item = st.sidebar.multiselect("Select Item", item_opts, default=[])
task_opts = norm_unique(df_filter, "task")
selected_task = st.sidebar.multiselect("Select Task", task_opts, default=[])
room_opts = norm_unique(df_filter, "room")
selected_room = st.sidebar.multiselect("Select Room", room_opts, default=[])
status_opts = norm_unique(df_filter, "status")
selected_statuses = st.sidebar.multiselect("Select Status", status_opts, default=[])
show_finished = st.sidebar.checkbox("Show Finished Tasks?", value=True)
st.sidebar.markdown("**Refine Gantt Grouping**")
group_by_room = st.sidebar.checkbox("Group by Room", value=False)
group_by_item = st.sidebar.checkbox("Group by Item", value=False)
group_by_task = st.sidebar.checkbox("Group by Task", value=False)
color_mode = st.sidebar.radio("Color Gantt By:", ["Status", "Progress"], index=0)
df_dates = df_filter.dropna(subset=["start_date", "end_date"])
if df_dates.empty:
    default_min = datetime.today()
    default_max = datetime.today()
else:
    default_min = df_dates["start_date"].min()
    default_max = df_dates["end_date"].max()
selected_date_range = st.sidebar.date_input("Select Date Range", [default_min, default_max])

#################################
# 5) FILTER THE DATAFRAME
#################################
df_filtered = df_filter.copy()
if selected_activity:
    chosen = [a.lower().strip() for a in selected_activity]
    df_filtered = df_filtered[df_filtered["activity"].astype(str).str.lower().str.strip().isin(chosen)]
if selected_item:
    chosen = [a.lower().strip() for a in selected_item]
    df_filtered = df_filtered[df_filtered["item"].astype(str).str.lower().str.strip().isin(chosen)]
if selected_task:
    chosen = [a.lower().strip() for a in selected_task]
    df_filtered = df_filtered[df_filtered["task"].astype(str).str.lower().str.strip().isin(chosen)]
if selected_room:
    chosen = [a.lower().strip() for a in selected_room]
    df_filtered = df_filtered[df_filtered["room"].astype(str).str.lower().str.strip().isin(chosen)]
if selected_statuses:
    chosen = [a.lower().strip() for a in selected_statuses]
    df_filtered = df_filtered[df_filtered["status"].astype(str).str.lower().str.strip().isin(chosen)]
if not show_finished:
    df_filtered = df_filtered[df_filtered["status"].astype(str).str.lower().str.strip() != "finished"]
if len(selected_date_range) == 2:
    start_filter = pd.to_datetime(selected_date_range[0])
    end_filter = pd.to_datetime(selected_date_range[1])
    df_filtered = df_filtered[(df_filtered["start_date"] >= start_filter) & (df_filtered["end_date"] <= end_filter)]

#################################
# 6) GANTT CHART
#################################
st.subheader("Gantt Chart")
today = pd.to_datetime(datetime.today().date())
def compute_display_status(row):
    stat = row["status"].strip().lower() if pd.notnull(row["status"]) else ""
    if stat == "finished":
        return "Finished"
    if pd.notnull(row["end_date"]) and row["end_date"] < today:
        return "Delayed"
    if stat == "in progress":
        return "In Progress"
    return "Not Started"
if not df_filtered.empty:
    df_gantt = df_filtered.copy()
    df_gantt["Display Status"] = df_gantt.apply(compute_display_status, axis=1)
    group_cols = ["activity"]
    if group_by_room and "room" in df_gantt.columns:
        group_cols.append("room")
    if group_by_item and "item" in df_gantt.columns:
        group_cols.append("item")
    if group_by_task and "task" in df_gantt.columns:
        group_cols.append("task")
    if len(group_cols) > 1:
        df_gantt["Group Label"] = df_gantt[group_cols].astype(str).agg(" | ".join, axis=1)
    else:
        df_gantt["Group Label"] = df_gantt["activity"].astype(str)
    if color_mode == "Status":
        color_discrete_map = {
            "Not Started": "lightgray",
            "In Progress": "blue",
            "Delayed": "red",
            "Finished": "green"
        }
        fig = px.timeline(
            df_gantt,
            x_start="start_date",
            x_end="end_date",
            y="Group Label",
            color="Display Status",
            color_discrete_map=color_discrete_map,
            title="Gantt Chart (by Status with Delayed Logic)"
        )
        fig.update_layout(yaxis_title=" | ".join(group_cols))
    else:  # Color by Progress
        fig = px.timeline(
            df_gantt,
            x_start="start_date",
            x_end="end_date",
            y="Group Label",
            color="progress",
            range_color=[0, 100],
            color_continuous_scale="Blues",
            hover_data=["progress"],
            title="Gantt Chart (by Progress)"
        )
        fig.update_layout(yaxis_title=" | ".join(group_cols))
        fig.update_coloraxes(colorbar_title="Progress (%)")
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Timeline")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No data available for the Gantt chart (filters may have excluded all rows).")

#################################
# 7) FILTERED DATA SNAPSHOT + IMAGE GALLERY (Clickable Links)
#################################
st.subheader("Current Filtered Data Snapshot")
st.dataframe(df_filtered, use_container_width=True)

st.subheader("Image Gallery (Clickable Links)")
if df_filtered.empty:
    st.info("No tasks available for the image gallery.")
else:
    for idx, row in df_filtered.iterrows():
        st.markdown(f"**Task ID {row['id']} – {row['activity']} – {row['task']}**")
        if row["image_links"]:
            for link in row["image_links"]:
                st.markdown(link, unsafe_allow_html=True)
        else:
            st.write("No images for this task.")

st.markdown("---")
st.markdown("**End of the Dashboard**")
