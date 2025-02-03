import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from datetime import datetime
from docx import Document
from docx.shared import Inches

# ---------------------------------------------------
# App Configuration
# ---------------------------------------------------
st.set_page_config(page_title="Construction Project Manager Dashboard", layout="wide")
st.title("Construction Project Manager Dashboard")
st.markdown("This dashboard provides an executive overview of the project—including task snapshots, timeline visualization, and detailed reports. Use the sidebar to filter the data.")

# ---------------------------------------------------
# 1. Data Loading from Excel
# ---------------------------------------------------
@st.cache_data
def load_data(file_path):
    if not os.path.exists(file_path):
        st.error(f"File {file_path} not found!")
        st.stop()
    df = pd.read_excel(file_path)
    # Clean column names and convert date columns
    df.columns = df.columns.str.strip()
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    # Ensure Status is a string
    df["Status"] = df["Status"].astype(str)
    return df

DATA_FILE = "construction_timeline.xlsx"
df = load_data(DATA_FILE)

# ---------------------------------------------------
# 2. Data Editing Option (Direct Editing)
# ---------------------------------------------------
st.subheader("Update Task Information")
st.markdown(
    """
    **Instructions:**  
    You can update any field below. For the **Status** column, please choose from the dropdown – select either **Finished** or **In Progress**.
    """
)
# Force the Status column to be a dropdown.
column_config = {
    "Status": st.column_config.SelectboxColumn(
        "Status",
        options=["Finished", "In Progress"],
        help="Select 'Finished' for completed tasks or 'In Progress' for ongoing tasks."
    )
}
edited_df = st.data_editor(df, column_config=column_config, use_container_width=True)

# Replace blank or missing statuses with "In Progress"
edited_df["Status"] = edited_df["Status"].fillna("In Progress").replace("", "In Progress")

# ---------------------------------------------------
# 2a. Save Updates Button
# ---------------------------------------------------
if st.button("Save Updates"):
    try:
        edited_df.to_excel(DATA_FILE, index=False)
        st.success("Data successfully saved!")
        load_data.clear()  # Clear cache so that the next load uses the updated file
    except Exception as e:
        st.error(f"Error saving data: {e}")

# ---------------------------------------------------
# 3. Sidebar Filters & Options
# ---------------------------------------------------
st.sidebar.header("Filter Options")

activities = sorted(edited_df["Activity"].dropna().unique())
selected_activities = st.sidebar.multiselect("Select Activity (leave empty for all)", options=activities, default=[])

rooms = sorted(edited_df["Room"].dropna().unique())
selected_rooms = st.sidebar.multiselect("Select Room (leave empty for all)", options=rooms, default=[])

if edited_df["Status"].notna().sum() > 0:
    statuses = sorted(edited_df["Status"].dropna().unique())
    selected_statuses = st.sidebar.multiselect("Select Status (leave empty for all)", options=statuses, default=[])
else:
    selected_statuses = []

show_finished = st.sidebar.checkbox("Show Finished Tasks", value=True)

min_date = edited_df["Start Date"].min()
max_date = edited_df["End Date"].max()
selected_date_range = st.sidebar.date_input("Select Date Range", value=[min_date, max_date])

# ---------------------------------------------------
# 4. Filter the DataFrame Based on User Input
# ---------------------------------------------------
df_filtered = edited_df.copy()
if selected_activities:
    df_filtered = df_filtered[df_filtered["Activity"].isin(selected_activities)]
if selected_rooms:
    df_filtered = df_filtered[df_filtered["Room"].isin(selected_rooms)]
if selected_statuses:
    df_filtered = df_filtered[df_filtered["Status"].isin(selected_statuses)]
if not show_finished:
    df_filtered = df_filtered[~df_filtered["Status"].str.strip().str.lower().eq("finished")]
if len(selected_date_range) == 2:
    start_range = pd.to_datetime(selected_date_range[0])
    end_range = pd.to_datetime(selected_date_range[1])
    df_filtered = df_filtered[(df_filtered["Start Date"] >= start_range) & (df_filtered["End Date"] <= end_range)]

# ---------------------------------------------------
# 5. Gantt Chart Generation
# ---------------------------------------------------
def create_gantt_chart(df_filtered):
    group_cols = ["Activity", "Room"] if selected_rooms else ["Activity"]
    agg_df = df_filtered.groupby(group_cols).agg({
        "Start Date": "min",
        "End Date": "max",
        "Task": lambda x: ", ".join(sorted(set(x.dropna()))),
        "Item": lambda x: ", ".join(sorted(set(x.dropna())))
    }).reset_index()
    agg_df.rename(columns={"Task": "Tasks", "Item": "Items"}, inplace=True)
    
    if "Room" in group_cols:
        agg_df["Activity_Room"] = agg_df["Activity"] + " (" + agg_df["Room"] + ")"
        fig = px.timeline(
            agg_df,
            x_start="Start Date",
            x_end="End Date",
            y="Activity_Room",
            color="Activity",
            hover_data=["Items", "Tasks"],
            title="Activity & Room Timeline"
        )
        fig.update_layout(yaxis_title="Activity (Room)")
    else:
        fig = px.timeline(
            agg_df,
            x_start="Start Date",
            x_end="End Date",
            y="Activity",
            color="Activity",
            hover_data=["Items", "Tasks"],
            title="Activity Timeline"
        )
        fig.update_layout(yaxis_title="Activity")
    
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Timeline")
    return fig

gantt_fig = create_gantt_chart(df_filtered)

# ---------------------------------------------------
# 6. Overall Completion & Progress Bar
# ---------------------------------------------------
total_tasks = edited_df.shape[0]
finished_tasks = edited_df[edited_df["Status"].str.strip().str.lower() == "finished"].shape[0]
completion_percentage = (finished_tasks / total_tasks) * 100 if total_tasks > 0 else 0

# ---------------------------------------------------
# 7. Detailed Status Summary (for Detailed Summary Tab)
# ---------------------------------------------------
def get_status_category(status):
    s = status.strip().lower()
    if s == "finished":
        return "Finished"
    elif s == "in progress":
        return "In Progress"
    else:
        return "Not Declared"

edited_df["Status Category"] = edited_df["Status"].apply(get_status_category)
status_summary = edited_df.groupby("Status Category").size().reset_index(name="Count")
desired_order = ["Not Declared", "In Progress", "Finished"]
status_summary["Order"] = status_summary["Status Category"].apply(lambda x: desired_order.index(x) if x in desired_order else 99)
status_summary = status_summary.sort_values("Order").drop("Order", axis=1)

# ---------------------------------------------------
# 8. Reports: Construction Daily Report & Change Order Template
# ---------------------------------------------------
def generate_daily_report(df):
    """
    Generate a Word document report that lists each task (with Activity, Room, Task, Status, Start and End dates)
    for the current day (or for the filtered dataset).
    """
    document = Document()
    document.add_heading("Construction Daily Report", 0)
    document.add_paragraph(f"Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    document.add_heading("Daily Tasks", level=1)
    table = document.add_table(rows=1, cols=6)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Activity"
    hdr_cells[1].text = "Room"
    hdr_cells[2].text = "Task"
    hdr_cells[3].text = "Status"
    hdr_cells[4].text = "Start Date"
    hdr_cells[5].text = "End Date"
    # For simplicity, include all filtered tasks in the daily report.
    for _, row in df.iterrows():
        row_cells = table.add_row().cells
        row_cells[0].text = str(row["Activity"])
        row_cells[1].text = str(row["Room"])
        row_cells[2].text = str(row["Task"])
        row_cells[3].text = str(row["Status"])
        row_cells[4].text = row["Start Date"].strftime("%Y-%m-%d") if pd.notnull(row["Start Date"]) else ""
        row_cells[5].text = row["End Date"].strftime("%Y-%m-%d") if pd.notnull(row["End Date"]) else ""
    f = io.BytesIO()
    document.save(f)
    return f.getvalue()

def generate_change_order_report(form_data):
    """
    Generate a Word document change order form using the data from the form.
    """
    document = Document()
    document.add_heading("Change Order Form", 0)
    document.add_paragraph(f"Date: {form_data['date']}")
    document.add_paragraph(f"Change Order Number: {form_data['change_order_number']}")
    document.add_paragraph(f"Project Name: {form_data['project_name']}")
    document.add_paragraph(f"Requested By: {form_data['requested_by']}")
    document.add_heading("Change Description", level=1)
    document.add_paragraph(form_data['change_description'])
    document.add_heading("Reason for Change", level=1)
    document.add_paragraph(form_data['reason_for_change'])
    document.add_heading("Estimated Cost Impact", level=1)
    document.add_paragraph(form_data['estimated_cost_impact'])
    document.add_heading("Approval", level=1)
    document.add_paragraph(form_data['approval'])
    f = io.BytesIO()
    document.save(f)
    return f.getvalue()

# ---------------------------------------------------
# 9. Layout with Tabs: Dashboard, Detailed Summary, Reports
# ---------------------------------------------------
tabs = st.tabs(["Dashboard", "Detailed Summary", "Reports"])

# ---------- Dashboard Tab ----------
with tabs[0]:
    st.header("Dashboard Overview")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Current Tasks Snapshot")
        st.dataframe(df_filtered)
    with col2:
        st.subheader("Project Timeline")
        st.plotly_chart(gantt_fig, use_container_width=True)
    st.metric("Overall Completion", f"{completion_percentage:.1f}%")
    st.progress(completion_percentage / 100)
    st.markdown("Use the filters on the sidebar to adjust the view.")

# ---------- Detailed Summary Tab ----------
with tabs[1]:
    st.header("Detailed Summary")
    st.markdown("### Task Progress Tracker")
    st.dataframe(status_summary, use_container_width=True)
    st.markdown("### Full Detailed Data")
    st.dataframe(df_filtered)

# ---------- Reports Tab ----------
with tabs[2]:
    st.header("Reports")
    
    # Construction Daily Report Section
    st.markdown("### Construction Daily Report")
    daily_report = generate_daily_report(df_filtered)
    st.download_button(
        label="Download Daily Report as Word Document",
        data=daily_report,
        file_name="Construction_Daily_Report.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    
    st.markdown("---")
    
    # Change Order Template Section
    st.markdown("### Change Order Template")
    with st.form("change_order_form"):
        change_order_number = st.text_input("Change Order Number")
        project_name = st.text_input("Project Name")
        requested_by = st.text_input("Requested By")
        date = st.date_input("Date", value=datetime.today())
        change_description = st.text_area("Change Description")
        reason_for_change = st.text_area("Reason for Change")
        estimated_cost_impact = st.text_input("Estimated Cost Impact")
        approval = st.text_input("Approval (Enter name of approver)")
        submitted = st.form_submit_button("Generate Change Order Document")
        if submitted:
            form_data = {
                "change_order_number": change_order_number,
                "project_name": project_name,
                "requested_by": requested_by,
                "date": date.strftime("%Y-%m-%d"),
                "change_description": change_description,
                "reason_for_change": reason_for_change,
                "estimated_cost_impact": estimated_cost_impact,
                "approval": approval
            }
            change_order_doc = generate_change_order_report(form_data)
            st.download_button(
                label="Download Change Order Document",
                data=change_order_doc,
                file_name="Change_Order_Document.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
    
    st.markdown("---")
    st.markdown("### Export Data")
    def convert_df_to_csv(df):
        return df.to_csv(index=False).encode("utf-8")
    def convert_df_to_excel(df):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="FilteredData")
        return output.getvalue()
    csv_data = convert_df_to_csv(df_filtered)
    st.download_button(label="Download Filtered Data as CSV", data=csv_data, file_name="filtered_construction_data.csv", mime="text/csv")
    excel_data = convert_df_to_excel(df_filtered)
    st.download_button(label="Download Filtered Data as Excel", data=excel_data, file_name="filtered_construction_data.xlsx", mime="application/vnd.ms-excel")

st.markdown("---")
st.markdown("Developed with a forward-thinking, data-driven approach. Enjoy tracking your construction project!")
