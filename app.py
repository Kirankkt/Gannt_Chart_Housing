import streamlit as st
import sqlite3
import os
import json
import pandas as pd
import plotly.express as px
from datetime import datetime

#################################
# DATABASE SETUP
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

def fetch_tasks():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM tasks", conn)
    conn.close()
    if not df.empty:
        df["start_date"] = pd.to_datetime(df["start_date"])
        df["end_date"] = pd.to_datetime(df["end_date"])
        df["image_links"] = df["image_links"].apply(lambda x: json.loads(x) if x else [])
    return df

#################################
# CONSTANTS
#################################

STATUS_OPTIONS = ["Not Started", "In Progress", "Finished", "Delivered", "Not Delivered"]
ORDER_OPTIONS = ["Ordered", "Not Ordered"]
PROGRESS_DEFAULT = 0

#################################
# SIDEBAR FILTERS
#################################

st.sidebar.title("Filter Options")

def create_filter_section():
    st.sidebar.markdown("Select Activity (leave empty for all)")
    activity_filter = st.sidebar.selectbox(
        "",
        ["Choose an option"] + list(fetch_tasks()["activity"].unique()),
        key="activity_filter"
    )
    
    st.sidebar.markdown("Select Item (leave empty for all)")
    item_filter = st.sidebar.selectbox(
        "",
        ["Choose an option"] + list(fetch_tasks()["item"].unique()),
        key="item_filter"
    )
    
    st.sidebar.markdown("Select Task (leave empty for all)")
    task_filter = st.sidebar.selectbox(
        "",
        ["Choose an option"] + list(fetch_tasks()["task"].unique()),
        key="task_filter"
    )
    
    st.sidebar.markdown("Select Room (leave empty for all)")
    room_filter = st.sidebar.selectbox(
        "",
        ["Choose an option"] + list(fetch_tasks()["room"].unique()),
        key="room_filter"
    )
    
    st.sidebar.markdown("Select Status (leave empty for all)")
    status_filter = st.sidebar.selectbox(
        "",
        ["Choose an option"] + STATUS_OPTIONS,
        key="status_filter"
    )
    
    show_finished = st.sidebar.checkbox("Show Finished Tasks", value=True)
    color_code_status = st.sidebar.checkbox("Color-code Gantt Chart by Activity Status", value=True)
    
    st.sidebar.markdown("Refine Gantt Grouping")
    group_by_room = st.sidebar.checkbox("Group by Room")
    group_by_item = st.sidebar.checkbox("Group by Item")
    group_by_task = st.sidebar.checkbox("Group by Task")
    
    return {
        "activity": None if activity_filter == "Choose an option" else activity_filter,
        "item": None if item_filter == "Choose an option" else item_filter,
        "task": None if task_filter == "Choose an option" else task_filter,
        "room": None if room_filter == "Choose an option" else room_filter,
        "status": None if status_filter == "Choose an option" else status_filter,
        "show_finished": show_finished,
        "color_code_status": color_code_status,
        "grouping": {
            "room": group_by_room,
            "item": group_by_item,
            "task": group_by_task
        }
    }

#################################
# MAIN APP
#################################

st.title("Task Dashboard")

# Task Viewer
st.header("Task Viewer")
tasks_df = fetch_tasks()
if not tasks_df.empty:
    edited_df = st.data_editor(
        tasks_df,
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
            "progress": st.column_config.NumberColumn(
                "Progress (%)",
                min_value=0,
                max_value=100,
                step=1,
                required=True
            ),
            "start_date": st.column_config.DateColumn("Start Date"),
            "end_date": st.column_config.DateColumn("End Date")
        },
        hide_index=True,
        use_container_width=True
    )

# Add New Task
st.header("Add New Task")
with st.form("new_task_form"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        activity = st.text_input("Activity")
        item = st.text_input("Item")
        task = st.text_input("Task")
        room = st.text_input("Room")
    
    with col2:
        status = st.selectbox("Status", STATUS_OPTIONS)
        order_status = st.selectbox("Order Status", ORDER_OPTIONS)
        progress = st.slider("Progress (%)", 0, 100, PROGRESS_DEFAULT)
    
    with col3:
        start_date = st.date_input("Start Date")
        end_date = st.date_input("End Date")
        notes = st.text_area("Notes")
    
    uploaded_files = st.file_uploader(
        "Upload Images",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        help="Limit 200MB per file • JPG, JPEG, PNG"
    )
    
    submitted = st.form_submit_button("Add Task")

#################################
# GANTT CHART
#################################

st.header("Project Timeline")
filters = create_filter_section()

if not tasks_df.empty:
    # Apply filters
    df_filtered = tasks_df.copy()
    for key, value in filters.items():
        if key not in ["show_finished", "color_code_status", "grouping"] and value:
            df_filtered = df_filtered[df_filtered[key] == value]
    
    if not filters["show_finished"]:
        df_filtered = df_filtered[df_filtered["status"] != "Finished"]
    
    # Create Gantt chart
    if not df_filtered.empty:
        fig = px.timeline(
            df_filtered,
            x_start="start_date",
            x_end="end_date",
            y="activity",
            color="status" if filters["color_code_status"] else None,
            title="Project Timeline (Color-coded by Status)",
            color_discrete_map={
                "Not Started": "lightgray",
                "In Progress": "blue",
                "Finished": "green",
                "Delivered": "purple",
                "Not Delivered": "orange"
            }
        )
        
        fig.update_layout(
            xaxis_title="Timeline",
            yaxis_title="Activity",
            yaxis={'categoryorder': 'total ascending'},
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show overall completion
        total_tasks = len(df_filtered)
        completed_tasks = len(df_filtered[df_filtered["status"].isin(["Finished", "Delivered"])])
        completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        st.markdown("### Overall Completion")
        st.markdown(f"## {completion_percentage:.1f}%")

else:
    st.info("No tasks available. Add some tasks to see the Gantt chart.")
