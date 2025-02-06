import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime

#####################
# Must be FIRST: set page config
#####################
st.set_page_config(page_title="Robust Construction Dashboard", layout="wide")

#####################
# Helper: Safe rerun fallback
#####################
def safe_rerun():
    """
    Tries to call st.experimental_rerun() if available;
    otherwise instructs the user to refresh manually.
    """
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.info("Please refresh the page to see updated changes.")

#####################
# 1) Load Excel + Ensure Columns
#####################
@st.cache_data
def load_data(file_path: str) -> pd.DataFrame:
    if not os.path.exists(file_path):
        st.error(f"Excel file '{file_path}' not found! Please make sure it exists.")
        st.stop()

    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()

    # Convert date columns
    for col in ["Start Date", "End Date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Ensure certain columns exist or have correct types
    needed_str_cols = ["Status", "Order Status", "Delivery Status"]
    for c in needed_str_cols:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].astype(str)

    # Add columns if they do not exist
    if "Progress" not in df.columns:
        df["Progress"] = 0
    if "Image" not in df.columns:
        df["Image"] = ""

    # Force numeric for "Progress"
    df["Progress"] = pd.to_numeric(df["Progress"], errors="coerce").fillna(0)

    return df

DATA_FILE = "construction_timeline.xlsx"
df_original = load_data(DATA_FILE)

# Write back any newly-created columns (one time) so Excel has them
df_original.to_excel(DATA_FILE, index=False)

#####################
# 2) Title & Description
#####################
st.title("Robust Construction Project Dashboard")

st.markdown("""
This dashboard includes:
- **Filters**: Activity, Item, Task, Room, Status, date range, etc.
- **Data Editor** for updating **existing rows** (including new columns: *Order Status, Delivery Status, Progress, Image*).
- **Add New Row** form (to insert brand-new tasks/activities).
- **Update Image** form (to attach/change images for existing rows).
- **Gantt Chart** with:
   - **Color by Status** (incl. "Delayed" logic if End Date < today and not finished).
   - **Color by Progress** (numeric 0–100).
   - **Refine Gantt Grouping** by (Room, Item, Task).
- **Image Gallery** for the *filtered* rows.
""")

#####################
# 3) Data Editor for Existing Rows
#####################
st.subheader("Data Editor: Existing Rows")

st.markdown("""
- **Status**: `Not Started`, `In Progress`, `Finished` (but we also account for "Delayed" if End Date < today and not finished).
- **Order Status**: `Ordered` / `Not Ordered`
- **Delivery Status**: `Delivered` / `Not Delivered`
- **Progress**: integer [0–100]
- **Image**: relative file path (e.g., `uploaded_images/filename.jpg`)
""")

# Define column configs for st.data_editor
column_config = {
    "Status": st.column_config.SelectboxColumn(
        "Status",
        options=["Finished", "In Progress", "Not Started"],
        help="Choose the main status. If End Date < today and not finished, it is considered Delayed."
    ),
    "Order Status": st.column_config.SelectboxColumn(
        "Order Status",
        options=["Not Ordered", "Ordered"],
        help="Has the item/material been ordered?"
    ),
    "Delivery Status": st.column_config.SelectboxColumn(
        "Delivery Status",
        options=["Not Delivered", "Delivered"],
        help="Has the item/material been delivered?"
    ),
    "Progress": st.column_config.NumberColumn(
        "Progress (%)",
        help="Progress from 0 to 100",
        min_value=0,
        max_value=100,
        step=1
    ),
    # For "Image", we keep a text field for the relative file path.
}

edited_df = st.data_editor(
    df_original,
    column_config=column_config,
    use_container_width=True,
    key="data_editor"
)

# Force some defaults
edited_df["Status"] = edited_df["Status"].replace("", "Not Started")

if st.button("Save Changes (Data Editor)"):
    try:
        edited_df.to_excel(DATA_FILE, index=False)
        st.success("Data successfully saved to Excel.")
        safe_rerun()
    except Exception as e:
        st.error(f"Error saving data: {e}")

#####################
# 4) Add New Row
#####################
st.subheader("Add a New Row (New Task/Activity)")

with st.form("add_row_form", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        new_activity = st.text_input("Activity")
        new_item = st.text_input("Item")
        new_task = st.text_input("Task")
        new_room = st.text_input("Room")
    with c2:
        new_status = st.selectbox("Status", ["Not Started", "In Progress", "Finished"])
        new_order_status = st.selectbox("Order Status", ["Not Ordered", "Ordered"])
        new_delivery_status = st.selectbox("Delivery Status", ["Not Delivered", "Delivered"])
        new_progress = st.slider("Progress (%)", 0, 100, 0, step=1)
    with c3:
        new_start_date = st.date_input("Start Date", value=datetime.today())
        new_end_date = st.date_input("End Date", value=datetime.today())
        new_notes = st.text_area("Notes", "")

    st.write("**Optionally upload an image** for this new row:")
    uploaded_file_new = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"], key="new_row_upload")

    submitted = st.form_submit_button("Add Row")
    if submitted:
        # Initialize image relative path as an empty string
        img_relative_path = ""
        if uploaded_file_new is not None:
            img_folder = "uploaded_images"
            if not os.path.exists(img_folder):
                os.makedirs(img_folder)
            img_filename = uploaded_file_new.name
            img_relative_path = os.path.join(img_folder, img_filename)
            # Save file using the relative path
            with open(img_relative_path, "wb") as f:
                f.write(uploaded_file_new.getbuffer())

        # Build new row with relative image path
        new_row = {
            "Activity": new_activity,
            "Item": new_item,
            "Task": new_task,
            "Room": new_room,
            "Status": new_status,
            "Order Status": new_order_status,
            "Delivery Status": new_delivery_status,
            "Progress": new_progress,
            "Start Date": pd.to_datetime(new_start_date),
            "End Date": pd.to_datetime(new_end_date),
            "Notes": new_notes,
            "Image": img_relative_path
        }

        # Concat to existing data
        new_row_df = pd.DataFrame([new_row])
        updated_df = pd.concat([edited_df, new_row_df], ignore_index=True)

        # Save to Excel
        try:
            updated_df.to_excel(DATA_FILE, index=False)
            st.success("New row added and saved successfully!")
            safe_rerun()
        except Exception as e:
            st.error(f"Error adding row: {e}")

#####################
# 5) Update Image for Existing Row
#####################
st.subheader("Update an Image for an Existing Row")
st.markdown("Pick which row (by index) to update the `Image` file.")

row_indices = [f"Row {i}" for i in range(len(edited_df))]
chosen_row_str = st.selectbox("Select row index", options=row_indices)
chosen_index = int(chosen_row_str.replace("Row ", ""))

uploaded_file_existing = st.file_uploader("Upload or replace image", type=["jpg", "jpeg", "png"], key="existing_upload")
if st.button("Update Image on Row"):
    if uploaded_file_existing is None:
        st.warning("No file selected.")
    else:
        img_folder = "uploaded_images"
        if not os.path.exists(img_folder):
            os.makedirs(img_folder)
        img_filename = uploaded_file_existing.name
        img_relative_path = os.path.join(img_folder, img_filename)
        with open(img_relative_path, "wb") as f:
            f.write(uploaded_file_existing.getbuffer())

        # Update the relative path in the selected row
        edited_df.loc[chosen_index, "Image"] = img_relative_path
        try:
            edited_df.to_excel(DATA_FILE, index=False)
            st.success(f"Image updated for row {chosen_index}.")
            safe_rerun()
        except Exception as ex:
            st.error(f"Error saving updated image: {ex}")

#####################
# 6) Sidebar Filters & Options
#####################
st.sidebar.header("Filter Options")

def norm_unique(col_name: str):
    return sorted(set(edited_df[col_name].dropna().astype(str).str.strip()))

activity_opts = norm_unique("Activity")
selected_activity_norm = st.sidebar.multiselect("Select Activity", activity_opts, default=[])

item_opts = norm_unique("Item")
selected_item_norm = st.sidebar.multiselect("Select Item", item_opts, default=[])

task_opts = norm_unique("Task")
selected_task_norm = st.sidebar.multiselect("Select Task", task_opts, default=[])

room_opts = norm_unique("Room")
selected_room_norm = st.sidebar.multiselect("Select Room", room_opts, default=[])

status_opts = norm_unique("Status")
selected_statuses = st.sidebar.multiselect("Select Status", status_opts, default=[])

show_finished = st.sidebar.checkbox("Show Finished Tasks?", value=True)

st.sidebar.markdown("**Refine Gantt Grouping**")
group_by_room = st.sidebar.checkbox("Group by Room", value=False)
group_by_item = st.sidebar.checkbox("Group by Item", value=False)
group_by_task = st.sidebar.checkbox("Group by Task", value=False)

color_mode = st.sidebar.radio("Color Gantt By:", ["Status", "Progress"], index=0)

df_dates = edited_df.dropna(subset=["Start Date", "End Date"])
if df_dates.empty:
    default_min = datetime.today()
    default_max = datetime.today()
else:
    default_min = df_dates["Start Date"].min()
    default_max = df_dates["End Date"].max()

selected_date_range = st.sidebar.date_input("Select Date Range", [default_min, default_max])

#####################
# 7) Filter the DataFrame
#####################
df_filtered = edited_df.copy()

if selected_activity_norm:
    chosen_lc = [a.lower().strip() for a in selected_activity_norm]
    df_filtered = df_filtered[df_filtered["Activity"].astype(str).str.lower().str.strip().isin(chosen_lc)]
if selected_item_norm:
    chosen_lc = [a.lower().strip() for a in selected_item_norm]
    df_filtered = df_filtered[df_filtered["Item"].astype(str).str.lower().str.strip().isin(chosen_lc)]
if selected_task_norm:
    chosen_lc = [a.lower().strip() for a in selected_task_norm]
    df_filtered = df_filtered[df_filtered["Task"].astype(str).str.lower().str.strip().isin(chosen_lc)]
if selected_room_norm:
    chosen_lc = [a.lower().strip() for a in selected_room_norm]
    df_filtered = df_filtered[df_filtered["Room"].astype(str).str.lower().str.strip().isin(chosen_lc)]

if selected_statuses:
    chosen_lc = [a.lower().strip() for a in selected_statuses]
    df_filtered = df_filtered[df_filtered["Status"].str.lower().str.strip().isin(chosen_lc)]

if not show_finished:
    df_filtered = df_filtered[df_filtered["Status"].str.lower().str.strip() != "finished"]

if len(selected_date_range) == 2:
    start_filter = pd.to_datetime(selected_date_range[0])
    end_filter = pd.to_datetime(selected_date_range[1])
    if "Start Date" in df_filtered.columns and "End Date" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["Start Date"] >= start_filter) &
            (df_filtered["End Date"] <= end_filter)
        ]

#####################
# 8) Gantt Chart
#####################
st.subheader("Gantt Chart")
today = pd.to_datetime("today").normalize()

def compute_display_status(row):
    raw_status = row["Status"].strip().lower()
    if raw_status == "finished":
        return "Finished"
    if pd.notnull(row["End Date"]) and row["End Date"] < today:
        return "Delayed"
    if raw_status == "in progress":
        return "In Progress"
    return "Not Started"

def create_gantt_chart(df_in: pd.DataFrame):
    if df_in.empty:
        return None

    group_cols = ["Activity"]
    if group_by_room and "Room" in df_in.columns:
        group_cols.append("Room")
    if group_by_item and "Item" in df_in.columns:
        group_cols.append("Item")
    if group_by_task and "Task" in df_in.columns:
        group_cols.append("Task")

    if not group_cols:
        return None

    agg_dict = {"Start Date": "min", "End Date": "max"}
    if color_mode == "Progress":
        agg_dict["Progress"] = "mean"

    grouped = df_in.groupby(group_cols).agg(agg_dict).reset_index()

    if len(group_cols) == 1:
        grouped["Group Label"] = grouped[group_cols[0]].astype(str)
    else:
        grouped["Group Label"] = grouped[group_cols].astype(str).agg(" | ".join, axis=1)

    if color_mode == "Status":
        def get_group_status(grp_row):
            cond = True
            for gcol in group_cols:
                cond = cond & (df_in[gcol] == grp_row[gcol])
            subset = df_in[cond]
            statuses = [compute_display_status(r) for _, r in subset.iterrows()]
            if "Delayed" in statuses:
                return "Delayed"
            if "In Progress" in statuses:
                return "In Progress"
            if all(s == "Finished" for s in statuses):
                return "Finished"
            return "Not Started"
        grouped["Display Status"] = grouped.apply(get_group_status, axis=1)
        color_discrete_map = {
            "Not Started": "lightgray",
            "In Progress": "blue",
            "Delayed": "red",
            "Finished": "green"
        }
        fig = px.timeline(
            grouped,
            x_start="Start Date",
            x_end="End Date",
            y="Group Label",
            color="Display Status",
            color_discrete_map=color_discrete_map,
            title="Gantt Chart (Color by Status w/ Delayed Logic)"
        )
        fig.update_layout(yaxis_title=" | ".join(group_cols))
    else:
        fig = px.timeline(
            grouped,
            x_start="Start Date",
            x_end="End Date",
            y="Group Label",
            color="Progress",
            range_color=[0, 100],
            color_continuous_scale="Blues",
            hover_data=["Progress"],
            title="Gantt Chart (Color by Avg Progress)"
        )
        fig.update_layout(yaxis_title=" | ".join(group_cols))
        fig.update_coloraxes(colorbar_title="Avg Progress (%)")

    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Timeline")
    return fig

gantt_fig = create_gantt_chart(df_filtered)
if gantt_fig is None:
    st.info("No data available for the Gantt chart (perhaps filters eliminated all rows).")
else:
    st.plotly_chart(gantt_fig, use_container_width=True)

#####################
# 9) Filtered Data Snapshot + Image Gallery
#####################
st.subheader("Current Filtered Data Snapshot")
st.dataframe(df_filtered, use_container_width=True)

st.subheader("Image Gallery (Filtered Rows)")
df_images = df_filtered[df_filtered["Image"].astype(bool)]
if df_images.empty:
    st.info("No images found in the current filtered dataset.")
else:
    for idx, row in df_images.iterrows():
        img_path = row["Image"]
        st.markdown(f"**Row {idx}:** Activity = {row.get('Activity','(none)')}, Task = {row.get('Task','(none)')}")
        if img_path and os.path.exists(img_path):
            st.image(img_path, caption=f"File: {os.path.basename(img_path)}", use_column_width=False)
        else:
            st.warning(f"File not found: {img_path}")

st.markdown("---")
st.markdown("**End of the Dashboard**")
