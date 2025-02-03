import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from datetime import datetime
from docx import Document

# ---------------------------------------------------
# App Configuration
# ---------------------------------------------------
st.set_page_config(page_title="Construction Project Manager Dashboard", layout="wide")
st.title("Construction Project Manager Dashboard")
st.markdown(
    "This dashboard provides an executive overview of the project—including task snapshots, timeline visualization, and detailed reports. Use the sidebar to filter the data."
)

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
column_config = {
    "Status": st.column_config.SelectboxColumn(
        "Status",
        options=["Finished", "In Progress"],
        help="Select 'Finished' for completed tasks or 'In Progress' for ongoing tasks."
    )
}
edited_df = st.data_editor(df, column_config=column_config, use_container_width=True)
edited_df["Status"] = edited_df["Status"].fillna("In Progress").replace("", "In Progress")

# ---------------------------------------------------
# 2a. Save Updates Button
# ---------------------------------------------------
if st.button("Save Updates"):
    try:
        edited_df.to_excel(DATA_FILE, index=False)
        st.success("Data successfully saved!")
        load_data.clear()  # Clear cache so next load uses updated data
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
# NEW: Toggle for color-coding the aggregated Gantt chart by activity status.
color_by_status = st.sidebar.checkbox("Color-code Gantt Chart by Activity Status", value=True)
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
# 5. Additional Template Functions
# ---------------------------------------------------
def generate_work_order_report(form_data):
    doc = Document()
    doc.add_heading("Work Order", 0)
    doc.add_paragraph(f"Work Order Number: {form_data.get('work_order_number', '')}")
    doc.add_paragraph(f"Contractor: {form_data.get('contractor', '')}")
    doc.add_heading("Work Description", level=1)
    doc.add_paragraph(form_data.get("description", ""))
    doc.add_heading("Assigned Tasks", level=1)
    doc.add_paragraph(form_data.get("tasks", ""))
    doc.add_paragraph(f"Due Date: {form_data.get('due_date', '')}")
    f = io.BytesIO()
    doc.save(f)
    return f.getvalue()

def generate_risk_register_report(form_data):
    doc = Document()
    doc.add_heading("Risk Register", 0)
    doc.add_paragraph(f"Risk ID: {form_data.get('risk_id', '')}")
    doc.add_heading("Risk Description", level=1)
    doc.add_paragraph(form_data.get("description", ""))
    doc.add_paragraph(f"Impact: {form_data.get('impact', '')}")
    doc.add_paragraph(f"Likelihood: {form_data.get('likelihood', '')}")
    doc.add_heading("Mitigation Plan", level=1)
    doc.add_paragraph(form_data.get("mitigation", ""))
    f = io.BytesIO()
    doc.save(f)
    return f.getvalue()

def generate_rfq_report(form_data):
    doc = Document()
    doc.add_heading("Request for Quote (RFQ)", 0)
    doc.add_paragraph(f"Quotation Number: {form_data.get('quotation_number', '')}")
    doc.add_paragraph(f"Customer ID: {form_data.get('customer_id', '')}")
    doc.add_paragraph(f"Company Name: {form_data.get('company_name', '')}")
    doc.add_heading("Requested Items/Services", level=1)
    doc.add_paragraph(form_data.get("requested", ""))
    doc.add_paragraph(f"Quote Validity (days): {form_data.get('validity', '')}")
    f = io.BytesIO()
    doc.save(f)
    return f.getvalue()

def generate_rfp_report(form_data):
    doc = Document()
    doc.add_heading("Request for Proposal (RFP)", 0)
    doc.add_paragraph(f"RFP Number: {form_data.get('rfp_number', '')}")
    doc.add_heading("Project Background", level=1)
    doc.add_paragraph(form_data.get("background", ""))
    doc.add_heading("Scope of Work", level=1)
    doc.add_paragraph(form_data.get("scope", ""))
    doc.add_paragraph(f"Timeline: {form_data.get('timeline', '')}")
    doc.add_paragraph(f"Submission Deadline: {form_data.get('deadline', '')}")
    f = io.BytesIO()
    doc.save(f)
    return f.getvalue()

def generate_rfi_report(form_data):
    doc = Document()
    doc.add_heading("Request for Information (RFI)", 0)
    doc.add_paragraph(f"RFI Number: {form_data.get('rfi_number', '')}")
    doc.add_paragraph(f"Subject: {form_data.get('subject', '')}")
    doc.add_heading("Question", level=1)
    doc.add_paragraph(form_data.get("question", ""))
    doc.add_paragraph(f"Requested Response Date: {form_data.get('response_date', '')}")
    f = io.BytesIO()
    doc.save(f)
    return f.getvalue()

def generate_schedule_of_values_report(form_data):
    doc = Document()
    doc.add_heading("Schedule of Values", 0)
    doc.add_paragraph(f"Project: {form_data.get('project', '')}")
    doc.add_paragraph(f"Total Contract Amount: {form_data.get('total_amount', '')}")
    doc.add_heading("Task Breakdown", level=1)
    doc.add_paragraph(form_data.get("breakdown", ""))
    f = io.BytesIO()
    doc.save(f)
    return f.getvalue()

def generate_contractor_estimate_report(form_data):
    doc = Document()
    doc.add_heading("Contractor Estimate", 0)
    doc.add_paragraph(f"Estimate Number: {form_data.get('estimate_number', '')}")
    doc.add_paragraph(f"Project: {form_data.get('project', '')}")
    doc.add_paragraph(f"Estimated Material Costs: {form_data.get('material_costs', '')}")
    doc.add_paragraph(f"Estimated Labor Costs: {form_data.get('labor_costs', '')}")
    f = io.BytesIO()
    doc.save(f)
    return f.getvalue()

def generate_construction_quote_report(form_data):
    doc = Document()
    doc.add_heading("Construction Quote", 0)
    doc.add_paragraph(f"Quote Number: {form_data.get('quote_number', '')}")
    doc.add_paragraph(f"Project: {form_data.get('project', '')}")
    doc.add_paragraph(f"Estimated Total Cost: {form_data.get('total_cost', '')}")
    f = io.BytesIO()
    doc.save(f)
    return f.getvalue()

def generate_scope_of_work_report(form_data):
    doc = Document()
    doc.add_heading("Scope of Work", 0)
    doc.add_paragraph(f"Project Name: {form_data.get('project_name', '')}")
    doc.add_heading("Scope Details", level=1)
    doc.add_paragraph(form_data.get("scope_details", ""))
    doc.add_heading("Milestones and Deliverables", level=1)
    doc.add_paragraph(form_data.get("milestones", ""))
    f = io.BytesIO()
    doc.save(f)
    return f.getvalue()

def generate_painting_estimate_report(form_data):
    doc = Document()
    doc.add_heading("Painting Estimate", 0)
    doc.add_paragraph(f"Estimate Number: {form_data.get('estimate_number', '')}")
    doc.add_paragraph(f"Project/Location: {form_data.get('project', '')}")
    doc.add_paragraph(f"Estimated Material Costs: {form_data.get('material_costs', '')}")
    doc.add_paragraph(f"Estimated Labor Costs: {form_data.get('labor_costs', '')}")
    f = io.BytesIO()
    doc.save(f)
    return f.getvalue()

def generate_roofing_estimate_report(form_data):
    doc = Document()
    doc.add_heading("Roofing Estimate", 0)
    doc.add_paragraph(f"Estimate Number: {form_data.get('estimate_number', '')}")
    doc.add_paragraph(f"Total Area (sq ft): {form_data.get('area', '')}")
    doc.add_paragraph(f"Material Specification: {form_data.get('materials', '')}")
    doc.add_paragraph(f"Estimated Cost: {form_data.get('estimated_cost', '')}")
    f = io.BytesIO()
    doc.save(f)
    return f.getvalue()

# ---------------------------------------------------
# 6. Gantt Chart Generation (Aggregated by Activity)
# ---------------------------------------------------
def create_gantt_chart(df_filtered, color_by_status=False):
    if color_by_status:
        # Aggregate by Activity only.
        agg_df = df_filtered.groupby("Activity").agg({
            "Start Date": "min",
            "End Date": "max"
        }).reset_index()
        def compute_activity_status(activity):
            subset = df_filtered[df_filtered["Activity"] == activity]
            return aggregated_status(subset)
        agg_df["Display Status"] = agg_df["Activity"].apply(compute_activity_status)
        color_discrete_map = {
            "Not Started": "lightgray",
            "In Progress": "blue",
            "Finished On Time": "green",
            "Finished Late": "orange"
        }
        fig = px.timeline(
            agg_df,
            x_start="Start Date",
            x_end="End Date",
            y="Activity",
            color="Display Status",
            color_discrete_map=color_discrete_map,
            title="Activity Timeline (Color-coded by Status)"
        )
        fig.update_layout(yaxis_title="Activity")
    else:
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

gantt_fig = create_gantt_chart(df_filtered, color_by_status=color_by_status)

# ---------------------------------------------------
# 7. Overall Completion & Progress Bar Calculation
# ---------------------------------------------------
total_tasks = edited_df.shape[0]
finished_tasks = edited_df[edited_df["Status"].str.strip().str.lower() == "finished"].shape[0]
completion_percentage = (finished_tasks / total_tasks) * 100 if total_tasks > 0 else 0

# ---------------------------------------------------
# 8. Detailed Status Summary (for Detailed Summary Tab)
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
# 9. Additional Dashboard Features
# ---------------------------------------------------
today = pd.Timestamp(datetime.today().date())
overdue_df = df_filtered[(df_filtered["End Date"] < today) &
                         (df_filtered["Status"].str.strip().str.lower() != "finished")]
overdue_count = overdue_df.shape[0]
task_distribution = df_filtered.groupby("Activity").size().reset_index(name="Task Count")
dist_fig = px.bar(task_distribution, x="Activity", y="Task Count", title="Task Distribution by Activity")
upcoming_start = today
upcoming_end = today + pd.Timedelta(days=7)
upcoming_df = df_filtered[(df_filtered["Start Date"] >= upcoming_start) & (df_filtered["Start Date"] <= upcoming_end)]
filter_summary = []
if selected_activities:
    filter_summary.append("Activities: " + ", ".join(selected_activities))
if selected_rooms:
    filter_summary.append("Rooms: " + ", ".join(selected_rooms))
if selected_statuses:
    filter_summary.append("Status: " + ", ".join(selected_statuses))
if selected_date_range:
    filter_summary.append(f"Date Range: {selected_date_range[0]} to {selected_date_range[1]}")
filter_summary_text = "; ".join(filter_summary) if filter_summary else "No filters applied."
tasks_in_progress = edited_df[edited_df["Status"].str.strip().str.lower() == "in progress"].shape[0]
not_declared = edited_df[~edited_df["Status"].str.strip().str.lower().isin(["finished", "in progress"])].shape[0]
notes_df = df_filtered[df_filtered["Notes"].notna() & (df_filtered["Notes"].str.strip() != "")]

# ---------------------------------------------------
# 10. Layout with Tabs: Dashboard, Detailed Summary, Reports
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
    st.markdown("#### Additional Insights")
    st.markdown(f"**Overdue Tasks:** {overdue_count}")
    if not overdue_df.empty:
        st.dataframe(overdue_df[["Activity", "Room", "Task", "Status", "End Date"]])
    st.markdown("**Task Distribution by Activity:**")
    st.plotly_chart(dist_fig, use_container_width=True)
    st.markdown("**Upcoming Tasks (Next 7 Days):**")
    if not upcoming_df.empty:
        st.dataframe(upcoming_df[["Activity", "Room", "Task", "Start Date", "Status"]])
    else:
        st.info("No upcoming tasks in the next 7 days.")
    st.markdown("**Active Filters:**")
    st.write(filter_summary_text)
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    col_kpi1.metric("Total Tasks", total_tasks)
    col_kpi2.metric("In Progress", tasks_in_progress)
    col_kpi3.metric("Finished", finished_tasks)
    col_kpi4.metric("Not Declared", not_declared)
    st.markdown("**Task Comments/Notes:**")
    if not notes_df.empty:
        st.dataframe(notes_df[["Activity", "Room", "Task", "Notes"]])
    else:
        st.info("No additional comments or notes.")
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
    def generate_daily_report(df):
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
        approval = st.text_input("Approval (Enter approver's name)")
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
            doc = Document()
            doc.add_heading("Change Order", 0)
            doc.add_paragraph(f"Change Order Number: {form_data['change_order_number']}")
            doc.add_paragraph(f"Project Name: {form_data['project_name']}")
            doc.add_paragraph(f"Requested By: {form_data['requested_by']}")
            doc.add_paragraph(f"Date: {form_data['date']}")
            doc.add_paragraph("Change Description:")
            doc.add_paragraph(form_data['change_description'])
            doc.add_paragraph("Reason for Change:")
            doc.add_paragraph(form_data['reason_for_change'])
            doc.add_paragraph(f"Estimated Cost Impact: {form_data['estimated_cost_impact']}")
            doc.add_paragraph(f"Approval: {form_data['approval']}")
            f = io.BytesIO()
            doc.save(f)
            change_order_doc = f.getvalue()
            st.download_button(
                label="Download Change Order Document",
                data=change_order_doc,
                file_name="Change_Order_Document.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
    
    st.markdown("---")
    
    # Additional Templates Section
    st.markdown("### Additional Templates")
    template_choice = st.selectbox("Select Template to Generate", options=[
        "Work Order Template",
        "Risk Register Template",
        "Request for Quote (RFQ) Template",
        "Request for Proposal (RFP) Template",
        "Request for Information (RFI) Template",
        "Schedule of Values Template",
        "Contractor Estimate Template",
        "Construction Quote Template",
        "Scope of Work Template",
        "Painting Estimate Template",
        "Roofing Estimate Template"
    ])
    
    if template_choice == "Work Order Template":
        with st.form("work_order_form"):
            work_order_number = st.text_input("Work Order Number")
            contractor = st.text_input("Contractor")
            description = st.text_area("Work Description")
            tasks_input = st.text_area("Assigned Tasks")
            due_date = st.date_input("Due Date", value=datetime.today())
            submitted = st.form_submit_button("Generate Work Order Document")
            if submitted:
                form_data = {
                    "work_order_number": work_order_number,
                    "contractor": contractor,
                    "description": description,
                    "tasks": tasks_input,
                    "due_date": due_date.strftime("%Y-%m-%d")
                }
                doc_bytes = generate_work_order_report(form_data)
                st.download_button(
                    label="Download Work Order Document",
                    data=doc_bytes,
                    file_name="Work_Order_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    
    elif template_choice == "Risk Register Template":
        with st.form("risk_register_form"):
            risk_id = st.text_input("Risk ID")
            description = st.text_area("Risk Description")
            impact = st.text_input("Impact")
            likelihood = st.text_input("Likelihood")
            mitigation = st.text_area("Mitigation Plan")
            submitted = st.form_submit_button("Generate Risk Register Document")
            if submitted:
                form_data = {
                    "risk_id": risk_id,
                    "description": description,
                    "impact": impact,
                    "likelihood": likelihood,
                    "mitigation": mitigation
                }
                doc_bytes = generate_risk_register_report(form_data)
                st.download_button(
                    label="Download Risk Register Document",
                    data=doc_bytes,
                    file_name="Risk_Register_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    
    elif template_choice == "Request for Quote (RFQ) Template":
        with st.form("rfq_form"):
            quotation_number = st.text_input("Quotation Number")
            customer_id = st.text_input("Customer ID")
            company_name = st.text_input("Company Name")
            requested = st.text_area("Requested Items/Services")
            validity = st.text_input("Quote Validity (days)")
            submitted = st.form_submit_button("Generate RFQ Document")
            if submitted:
                form_data = {
                    "quotation_number": quotation_number,
                    "customer_id": customer_id,
                    "company_name": company_name,
                    "requested": requested,
                    "validity": validity
                }
                doc_bytes = generate_rfq_report(form_data)
                st.download_button(
                    label="Download RFQ Document",
                    data=doc_bytes,
                    file_name="RFQ_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    
    elif template_choice == "Request for Proposal (RFP) Template":
        with st.form("rfp_form"):
            rfp_number = st.text_input("RFP Number")
            background = st.text_area("Project Background")
            scope = st.text_area("Scope of Work")
            timeline = st.text_input("Timeline")
            deadline = st.date_input("Submission Deadline", value=datetime.today())
            submitted = st.form_submit_button("Generate RFP Document")
            if submitted:
                form_data = {
                    "rfp_number": rfp_number,
                    "background": background,
                    "scope": scope,
                    "timeline": timeline,
                    "deadline": deadline.strftime("%Y-%m-%d")
                }
                doc_bytes = generate_rfp_report(form_data)
                st.download_button(
                    label="Download RFP Document",
                    data=doc_bytes,
                    file_name="RFP_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    
    elif template_choice == "Request for Information (RFI) Template":
        with st.form("rfi_form"):
            rfi_number = st.text_input("RFI Number")
            subject = st.text_input("Subject")
            question = st.text_area("Question")
            response_date = st.date_input("Requested Response Date", value=datetime.today())
            submitted = st.form_submit_button("Generate RFI Document")
            if submitted:
                form_data = {
                    "rfi_number": rfi_number,
                    "subject": subject,
                    "question": question,
                    "response_date": response_date.strftime("%Y-%m-%d")
                }
                doc_bytes = generate_rfi_report(form_data)
                st.download_button(
                    label="Download RFI Document",
                    data=doc_bytes,
                    file_name="RFI_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    
    elif template_choice == "Schedule of Values Template":
        with st.form("schedule_values_form"):
            project = st.text_input("Project Name")
            total_amount = st.text_input("Total Contract Amount")
            breakdown = st.text_area("Task Breakdown (list tasks and amounts)")
            submitted = st.form_submit_button("Generate Schedule of Values Document")
            if submitted:
                form_data = {
                    "project": project,
                    "total_amount": total_amount,
                    "breakdown": breakdown
                }
                doc_bytes = generate_schedule_of_values_report(form_data)
                st.download_button(
                    label="Download Schedule of Values Document",
                    data=doc_bytes,
                    file_name="Schedule_of_Values_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    
    elif template_choice == "Contractor Estimate Template":
        with st.form("contractor_estimate_form"):
            estimate_number = st.text_input("Estimate Number")
            project = st.text_input("Project Name")
            material_costs = st.text_input("Estimated Material Costs")
            labor_costs = st.text_input("Estimated Labor Costs")
            submitted = st.form_submit_button("Generate Contractor Estimate Document")
            if submitted:
                form_data = {
                    "estimate_number": estimate_number,
                    "project": project,
                    "material_costs": material_costs,
                    "labor_costs": labor_costs
                }
                doc_bytes = generate_contractor_estimate_report(form_data)
                st.download_button(
                    label="Download Contractor Estimate Document",
                    data=doc_bytes,
                    file_name="Contractor_Estimate_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    
    elif template_choice == "Construction Quote Template":
        with st.form("construction_quote_form"):
            quote_number = st.text_input("Quote Number")
            project = st.text_input("Project Name")
            total_cost = st.text_input("Estimated Total Cost")
            submitted = st.form_submit_button("Generate Construction Quote Document")
            if submitted:
                form_data = {
                    "quote_number": quote_number,
                    "project": project,
                    "total_cost": total_cost
                }
                doc_bytes = generate_construction_quote_report(form_data)
                st.download_button(
                    label="Download Construction Quote Document",
                    data=doc_bytes,
                    file_name="Construction_Quote_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    
    elif template_choice == "Scope of Work Template":
        with st.form("scope_work_form"):
            project_name = st.text_input("Project Name")
            scope_details = st.text_area("Scope Details")
            milestones = st.text_area("Milestones and Deliverables")
            submitted = st.form_submit_button("Generate Scope of Work Document")
            if submitted:
                form_data = {
                    "project_name": project_name,
                    "scope_details": scope_details,
                    "milestones": milestones
                }
                doc_bytes = generate_scope_of_work_report(form_data)
                st.download_button(
                    label="Download Scope of Work Document",
                    data=doc_bytes,
                    file_name="Scope_of_Work_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    
    elif template_choice == "Painting Estimate Template":
        with st.form("painting_estimate_form"):
            estimate_number = st.text_input("Estimate Number")
            project = st.text_input("Project/Location")
            material_costs = st.text_input("Estimated Material Costs")
            labor_costs = st.text_input("Estimated Labor Costs")
            submitted = st.form_submit_button("Generate Painting Estimate Document")
            if submitted:
                form_data = {
                    "estimate_number": estimate_number,
                    "project": project,
                    "material_costs": material_costs,
                    "labor_costs": labor_costs
                }
                doc_bytes = generate_painting_estimate_report(form_data)
                st.download_button(
                    label="Download Painting Estimate Document",
                    data=doc_bytes,
                    file_name="Painting_Estimate_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    
    elif template_choice == "Roofing Estimate Template":
        with st.form("roofing_estimate_form"):
            estimate_number = st.text_input("Estimate Number")
            area = st.text_input("Total Area (sq ft)")
            materials = st.text_input("Material Specification")
            estimated_cost = st.text_input("Estimated Cost")
            submitted = st.form_submit_button("Generate Roofing Estimate Document")
            if submitted:
                form_data = {
                    "estimate_number": estimate_number,
                    "area": area,
                    "materials": materials,
                    "estimated_cost": estimated_cost
                }
                doc_bytes = generate_roofing_estimate_report(form_data)
                st.download_button(
                    label="Download Roofing Estimate Document",
                    data=doc_bytes,
                    file_name="Roofing_Estimate_Document.docx",
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
