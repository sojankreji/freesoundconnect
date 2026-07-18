"""Application-wide Qt stylesheet."""

STYLESHEET = """
QWidget {
    background: #12152b;
    color: #e7e9f5;
    font-size: 13px;
}
QLabel#Hint {
    color: #9aa0c3;
    padding: 4px 2px;
}
QLabel#Status {
    color: #9aa0c3;
    padding-top: 4px;
}
QLabel#AppTitle {
    font-size: 17px;
    font-weight: 600;
    color: #ffffff;
}
QLabel#PanelTitle {
    font-weight: 600;
    color: #ffffff;
    padding: 2px 0;
}
QLabel#TimeLabel {
    color: #9aa0c3;
    font-family: Menlo, Consolas, monospace;
    font-size: 12px;
}
QLabel#SelectionLabel {
    color: #35e0c3;
    font-size: 12px;
}
QLineEdit, QComboBox {
    background: #1b2044;
    border: 1px solid #2a3060;
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: #35e0c3;
    selection-color: #0c0f1f;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #4f9dff;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background: #1b2044;
    border: 1px solid #2a3060;
    selection-background-color: #2a3161;
    outline: none;
}
QPushButton {
    background: #1e2450;
    border: 1px solid #2a3060;
    border-radius: 8px;
    padding: 7px 14px;
    color: #e7e9f5;
}
QPushButton:hover {
    background: #262d5c;
    border: 1px solid #3a4280;
}
QPushButton:pressed {
    background: #171b3d;
}
QPushButton:disabled {
    color: #5c6289;
}
QPushButton#PrimaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                 stop:0 #35e0c3, stop:1 #4f9dff);
    color: #0c0f1f;
    font-weight: 600;
    border: none;
}
QPushButton#PrimaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                 stop:0 #4aeed3, stop:1 #66aeff);
}
QPushButton#PrimaryButton:disabled {
    background: #2a3060;
    color: #5c6289;
}
QPushButton#LogoutButton {
    background: transparent;
    border: none;
    color: #9aa0c3;
    padding: 4px 8px;
}
QPushButton#LogoutButton:hover {
    color: #ff8fa3;
}
QPushButton#TransportButton {
    min-width: 30px;
    padding: 6px 10px;
    font-size: 14px;
}
QPushButton#SmallButton {
    padding: 4px 10px;
    font-size: 12px;
}
QLabel#Username {
    color: #e7e9f5;
    font-weight: 500;
}
QTreeWidget {
    background: #171b3d;
    alternate-background-color: #1a1f45;
    border: 1px solid #262c56;
    border-radius: 10px;
    padding: 2px;
}
QTreeWidget::item {
    padding: 6px 4px;
    border: none;
}
QTreeWidget::item:selected {
    background: #2a4a6b;
    color: #ffffff;
    border-radius: 4px;
}
QHeaderView::section {
    background: #12152b;
    color: #9aa0c3;
    border: none;
    border-bottom: 1px solid #262c56;
    padding: 6px 4px;
    font-weight: 600;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #2a3060;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background: #2a3060;
    border-radius: 5px;
    min-width: 24px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #2a3060;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
    background: #4f9dff;
}
QSlider::sub-page:horizontal {
    background: #35e0c3;
    border-radius: 2px;
}
QSplitter::handle {
    background: #12152b;
    width: 6px;
}
QFrame#PlayerBar {
    background: #171b3d;
    border: 1px solid #262c56;
    border-radius: 10px;
}
QFrame#PlayerBar QWidget {
    background: transparent;
}
QFrame#PopupFrame {
    background: #171b3d;
    border: 1px solid #3a4280;
    border-radius: 12px;
}
QPushButton#CartButton {
    background: #1e2450;
    border: 1px solid #3a4280;
    border-radius: 8px;
    padding: 7px 12px;
    font-weight: 600;
}
QPushButton#CartButton:hover {
    background: #262d5c;
    border: 1px solid #4f9dff;
}
QWidget#NavSidebar {
    background: #0c0f22;
    border-right: 1px solid #262c56;
}
QWidget#NavSidebar QLabel {
    background: transparent;
}
QLabel#NavTitle {
    font-size: 14px;
    font-weight: 700;
    color: #ffffff;
}
QListWidget#NavList {
    background: transparent;
    border: none;
    font-size: 14px;
    outline: none;
}
QListWidget#NavList::item {
    padding: 10px 12px;
    border-radius: 8px;
    margin: 2px 4px;
    color: #9aa0c3;
}
QListWidget#NavList::item:hover {
    background: #1b2044;
    color: #e7e9f5;
}
QListWidget#NavList::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                 stop:0 #223a6b, stop:1 #1e2a5c);
    color: #ffffff;
    font-weight: 600;
}
"""
