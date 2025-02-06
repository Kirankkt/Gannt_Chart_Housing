import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from datetime import datetime

# ------------------------------------
# 1) Load Excel + Ensure columns
# ------------------------------------
@st.cache_data
def load_data(file_path: str) -> pd.DataFrame:
    if not os.path.exists(file_path):
        st.error(f"Excel file '{file_path}' not found! Please make sure it exists.")
        st.stop()

    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()

    # Convert date columns
    if "Start Date" in df.columns:
        df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    if "End Date" in df.columns:
        df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")

    # Ensure "Status" is a string
    if "Status" in df.columns:
        df["Status"] = df["Status"].astype(str)

    # Make sure we have these columns
    needed_cols = ["Progress", "Image"]
    for c in needed_cols:
        if c not in df.columns:
            df[c] = ""

    # Force numeric for "Progress"
    df["Progress"] = pd.to_numeric(df["Progress"], errors="coerce").fillna(0)

    return df

DATA_FILE = "construction_timeline.xlsx"
df_original = load_data(DATA_FILE)

# Write back any newly-created columns (one time) so Excel has them
df_original.to_excel(DATA_FILE, index=False)

# ------------------------------------
# 2) Streamlit Title & Setup
# ------------------------------------
st.set_page_config(page_title="Construction Dashboard", layout="wide")
st.title("Construction Project Manager - Dashboard")

st.markdown("""
This single-page dashboard lets you:
- **View and edit** existing tasks (including new columns like *Progress* and *Image*).
- **Add new rows** (new tasks/activities).
- **Upload/update images** for any row.
- **Filter** the data and see it in a **Gantt chart** grouped by *Activity*, color-coded by **average progress**.
- **Optionally view images** in an **Image Gallery** below the Gantt chart.
""")

# ------------------------------------
# 3) Data Editor for Existing Rows
# ------------------------------------
st.subheader("Data Editor (Existing Rows)")
st.markdown("""
Use this table to edit existing rows.  
- **Progress**: enter a number from 0 to 100.  
- **Image**: normally shows the filename. We'll display actual images in the gallery below.  
""")

# We'll copy df_original to "edited_df" for the data editor
edited_df = st.data_editor(
    df_original,
    use_container_width=True,
    key="existing_data_editor"
)

# Force "Status" defaults if blank
edited_df["Status"] = edited_df["Status"].replace("", "Not Started")

# Button to save changes from the data editor
if st.button("Save Changes from Editor"):
    try:
        edited_df.to_excel(DATA_FILE, index=False)
        st.success("Data successfully saved to Excel!")
        st.experimental_rerun()  # reload so table + Gantt reflect changes
    except Exception as e:
        st.error(f"Error saving data: {e}")

# ------------------------------------
# 4) Add New Row
# ------------------------------------
st.subheader("Add New Row")
st.markdown("Fill out this form to add a new task/activity row to the sheet.")

with st.form("add_row_form", clear_on_submit=True):
    new_activity = st.text_input("Activity")
    new_item = st.text_input("Item")
    new_task = st.text_input("Task")
    new_room = st.text_input("Room")
    new_status = st.selectbox("Status", ["Not Started", "In Progress", "Finished"])
    new_progress = st.slider("Progress (%)", 0, 100, 0, step=1)
    new_start_date = st.date_input("Start Date", value=datetime.today())
    new_end_date = st.date_input("End Date", value=datetime.today())
    new_notes = st.text_area("Notes", "")
    st.markdown("**Optionally upload an image** for this new row:")
    uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"], key="new_row_upload")

    submitted = st.form_submit_button("Add Row")
    if submitted:
        img_filename = ""
        if uploaded_file is not None:
            # Make sure folder exists
            if not os.path.exists("uploaded_images"):
                os.makedirs("uploaded_images")
            img_filename = uploaded_file.name
            with open(os.path.join("uploaded_images", img_filename), "wb") as f:
                f.write(uploaded_file.getbuffer())

        # Build new row as dict
        new_row_dict = {
            "Activity": new_activity,
            "Item": new_item,
            "Task": new_task,
            "Room": new_room,
            "Status": new_status,
            "Progress": new_progress,
            "Start Date": pd.to_datetime(new_start_date),
            "End Date": pd.to_datetime(new_end_date),
            "Notes": new_notes,
            "Image": img_filename
        }
        # Concat new row to "edited_df"
        new_row_df = pd.DataFrame([new_row_dict])
        updated_df = pd.concat([edited_df, new_row_df], ignore_index=True)

        # Save to Excel
        try:
            updated_df.to_excel(DATA_FILE, index=False)
            st.success("New row added and saved successfully!")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error adding new row: {e}")

# ------------------------------------
# 5) Update Image for an Existing Row
# ------------------------------------
st.subheader("Update Image for an Existing Row")
st.markdown("""
If you want to add or change an image **after** a row has been created, use this form:
""")

with st.form("update_image_form"):
    # Let user choose the row index from a dropdown
    row_choices = [f"Row {i}" for i in range(len(edited_df))]
    selected_row_str = st.selectbox("Select which row to update", options=row_choices)
    selected_index = int(selected_row_str.replace("Row ", ""))

    new_image_file = st.file_uploader("Upload or replace the existing image", type=["jpg","jpeg","png"], key="existing_upload")
    update_submitted = st.form_submit_button("Update Image")

    if update_submitted:
        if new_image_file is not None:
            if not os.path.exists("uploaded_images"):
                os.makedirs("uploaded_images")
            img_filename = new_image_file.name
            with open(os.path.join("uploaded_images", img_filename), "wb") as f:
                f.write(new_image_file.getbuffer())

            # Save it in the "Image" column
            edited_df.loc[selected_index, "Image"] = img_filename
            try:
                edited_df.to_excel(DATA_FILE, index=False)
                st.success(f"Row {selected_index} image updated!")
                st.experimental_rerun()
            except Exception as ex:
                st.error(f"Error saving updated image: {ex}")
        else:
            st.warning("No image file selected!")

# ------------------------------------
# 6) Sidebar Filters
# ------------------------------------
st.sidebar.header("Filters")

def norm_unique(col_name: str):
    return sorted(set(edited_df[col_name].dropna().astype(str).str.lower().str.strip()))

activity_options = norm_unique("Activity")
selected_activities = st.sidebar.multiselect("Filter by Activity (empty = all)", activity_options, default=[])

show_finished = st.sidebar.checkbox("Show Finished Tasks", value=True)

min_date_all = edited_df["Start Date"].min() if "Start Date" in edited_df.columns else datetime.today()
max_date_all = edited_df["End Date"].max() if "End Date" in edited_df.columns else datetime.today()
selected_date_range = st.sidebar.date_input("Filter by Date Range", [min_date_all, max_date_all])

# Filter logic
df_filtered = edited_df.copy()
if selected_activities:
    df_filtered = df_filtered[df_filtered["Activity"].str.lower().isin([a.lower() for a in selected_activities])]
if not show_finished:
    df_filtered = df_filtered[df_filtered["Status"].str.lower() != "finished"]

if len(selected_date_range) == 2:
    start_filter = pd.to_datetime(selected_date_range[0])
    end_filter = pd.to_datetime(selected_date_range[1])
    df_filtered = df_filtered[
        (df_filtered["Start Date"] >= start_filter) &
        (df_filtered["End Date"] <= end_filter)
    ]

# ------------------------------------
# 7) Gantt Chart by Activity, color = avg Progress
# ------------------------------------
st.subheader("Gantt Chart (by Activity, color by Average Progress)")

def create_gantt(df_in: pd.DataFrame):
    # For each Activity, find min(Start Date), max(End Date), avg(Progress)
    agg = df_in.groupby("Activity").agg({
        "Start Date": "min",
        "End Date": "max",
        "Progress": "mean"
    }).reset_index()

    # If no data after filtering, return an empty placeholder
    if agg.empty:
        return None

    fig = px.timeline(
        agg,
        x_start="Start Date",
        x_end="End Date",
        y="Activity",
        color="Progress",
        hover_data=["Progress"],
        range_color=[0,100],
        color_continuous_scale="Blues",
        title="Activity Timeline (Color by Average Progress)"
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Timeline", yaxis_title="Activity")
    fig.update_coloraxes(colorbar_title="Avg Progress (%)")
    return fig

chart_fig = create_gantt(df_filtered)
if chart_fig is not None:
    st.plotly_chart(chart_fig, use_container_width=True)
else:
    st.info("No data to display in the Gantt chart (possibly due to filters).")

# ------------------------------------
# 8) Optional Image Gallery
# ------------------------------------
st.subheader("Image Gallery")
st.markdown("Below are images for the **filtered** rows (if any).")

df_with_images = df_filtered[df_filtered["Image"].astype(bool)]
if df_with_images.empty:
    st.info("No images found in the current filtered dataset.")
else:
    for idx, row in df_with_images.iterrows():
        filename = row["Image"]
        # The file should exist in uploaded_images/<filename>
        filepath = os.path.join("uploaded_images", filename)
        st.write(f"**Row {idx}**: Activity = {row.get('Activity','')}, Task = {row.get('Task','')}")
        if os.path.exists(filepath):
            st.image(filepath, caption=filename, use_column_width=False)
        else:
            st.warning(f"Image file not found: {filepath}")

# ------------------------------------
# Done
# ------------------------------------
st.markdown("---")
st.markdown("**End of Dashboard**")
