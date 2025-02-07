import streamlit as st
import sqlite3
import os
import json
import pandas as pd
import plotly.express as px
from datetime import datetime

# Database setup & helper functions
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

def update_task(task_id, updates):
    conn = get_connection()
    c = conn.cursor()
    
    set_clause = ", ".join([f"{k}=?" for k in updates.keys()])
    values = list(updates.values()) + [task_id]
    
    c.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", values)
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

# App configuration
st.set_page_config(page_title="Task Dashboard", layout="wide")
st.title("Task Dashboard")

# Status options
STATUS_OPTIONS = ["Not Started", "In Progress", "Finished"]
ORDER_OPTIONS = ["Not Ordered", "Ordered"]
DELIVERY_OPTIONS = ["Not Delivered", "Delivered"]

# Add New Task Form
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
    
    # Image upload
    st.write("Upload Images (links will be stored)")
    uploaded_files = st.file_uploader(
        "Select images",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )
    
    if st.form_submit_button("Add Task"):
        image_links = []
        if uploaded_files:
            for file in uploaded_files:
                # Generate a unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{file.name}"
                filepath = os.path.join("uploaded_images", filename)
                
                # Save file
                os.makedirs("uploaded_images", exist_ok=True)
                with open(filepath, "wb") as f:
                    f.write(file.getbuffer())
                
                # Store as clickable link
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
        st.success("Task added successfully!")
        st.experimental_rerun()

# Data Editor
st.subheader("Task Editor")
df = fetch_tasks()

if not df.empty:
    edited_df = st.data_editor(
        df,
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
            "image_links": st.column_config.Column(
                "Image Links",
                help="Clickable image links"
            )
        },
        hide_index=True,
        key="task_editor"
    )

    if st.button("Save Changes"):
        for idx, row in edited_df.iterrows():
            original_row = df.loc[df['id'] == row['id']].iloc[0]
            
            # Check for changes
            updates = {}
            for col in df.columns:
                if row[col] != original_row[col]:
                    if col in ['image_links']:
                        updates[col] = json.dumps(row[col])
                    else:
                        updates[col] = row[col]
            
            if updates:
                update_task(row['id'], updates)
        
        st.success("Changes saved!")
        st.experimental_rerun()

# Download as Excel
if st.button("Download as Excel"):
    df_download = df.copy()
    df_download['image_links'] = df_download['image_links'].apply(lambda x: ', '.join(x) if x else '')
    
    # Save to Excel
    excel_file = "tasks_export.xlsx"
    df_download.to_excel(excel_file, index=False)
    
    # Offer download
    with open(excel_file, "rb") as f:
        st.download_button(
            "Download Excel File",
            f,
            file_name="tasks.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# Gantt Chart
st.subheader("Gantt Chart")
if not df.empty:
    # Prepare data for Gantt
    df_gantt = df.copy()
    df_gantt['Task'] = df_gantt.apply(
        lambda x: f"{x['activity']} - {x['task']} ({x['status']})",
        axis=1
    )
    
    fig = px.timeline(
        df_gantt,
        x_start="start_date",
        x_end="end_date",
        y="Task",
        color="progress",
        hover_data=["status", "order_status", "delivery_status", "progress"],
        color_continuous_scale="Blues",
        range_color=[0, 100]
    )
    
    fig.update_layout(
        xaxis_title="Timeline",
        yaxis_title="Tasks",
        yaxis={'categoryorder': 'total ascending'}
    )
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No tasks available for Gantt chart")

# Display Images (as clickable links in the task editor)
if not df.empty:
    st.subheader("Task Images")
    for _, row in df.iterrows():
        if row['image_links']:
            st.write(f"**{row['activity']} - {row['task']}**")
            for link in row['image_links']:
                st.markdown(link)
