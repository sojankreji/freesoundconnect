"""Login dialog shown while the OAuth2 browser flow is in progress."""

import urllib.parse

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from .workers import RedirectWaiterWorker


class LoginDialog(QDialog):
    """Shown while logging in. A background thread waits for Freesound's
    browser redirect to reach our local callback server, but the user can
    also paste the authorization code (or the whole redirect URL) by
    hand — needed when the automatic redirect can't reach localhost, e.g.
    behind a strict firewall/proxy or an unusual browser setup."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.code = None
        self.setWindowTitle("Log in with Freesound")
        self.setMinimumWidth(480)

        info = QLabel(
            "A browser window opened for you to log in to Freesound.\n\n"
            "If it doesn't redirect back here automatically within a few "
            "seconds of approving, copy the authorization code (or the "
            "whole address-bar URL) from the browser and paste it below.")
        info.setWordWrap(True)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText(
            "Paste authorization code or redirect URL here")
        self.code_edit.returnPressed.connect(self._submit_manual)

        submit_btn = QPushButton("Submit code")
        submit_btn.setObjectName("PrimaryButton")
        submit_btn.clicked.connect(self._submit_manual)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(submit_btn)

        self.status_label = QLabel("Waiting for the browser…")
        self.status_label.setObjectName("Hint")
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(self.code_edit)
        layout.addLayout(buttons)
        layout.addWidget(self.status_label)

        self._waiter = RedirectWaiterWorker()
        self._waiter.succeeded.connect(self._on_auto_code)
        self._waiter.failed.connect(self._on_wait_failed)
        self._waiter.start()

    def _submit_manual(self):
        text = self.code_edit.text().strip()
        if not text:
            return
        self.code = self._extract_code(text)
        self.accept()

    @staticmethod
    def _extract_code(text):
        if "code=" in text:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(text).query)
            values = params.get("code")
            if values:
                return values[0]
        return text

    def _on_auto_code(self, code):
        self.code = code
        self.accept()

    def _on_wait_failed(self, message):
        self.status_label.setText(
            "%s You can still paste the code manually above." % message)

    def done(self, result):  # noqa: N802 (Qt override)
        # The waiter thread blocks in a system call we cannot interrupt;
        # let it run to its own timeout in the background instead of
        # freezing the dialog close on wait().
        self._waiter.succeeded.disconnect(self._on_auto_code)
        self._waiter.failed.disconnect(self._on_wait_failed)
        super().done(result)
