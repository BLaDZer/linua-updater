from PyQt6.QtCore import Qt, QThread, pyqtSlot
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from linua_updater.core.database import DLCDatabase
from linua_updater.workers.database_refresh_worker import DatabaseRefreshWorker


class CompletionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Installation Complete")
        self.setFixedSize(450, 200)
        self.setModal(True)
        self.setup_ui()
        self.apply_theme()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("All done. Enjoy and have fun playing!")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #6bcf7f; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        warning_text = QLabel("IMPORTANT: DLC need to be activated with DLC Unlocker!\nMake sure to run DLC Unlocker to activate the installed DLC.")
        warning_text.setStyleSheet("font-size: 11px; color: #cccccc; padding: 10px;")
        warning_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        warning_text.setWordWrap(True)
        layout.addWidget(warning_text)

        layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                padding: 10px 30px;
                font-size: 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QPushButton:pressed {
                background-color: #222;
            }
        """)
        close_btn.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

    def apply_theme(self):
        self.setStyleSheet("QDialog { background-color: #1e1e1e; }")

class SettingsDialog(QDialog):
    def __init__(self, parent=None, db=None, logger=None):
        super().__init__(parent)
        self.db = db
        self.logger = logger
        self._db_reset_thread = None
        self._db_reset_worker = None
        self.setWindowTitle("Settings")
        self.setFixedSize(420, 440)
        self.setup_ui()
        self.apply_dark_theme()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        thread_group = QGroupBox("Parallel Download Settings")
        thread_layout = QGridLayout()
        thread_layout.addWidget(QLabel("Maximum parallel downloads:"), 0, 0)
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 10)
        self.thread_spin.setValue(3)
        thread_layout.addWidget(self.thread_spin, 0, 1)
        thread_layout.addWidget(QLabel("Note: More threads = faster but may cause network issues"), 1, 0, 1, 2)
        thread_group.setLayout(thread_layout)
        layout.addWidget(thread_group)
        network_group = QGroupBox("Network Settings")
        network_layout = QVBoxLayout()
        self.proxy_check = QCheckBox("Use proxy if available")
        self.proxy_check.setChecked(True)
        network_layout.addWidget(self.proxy_check)
        self.resume_check = QCheckBox("Resume interrupted downloads")
        self.resume_check.setChecked(True)
        network_layout.addWidget(self.resume_check)
        self.cleanup_check = QCheckBox("Clean temp files after install")
        self.cleanup_check.setChecked(True)
        network_layout.addWidget(self.cleanup_check)
        network_group.setLayout(network_layout)
        layout.addWidget(network_group)
        db_group = QGroupBox("Database")
        db_layout = QVBoxLayout()
        db_hint = QLabel("Delete the cached DLC database and download the latest from the remote source.")
        db_hint.setWordWrap(True)
        db_layout.addWidget(db_hint)
        self.reset_db_btn = QPushButton("Reset database cache")
        self.reset_db_btn.clicked.connect(self.reset_database_cache)
        db_layout.addWidget(self.reset_db_btn)
        db_group.setLayout(db_layout)
        layout.addWidget(db_group)
        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def reset_database_cache(self):
        if self._db_reset_thread:
            return
        if self.logger:
            self.logger.log("Database cache reset requested...", "INFO")
        self.reset_db_btn.setEnabled(False)
        self.reset_db_btn.setText("Refreshing...")
        self._db_reset_worker = DatabaseRefreshWorker(self.db)
        self._db_reset_worker.result_ready.connect(self._on_db_reset_done)
        self._db_reset_thread = QThread()
        self._db_reset_worker.moveToThread(self._db_reset_thread)
        self._db_reset_thread.started.connect(self._db_reset_worker.run)
        self._db_reset_thread.start()

    @pyqtSlot(bool)
    def _on_db_reset_done(self, ok):
        self.reset_db_btn.setText("Reset database cache")
        self.reset_db_btn.setEnabled(True)
        if self.logger:
            if ok:
                self.logger.log(self.db.source_description(), "INFO")
            else:
                self.logger.log("Database cache reset failed: " + self.db.source_description(), "WARNING")
        if self._db_reset_thread:
            self._db_reset_thread.quit()
            self._db_reset_thread.wait()
            self._db_reset_thread.deleteLater()
            self._db_reset_thread = None
        if self._db_reset_worker:
            self._db_reset_worker.deleteLater()
            self._db_reset_worker = None

    def apply_dark_theme(self):
        self.setStyleSheet("QDialog{background-color:#1e1e1e;}QLabel{color:white;}QGroupBox{color:white;border:1px solid #555;border-radius:5px;margin-top:10px;padding-top:10px;}QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 5px 0 5px;}QSpinBox,QCheckBox{color:white;background-color:#2a2a2a;}")

    def get_settings(self):
        return {'max_threads': self.thread_spin.value(), 'use_proxy': self.proxy_check.isChecked(), 'resume_downloads': self.resume_check.isChecked(), 'cleanup_temp': self.cleanup_check.isChecked()}

class SpaceWarningDialog(QDialog):
    """Warning dialog for insufficient disk space"""

    def __init__(self, parent=None, space_info=None):
        super().__init__(parent)
        self.space_info = space_info or {}
        self.setWindowTitle("Insufficient Disk Space")
        self.setFixedSize(450, 250)
        self.setModal(True)
        self.setup_ui()
        self.apply_theme()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Warning icon and title
        title = QLabel("Insufficient Disk Space")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffd93d; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Space details
        required_gb = self.space_info.get('required_gb', 0)
        available_gb = self.space_info.get('available_gb', 0)
        shortage_gb = self.space_info.get('shortage_gb', 0)

        details = QLabel(
            f"Required space: {required_gb:.1f} GB\n"
            f"Available space: {available_gb:.1f} GB\n"
            f"You need {shortage_gb:.1f} GB more disk space!"
        )
        details.setStyleSheet("font-size: 12px; color: #cccccc; padding: 15px; background:#2a2a2a; border-radius:4px;")
        details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details.setWordWrap(True)
        layout.addWidget(details)

        # Advice
        advice = QLabel("Free up some disk space or select fewer DLC to install.")
        advice.setStyleSheet("font-size: 11px; color: #aaaaaa; padding: 10px;")
        advice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        advice.setWordWrap(True)
        layout.addWidget(advice)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        continue_btn = QPushButton("Continue Anyway")
        continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffd93d;
                color: #1e1e1e;
                border: none;
                padding: 10px 20px;
                font-size: 11px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ffc93d;
            }
        """)
        cancel_btn = QPushButton("Cancel")
        continue_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(continue_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def apply_theme(self):
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; }
            QPushButton {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                padding: 10px 20px;
                font-size: 11px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444;
            }
        """)

class DLCSelector(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select DLC")
        self.setFixedSize(600, 700)
        self.apply_dark_theme()
        self.cbs = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.info = QLabel("Select DLC to install.\nAlready installed DLC are hidden.")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("QLabel{color:#ffaa00;padding:10px;background:#2a2a2a;border-radius:4px;border:1px solid #ffaa00;font-weight:bold;}")
        layout.addWidget(self.info)

        self.check_all = QCheckBox("Select all available")
        self.check_all.setStyleSheet("color:white;font-weight:bold;padding:10px;")
        self.check_all.checkStateChanged.connect(self.toggle_all)
        layout.addWidget(self.check_all)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color:#2a2a2a;border:none;")
        layout.addWidget(scroll)

        self.container = QWidget()
        self.container.setStyleSheet("background-color:#2a2a2a;")
        self.layout_c = QVBoxLayout(self.container)
        self.layout_c.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.container)

        bottom = QHBoxLayout()
        self.install_btn = QPushButton("Install Selected (0)")
        cancel = QPushButton("Cancel")
        self.install_btn.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        bottom.addWidget(self.install_btn)
        bottom.addWidget(cancel)
        layout.addLayout(bottom)

        self.check_all.stateChanged.connect(self.update_install_button)

    def apply_dark_theme(self):
        self.setStyleSheet("QDialog{background-color:#1e1e1e;}QLabel{color:white;padding:5px;}QLineEdit{background-color:#0a0a0a;color:white;border:1px solid #444;padding:8px;border-radius:4px;}QCheckBox{color:white;background-color:#2a2a2a;padding:8px;border-radius:3px;margin:2px;}QCheckBox::indicator{width:18px;height:18px;}QCheckBox::indicator:unchecked{border:2px solid #555;background-color:#333;}QCheckBox::indicator:checked{border:2px solid #0078d7;background-color:#0078d7;}QCheckBox:hover{background-color:#333;}QPushButton{background-color:#333;color:white;border:1px solid #555;padding:10px 20px;border-radius:4px;font-weight:bold;}QPushButton:hover{background-color:#444;}QPushButton:pressed{background-color:#222;}")

    def toggle_all(self, state):
        checked = (state == Qt.CheckState.Checked)
        for dlc_id, cb in self.cbs.items():
            if cb.isVisible() and cb.isEnabled():
                cb.setChecked(checked)
        self.update_install_button()

    def populate(self, db, installed):
        for i in reversed(range(self.layout_c.count())):
            item = self.layout_c.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        self.cbs.clear()

        available = [(dlc_id, info) for dlc_id, info in db.items() if dlc_id.upper() not in installed]

        if not available:
            no_dlc = QLabel("ALL DLC ALREADY INSTALLED!")
            no_dlc.setStyleSheet("QLabel{color:#00ff00;padding:30px;font-size:16px;font-weight:bold;text-align:center;background:#2a2a2a;border-radius:10px;margin:20px;border:2px solid #00ff00;}")
            no_dlc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout_c.addWidget(no_dlc)
            info_label = QLabel("All available DLC are already installed.\n\nFor new DLC, check for application updates.")
            info_label.setStyleSheet("color:#aaaaaa;padding:15px;text-align:center;")
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_label.setWordWrap(True)
            self.layout_c.addWidget(info_label)
            self.check_all.setVisible(False)
            self.install_btn.setEnabled(False)
            self.install_btn.setText("All installed")
            return

        self.check_all.setVisible(True)
        self.install_btn.setEnabled(True)

        for dlc_id, info in sorted(available):
            cb = QCheckBox(f"[{dlc_id}] {info['name']}")
            cb.setStyleSheet("color:white;font-size:11px;")
            cb.stateChanged.connect(self.update_install_button)
            self.layout_c.addWidget(cb)
            self.cbs[dlc_id] = cb

        self.layout_c.addStretch()
        self.update_install_button()

    def update_install_button(self):
        selected = len([cb for cb in self.cbs.values() if cb.isChecked() and cb.isEnabled()])
        if selected > 0:
            self.install_btn.setText(f"Install Selected ({selected})")
            self.install_btn.setEnabled(True)
        else:
            self.install_btn.setText("Install Selected (0)")
            self.install_btn.setEnabled(False)

    def get(self):
        return [dlc for dlc, cb in self.cbs.items() if cb.isChecked() and cb.isEnabled()]

class UninstallDialog(QDialog):
    """DLC Uninstaller in Linua style - dark theme, clean UI"""
    def __init__(self, parent=None, game_path="", installed_dlc=None):
        super().__init__(parent)
        self.game_path = game_path
        self.installed_dlc = installed_dlc or []
        self.setWindowTitle("Uninstall DLC")
        self.setFixedSize(600, 700)
        self.apply_dark_theme()
        self.cbs = {}
        self.setup_ui()
    def setup_ui(self):
        layout = QVBoxLayout(self)
        # Info label
        self.info = QLabel(f"Select DLC to uninstall from:\n{self.game_path}")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("QLabel{color:#ff6b6b;padding:10px;background:#2a2a2a;border-radius:4px;border:1px solid #ff6b6b;font-weight:bold;}")
        layout.addWidget(self.info)
        # Warning
        warning = QLabel("WARNING: This will permanently delete selected DLC files!")
        warning.setStyleSheet("QLabel{color:#ffd93d;padding:8px;background:#3a2a1a;border-radius:4px;font-size:11px;}")
        warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning)
        # Select all checkbox
        self.check_all = QCheckBox("Select all installed DLC")
        self.check_all.setStyleSheet("color:white;font-weight:bold;padding:10px;")
        self.check_all.checkStateChanged.connect(self.toggle_all)
        layout.addWidget(self.check_all)
        # Scroll area with DLC list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color:#2a2a2a;border:none;")
        layout.addWidget(scroll)
        self.container = QWidget()
        self.container.setStyleSheet("background-color:#2a2a2a;")
        self.layout_c = QVBoxLayout(self.container)
        self.layout_c.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.container)
        # Populate DLC list
        self.populate_dlc()
        # Buttons
        bottom = QHBoxLayout()
        self.uninstall_btn = QPushButton("Uninstall Selected (0)")
        self.uninstall_btn.setStyleSheet("""
            QPushButton {
                background-color: #c92a2a;
                color: white;
                border: 1px solid #a61e1e;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e03131;
            }
            QPushButton:pressed {
                background-color: #a61e1e;
            }
            QPushButton:disabled {
                background-color: #5c2020;
                color: #888;
            }
        """)
        cancel = QPushButton("Cancel")
        self.uninstall_btn.clicked.connect(self.confirm_uninstall)
        cancel.clicked.connect(self.reject)
        bottom.addWidget(self.uninstall_btn)
        bottom.addWidget(cancel)
        layout.addLayout(bottom)
        self.check_all.stateChanged.connect(self.update_uninstall_button)
    def apply_dark_theme(self):
        self.setStyleSheet("""
            QDialog{background-color:#1e1e1e;}
            QLabel{color:white;padding:5px;}
            QCheckBox{color:white;background-color:#2a2a2a;padding:8px;border-radius:3px;margin:2px;}
            QCheckBox::indicator{width:18px;height:18px;}
            QCheckBox::indicator:unchecked{border:2px solid #555;background-color:#333;}
            QCheckBox::indicator:checked{border:2px solid #c92a2a;background-color:#c92a2a;}
            QCheckBox:hover{background-color:#333;}
            QPushButton{background-color:#333;color:white;border:1px solid #555;padding:10px 20px;border-radius:4px;font-weight:bold;}
            QPushButton:hover{background-color:#444;}
            QPushButton:pressed{background-color:#222;}
        """)
    def populate_dlc(self):
        """Populate list with installed DLC"""
        if not self.installed_dlc:
            no_dlc = QLabel("No DLC installed!")
            no_dlc.setStyleSheet("QLabel{color:#888;padding:30px;font-size:14px;text-align:center;}")
            no_dlc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout_c.addWidget(no_dlc)
            self.uninstall_btn.setEnabled(False)
            return
        db = DLCDatabase()
        for dlc_id in sorted(self.installed_dlc):
            info = db.all().get(dlc_id)
            name = info.get('name', 'Unknown') if info else 'Unknown'
            cb = QCheckBox(f"[{dlc_id}] {name}")
            cb.setStyleSheet("color:white;font-size:11px;")
            cb.stateChanged.connect(self.update_uninstall_button)
            self.layout_c.addWidget(cb)
            self.cbs[dlc_id] = cb
        self.layout_c.addStretch()
    def toggle_all(self, state):
        checked = (state == Qt.CheckState.Checked)
        for dlc_id, cb in self.cbs.items():
            cb.setChecked(checked)
    def update_uninstall_button(self):
        selected = len([cb for cb in self.cbs.values() if cb.isChecked()])
        if selected > 0:
            self.uninstall_btn.setText(f"Uninstall Selected ({selected})")
            self.uninstall_btn.setEnabled(True)
        else:
            self.uninstall_btn.setText("Uninstall Selected (0)")
            self.uninstall_btn.setEnabled(False)
    def confirm_uninstall(self):
        """Show confirmation dialog before uninstalling"""
        selected = self.get_selected()
        if not selected:
            return
        reply = QMessageBox.warning(
            self,
            "Confirm Uninstall",
            f"Are you sure you want to uninstall {len(selected)} DLC?\n\n"
            f"This will permanently delete:\n" + "\n".join([f"- {dlc}" for dlc in selected[:5]]) +
            (f"\n... and {len(selected) - 5} more" if len(selected) > 5 else ""),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()
    def get_selected(self):
        """Get list of selected DLC IDs"""
        return [dlc_id for dlc_id, cb in self.cbs.items() if cb.isChecked()]