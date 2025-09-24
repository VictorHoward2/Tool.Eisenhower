# src/ui/main_window.py
import json
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGridLayout, QLineEdit, QDialog,
    QFormLayout, QComboBox, QTextEdit, QDateEdit, QDialogButtonBox, QMessageBox,
    QFileDialog, QMenuBar, QMenu, QAbstractItemView
)
from PySide6.QtGui import QFont, QAction
from models.task import Task
from db import db
from services import export as export_service

PRIORITY_ROWS = ["high", "medium", "low"]    # hàng: top -> bottom
URGENCY_COLS = ["low", "medium", "high"]     # cột: left -> right

class CellListWidget(QListWidget):
    def __init__(self, importance: str, urgency: str, on_cell_changed=None, parent=None):
        super().__init__(parent)
        self.importance = importance
        self.urgency = urgency
        self.on_cell_changed = on_cell_changed
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)

    def dropEvent(self, event):
        super().dropEvent(event)
        # After drop, update items' metadata & notify
        for i in range(self.count()):
            item = self.item(i)
            try:
                raw = item.data(Qt.UserRole)
                if raw:
                    d = json.loads(raw)
                    d["importance"] = self.importance
                    d["urgency"] = self.urgency
                    d["updated_at"] = datetime.utcnow().isoformat()
                    item.setData(Qt.UserRole, json.dumps(d))
                    item.setText(d.get("title", "<no title>"))
            except Exception:
                pass
        # call callback to persist changes
        if callable(self.on_cell_changed):
            self.on_cell_changed(self.importance, self.urgency)

class AddEditTaskDialog(QDialog):
    def __init__(self, parent=None, task: Task=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Task" if task else "Add Task")
        self.task = task
        self.build_ui()
        if task:
            self.load_task(task)

    def build_ui(self):
        self.form = QFormLayout(self)
        self.title_edit = QLineEdit()
        self.desc_edit = QTextEdit()
        self.importance_cb = QComboBox()
        self.importance_cb.addItems(["low", "medium", "high"])
        self.urgency_cb = QComboBox()
        self.urgency_cb.addItems(["low", "medium", "high"])
        self.due_date = QDateEdit()
        self.due_date.setCalendarPopup(True)
        self.due_date.setDisplayFormat("yyyy-MM-dd")
        self.due_date.setSpecialValueText("")  # allow empty

        self.form.addRow("Title*", self.title_edit)
        self.form.addRow("Description", self.desc_edit)
        self.form.addRow("Importance", self.importance_cb)
        self.form.addRow("Urgency", self.urgency_cb)
        self.form.addRow("Due date", self.due_date)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.form.addRow(self.buttons)

    def load_task(self, task: Task):
        self.title_edit.setText(task.title)
        self.desc_edit.setText(task.description or "")
        self.importance_cb.setCurrentText(task.importance)
        self.urgency_cb.setCurrentText(task.urgency)
        if task.due_date:
            from PySide6.QtCore import QDate
            parts = task.due_date.split("-")
            try:
                qd = QDate(int(parts[0]), int(parts[1]), int(parts[2]))
                self.due_date.setDate(qd)
            except Exception:
                pass

    def get_task_data(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Title is required.")
            return None
        desc = self.desc_edit.toPlainText().strip()
        imp = self.importance_cb.currentText()
        urg = self.urgency_cb.currentText()
        d = None
        if self.due_date.date().isValid():
            d = self.due_date.date().toString("yyyy-MM-dd")
        return {
            "title": title,
            "description": desc,
            "importance": imp,
            "urgency": urg,
            "due_date": d,
            "updated_at": datetime.utcnow().isoformat()
        }

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Eisenhower 3x3 - Prototype")
        self.tasks = {}  # id -> Task (in-memory)
        db.init_db_if_needed()
        self._setup_ui()
        self._load_tasks_from_db()

    def _setup_ui(self):
        # Menu
        menubar = QMenuBar(self)
        file_menu = QMenu("&File", self)
        export_csv = QAction("Export CSV", self)
        export_csv.triggered.connect(self.on_export_csv)
        export_xlsx = QAction("Export Excel (.xlsx)", self)
        export_xlsx.triggered.connect(self.on_export_xlsx)
        import_csv = QAction("Import CSV", self)
        import_csv.triggered.connect(self.on_import_csv)
        file_menu.addAction(export_csv)
        file_menu.addAction(export_xlsx)
        file_menu.addAction(import_csv)
        menubar.addMenu(file_menu)
        self.setMenuBar(menubar)

        central = QWidget()
        v = QVBoxLayout(central)

        # toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("+ Add Task")
        add_btn.clicked.connect(self.on_add_task)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search title...")
        self.search.textChanged.connect(self.on_search)
        toolbar.addWidget(add_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self.search)
        v.addLayout(toolbar)

        # matrix grid
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(10)

        self.cells = {}  # (importance, urgency) -> CellListWidget
        for row_idx, imp in enumerate(PRIORITY_ROWS):
            for col_idx, urg in enumerate(URGENCY_COLS):
                cell_container = QWidget()
                cell_layout = QVBoxLayout(cell_container)
                header = QLabel(f"{imp.capitalize()} / {urg.capitalize()}")
                header.setFont(QFont("", 9, QFont.Bold))
                lw = CellListWidget(importance=imp, urgency=urg, on_cell_changed=self.on_cell_changed)
                lw.itemDoubleClicked.connect(self.on_item_double_clicked)
                cell_layout.addWidget(header)
                cell_layout.addWidget(lw)
                grid.addWidget(cell_container, row_idx, col_idx)
                self.cells[(imp, urg)] = lw

        v.addWidget(grid_widget)
        self.setCentralWidget(central)

    def _load_tasks_from_db(self):
        tasks = db.load_all_tasks()
        for t in tasks:
            self.tasks[t.id] = t
            self._add_task_item_to_cell(t)

    def _add_task_item_to_cell(self, task: Task):
        cell = self.cells.get((task.importance, task.urgency))
        if not cell:
            return
        item = QListWidgetItem(task.title)
        item.setData(Qt.UserRole, json.dumps(task.to_dict()))
        cell.addItem(item)

    def on_add_task(self):
        dlg = AddEditTaskDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_task_data()
            if not data:
                return
            t = Task(
                title=data["title"],
                description=data["description"],
                importance=data["importance"],
                urgency=data["urgency"],
                due_date=data["due_date"]
            )
            t.updated_at = data["updated_at"]
            self.tasks[t.id] = t
            db.save_task(t)  # persist immediately
            self._add_task_item_to_cell(t)

    def on_item_double_clicked(self, item: QListWidgetItem):
        raw = item.data(Qt.UserRole)
        if not raw:
            return
        d = json.loads(raw)
        t = Task.from_dict(d)
        dlg = AddEditTaskDialog(self, task=t)
        if dlg.exec() == QDialog.Accepted:
            newdata = dlg.get_task_data()
            if not newdata:
                return
            # update task
            t.title = newdata["title"]
            t.description = newdata["description"]
            t.importance = newdata["importance"]
            t.urgency = newdata["urgency"]
            t.due_date = newdata["due_date"]
            t.updated_at = newdata["updated_at"]
            # in-memory & DB
            self.tasks[t.id] = t
            db.save_task(t)
            # update UI: find and remove the original item from any cell, then add updated
            found = None
            for lw in self.cells.values():
                for i in range(lw.count()):
                    it = lw.item(i)
                    raw2 = it.data(Qt.UserRole)
                    if not raw2:
                        continue
                    try:
                        d2 = json.loads(raw2)
                        if d2.get("id") == t.id:
                            lw.takeItem(i)
                            found = True
                            break
                    except Exception:
                        continue
                if found:
                    break
            self._add_task_item_to_cell(t)

    def on_cell_changed(self, importance: str, urgency: str):
        # persist all tasks in this cell after drag-drop
        lw = self.cells.get((importance, urgency))
        if not lw:
            return
        for i in range(lw.count()):
            it = lw.item(i)
            raw = it.data(Qt.UserRole)
            if not raw:
                continue
            try:
                d = json.loads(raw)
                t = Task.from_dict(d)
                # save
                self.tasks[t.id] = t
                db.save_task(t)
            except Exception:
                continue

    def on_search(self, text):
        q = text.strip().lower()
        for lw in self.cells.values():
            for i in range(lw.count()):
                it = lw.item(i)
                title = it.text().lower()
                it.setHidden(False if (not q or q in title) else True)

    # Export/Import handlers
    def on_export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", str(Path.home() / "tasks.csv"), "CSV Files (*.csv)")
        if not path:
            return
        tasks = list(self.tasks.values())
        export_service.export_tasks_to_csv(tasks, path)
        QMessageBox.information(self, "Export", f"Exported {len(tasks)} tasks to {path}")

    def on_export_xlsx(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Excel", str(Path.home() / "tasks.xlsx"), "Excel Files (*.xlsx)")
        if not path:
            return
        tasks = list(self.tasks.values())
        export_service.export_tasks_to_excel(tasks, path)
        QMessageBox.information(self, "Export", f"Exported {len(tasks)} tasks to {path}")

    def on_import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", str(Path.home()), "CSV Files (*.csv)")
        if not path:
            return
        imported = export_service.import_tasks_from_csv(path, overwrite_duplicates=False)
        for t in imported:
            self.tasks[t.id] = t
            self._add_task_item_to_cell(t)
        QMessageBox.information(self, "Import", f"Imported {len(imported)} tasks from {path}")
