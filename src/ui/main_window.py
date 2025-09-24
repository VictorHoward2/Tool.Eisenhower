import json
from datetime import datetime, date
from pathlib import Path
from functools import partial

from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGridLayout, QLineEdit, QDialog,
    QFormLayout, QComboBox, QTextEdit, QDateEdit, QDialogButtonBox, QMessageBox,
    QFileDialog, QMenuBar, QMenu, QAbstractItemView, QSplitter, QFrame, QStatusBar
)
from PySide6.QtGui import QFont, QAction, QColor, QBrush, QPixmap, QPainter, QIcon

from models.task import Task
from db import db
from services import export as export_service

PRIORITY_ROWS = ["high", "medium", "low"]    # hàng: top -> bottom
URGENCY_COLS = ["low", "medium", "high"]     # cột: left -> right

# UI / UX constants
PRIORITY_COLORS = {
    "high": "#ff6b6b",    # red
    "medium": "#ffd166",  # amber
    "low": "#8ecae6"      # blue
}
DUE_SOON_DAYS = 3  # tasks within this number of days will be highlighted as "due soon"


class CellListWidget(QListWidget):
    """Custom QListWidget for each cell in the 3x3 matrix.

    - Supports drag & drop (preserves previous behavior)
    - Provides a right-click context menu for edit/delete/add
    - Calls back to a handler in MainWindow for item actions
    """

    item_action_requested = Signal(str, QListWidgetItem)

    def __init__(self, importance: str, urgency: str, on_cell_changed=None, on_item_action=None, parent=None):
        super().__init__(parent)
        self.importance = importance
        self.urgency = urgency
        self.on_cell_changed = on_cell_changed
        self.on_item_action = on_item_action
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

    def contextMenuEvent(self, event):
        # Right click menu: Edit / Delete / Show details / Add here
        item = self.itemAt(event.pos())
        menu = QMenu(self)
        if item:
            edit_act = menu.addAction("Edit")
            delete_act = menu.addAction("Delete")
            details_act = menu.addAction("Show details")
            chosen = menu.exec_(event.globalPos())
            if chosen == edit_act:
                if callable(self.on_item_action):
                    self.on_item_action("edit", item)
            elif chosen == delete_act:
                if callable(self.on_item_action):
                    self.on_item_action("delete", item)
            elif chosen == details_act:
                if callable(self.on_item_action):
                    self.on_item_action("details", item)
        else:
            add_act = menu.addAction("Add task here")
            chosen = menu.exec_(event.globalPos())
            if chosen == add_act and callable(self.on_item_action):
                # allow adding task already prefilled with this cell
                self.on_item_action("add_here", None)


class AddEditTaskDialog(QDialog):
    def __init__(self, parent=None, task: Task=None, prefill=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Task" if task else "Add Task")
        self.task = task
        self.prefill = prefill or {}
        self.build_ui()
        if task:
            self.load_task(task)
        else:
            # apply prefill importance/urgency
            imp = self.prefill.get("importance")
            urg = self.prefill.get("urgency")
            if imp:
                self.importance_cb.setCurrentText(imp)
            if urg:
                self.urgency_cb.setCurrentText(urg)

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

        # new: tags field (comma-separated)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("tags (comma-separated)")

        self.form.addRow("Title*", self.title_edit)
        self.form.addRow("Description", self.desc_edit)
        self.form.addRow("Importance", self.importance_cb)
        self.form.addRow("Urgency", self.urgency_cb)
        self.form.addRow("Due date", self.due_date)
        self.form.addRow("Tags", self.tags_edit)

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
            try:
                qd = QDate.fromString(task.due_date, "yyyy-MM-dd")
                if qd.isValid():
                    self.due_date.setDate(qd)
            except Exception:
                pass
        # load tags if available
        tags_val = None
        if hasattr(task, "tags") and task.tags:
            if isinstance(task.tags, (list, tuple)):
                tags_val = ",".join(task.tags)
            else:
                tags_val = str(task.tags)
        if tags_val:
            self.tags_edit.setText(tags_val)

    def get_task_data(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Title is required.")
            return None
        desc = self.desc_edit.toPlainText().strip()
        imp = self.importance_cb.currentText()
        urg = self.urgency_cb.currentText()
        d = None
        if self.due_date.date().isValid() and self.due_date.date().toString("yyyy-MM-dd"):
            d = self.due_date.date().toString("yyyy-MM-dd")
        tags_raw = self.tags_edit.text().strip()
        # normalize tags as comma-separated string (consumer code can split to list)
        tags = ",".join([t.strip() for t in tags_raw.split(",") if t.strip()]) if tags_raw else ""
        return {
            "title": title,
            "description": desc,
            "importance": imp,
            "urgency": urg,
            "due_date": d,
            "tags": tags,
            "updated_at": datetime.utcnow().isoformat()
        }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Eisenhower 3x3 - Polished UI")
        self.tasks = {}  # id -> Task (in-memory)
        db.init_db_if_needed()
        self._setup_ui()
        self._load_tasks_from_db()
        self.update_status_bar()

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

        view_menu = QMenu("&View", self)
        refresh_act = QAction("Refresh counts", self)
        refresh_act.triggered.connect(self.update_status_bar)
        view_menu.addAction(refresh_act)
        menubar.addMenu(view_menu)

        help_menu = QMenu("&Help", self)
        about_act = QAction("About", self)
        about_act.triggered.connect(self.on_about)
        help_menu.addAction(about_act)
        menubar.addMenu(help_menu)

        self.setMenuBar(menubar)

        central = QWidget()
        v = QVBoxLayout(central)

        # toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("+ Add Task")
        add_btn.clicked.connect(self.on_add_task)
        add_btn.setShortcut("Ctrl+N")

        # filters
        self.importance_filter = QComboBox()
        self.importance_filter.addItems(["All", "high", "medium", "low"])
        self.importance_filter.currentTextChanged.connect(self.apply_filters)
        self.tags_filter = QLineEdit()
        self.tags_filter.setPlaceholderText("Filter tags (comma-separated)")
        self.tags_filter.textChanged.connect(self.apply_filters)
        self.from_date_filter = QDateEdit()
        self.from_date_filter.setCalendarPopup(True)
        self.from_date_filter.setDisplayFormat("yyyy-MM-dd")
        self.from_date_filter.setSpecialValueText("")
        self.from_date_filter.dateChanged.connect(self.apply_filters)
        self.to_date_filter = QDateEdit()
        self.to_date_filter.setCalendarPopup(True)
        self.to_date_filter.setDisplayFormat("yyyy-MM-dd")
        self.to_date_filter.setSpecialValueText("")
        self.to_date_filter.dateChanged.connect(self.apply_filters)
        clear_filters_btn = QPushButton("Clear filters")
        clear_filters_btn.clicked.connect(self.clear_filters)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search title...")
        self.search.textChanged.connect(self.on_search)

        toolbar.addWidget(add_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Filter:"))
        toolbar.addWidget(QLabel("Importance"))
        toolbar.addWidget(self.importance_filter)
        toolbar.addWidget(QLabel("Tags"))
        toolbar.addWidget(self.tags_filter)
        toolbar.addWidget(QLabel("From"))
        toolbar.addWidget(self.from_date_filter)
        toolbar.addWidget(QLabel("To"))
        toolbar.addWidget(self.to_date_filter)
        toolbar.addWidget(clear_filters_btn)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self.search)
        v.addLayout(toolbar)

        # main area: left = matrix, right = task detail
        splitter = QSplitter(Qt.Horizontal)

        # matrix grid
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(10)

        self.cells = {}  # (importance, urgency) -> CellListWidget
        for row_idx, imp in enumerate(PRIORITY_ROWS):
            for col_idx, urg in enumerate(URGENCY_COLS):
                cell_container = QFrame()
                cell_container.setFrameShape(QFrame.StyledPanel)
                cell_layout = QVBoxLayout(cell_container)

                header = QLabel(f"{imp.capitalize()} / {urg.capitalize()}")
                header.setFont(QFont("", 9, QFont.Bold))
                header.setAlignment(Qt.AlignCenter)
                header.setFixedHeight(20)

                lw = CellListWidget(importance=imp, urgency=urg,
                                     on_cell_changed=self.on_cell_changed,
                                     on_item_action=self.on_cell_item_action)
                lw.itemDoubleClicked.connect(self.on_item_double_clicked)
                # connect selection changed to global handler
                lw.itemSelectionChanged.connect(partial(self.on_cell_selection_changed, lw))

                cell_layout.addWidget(header)
                cell_layout.addWidget(lw)
                grid.addWidget(cell_container, row_idx, col_idx)
                self.cells[(imp, urg)] = lw

        splitter.addWidget(grid_widget)

        # right panel: details + actions
        details = QFrame()
        details.setFrameShape(QFrame.StyledPanel)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(8, 8, 8, 8)

        self.title_label = QLabel("Select a task to see details")
        self.title_label.setWordWrap(True)
        self.title_label.setFont(QFont("", 12, QFont.Bold))

        self.meta_label = QLabel("")
        self.meta_label.setWordWrap(True)

        self.desc_view = QTextEdit()
        self.desc_view.setReadOnly(True)
        self.desc_view.setFixedHeight(150)

        btn_layout = QHBoxLayout()
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self.on_edit_selected)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.on_delete_selected)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)

        details_layout.addWidget(self.title_label)
        details_layout.addWidget(self.meta_label)
        details_layout.addWidget(self.desc_view)
        details_layout.addLayout(btn_layout)
        details_layout.addStretch()

        splitter.addWidget(details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        v.addWidget(splitter)

        self.setCentralWidget(central)

        # status bar
        self.status = QStatusBar(self)
        self.setStatusBar(self.status)

        # shortcuts
        delete_shortcut = QAction(self)
        delete_shortcut.setShortcut("Delete")
        delete_shortcut.triggered.connect(self.on_delete_selected)
        self.addAction(delete_shortcut)

        # small hints
        self.status.showMessage("Tip: Right-click a task for Edit/Delete. Use filters above to narrow tasks.")

        # internal state
        self.selected_task_id = None

    def _load_tasks_from_db(self):
        tasks = db.load_all_tasks()
        for t in tasks:
            self.tasks[t.id] = t
            self._add_task_item_to_cell(t)
        # sort items in each cell by due date
        for lw in self.cells.values():
            self._sort_cell_by_due_date(lw)

    def _priority_icon(self, importance: str) -> QIcon:
        # create a small circular pixmap filled with priority color
        color = QColor(PRIORITY_COLORS.get(importance, "#cccccc"))
        size = 14
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, size - 1, size - 1)
        p.end()
        return QIcon(pix)

    def _decorate_item_from_raw(self, item: QListWidgetItem, raw: str):
        # set text/icon/tooltip/background/font using raw json
        try:
            d = json.loads(raw) if raw else {}
        except Exception:
            d = {}
        title = d.get("title", "<no title>")
        item.setText(title)
        item.setData(Qt.UserRole, raw)
        # tooltip
        tooltip = f"Due: {d.get('due_date') or '—'}\nUpdated: {d.get('updated_at') or '—'}"
        if d.get("description"):
            tooltip += f"\n{d.get('description')[:180]}"
        if d.get("tags"):
            tooltip += f"\nTags: {d.get('tags')}"
        item.setToolTip(tooltip)
        # icon
        item.setIcon(self._priority_icon(d.get("importance")))
        # visual hint for overdue / due soon
        try:
            fnt = item.font()
            fnt.setBold(False)
            item.setFont(fnt)
            item.setBackground(QBrush())
            if d.get("due_date"):
                ddate = datetime.strptime(d.get("due_date"), "%Y-%m-%d").date()
                today = datetime.utcnow().date()
                days_left = (ddate - today).days
                if ddate < today:
                    item.setBackground(QBrush(QColor("#ffe6e6")))  # overdue → light red
                elif days_left <= DUE_SOON_DAYS:
                    # due soon: make font bold and subtle orange background
                    fnt.setBold(True)
                    item.setFont(fnt)
                    item.setBackground(QBrush(QColor("#fff4e0")))
        except Exception:
            pass

    def _add_task_item_to_cell(self, task: Task):
        cell = self.cells.get((task.importance, task.urgency))
        if not cell:
            return
        raw = json.dumps(task.to_dict()) if hasattr(task, 'to_dict') else json.dumps({
            'id': getattr(task, 'id', None),
            'title': getattr(task, 'title', ''),
            'description': getattr(task, 'description', ''),
            'importance': getattr(task, 'importance', ''),
            'urgency': getattr(task, 'urgency', ''),
            'due_date': getattr(task, 'due_date', ''),
            'updated_at': getattr(task, 'updated_at', '')
        })
        item = QListWidgetItem()
        self._decorate_item_from_raw(item, raw)
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
            # attach tags attribute to Task object (consumer may convert to list in Task.to_dict)
            try:
                t.tags = data.get('tags', "")
            except Exception:
                pass
            t.updated_at = data["updated_at"]
            self.tasks[t.id] = t
            db.save_task(t)  # persist immediately
            self._add_task_item_to_cell(t)
            self._sort_cell_by_due_date(self.cells[(t.importance, t.urgency)])
            self.update_status_bar()
            # re-apply filters/search so new item respects them
            self.apply_filters()

    def on_cell_item_action(self, action: str, item: QListWidgetItem):
        # callback from CellListWidget context menu
        if action == "add_here":
            # find which cell the sender is
            sender = self.sender()
            importance = getattr(sender, "importance", None)
            urgency = getattr(sender, "urgency", None)
            prefill = {}
            if importance:
                prefill["importance"] = importance
            if urgency:
                prefill["urgency"] = urgency
            dlg = AddEditTaskDialog(self, prefill=prefill)
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
                try:
                    t.tags = data.get('tags', "")
                except Exception:
                    pass
                t.updated_at = data["updated_at"]
                self.tasks[t.id] = t
                db.save_task(t)
                self._add_task_item_to_cell(t)
                self._sort_cell_by_due_date(self.cells[(t.importance, t.urgency)])
                self.update_status_bar()
                self.apply_filters()
            return

        if not item:
            return
        raw = item.data(Qt.UserRole)
        if not raw:
            return
        try:
            d = json.loads(raw)
            t = Task.from_dict(d)
        except Exception:
            return

        if action == "edit":
            dlg = AddEditTaskDialog(self, task=t)
            if dlg.exec() == QDialog.Accepted:
                newdata = dlg.get_task_data()
                if not newdata:
                    return
                t.title = newdata["title"]
                t.description = newdata["description"]
                t.importance = newdata["importance"]
                t.urgency = newdata["urgency"]
                t.due_date = newdata["due_date"]
                try:
                    t.tags = newdata.get('tags', "")
                except Exception:
                    pass
                t.updated_at = newdata["updated_at"]
                self.tasks[t.id] = t
                db.save_task(t)
                # remove original item and re-add
                self._remove_item_by_task_id(t.id)
                self._add_task_item_to_cell(t)
                self._sort_cell_by_due_date(self.cells[(t.importance, t.urgency)])
                self.update_status_bar()
                self.apply_filters()
        elif action == "delete":
            ok = QMessageBox.question(self, "Delete", f"Delete task '{t.title}'?")
            if ok == QMessageBox.StandardButton.Yes:
                # delete from db & UI
                db.delete_task(t.id)
                if t.id in self.tasks:
                    del self.tasks[t.id]
                self._remove_item_by_task_id(t.id)
                self.update_status_bar()
        elif action == "details":
            # show in right panel
            self._show_task_in_details(t)

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
            try:
                t.tags = newdata.get('tags', "")
            except Exception:
                pass
            t.updated_at = newdata["updated_at"]
            # in-memory & DB
            self.tasks[t.id] = t
            db.save_task(t)
            # update UI: find and remove the original item from any cell, then add updated
            self._remove_item_by_task_id(t.id)
            self._add_task_item_to_cell(t)
            self._sort_cell_by_due_date(self.cells[(t.importance, t.urgency)])
            self.update_status_bar()
            self.apply_filters()

    def _remove_item_by_task_id(self, task_id: str):
        for lw in self.cells.values():
            for i in range(lw.count() - 1, -1, -1):
                it = lw.item(i)
                raw2 = it.data(Qt.UserRole)
                if not raw2:
                    continue
                try:
                    d2 = json.loads(raw2)
                    if d2.get("id") == task_id:
                        lw.takeItem(i)
                except Exception:
                    continue

    def on_cell_changed(self, importance: str, urgency: str):
        # persist all tasks in this cell after drag-drop; then sort
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
        self._sort_cell_by_due_date(lw)
        self.update_status_bar()
        self.apply_filters()

    def on_search(self, text):
        # integrate search into general filtering
        self.apply_filters()

    def on_cell_selection_changed(self, lw: CellListWidget):
        # show first selected item in details panel
        sel = lw.selectedItems()
        if not sel:
            # clear selection only if nothing selected anywhere
            any_selected = any((len(c.selectedItems()) > 0 for c in self.cells.values()))
            if not any_selected:
                self._clear_details()
            return
        item = sel[0]
        raw = item.data(Qt.UserRole)
        if not raw:
            return
        try:
            d = json.loads(raw)
            t = Task.from_dict(d)
            self._show_task_in_details(t)
        except Exception:
            return

    def _show_task_in_details(self, t: Task):
        self.selected_task_id = t.id
        self.title_label.setText(t.title)
        md = f"Importance: {t.importance}  •  Urgency: {t.urgency}"
        if t.due_date:
            md += f"\nDue date: {t.due_date}"
            try:
                d = datetime.strptime(t.due_date, "%Y-%m-%d").date()
                today = datetime.utcnow().date()
                if d < today:
                    md += "  (OVERDUE)"
                elif (d - today).days <= DUE_SOON_DAYS:
                    md += "  (Due soon)"
            except Exception:
                pass
        if hasattr(t, 'tags') and t.tags:
            md += f"\nTags: {t.tags}"
        md += f"\nUpdated: {t.updated_at or '—'}"
        self.meta_label.setText(md)
        self.desc_view.setPlainText(t.description or "")

    def _clear_details(self):
        self.selected_task_id = None
        self.title_label.setText("Select a task to see details")
        self.meta_label.setText("")
        self.desc_view.setPlainText("")

    def on_edit_selected(self):
        if not self.selected_task_id:
            QMessageBox.information(self, "Edit", "Select a task first")
            return
        t = self.tasks.get(self.selected_task_id)
        if not t:
            return
        dlg = AddEditTaskDialog(self, task=t)
        if dlg.exec() == QDialog.Accepted:
            newdata = dlg.get_task_data()
            if not newdata:
                return
            t.title = newdata["title"]
            t.description = newdata["description"]
            t.importance = newdata["importance"]
            t.urgency = newdata["urgency"]
            t.due_date = newdata["due_date"]
            try:
                t.tags = newdata.get('tags', "")
            except Exception:
                pass
            t.updated_at = newdata["updated_at"]
            self.tasks[t.id] = t
            db.save_task(t)
            self._remove_item_by_task_id(t.id)
            self._add_task_item_to_cell(t)
            self._sort_cell_by_due_date(self.cells[(t.importance, t.urgency)])
            self.update_status_bar()
            self.apply_filters()

    def on_delete_selected(self):
        if not self.selected_task_id:
            # try to find currently selected item in any list
            for lw in self.cells.values():
                if lw.selectedItems():
                    raw = lw.selectedItems()[0].data(Qt.UserRole)
                    if raw:
                        try:
                            d = json.loads(raw)
                            self.selected_task_id = d.get("id")
                            break
                        except Exception:
                            pass
        if not self.selected_task_id:
            QMessageBox.information(self, "Delete", "Select a task first")
            return
        t = self.tasks.get(self.selected_task_id)
        if not t:
            return
        ok = QMessageBox.question(self, "Delete", f"Delete task '{t.title}'?")
        if ok == QMessageBox.StandardButton.Yes:
            db.delete_task(t.id)
            if t.id in self.tasks:
                del self.tasks[t.id]
            self._remove_item_by_task_id(t.id)
            self._clear_details()
            self.update_status_bar()

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
        for lw in self.cells.values():
            self._sort_cell_by_due_date(lw)
        self.update_status_bar()
        self.apply_filters()

    def update_status_bar(self):
        total = len(self.tasks)
        by_importance = {k: 0 for k in PRIORITY_ROWS}
        for t in self.tasks.values():
            by_importance[t.importance] = by_importance.get(t.importance, 0) + 1
        legend = "  ".join([f"{k.capitalize()}: {by_importance[k]}" for k in PRIORITY_ROWS])
        self.status.showMessage(f"Total: {total}  —  {legend}")

    def _sort_cell_by_due_date(self, lw: CellListWidget):
        # Collect items, sort by due date (None => after dates), then repopulate the list
        items = []
        for i in range(lw.count()):
            it = lw.item(i)
            raw = it.data(Qt.UserRole)
            try:
                d = json.loads(raw) if raw else {}
            except Exception:
                d = {}
            due = None
            try:
                if d.get("due_date"):
                    due = datetime.strptime(d.get("due_date"), "%Y-%m-%d").date()
            except Exception:
                due = None
            items.append((due, d.get("title", it.text()), raw))
        # sort: earliest due first; None last; tie-breaker by title
        items.sort(key=lambda x: (x[0] is None, x[0] or date.max, x[1].lower()))
        lw.clear()
        for due, title, raw in items:
            it = QListWidgetItem()
            self._decorate_item_from_raw(it, raw)
            lw.addItem(it)

    def on_about(self):
        QMessageBox.information(self, "About", "Eisenhower 3x3 - Polished UI\nImprovements: detail panel, context menu, overdue highlight, status bar, keyboard shortcuts.\n\nNew in this version: filters (importance/tags/due date range), priority color icons, stronger 'due soon' highlighting, and tags support in the task dialog.")

    # -- Filtering utilities --
    def _parse_tags(self, tags_field) -> set:
        if not tags_field:
            return set()
        if isinstance(tags_field, (list, tuple)):
            return set([t.strip().lower() for t in tags_field if t.strip()])
        return set([t.strip().lower() for t in str(tags_field).split(",") if t.strip()])

    def apply_filters(self):
        q = self.search.text().strip().lower()
        importance = self.importance_filter.currentText()
        tags_q = self._parse_tags(self.tags_filter.text())
        from_ok = self.from_date_filter.date().isValid()
        to_ok = self.to_date_filter.date().isValid()
        from_date = None
        to_date = None
        try:
            if from_ok:
                from_date = datetime.strptime(self.from_date_filter.date().toString("yyyy-MM-dd"), "%Y-%m-%d").date()
            if to_ok:
                to_date = datetime.strptime(self.to_date_filter.date().toString("yyyy-MM-dd"), "%Y-%m-%d").date()
        except Exception:
            from_date = to_date = None

        for lw in self.cells.values():
            for i in range(lw.count()):
                it = lw.item(i)
                raw = it.data(Qt.UserRole)
                try:
                    d = json.loads(raw) if raw else {}
                except Exception:
                    d = {}
                title = d.get("title", "").lower()
                imp = d.get("importance", "")
                item_tags = self._parse_tags(d.get("tags", ""))

                hidden = False
                # search
                if q and q not in title:
                    hidden = True
                # importance
                if importance and importance != "All" and imp != importance:
                    hidden = True
                # tags (any match)
                if tags_q and not (tags_q & item_tags):
                    hidden = True
                # due date range
                if (from_date or to_date) and d.get("due_date"):
                    try:
                        dd = datetime.strptime(d.get("due_date"), "%Y-%m-%d").date()
                        if from_date and dd < from_date:
                            hidden = True
                        if to_date and dd > to_date:
                            hidden = True
                    except Exception:
                        pass
                elif (from_date or to_date) and not d.get("due_date"):
                    # if user filters by date range but task has no due date -> hide
                    hidden = True

                it.setHidden(hidden)

    def clear_filters(self):
        self.importance_filter.setCurrentIndex(0)
        self.tags_filter.setText("")
        self.from_date_filter.clear()
        self.to_date_filter.clear()
        self.search.setText("")git 
        self.apply_filters()
