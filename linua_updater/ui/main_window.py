import json
import os
import time

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

from linua_updater.constants import APP_VERSION
from linua_updater.core.detection import GameDetector
from linua_updater.core.diagnostics import NetworkDiagnostics
from linua_updater.core.downloader import SmartDownloader
from linua_updater.core.extractor import Extractor
from linua_updater.logging_util import ImprovedLogger
from linua_updater.paths import AppPaths
from linua_updater.persistence.download_state import DownloadState
from linua_updater.ui.dialogs import CompletionDialog, DLCSelector, SettingsDialog, SpaceWarningDialog, UninstallDialog
from linua_updater.ui.theme import MAIN_STYLESHEET
from linua_updater.ui.widgets import SimpleDetailWidget, SimpleProgressBar
from linua_updater.utils.admin import AdminElevator
from linua_updater.utils.disk_space import DiskSpaceChecker
from linua_updater.workers.diagnostics_worker import DiagnosticsWorker
from linua_updater.workers.install_worker import InstallWorker
from linua_updater.workers.uninstall_worker import UninstallWorker
from linua_updater.workers.update_checker import UpdateChecker


class LinuaUI(QMainWindow):
    def __init__(self, config, db):
        super().__init__()
        self.config = config
        self.db = db
        self.is_closing = False
        self.setWindowTitle(f"Linua Updater v{APP_VERSION}")
        self.setFixedSize(650, 650)
        self.setup_ui()
        self.apply_dark_theme()
        self.logger = ImprovedLogger(self.log_text)
        self.diagnostics = None
        self.downloader = SmartDownloader(self.logger)
        self.extractor = Extractor(self.logger)
        self.install_thread = None
        self.install_worker = None
        self._update_thread = None
        self._diag_thread = None
        self.progress_total = 0
        self.progress_done = 0
        self.successful_count = 0
        self.failed_count = 0
        self.settings = self.config.get_settings()
        self.network = self.config.get_network()
        self.dlc_check_timer = QTimer()
        self.dlc_check_timer.timeout.connect(self.update_dlc_status)
        saved = self.config.get("game_path", "")
        if saved:
            self.path_input.setText(saved)
        QTimer.singleShot(100, self.check_for_updates)
        QTimer.singleShot(300, self.run_diagnostics)
        QTimer.singleShot(500, self.auto_detect)
        self.dlc_check_timer.start(3000)
        QTimer.singleShot(1000, self.update_dlc_status)
        QTimer.singleShot(600, self.check_saved_download_state)

    def check_for_updates(self):
        """Check for updates on startup"""
        self.logger.log("Checking for updates...")
        self.update_checker = UpdateChecker(None, version_url=self.network['version_check_url'])  # logger=None: worker logs via signals
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.no_update.connect(lambda: self.logger.log("No updates available"))
        self.update_checker.check_failed.connect(
            lambda err: self.logger.log(f"Update check failed: {err}", "WARNING")
        )
        self._update_thread = QThread()
        self.update_checker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self.update_checker.check_for_updates)
        self._update_thread.finished.connect(self._update_thread.deleteLater)
        self._update_thread.start()

    def on_update_available(self, version, url):
        """Handle update notification"""
        self.logger.log(f"New version available: {version}")
        reply = QMessageBox.question(
            self,
            "Update Available",
            f"New version {version} is available!\n\nDo you want to download it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            import webbrowser
            webbrowser.open(url)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        title = QLabel(f"Linua Updater v{APP_VERSION}")
        title.setStyleSheet("QLabel{font-weight:bold;font-size:14px;padding:8px;color:#0078d7;background:#2a2a2a;border-radius:6px;text-align:center;}")
        layout.addWidget(title)
        path_label = QLabel("The Sims 4 folder:")
        path_label.setStyleSheet("color:white;font-weight:bold;")
        layout.addWidget(path_label)
        row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("C:\\Program Files (x86)\\Steam\\steamapps\\common\\The Sims 4")
        self.path_input.textChanged.connect(self.on_path_changed)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self.browse_folder)
        auto = QPushButton("Auto Detect")
        auto.clicked.connect(self.auto_detect)
        row.addWidget(self.path_input, 3)
        row.addWidget(browse, 1)
        row.addWidget(auto, 1)
        layout.addLayout(row)
        self.dlc_status = QLabel("Select game folder")
        self.dlc_status.setStyleSheet("QLabel{color:#00ff00;background:#2a2a2a;padding:6px;border-radius:4px;font-size:11px;text-align:center;margin:2px 0;}")
        self.dlc_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.dlc_status)
        self.download_progress = SimpleProgressBar()
        self.download_progress.setVisible(False)
        self.download_progress.setStyleSheet("QProgressBar{background-color:#1a1a1a;border:2px solid #333;border-radius:6px;text-align:center;color:white;height:30px;font-weight:bold;font-size:14px;font-family:'Segoe UI',Arial;}QProgressBar::chunk{background-color:#00aa00;border-radius:4px;border:1px solid #008800;}")
        layout.addWidget(self.download_progress)
        self.download_detail = SimpleDetailWidget()
        layout.addWidget(self.download_detail)
        self.buttons_row = QHBoxLayout()
        self.update_btn = QPushButton("Install")
        self.update_btn.clicked.connect(self.on_update)
        self.uninstall_btn = QPushButton("Uninstall")
        self.uninstall_btn.clicked.connect(self.on_uninstall)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.on_pause)
        self.pause_btn.setVisible(False)
        self.pause_btn.setEnabled(False)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.on_cancel)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        self.export_logs_btn = QPushButton("Export Logs")
        self.export_logs_btn.clicked.connect(self.export_logs)
        self.buttons_row.addWidget(self.update_btn)
        self.buttons_row.addWidget(self.uninstall_btn)
        self.buttons_row.addWidget(self.pause_btn)
        self.buttons_row.addWidget(self.cancel_btn)
        self.buttons_row.addWidget(self.settings_btn)
        self.buttons_row.addWidget(self.export_logs_btn)
        layout.addLayout(self.buttons_row)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("QTextEdit{background-color:#0a0a0a;color:#00ff00;border:1px solid #444;border-radius:4px;padding:5px;}")
        layout.addWidget(self.log_text, 1)
        info = QLabel(
            "Enjoying Linua Updater? Support the project!<br>"
            "<a href='https://boosty.to/l1ntol' style='color:#ffd700;'>Boosty</a> | "
            "<a href='https://www.donationalerts.com/r/l1ntol' style='color:#ffd700;'>DonationAlerts</a>"
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setStyleSheet("QLabel{background-color:#2a2a2a;padding:10px;border-radius:6px;"
                   "color:#ffd700;font-size:11px;border-left:4px solid #ffd700;}")
        layout.addWidget(info)

    def apply_dark_theme(self):
        self.setStyleSheet(MAIN_STYLESHEET)

    def export_logs(self):
        """Export logs to the default location and reveal it."""
        success, result = self.logger.export_logs()
        if success:
            self.logger.log(f"Logs exported to: {result}", "INFO")
        else:
            QMessageBox.warning(self, "Export Failed", f"Failed to export logs:\n{result}")

    def on_path_changed(self, text):
        QTimer.singleShot(500, self.update_dlc_status)

    def update_dlc_status(self):
        if self.is_closing or not self.isVisible():
            return
        path = self.path_input.text().strip()
        if not path or not os.path.exists(path):
            self.dlc_status.setText("Select valid game folder")
            self.update_btn.setEnabled(False)
            return
        installed = self.detect_installed(path)
        total_dlc = len(self.db.all())
        available = [k for k in self.db.all().keys() if k.upper() not in installed]
        if len(available) == 0:
            self.dlc_status.setText(f"ALL {total_dlc} DLC INSTALLED")
            self.update_btn.setEnabled(False)
            self.update_btn.setText("All installed")
        else:
            self.dlc_status.setText(f"Installed: {len(installed)}/{total_dlc} | Available: {len(available)}")
            self.update_btn.setEnabled(True)
            self.update_btn.setText(f"Update ({len(available)} available)")

    def run_diagnostics(self):
        if self.is_closing:
            return

        # Check diagnostics cache (3 hours)
        cache_file = AppPaths.DIAG_CACHE_FILE
        cache_duration = AppPaths.DIAG_CACHE_DURATION

        try:
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    cache = json.load(f)
                if time.time() - cache.get('timestamp', 0) < cache_duration:
                    tool = NetworkDiagnostics(self.logger, region_api=self.network['region_api'], proxy_ports=self.network['proxy_ports'])
                    tool.can_reach_github = cache.get('can_reach_github', True)
                    tool.proxy_needed = cache.get('proxy_needed', False)
                    tool.recommended_solution = cache.get('recommended_solution', 'direct')
                    self.logger.log(f"Network: cached diagnostics ({int((time.time() - cache['timestamp']) / 60)} min old)", "DEBUG")
                    self.diagnostics = tool
                    self.downloader = SmartDownloader(self.logger, self.diagnostics, mirrors=self.network['mirrors'])
                    return
        except:
            pass

        self._diag_worker = DiagnosticsWorker(self.network)
        self._diag_worker.result_ready.connect(self._apply_diagnostics)
        self._diag_thread = QThread()
        self._diag_worker.moveToThread(self._diag_thread)
        self._diag_thread.started.connect(self._diag_worker.run)
        self._diag_thread.finished.connect(self._diag_thread.deleteLater)
        self._diag_thread.start()

    def _apply_diagnostics(self, tool):
        self.diagnostics = tool
        self.downloader = SmartDownloader(self.logger, self.diagnostics, mirrors=self.network['mirrors'])
        cache_file = AppPaths.DIAG_CACHE_FILE
        try:
            AppPaths.ensure()
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'can_reach_github': tool.can_reach_github,
                    'proxy_needed': tool.proxy_needed,
                    'recommended_solution': tool.recommended_solution
                }, f)
        except:
            pass
        if tool.recommended_solution == "direct":
            self.logger.log("Network check: OK (direct connection)")
        elif tool.recommended_solution == "proxy":
            self.logger.log(f"Network: using proxy ({len(tool.working_proxies)} found)")
        else:
            self.logger.log("Network: blocked. Install Cloudflare WARP: https://1.1.1.1/", "WARNING")

    def show_settings(self):
        dlg = SettingsDialog(self)
        dlg.thread_spin.setValue(self.settings.get('max_threads', 3))
        dlg.proxy_check.setChecked(self.settings.get('use_proxy', True))
        dlg.resume_check.setChecked(self.settings.get('resume_downloads', True))
        dlg.cleanup_check.setChecked(self.settings.get('cleanup_temp', True))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_settings = dlg.get_settings()
            self.settings.update(new_settings)
            self.config.set("settings", self.settings)
            self.logger.log("Settings saved")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select The Sims 4 Folder", self.path_input.text() or "C:\\")
        if folder:
            self.path_input.setText(folder)
            self.config.set("game_path", folder)
            self.logger.log(f"Selected: {folder}")

    def auto_detect(self):
        if self.is_closing:
            return
        self.logger.log("Searching for game...")
        found_path = GameDetector.find_game()
        if found_path:
            self.path_input.setText(found_path)
            self.config.set("game_path", found_path)
            self.logger.log(f"Game found: {found_path}")
            self.update_dlc_status()
        else:
            self.logger.log("Game not found. Please select manually", "WARNING")

    def detect_installed(self, game_path):
        installed = set()
        if not os.path.exists(game_path):
            return installed
        try:
            for item in os.listdir(game_path):
                u = item.upper()
                if u.startswith(("EP", "GP", "SP", "FP")):
                    item_path = os.path.join(game_path, item)
                    if os.path.isdir(item_path):
                        try:
                            if any(os.scandir(item_path)):
                                installed.add(u)
                        except:
                            installed.add(u)
        except Exception as e:
            if not self.is_closing:
                self.logger.log(f"Error scanning DLC: {e}", "ERROR")
        return installed

    def on_update(self):
        if self.is_closing:
            return
        path = self.path_input.text().strip()
        if path and os.path.exists(path):
            installed = self.detect_installed(path)
            available = [(dlc_id, info) for dlc_id, info in self.db.all().items() if dlc_id.upper() not in installed]
            if not available:
                self.logger.log("All DLC already installed!")
                QMessageBox.information(self, "All Installed!", "All available DLC are already installed!\n\nFor new DLC, check for application updates.")
                return
        if not path:
            self.logger.log("Please select game folder", "ERROR")
            QMessageBox.warning(self, "No Path", "Please select your Sims 4 folder first.")
            return
        if not os.path.exists(path):
            self.logger.log("Path doesn't exist", "ERROR")
            QMessageBox.critical(self, "Invalid Path", "The selected path doesn't exist.")
            return
        if AdminElevator.requires_admin(path):
            if not AdminElevator.is_admin():
                self.logger.log("Administrator privileges required", "WARNING")
                reply = QMessageBox.question(self, "Administrator Required", f"The selected path requires administrator privileges:\n\n{path}\n\nThe application needs to restart with elevated privileges.\nClick Yes to restart as administrator.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    self.logger.log("Restarting with admin rights...")
                    AdminElevator.elevate()
                else:
                    self.logger.log("User declined elevation")
                return
            else:
                self.logger.log("Running with admin privileges")
        exe_path = os.path.join(path, "Game", "Bin", "TS4_x64.exe")
        if not os.path.exists(exe_path):
            self.logger.log("TS4_x64.exe not found", "WARNING")
            reply = QMessageBox.question(self, "Invalid Game Folder?", "TS4_x64.exe not found in this folder.\n\nThis may not be a valid Sims 4 installation.\nContinue anyway?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        else:
            self.logger.log("Game executable found")
        installed = self.detect_installed(path)
        dlg = DLCSelector(self)
        dlg.populate(self.db.all(), installed)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.logger.log("Selection cancelled")
            return
        selected = dlg.get()
        if not selected:
            self.logger.log("No DLC selected")
            QMessageBox.information(self, "No Selection", "No DLC selected for installation.")
            return

        # Check disk space for selected DLC
        space_info = DiskSpaceChecker.check_space(selected, path)
        if not space_info['enough_space']:
            space_dlg = SpaceWarningDialog(self, space_info)
            if space_dlg.exec() != QDialog.DialogCode.Accepted:
                self.logger.log("Installation cancelled due to insufficient space")
                return
            else:
                self.logger.log(f"User chose to continue despite low space ({space_info['shortage_gb']:.1f} GB short)", "WARNING")

        self.start_parallel_install(selected, path)

    def start_parallel_install(self, selected, path):
        self.logger.log(f"Installing {len(selected)} DLC (using {self.settings.get('max_threads', 3)} threads)")
        self.progress_total = len(selected)
        self.progress_done = 0
        self.successful_count = 0
        self.failed_count = 0
        self.download_progress.setVisible(True)
        self.download_progress.setValue(0)
        self.download_detail.setVisible(True)
        self.download_detail.setText("Starting download...")
        self.update_btn.setVisible(False)
        self.uninstall_btn.setVisible(False)
        self.pause_btn.setVisible(True)
        self.pause_btn.setEnabled(True)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self.settings_btn.setEnabled(False)
        self.export_logs_btn.setEnabled(False)
        self.install_worker = InstallWorker(selected, path, self.settings, mirrors=self.network['mirrors'])
        self.install_thread = QThread()
        self.install_worker.moveToThread(self.install_thread)
        self.install_worker.progress_updated.connect(self.on_progress_updated)
        self.install_worker.overall_progress_updated.connect(self.on_overall_progress_updated)
        self.install_worker.result_ready.connect(self.on_install_result)
        self.install_worker.started.connect(self.on_install_started)
        self.install_worker.finished.connect(self.on_install_finished)
        self.install_worker.stats_ready.connect(self.on_stats_ready)
        self.install_thread.started.connect(self.install_worker.run)
        self.install_thread.finished.connect(self.install_thread.deleteLater)
        self.install_thread.start()

    @pyqtSlot(str, float, int, int)
    def on_progress_updated(self, dlc_id, progress, downloaded, total):
        if total > 0:
            self.download_detail.update_progress(dlc_id, progress, downloaded, total)

    @pyqtSlot(float)
    def on_overall_progress_updated(self, progress):
        self.download_progress.setValue(int(progress))

    @pyqtSlot(str, bool, str)
    def on_install_result(self, dlc_id, success, message):
        self.progress_done += 1
        if success:
            self.successful_count += 1
            self.logger.log(f"{dlc_id}: Installation successful")
        else:
            self.failed_count += 1
            self.logger.log(f"{dlc_id}: FAILED - {message}", "ERROR")
        remaining = self.progress_total - self.progress_done
        if self.failed_count == 0:
            self.logger.log(f"Progress: {self.progress_done}/{self.progress_total} (Success: {self.successful_count}, Failed: {self.failed_count})")
        else:
            self.logger.log(f"Progress: {self.progress_done}/{self.progress_total} (Success: {self.successful_count}, Failed: {self.failed_count})", "WARNING")

    @pyqtSlot()
    def on_install_started(self):
        self.logger.log("Installation started")

    @pyqtSlot(dict)
    def on_stats_ready(self, stats):
        self.logger.log("")
        self.logger.log("=== STATISTICS ===")
        self.logger.log(f"Total: {stats['total_dlc']} DLC")
        self.logger.log(f"Size: {stats['total_size_mb']:.1f} MB")
        self.logger.log(f"Time: {stats['total_duration_sec']:.1f}s")
        self.logger.log(f"Speed: {stats['avg_speed_mbps']:.2f} MB/s")
        if stats['failed'] == 0:
            self.logger.log(f"Success: {stats['successful']}, Failed: {stats['failed']}")
        else:
            self.logger.log(f"Success: {stats['successful']}", "INFO")
            self.logger.log(f"Failed: {stats['failed']}", "ERROR")
            if stats.get('errors'):
                self.logger.log("", "INFO")
                self.logger.log("=== ERROR DETAILS ===", "ERROR")
                for err in stats['errors']:
                    self.logger.log(f"{err['dlc_id']}: {err['error']}", "ERROR")
                self.logger.log("=====================", "ERROR")
        self.logger.log("==================")

    @pyqtSlot()
    def on_install_finished(self):
        self.logger.log("Installation complete!")
        self.download_progress.setValue(100)
        self.download_detail.setText("Installation complete!")
        QTimer.singleShot(1000, self.reset_ui_after_install)

        if self.failed_count == 0:
            completion_dlg = CompletionDialog(self)
            completion_dlg.exec()
        else:
            msg = f"Installation finished:\n\nSuccessful: {self.successful_count}\nFailed: {self.failed_count}\n\nCheck log for details."
            QMessageBox.warning(self, "Installation Complete", msg)

        self.update_dlc_status()
        if self.install_thread:
            self.install_thread.quit()
            self.install_thread.wait()
            self.install_thread = None
            self.install_worker = None

    def reset_ui_after_install(self):
        if self.is_closing:
            return
        self.download_progress.setVisible(False)
        self.download_detail.setVisible(False)
        self.download_progress.setValue(0)
        self.update_btn.setVisible(True)
        self.update_btn.setText("Install")
        self.update_btn.setEnabled(True)
        self.uninstall_btn.setVisible(True)
        self.uninstall_btn.setEnabled(True)
        self.pause_btn.setVisible(False)
        self.pause_btn.setEnabled(False)
        if self.pause_btn.text() == "Resume":
            self.pause_btn.clicked.disconnect()
            self.pause_btn.clicked.connect(self.on_pause)
            self.pause_btn.setText("Pause")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self.settings_btn.setEnabled(True)
        self.export_logs_btn.setEnabled(True)

    def on_cancel(self):
        if self.install_worker:
            self.logger.log("Cancelling installation...", "WARNING")
            self.install_worker.cancel()
            self.cancel_btn.setText("Cancelling...")
            self.cancel_btn.setEnabled(False)
            QTimer.singleShot(1000, self.show_cancelled_message)

    def show_cancelled_message(self):
        self.logger.log("Installation cancelled", "WARNING")
        QMessageBox.information(self, "Installation Cancelled", "Installation has been cancelled.")
        self.reset_ui_after_install()
        self.update_dlc_status()

    def on_uninstall(self):
        """Handle uninstall button click"""
        path = self.path_input.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "No Path", "Please select your Sims 4 folder first.")
            return

        installed = self.detect_installed(path)
        if not installed:
            QMessageBox.information(self, "No DLC", "No DLC installed to uninstall!")
            return

        dlg = UninstallDialog(self, path, list(installed))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected = dlg.get_selected()
        if not selected:
            return

        self.start_uninstall(selected, path)

    def start_uninstall(self, dlc_ids, path):
        """Start uninstalling selected DLC"""
        self.logger.log(f"Uninstalling {len(dlc_ids)} DLC...")

        self.update_btn.setEnabled(False)
        self.uninstall_btn.setEnabled(False)
        self.download_progress.setVisible(True)
        self.download_progress.setValue(0)

        self.uninstall_worker = UninstallWorker(dlc_ids, path, self.logger)
        self.uninstall_thread = QThread()
        self.uninstall_worker.moveToThread(self.uninstall_thread)

        self.uninstall_worker.progress_updated.connect(lambda curr, total: self.download_progress.setValue(int((curr/total)*100)))
        self.uninstall_worker.dlc_removed.connect(self.on_dlc_removed)
        self.uninstall_worker.finished.connect(self.on_uninstall_finished)

        self.uninstall_thread.started.connect(self.uninstall_worker.run)
        self.uninstall_thread.start()

    def on_dlc_removed(self, dlc_id, success, message):
        """Handle single DLC removal result"""
        if success:
            self.logger.log(f"{dlc_id}: Removed", "INFO")
        else:
            self.logger.log(f"{dlc_id}: Failed - {message}", "ERROR")

    def on_uninstall_finished(self):
        """Handle uninstall completion"""
        self.logger.log("Uninstall complete!")
        self.download_progress.setVisible(False)
        self.update_btn.setEnabled(True)
        self.uninstall_btn.setEnabled(True)
        self.update_dlc_status()

        QMessageBox.information(self, "Complete", "Uninstall complete!")

        if self.uninstall_thread:
            self.uninstall_thread.quit()
            self.uninstall_thread.wait()

    def on_pause(self):
        """Handle pause button click"""
        if not self.install_worker:
            return
        self.install_worker.pause()
        self.pause_btn.setText("Resume")
        self.pause_btn.clicked.disconnect()
        self.pause_btn.clicked.connect(self.on_resume)
        self.cancel_btn.setEnabled(True)
        self.logger.log("Installation paused", "WARNING")

    def on_resume(self):
        """Handle resume button click"""
        if not self.install_worker:
            return
        self.install_worker.resume()
        self.pause_btn.setText("Pause")
        self.pause_btn.clicked.disconnect()
        self.pause_btn.clicked.connect(self.on_pause)
        self.logger.log("Resuming installation...", "INFO")

    def check_saved_download_state(self):
        if self.is_closing or self.install_worker:
            return
        state = DownloadState().load_state()
        if not state:
            return
        if not self.settings.get('resume_downloads', True):
            DownloadState().clear_state()
            return
        remaining = state.get('remaining') or []
        path = state.get('game_path') or self.config.get('game_path', '')
        if not path or not os.path.exists(path) or not remaining:
            DownloadState().clear_state()
            return
        available = [k for k in remaining if k.upper() not in self.detect_installed(path)]
        if not available:
            self.logger.log("All saved DLC already installed", "INFO")
            DownloadState().clear_state()
            return
        reply = QMessageBox.question(
            self,
            "Resume Install?",
            f"Found an unfinished installation ({len(available)} DLC remaining).\n\nResume it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.path_input.setText(path)
            self.config.set("game_path", path)
            self.start_parallel_install(available, path)
        else:
            DownloadState().clear_state()

    def closeEvent(self, event):
        self.is_closing = True
        self.logger.log("Shutting down...")
        self.dlc_check_timer.stop()
        if self.install_worker:
            self.install_worker.cancel()
        if self.install_thread:
            self.install_thread.quit()
            self.install_thread.wait()
        for child in self.findChildren(QDialog):
            try:
                child.close()
                child.deleteLater()
            except:
                pass
        event.accept()