# Construction Project Manager Dashboard

This project is a Streamlit-based dashboard for managing construction projects. It provides an executive overview through task snapshots, a detailed Gantt chart visualization, filtering options, and multiple downloadable reports. The app is designed to work with an Excel dataset (without modifying the original file) and allows for interactive editing and reporting.

## Features

- **Interactive Data Editor:**  
  Update task information (e.g., Status) directly within the app.

- **Advanced Gantt Chart:**  
  A color-coded timeline that aggregates tasks by activity. The chart is dynamically filtered based on user selections and shows the aggregated status (e.g., "In Progress," "Finished On Time") for each activity.

- **Filtering Options:**  
  Filter data by Activity, Room, Status, and date range using the sidebar.

- **Report Generation:**  
  Generate and download multiple reports as Word documents (e.g., Change Order Template, Work Order Template, Risk Register Template, etc.) along with data export options for CSV and Excel.

- **Dashboard Metrics:**  
  Overview metrics include overall task completion, overdue tasks, upcoming tasks, and more.

## Installation

### Prerequisites

Make sure you have Python installed (Python 3.7 or later is recommended). You will also need Git installed to clone the repository.

### Clone the Repository

Open your terminal and run:

```bash
git clone https://github.com/<your-username>/<repository-name>.git
cd <repository-name>
