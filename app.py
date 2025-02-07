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

DB_FILE = "tasks.db"

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
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
        json.dumps(task_data["image_links"])
    ))
    conn.commit()
    conn.close()

def update_task_row(task_row):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE tasks
        SET activity=?, item=?, task=?, room=?, status=?, order_status=?, delivery_status=?, 
            progress=?, start_date=?, end_date=?, notes=?, image_links=?
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
        task_row["image_links"] if isinstance(task_row["image_links"], str) else json.dumps(task_row["image_links"]),
        int(task_row["id"])
    ))
    conn.commit()
    conn.close()

def fetch_tasks():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM tasks", conn)
    conn.close()
    
    if not df.empty:
        df["start_date"] = pd.to_datetime(df["start_date"])
        df["end_date"] = pd.to_datetime(df["end_date"])
        df["image_links"] = df["image_links"].apply(lambda x: json.loads(x) if x else [])
    return df

# Initialize database
init_db()

#################################
# APP CONFIGURATION
#################################

st.set_page_config(page_title="Task Dashboard", layout="wide")
st.title("Task Dashboard")

# Define status options
STATUS_OPTIONS = ["Not Started", "In Progress", "Finished"]
ORDER_OPTIONS = ["Not Ordered", "Ordered"]
DELIVERY_OPTIONS = ["Not Delivered", "Delivered"]

#################################
# DATA EDITOR
#################################

st.subheader("Task Editor")
df_tasks = fetch_tasks()

if not df_tasks.empty:
    edited_df = st.data_editor(
        df_tasks,
        column_config={
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=STATUS_OPTIONS,
                required=True
            ),
            "order_status": st.column_config.SelectboxColumn(
                "Order Status",
                options=ORDER_OPTIONS,
                required=True
            ),
            "delivery_status": st.column_config.SelectboxColumn(
                "Delivery Status",
                options=DELIVERY_OPTIONS,
                required=True
            ),
            "progress": st.column_config.NumberColumn(
                "Progress (%)",
                min_value=0,
                max_value=100,
                step=1,
                required=True
            ),
            "start_date": st.column_config.DateColumn("Start Date"),
            "end_date": st.column_config.DateColumn("End Date"),
            "image_links": st.column_config.Column(
                "Image Links",
                help="Click to view images"
            )
        },
        hide_index=True,
        key="task_editor",
        use_container_width=True
    )

    if st.button("Save Changes"):
        for idx, row in edited_df.iterrows():
            update_task_row(row)
        st.success("Changes saved!")
        st.experimental_rerun()

#################################
# ADD NEW TASK
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
        new_status = st.selectbox("Status", STATUS_OPTIONS)
        new_order_status = st.selectbox("Order Status", ORDER_OPTIONS)
        new_delivery_status = st.selectbox("Delivery Status", DELIVERY_OPTIONS)
        new_progress = st.slider("Progress (%)", 0, 100, 0)
    
    with col3:
        new_start_date = st.date_input("Start Date")
        new_end_date = st.date_input("End Date")
        new_notes = st.text_area("Notes")
    
    uploaded_files = st.file_uploader(
        "Upload Images",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )
    
    if st.form_submit_button("Add Task"):
        image_links = []
        if uploaded_files:
            for file in uploaded_files:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{file.name}"
                filepath = os.path.join("uploaded_images", filename)
                
                os.makedirs("uploaded_images", exist_ok=True)
                with open(filepath, "wb") as f:
                    f.write(file.getbuffer())
                
                image_links.append(f"[View Image]({filepath})")
        
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
        st.success("Task added!")
        st.experimental_rerun()

#################################
# GANTT CHART
#################################

st.subheader("Gantt Chart")

# Sidebar filters
st.sidebar.header("Filter Options")

def get_unique_values(df, col):
    return sorted(df[col].dropna().unique())

if not df_tasks.empty:
    # Filters
    selected_activities = st.sidebar.multiselect(
        "Filter by Activity",
        options=get_unique_values(df_tasks, "activity")
    )
    
    selected_rooms = st.sidebar.multiselect(
        "Filter by Room",
        options=get_unique_values(df_tasks, "room")
    )
    
    selected_status = st.sidebar.multiselect(
        "Filter by Status",
        options=STATUS_OPTIONS
    )
    
    show_finished = st.sidebar.checkbox("Show Finished Tasks", value=True)
    
    # Gantt grouping options
    st.sidebar.markdown("**Gantt Chart Options**")
    group_by = st.sidebar.multiselect(
        "Group By",
        options=["Room", "Activity", "Item"],
        default=["Activity"]
    )
    
    color_by = st.sidebar.radio(
        "Color By",
        options=["Status", "Progress"]
    )

    # Filter the dataframe
    df_gantt = df_tasks.copy()
    
    if selected_activities:
        df_gantt = df_gantt[df_gantt["activity"].isin(selected_activities)]
    if selected_rooms:
        df_gantt = df_gantt[df_gantt["room"].isin(selected_rooms)]
    if selected_status:
        df_gantt = df_gantt[df_gantt["status"].isin(selected_status)]
    if not show_finished:
        df_gantt = df_gantt[df_gantt["status"] != "Finished"]

    if not df_gantt.empty:
        # Create group label
        if group_by:
            df_gantt["Group"] = df_gantt[list(map(str.lower, group_by))].fillna('').agg(' | '.join, axis=1)
        else:
            df_gantt["Group"] = df_gantt["activity"]

        # Create Gantt chart
        if color_by == "Status":
            fig = px.timeline(
                df_gantt,
                x_start="start_date",
                x_end="end_date",
                y="Group",
                color="status",
                hover_data=["task", "progress", "order_status", "delivery_status"],
                title="Project Timeline"
            )
        else:
            fig = px.timeline(
                df_gantt,
                x_start="start_date",
                x_end="end_date",
                y="Group",
                color="progress",
                color_continuous_scale="Blues",
                range_color=[0, 100],
                hover_data=["task", "status", "order_status", "delivery_status"],
                title="Project Timeline"
            )

        fig.update_layout(
            xaxis_title="Timeline",
            yaxis_title=" | ".join(group_by),
            yaxis={'categoryorder': 'total ascending'},
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for the selected filters")

#################################
# EXPORT TO EXCEL
#################################

if st.button("Export to Excel"):
    if not df_tasks.empty:
        df_export = df_tasks.copy()
        df_export["image_links"] = df_export["image_links"].apply(lambda x: ', '.join(x) if x else '')
        
        excel_file = "tasks_export.xlsx"
        df_export.to_excel(excel_file, index=False)
        
        with open(excel_file, "rb") as f:
            st.download_button(
                "Download Excel File",
                f,
                file_name="tasks.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
