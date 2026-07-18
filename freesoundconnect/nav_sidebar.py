"""Left navigation rail: app identity on top, page switcher below."""

import os

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget,
)

from . import APP_NAME, VERSION, resource_path

SIDEBAR_WIDTH = 192

PAGES = [
    ("🔍", "Search"),
    ("🎼", "Playlists"),
]


class NavSidebar(QWidget):
    page_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NavSidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(SIDEBAR_WIDTH)

        logo = QLabel()
        icon_path = resource_path("assets", "icon.png")
        if os.path.isfile(icon_path):
            logo.setPixmap(QPixmap(icon_path).scaled(
                28, 28, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        title = QLabel(APP_NAME.replace(" ", "\n"))
        title.setObjectName("NavTitle")

        brand = QHBoxLayout()
        brand.setSpacing(8)
        brand.addWidget(logo)
        brand.addWidget(title)
        brand.addStretch(1)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("NavList")
        self.nav_list.setIconSize(QSize(20, 20))
        self.nav_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.nav_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for emoji, label in PAGES:
            self.nav_list.addItem(QListWidgetItem("%s   %s" % (emoji, label)))
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self.page_selected)

        version = QLabel("v%s" % VERSION)
        version.setObjectName("Hint")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 8, 12)
        layout.setSpacing(18)
        layout.addLayout(brand)
        layout.addWidget(self.nav_list, 1)
        layout.addWidget(version)

    def select_page(self, index):
        self.nav_list.setCurrentRow(index)
