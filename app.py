import streamlit as st
import sqlite3
import os
import pandas as pd
import plotly.express as px
from datetime import datetime

#################################
# Database Setup and Helper Functions
#################################

DB_FILE = "construction_tasks.db"
EXCEL_FILE = "construction_timeline.xlsx"  # Existing Excel file to import, if present

def get_connection():
    """Returns a SQLite connection."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

def init_db():
    """Initializes the database and creates the tasks table if it doesn't exist."""
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
        image_path TEXT
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
            start_date, end_date, notes, image_path
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
        task_data["image_path"]
    ))
    conn.commit()
    conn.close()

def update_task_image(task_id, image_path):
    """Updates the image path for a given task."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE tasks SET image_path = ? WHERE id = ?", (image_path, task_id))
    conn.commit()
    conn.close()

def update_task_row(task_row):
    """Update a single task row in the database using its ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE tasks
        SET activity=?, item=?, task=?, room=?, status=?, order_status=?, delivery_status=?, progress=?,
            start_date=?, end_date=?, notes=?, image_path=?
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
        task_row["image_path"],
        int(task_row["id"])
    ))
    conn.commit()
    conn.close()

def fetch_tasks():
    """Fetches all tasks from the database as a pandas DataFrame."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks")
    rows = c.fetchall()
    columns = [col[0] for col in c.description]
    conn.close()
    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        # Convert date strings back to datetime objects
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
    return df

def import_excel_to_db():
    """Imports data from an Excel file into the SQLite database if the Excel file exists."""
    if os.path.exists(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE)
        # Clean column names and convert date columns as needed
        df.columns = df.columns.str.strip()
        for col in ["Start Date", "End Date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        needed_str_cols = ["Status", "Order Status", "Delivery Status"]
        for c in needed_str_cols:
            if c not in df.columns:
                df[c] = ""
            else:
                df[c] = df[c].astype(str)
        if "Progress" not in df.columns:
            df["Progress"] = 0
        if "Image" not in df.columns:
            df["Image"] = ""
        
        # Insert each row into the database
        for index, row in df.iterrows():
            task_data = {
                "activity": row.get("Activity", ""),
                "item": row.get("Item", ""),
                "task": row.get("Task", ""),
                "room": row.get("Room", ""),
                "status": row.get("Status", ""),
                "order_status": row.get("Order Status", ""),
                "delivery_status": row.get("Delivery Status", ""),
                "progress": int(row.get("Progress", 0)),
                "start_date": row.get("Start Date", datetime.today()),
                "end_date": row.get("End Date", datetime.today()),
                "notes": row.get("Notes", ""),
                "image_path": row.get("Image", "")
            }
            insert_task(task_data)

# Initialize the database (runs once when the app starts)
init_db()

# Import Excel data if the database is empty and the Excel file exists
if fetch_tasks().empty and os.path.exists(EXCEL_FILE):
    import_excel_to_db()

#################################
# Helper: Safe rerun
#################################
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.info("Please refresh the page to see updated changes.")

#################################
# Streamlit App Layout and Functionality
#################################

st.set_page_config(page_title="Robust Construction Dashboard with SQLite", layout="wide")
st.title("Robust Construction Project Dashboard")
st.markdown("""
This dashboard uses a SQLite database to store project tasks along with image file paths.
Uploaded images are saved in a dedicated folder (`uploaded_images`), and only their relative paths are stored.
Features include:
- **Data Editor**: Update existing tasks.
- **Add New Task**: Insert brand-new tasks.
- **Update Image**: Replace or add images for a task.
- **Filters & Options**: Filter tasks by Activity, Item, Task, Room, Status, date range, etc.
- **Gantt Chart**: Visual timeline (color by Status or Progress).
- **Image Gallery**: View images attached to tasks.
""")

#################################
# 1) Data Editor for Existing Rows
#################################
st.subheader("Data Editor: Existing Tasks")
df_tasks = fetch_tasks()
st.write("DEBUG: Data from database", df_tasks)  # For troubleshooting

if df_tasks.empty:
    st.info("No tasks found in the database. If you have an Excel file, ensure it is named 'construction_timeline.xlsx'.")
else:
    # Allow in-place editing of tasks
    edited_df = st.data_editor(
        df_tasks,
        use_container_width=True,
        key="data_editor"
    )
    if st.button("Save Changes (Data Editor)"):
        for idx, row in edited_df.iterrows():
            update_task_row(row)
        st.success("Changes saved successfully!")
        safe_rerun()

#################################
# 2) Add New Task Form
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
    
    st.write("**Optionally, upload an image** for this task:")
    uploaded_file_new = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"], key="new_task_upload")
    submitted = st.form_submit_button("Add Task")
    
    if submitted:
        img_relative_path = ""
        if uploaded_file_new is not None:
            img_folder = "uploaded_images"
            os.makedirs(img_folder, exist_ok=True)
            img_filename = uploaded_file_new.name
            img_relative_path = os.path.join(img_folder, img_filename)
            with open(img_relative_path, "wb") as f:
                f.write(uploaded_file_new.getbuffer())
        
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
            "image_path": img_relative_path
        }
        insert_task(task_data)
        st.success("New task added successfully!")
        safe_rerun()

#################################
# 3) Update Image for Existing Task
#################################
st.subheader("Update Image for Existing Task")
df_tasks = fetch_tasks()
if df_tasks.empty:
    st.info("No tasks available to update images.")
else:
    task_options = df_tasks[['id', 'activity', 'task']].apply(
        lambda row: f"ID {row['id']}: {row['activity']} - {row['task']}", axis=1
    ).tolist()
    task_choice = st.selectbox("Select a task to update its image", options=task_options)
    selected_id = int(task_choice.split(":")[0].replace("ID", "").strip())
    uploaded_file_existing = st.file_uploader("Upload new image", type=["jpg", "jpeg", "png"], key="update_task_upload")
    if st.button("Update Image"):
        if uploaded_file_existing is not None:
            img_folder = "uploaded_images"
            os.makedirs(img_folder, exist_ok=True)
            img_filename = uploaded_file_existing.name
            new_img_path = os.path.join(img_folder, img_filename)
            with open(new_img_path, "wb") as f:
                f.write(uploaded_file_existing.getbuffer())
            update_task_image(selected_id, new_img_path)
            st.success(f"Image updated for task ID {selected_id}.")
            safe_rerun()
        else:
            st.warning("Please upload an image to update.")

#################################
# 4) Sidebar Filters & Options
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
# 5) Filter the DataFrame
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
    df_filtered = df_filtered[
        (df_filtered["start_date"] >= start_filter) & 
        (df_filtered["end_date"] <= end_filter)
    ]

#################################
# 6) Gantt Chart
#################################
st.subheader("Gantt Chart")
today = pd.to_datetime(datetime.today().date())

def compute_display_status(row):
    status = row["status"].strip().lower() if pd.notnull(row["status"]) else ""
    if status == "finished":
        return "Finished"
    if pd.notnull(row["end_date"]) and row["end_date"] < today:
        return "Delayed"
    if status == "in progress":
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
            title="Gantt Chart (Color by Status with Delayed Logic)"
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
            title="Gantt Chart (Color by Average Progress)"
        )
        fig.update_layout(yaxis_title=" | ".join(group_cols))
        fig.update_coloraxes(colorbar_title="Progress (%)")
    
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Timeline")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No data available for the Gantt chart (filters may have excluded all rows).")

#################################
# 7) Filtered Data Snapshot + Image Gallery
#################################
st.subheader("Current Filtered Data Snapshot")
st.dataframe(df_filtered, use_container_width=True)

st.subheader("Image Gallery (Filtered Tasks)")
if df_filtered.empty:
    st.info("No tasks available for the image gallery.")
else:
    for idx, row in df_filtered.iterrows():
        st.markdown(f"**Task ID {row['id']} - {row['activity']} - {row['task']}**")
        if row["image_path"] and os.path.exists(row["image_path"]):
            st.image(row["image_path"], caption=os.path.basename(row["image_path"]), use_container_width=True)
        else:
            st.write("No image found for this task.")

st.markdown("---")
st.markdown("**End of the Dashboard**")
