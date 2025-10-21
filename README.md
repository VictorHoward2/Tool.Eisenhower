# Eisenhower Tool - Task Management Application

A modern desktop application for task management based on the Eisenhower Matrix (also known as the Urgent-Important Matrix). This tool helps you prioritize tasks by categorizing them into four quadrants based on their importance and urgency levels.

## 📋 Features

### Core Functionality
- **Eisenhower Matrix Interface**: Organize tasks in a 3x3 grid based on importance (low/medium/high) and urgency (low/medium/high)
- **Task Management**: Create, edit, delete, and organize tasks with drag-and-drop functionality
- **Task Details**: Rich task information including title, description, due dates, tags, and status
- **Data Persistence**: SQLite database for reliable data storage
- **Export/Import**: Export tasks to CSV/Excel formats and import from CSV

### User Interface
- **Modern Qt Interface**: Built with PySide6 for a native desktop experience
- **Intuitive Design**: Clean, user-friendly interface with color-coded task priorities
- **Responsive Layout**: Adaptive interface that works on different screen sizes
- **Menu System**: Comprehensive menu with file operations, task management, and settings

### Task Organization
- **Priority Matrix**: Visual representation of task importance vs urgency
- **Status Tracking**: Track task progress (todo, in-progress, completed)
- **Due Date Management**: Set and track task deadlines
- **Tagging System**: Organize tasks with custom tags
- **Order Management**: Customize task order within each matrix cell

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Windows 10/11 (primary target platform)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd "Eisenhower Tool"
   ```

2. **Create virtual environment**:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```powershell
   python src\app.py
   ```

## 📦 Building Executable

To create a standalone executable:

1. **Install PyInstaller**:
   ```powershell
   pip install pyinstaller
   ```

2. **Build the executable**:
   ```powershell
   pyinstaller app.spec
   ```

3. **Find the executable**:
   The built executable will be in the `dist/` folder as `Eisenhower.exe`

## 🏗️ Project Structure

```
Eisenhower Tool/
├── src/
│   ├── app.py                 # Main application entry point
│   ├── models/
│   │   └── task.py           # Task data model
│   ├── ui/
│   │   └── main_window.py    # Main user interface
│   ├── db/
│   │   └── db.py             # Database operations
│   ├── services/
│   │   └── export.py         # Export/import functionality
│   └── assets/
│       └── matrix.ico        # Application icon
├── build/                    # Build artifacts
├── dist/                     # Distribution files
├── requirements.txt          # Python dependencies
├── app.spec                  # PyInstaller configuration
└── README.md                 # This file
```

## 🔧 Dependencies

- **PySide6**: Qt framework for Python (GUI)
- **SQLAlchemy**: Database ORM (optional, currently using direct SQLite)
- **pandas**: Data manipulation for export features
- **openpyxl**: Excel file support
- **python-dateutil**: Date parsing utilities

## 💾 Data Storage

The application stores data in a SQLite database located at:
- **Windows**: `%APPDATA%\Eisenhower3x3\tasks.sqlite3`
- **Other platforms**: `~/.Eisenhower3x3/tasks.sqlite3`

## 🎯 How to Use

### Creating Tasks
1. Click the "Add Task" button or use the menu
2. Fill in task details (title, description, importance, urgency, due date)
3. Add tags for better organization
4. Save the task

### Organizing Tasks
- Tasks automatically appear in the appropriate matrix cell based on importance/urgency
- Drag and drop tasks between cells to change priorities
- Use the order controls to arrange tasks within each cell

### Managing Tasks
- Double-click tasks to edit them
- Right-click for context menu options
- Use the status dropdown to track progress
- Delete tasks when no longer needed

### Exporting Data
- Use File → Export to save tasks as CSV or Excel
- Use File → Import to load tasks from CSV files

## 🎨 Eisenhower Matrix

The application implements the classic Eisenhower Matrix:

| | Low Urgency | Medium Urgency | High Urgency |
|---|---|---|---|
| **High Importance** | Schedule | Important & Urgent | Do First |
| **Medium Importance** | Delegate | Plan | Delegate |
| **Low Importance** | Eliminate | Eliminate | Eliminate |

## 🛠️ Development

### Code Structure
- **Models**: Data classes and business logic (`src/models/`)
- **UI**: User interface components (`src/ui/`)
- **Database**: Data persistence layer (`src/db/`)
- **Services**: Business logic and utilities (`src/services/`)

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

This project is open source. Please check the license file for details.

## 🤝 Support

For issues, questions, or contributions, please:
1. Check existing issues
2. Create a new issue with detailed description
3. Provide system information and error logs if applicable

---

**Eisenhower Tool** - Helping you prioritize what matters most! 🎯