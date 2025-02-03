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
st.markdown("This dashboard provides an executive overview of the project—including task snapshots, timeline visualization, and detailed status reports. Use the sidebar to filter the data.")

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
    # Ensure Status is a string so it can be edited
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
# Use column_config to force the Status column to be a selectbox.
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
        load_data.clear()  # Clear cache to force reload on next run
    except Exception as e:
        st.error(f"Error saving data: {e}")

# ---------------------------------------------------
# 3. Sidebar Filters & Options
# ---------------------------------------------------
st.sidebar.header("Filter Options")

# Activity Filter (empty = show all)
activities = sorted(edited_df["Activity"].dropna().unique())
selected_activities = st.sidebar.multiselect(
    "Select Activity (leave empty for all)",
    options=activities,
    default=[]
)

# Room Filter (empty = show all)
rooms = sorted(edited_df["Room"].dropna().unique())
selected_rooms = st.sidebar.multiselect(
    "Select Room (leave empty for all)",
    options=rooms,
    default=[]
)

# Status Filter (empty = show all)
if edited_df["Status"].notna().sum() > 0:
    statuses = sorted(edited_df["Status"].dropna().unique())
    selected_statuses = st.sidebar.multiselect(
        "Select Status (leave empty for all)",
        options=statuses,
        default=[]
    )
else:
    selected_statuses = []

# Checkbox: Show Finished Tasks?
show_finished = st.sidebar.checkbox("Show Finished Tasks", value=True)

# Date Range Filter
min_date = edited_df["Start Date"].min()
max_date = edited_df["End Date"].max()
selected_date_range = st.sidebar.date_input("Select Date Range", value=[min_date, max_date])

# ---------------------------------------------------
# 4. Filtering the DataFrame Based on User Input
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
# 5. Gantt Chart Generation Function
# ---------------------------------------------------
def create_gantt_chart(df_filtered):
    # Group by Activity and, if Room filter applied, include Room.
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
# 6. Overall Completion & Progress Bar Calculation
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
# 8. Layout with Tabs: Dashboard, Detailed Summary, Reports
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
    st.markdown("### Download Project Report")
    
    def generate_word_report(df, status_summary, overall_completion):
        document = Document()
        document.add_heading("Construction Project Report", 0)
        document.add_paragraph(f"Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        document.add_heading("Overall Project Completion", level=1)
        document.add_paragraph(f"{overall_completion:.1f}% of tasks are finished.")
        document.add_heading("Task Status Summary", level=1)
        table = document.add_table(rows=1, cols=2)
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = "Status Category"
        hdr_cells[1].text = "Count"
        for index, row in status_summary.iterrows():
            row_cells = table.add_row().cells
            row_cells[0].text = str(row["Status Category"])
            row_cells[1].text = str(row["Count"])
        document.add_paragraph("\nPlease refer to the dashboard for more details.")
        f = io.BytesIO()
        document.save(f)
        return f.getvalue()

    word_report = generate_word_report(edited_df, status_summary, completion_percentage)
    st.download_button(
        label="Download Report as Word Document",
        data=word_report,
        file_name="Construction_Project_Report.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    
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
