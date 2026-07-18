"""Search page: query controls, results list, pagination and row actions.

Pure view — the search orchestration (auth, workers, paging state) stays
in MainWindow, which wires itself to the widgets exposed here.
"""

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QWidget,
)

from .config import LICENSE_CHOICES, SORT_CHOICES
from .results_tree import ResultsTree


class SearchPage(QWidget):
    def __init__(self, ensure_local_file, parent=None):
        super().__init__(parent)

        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText(
            "Search freesound.org  (e.g. rain, whoosh, door slam)")

        self.license_combo = QComboBox()
        for label, _ in LICENSE_CHOICES:
            self.license_combo.addItem(label)
        self.sort_combo = QComboBox()
        for label, _ in SORT_CHOICES:
            self.sort_combo.addItem(label)

        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("PrimaryButton")

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self.query_edit, 1)
        top.addWidget(self.license_combo)
        top.addWidget(self.sort_combo)
        top.addWidget(self.search_btn)

        hint = QLabel(
            "🎵  Drag a sound onto your DaVinci Resolve timeline (or Media "
            "Pool). Select part of the waveform below to insert only that "
            "region. Double-click a row to preview.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)

        self.tree = ResultsTree(ensure_local_file)

        self.prev_btn = QPushButton("‹ Prev")
        self.next_btn = QPushButton("Next ›")
        self.page_label = QLabel("")
        self.shotlist_btn = QPushButton("＋ Add to Shotlist")
        self.open_btn = QPushButton("Open on Freesound")
        self.folder_btn = QPushButton("Downloads Folder")

        nav = QHBoxLayout()
        nav.setSpacing(8)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.page_label)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        nav.addWidget(self.shotlist_btn)
        nav.addWidget(self.open_btn)
        nav.addWidget(self.folder_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(hint)
        layout.addWidget(self.tree, 1)
        layout.addLayout(nav)
