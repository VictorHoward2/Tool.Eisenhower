# src/ui/main_window.py
import json
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGridLayout, QLineEdit, QDialog, QAbstractItemView,
    QFormLayout, QComboBox, QTextEdit, QDateEdit, QDialogButtonBox, QMessageBox
)
from PySide6.QtGui import QFont
from models.task import Task

PRIORITY_ROWS = ["high", "medium", "low"]    # hàng: top -> bottom
URGENCY_COLS = ["low", "medium", "high"]     # cột: left -> right

class CellListWidget(QListWidget):
    """Custom QListWidget that knows its importance/urgency and
       updates tasks' metadata after drop."""
    def __init__(self, importance: str, urgency: str, parent=None):
        super().__init__(parent)
        self.importance = importance
        self.urgency = urgency
        # allow drag and drop between lists
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)

    def dropEvent(self, event):
        super().dropEvent(event)
        # After drop, iterate all items in this cell and set their importance/urgency
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
                    # update visual text if you want (title only)
                    item.setText(d.get("title", "<no title>"))
            except Exception as e:
                # ignore items without json payload
                pass

class AddEditTaskDialog(QDialog):
    def __init__(self, parent=None, task: Task=None):
        super().__init__(parent)
        self.setWindowTitle("Task" if task else "Add Task")
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
            # due_date stored as "YYYY-MM-DD"
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
        self.tasks = {}  # id -> Task (in-memory store)
        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        v = QVBoxLayout(central)

        # toolbar (simple)
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
                header = QLabel(f"Importance={imp.capitalize()}  •  Urgency={urg.capitalize()}")
                header.setFont(QFont("", 9, QFont.Bold))
                listw = CellListWidget(importance=imp, urgency=urg)
                listw.itemDoubleClicked.connect(self.on_item_double_clicked)
                cell_layout.addWidget(header)
                cell_layout.addWidget(listw)
                grid.addWidget(cell_container, row_idx, col_idx)
                self.cells[(imp, urg)] = listw

        v.addWidget(grid_widget)
        self.setCentralWidget(central)

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
            self.tasks[t.id] = t
            self._add_task_item_to_cell(t)

    def _add_task_item_to_cell(self, task: Task):
        cell = self.cells.get((task.importance, task.urgency))
        if not cell:
            return
        item = QListWidgetItem(task.title)
        # store full task as json string in UserRole
        item.setData(Qt.UserRole, json.dumps(task.to_dict()))
        cell.addItem(item)

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
            # update task object
            t.title = newdata["title"]
            t.description = newdata["description"]
            t.importance = newdata["importance"]
            t.urgency = newdata["urgency"]
            t.due_date = newdata["due_date"]
            t.updated_at = newdata["updated_at"]
            # persist in memory
            self.tasks[t.id] = t
            # update UI: remove item from all cells (if moved), then add to target cell
            item_widget = self.sender()  # this is tricky: we have item from signal, not the list
            # safest approach: remove the clicked item from its current parent list and re-add
            # find parent list widget by iterating cells
            for (imp, urg), lw in self.cells.items():
                # find equivalent item by comparing object identity or title+id stored
                for i in range(lw.count()):
                    it = lw.item(i)
                    if it is item:
                        lw.takeItem(i)
                        break
            self._add_task_item_to_cell(t)

    def on_search(self, text):
        q = text.strip().lower()
        for lw in self.cells.values():
            for i in range(lw.count()):
                it = lw.item(i)
                raw = it.data(Qt.UserRole)
                title = it.text().lower()
                visible = (q in title) if q else True
                lw.setRowHidden(i, not visible) if hasattr(lw, "setRowHidden") else it.setHidden(not visible)

