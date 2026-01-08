# ================================================================
#                       LINUA UPDATER v4.1
#           Complete Working Version • By l1ntol
# ================================================================

import os
import sys
import time
import json
import shutil
import zipfile
import tempfile
import subprocess
import requests
import socket
import ctypes
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime

# Для обработки Ctrl+C
if sys.platform != "win32":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

# Отключаем предупреждения SSL
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, pyqtSlot, QObject, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QFileDialog,
    QLabel, QPushButton, QTextEdit, QVBoxLayout,
    QHBoxLayout, QWidget, QLineEdit, QCheckBox,
    QScrollArea, QMessageBox, QProgressBar, QComboBox,
    QSpinBox, QGroupBox, QGridLayout
)
from PyQt6.QtGui import QFont, QPalette, QColor

APP_VERSION = "4.1"

# ================================================================
#                     SIMPLE PROGRESS BAR (ONE DIGIT IN CENTER)
# ================================================================
class SimpleProgressBar(QProgressBar):
    """Прогресс-бар с одной цифрой процентов по центру"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_percent = -1
    
    def setValue(self, value):
        """Установить значение с целыми процентами"""
        value = max(0, min(100, int(value)))
        
        # Обновляем только если процент изменился
        if value != self._last_percent:
            self._last_percent = value
            
            # Устанавливаем значение
            super().setValue(value)
            
            # Обновляем текст (просто цифра по центру)
            self.setFormat(f"{value}%")

# ================================================================
#                     SIMPLE DETAIL WIDGET
# ================================================================
class SimpleDetailWidget(QLabel):
    """Простая метка с деталями загрузки"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 11px;
                padding: 2px;
                text-align: center;
            }
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setVisible(False)
    
    def update_progress(self, dlc_id, percent, downloaded, total):
        """Обновить детали загрузки"""
        if total > 0:
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            
            # Форматируем: Downloading EP01: 45% (150.2MB/333.5MB)
            text = f"Downloading {dlc_id}: {int(percent)}% ({mb_downloaded:.1f}MB/{mb_total:.1f}MB)"
            self.setText(text)
            self.setVisible(True)

# ================================================================
#                     SOCKET-BASED SINGLE INSTANCE
# ================================================================
class SingleInstanceLock:
    """Socket-based cross-platform single instance lock"""
    
    def __init__(self, port=12345):
        self.port = port
        self.socket = None
        self.is_locked = False
    
    def acquire(self):
        """Try to acquire lock on localhost port"""
        for port in range(self.port, self.port + 10):
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socket.bind(('127.0.0.1', port))
                self.socket.listen(1)
                self.port = port
                self.is_locked = True
                return True
            except socket.error:
                self.socket.close()
                continue
        return False
    
    def release(self):
        """Release the lock"""
        if self.socket:
            self.socket.close()
            self.is_locked = False
    
    @staticmethod
    def is_already_running(port=12345):
        """Check if another instance is already running"""
        for test_port in range(port, port + 10):
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(0.5)
                test_socket.connect(('127.0.0.1', test_port))
                test_socket.close()
                return True
            except:
                continue
        return False

# ================================================================
#                     ADMIN ELEVATION (FIXED)
# ================================================================
class AdminElevator:
    """Handles Windows admin privileges - FIXED VERSION"""
    
    @staticmethod
    def is_admin() -> bool:
        """Check if running with admin rights"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    @staticmethod
    def requires_admin(path: str) -> bool:
        """Check if path requires admin to write"""
        if not path:
            return False
            
        path_lower = path.lower()
        
        admin_paths = [
            r"c:\program files",
            r"c:\program files (x86)",
            r"c:\windows",
            r"c:\programdata"
        ]
        
        for admin_path in admin_paths:
            if path_lower.startswith(admin_path):
                return True
        
        try:
            test_file = Path(path) / ".linua_write_test"
            test_file.touch()
            test_file.unlink()
            return False
        except:
            return True
    
    @staticmethod
    def elevate() -> bool:
        """Restart program with admin rights - FIXED"""
        try:
            if getattr(sys, 'frozen', False):
                script = sys.executable
                params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
            else:
                script = sys.executable
                params = f'"{sys.argv[0]}"'
                if len(sys.argv) > 1:
                    params += ' ' + ' '.join(sys.argv[1:])
            
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                script,
                params,
                None,
                1
            )
            
            if ret > 32:
                sys.exit(0)
            return False
            
        except Exception as e:
            print(f"Admin elevation failed: {e}")
            return False

# ================================================================
#                   NETWORK DIAGNOSTICS (UPDATED)
# ================================================================
class NetworkDiagnostics:
    """Test network and find solutions for blocked connections"""
    
    def __init__(self, logger=None):
        self.logger = logger
        self.can_reach_github = False
        self.proxy_needed = False
        self.working_proxies = []
        self.recommended_solution = "unknown"
    
    def log(self, msg):
        if self.logger:
            self.logger.log(msg)
    
    def test_connection(self, url: str, timeout: int = 5) -> bool:
        """Test if URL is reachable"""
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            return response.status_code < 400
        except:
            return False
    
    def test_proxy(self, proxy_dict: dict) -> tuple:
        """Test if proxy works. Returns (working, speed_ms)"""
        try:
            start = time.time()
            response = requests.get(
                "https://github.com",
                proxies=proxy_dict,
                timeout=10,
                verify=False
            )
            elapsed = (time.time() - start) * 1000
            return response.status_code < 400, elapsed
        except:
            return False, 0
    
    def diagnose(self):
        """Run full diagnostics with real proxies"""
        self.log("[DIAGNOSTIC] Testing GitHub connection...")
        
        self.can_reach_github = self.test_connection("https://github.com")
        raw_ok = self.test_connection("https://raw.githubusercontent.com")
        
        if self.can_reach_github and raw_ok:
            self.log("[DIAGNOSTIC] Direct connection working")
            self.recommended_solution = "direct"
            self.proxy_needed = False
            return
        
        self.log("[DIAGNOSTIC] Connection blocked, testing proxies...")
        self.proxy_needed = True
        
        test_proxies = [
            {"http": "socks5://127.0.0.1:1080", "https": "socks5://127.0.0.1:1080"},
            {"http": "http://127.0.0.1:8080", "https": "http://127.0.0.1:8080"},
            {"http": "socks5://127.0.0.1:7890", "https": "socks5://127.0.0.1:7890"},
            {"http": "socks5://127.0.0.1:10808", "https": "socks5://127.0.0.1:10808"},
            {"http": "http://127.0.0.1:8888", "https": "http://127.0.0.1:8888"},
        ]
        
        for proxy in test_proxies:
            is_working, speed = self.test_proxy(proxy)
            if is_working:
                self.working_proxies.append(proxy)
                self.log(f"[DIAGNOSTIC] Found working proxy ({speed:.0f}ms)")
        
        if self.working_proxies:
            self.recommended_solution = "proxy"
        else:
            self.recommended_solution = "vpn_needed"
            self.log("[DIAGNOSTIC] No working proxies. VPN recommended.")

# ================================================================
#                   SMART DOWNLOADER WITH RESUME
# ================================================================
class SmartDownloader:
    """Download with automatic fallback: direct → proxy → mirror + resume support"""
    
    def __init__(self, logger, diagnostics=None):
        self.logger = logger
        self.diagnostics = diagnostics
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Linua-Updater/4.1'})
        self._cancelled = False
        self._progress_callback = None
    
    def set_progress_callback(self, callback):
        """Установить callback для прогресса"""
        self._progress_callback = callback
    
    def set_proxy(self, proxy_dict):
        """Set proxy for session"""
        if proxy_dict:
            self.session.proxies = proxy_dict
            self.logger.log("[PROXY] Using proxy")
        else:
            self.session.proxies = {}
    
    def cancel(self):
        self._cancelled = True
    
    def download(self, url, out_path, dlc_name=None, resume=False):
        """
        Download with resume support
        Returns: (success: bool, message: str)
        """
        display = dlc_name or url
        self.logger.log(f"Downloading: {display}")
        
        temp_path = out_path + ".part"
        downloaded = 0
        
        if resume and os.path.exists(temp_path):
            downloaded = os.path.getsize(temp_path)
            self.logger.log(f"[RESUME] Resuming from {downloaded} bytes")
        
        success, msg = self._try_download(url, out_path, temp_path, downloaded)
        if success:
            return True, "OK"
        
        self.logger.log(f"[DOWNLOAD] Direct failed: {msg}")
        
        if self.diagnostics and self.diagnostics.working_proxies:
            for proxy in self.diagnostics.working_proxies:
                self.logger.log("[DOWNLOAD] Trying with proxy...")
                self.set_proxy(proxy)
                success, msg = self._try_download(url, out_path, temp_path, downloaded)
                if success:
                    return True, "Downloaded via proxy"
                self.logger.log(f"[DOWNLOAD] Proxy failed: {msg}")
        
        mirrors = {
            "github.com": "mirror.ghproxy.com/https://github.com",
            "raw.githubusercontent.com": "raw.fastgit.org"
        }
        
        for domain, mirror in mirrors.items():
            if domain in url:
                mirror_url = url.replace(domain, mirror)
                self.logger.log(f"[DOWNLOAD] Trying mirror: {mirror}")
                self.set_proxy(None)
                success, msg = self._try_download(mirror_url, out_path, temp_path, downloaded)
                if success:
                    return True, "Downloaded via mirror"
        
        return False, "All download attempts failed"
    
    def _try_download(self, url, out_path, temp_path, start_byte=0, retries=2):
        """Internal download with retries and resume"""
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(2)
                    self.logger.log(f"[DOWNLOAD] Retry {attempt}/{retries}")
                
                os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
                
                headers = {}
                if start_byte > 0:
                    headers['Range'] = f'bytes={start_byte}-'
                
                with self.session.get(url, stream=True, timeout=30, verify=False, headers=headers) as r:
                    r.raise_for_status()
                    
                    total_size = int(r.headers.get('content-length', 0)) + start_byte
                    
                    if total_size > 10 * 1024 * 1024 * 1024:
                        return False, "File too large"
                    
                    mode = 'ab' if start_byte > 0 else 'wb'
                    with open(temp_path, mode) as f:
                        downloaded = start_byte
                        for chunk in r.iter_content(chunk_size=256*1024):
                            if self._cancelled:
                                return False, "Cancelled"
                            
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if total_size > 0 and self._progress_callback:
                                    progress = (downloaded / total_size) * 100
                                    self._progress_callback(progress, downloaded, total_size)
                    
                    if os.path.exists(temp_path):
                        shutil.move(temp_path, out_path)
                    
                    if total_size > 0 and self._progress_callback and downloaded >= total_size:
                        self._progress_callback(100, downloaded, total_size)
                    
                    return True, "OK"
            
            except requests.exceptions.Timeout:
                if attempt == retries - 1:
                    return False, "Timeout"
            except requests.exceptions.ConnectionError:
                if attempt == retries - 1:
                    return False, "Connection error"
            except Exception as e:
                if attempt == retries - 1:
                    return False, str(e)
        
        return False, "Max retries exceeded"

# ================================================================
#                     WORKER THREAD WITH SIGNALS
# ================================================================
class InstallWorker(QObject):
    """Worker thread for installation with signals"""
    
    progress_updated = pyqtSignal(str, float, int, int)
    overall_progress_updated = pyqtSignal(float)
    status_updated = pyqtSignal(str, str)
    download_detail = pyqtSignal(str)
    started = pyqtSignal()
    finished = pyqtSignal()
    result_ready = pyqtSignal(str, bool, str)
    
    def __init__(self, dlc_ids, game_path, max_workers=3):
        super().__init__()
        self.dlc_ids = dlc_ids
        self.game_path = game_path
        self.max_workers = max_workers
        self._cancelled = False
        self.parallel_manager = None
        self.logger = Logger()
        self.db = DLCDatabase()
        self.downloader = SmartDownloader(self.logger)
        self.extractor = Extractor(self.logger)
        self.download_progress = {}
        
    def cancel(self):
        """Cancel the installation"""
        self._cancelled = True
        if self.parallel_manager:
            self.parallel_manager.cancel_all()
    
    def run(self):
        """Main worker execution"""
        try:
            self.started.emit()
            
            total_dlc = len(self.dlc_ids)
            installed_dlc = set()
            
            self.overall_progress_updated.emit(0)
            
            self.parallel_manager = ParallelInstallManager(max_workers=self.max_workers)
            
            self.parallel_manager.set_overall_progress_callback(
                lambda progress: self.overall_progress_updated.emit(progress)
            )
            
            for dlc_id in self.dlc_ids:
                if self._cancelled:
                    break
                
                self.status_updated.emit(dlc_id, "Starting installation...")
                
                info = self.db.all().get(dlc_id)
                if not info:
                    self.result_ready.emit(dlc_id, False, "DLC not found in database")
                    continue
                
                try:
                    if "parts" in info and info["parts"]:
                        seven_finder = SevenZipFinder(self.logger)
                        seven_path = seven_finder.find()
                        if not seven_path:
                            self.result_ready.emit(dlc_id, False, "7-zip not found")
                            continue
                        
                        installer = MultiPartInstaller(
                            dlc_id, info, self.game_path,
                            self.downloader, self.extractor, seven_path, self.logger
                        )
                    else:
                        installer = SingleDLCInstaller(
                            dlc_id, info, self.game_path,
                            self.downloader, self.extractor, self.logger
                        )
                    
                    installer.set_progress_callback(
                        lambda progress, downloaded, total, dlc=dlc_id: 
                        self._handle_progress(dlc, progress, downloaded, total)
                    )
                    
                    success, message = installer.run()
                    
                    if success:
                        installed_dlc.add(dlc_id)
                    
                    self.result_ready.emit(dlc_id, success, message)
                    
                except Exception as e:
                    self.result_ready.emit(dlc_id, False, f"Error: {str(e)}")
            
            self.overall_progress_updated.emit(100)
            self.finished.emit()
            
        except Exception as e:
            self.result_ready.emit("SYSTEM", False, f"Worker error: {str(e)}")
            self.finished.emit()
    
    def _handle_progress(self, dlc_id, progress, downloaded, total):
        """Handle progress update from installer"""
        self.progress_updated.emit(dlc_id, progress, downloaded, total)
        
        if total > 0:
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            detail = f"Downloading {dlc_id}: {progress:.1f}% ({mb_downloaded:.1f}MB/{mb_total:.1f}MB)"
            self.download_detail.emit(detail)

# ================================================================
#                     7ZIP FINDER
# ================================================================
class SevenZipFinder:
    POSSIBLE_LOCATIONS = [
        "7z.exe",
        "7za.exe",
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files\7-Zip\7za.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7za.exe",
    ]

    def __init__(self, logger):
        self.logger = logger

    def find(self):
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        local = os.path.join(exe_dir, "7z.exe")
        if os.path.exists(local):
            if self.logger:
                self.logger.log("[7ZIP] Using local 7z.exe")
            return local

        for p in self.POSSIBLE_LOCATIONS:
            if os.path.exists(p):
                if self.logger:
                    self.logger.log(f"[7ZIP] Found at: {p}")
                return p

        try:
            if sys.platform == "win32":
                result = subprocess.run(["where", "7z"], capture_output=True, text=True, shell=True)
            else:
                result = subprocess.run(["which", "7z"], capture_output=True, text=True)
                
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                if self.logger:
                    self.logger.log(f"[7ZIP] Found via PATH: {path}")
                return path
        except:
            pass

        if self.logger:
            self.logger.log("[7ZIP] Not found")
        return None

# ================================================================
#                     EXTRACTOR
# ================================================================
class Extractor:
    def __init__(self, logger):
        self.logger = logger

    def log(self, text):
        if self.logger:
            self.logger.log(text)

    def extract_zip(self, file, out_dir):
        """Extract ZIP archive"""
        try:
            os.makedirs(out_dir, exist_ok=True)
            
            with zipfile.ZipFile(file, "r") as z:
                bad_file = z.testzip()
                if bad_file:
                    return False, f"Corrupted: {bad_file}"
                    
                total = len(z.infolist())
                for member in z.infolist():
                    z.extract(member, out_dir)
                    
            self.log(f"Extracted {total} files")
            return True, "OK"
        except zipfile.BadZipFile:
            return False, "Invalid ZIP"
        except Exception as e:
            return False, str(e)

    def extract_7z(self, seven, archive_path, out_dir):
        """Extract 7z archive"""
        try:
            if not os.path.exists(seven):
                return False, "7z.exe not found"
                
            if not os.path.exists(archive_path):
                return False, "Archive not found"
                
            os.makedirs(out_dir, exist_ok=True)
            
            cmd = [seven, "x", archive_path, f"-o{out_dir}", "-y"]
            
            self.log(f"Running 7z extraction...")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
            
            return True, "OK"

        except subprocess.CalledProcessError as e:
            return False, f"7z error: {e.stderr}"
        except subprocess.TimeoutExpired:
            return False, "7z timeout"
        except Exception as e:
            return False, str(e)

# ================================================================
#                     PARALLEL INSTALL MANAGER
# ================================================================
class ParallelInstallManager:
    """Управляет параллельной установкой нескольких DLC"""
    
    def __init__(self, max_workers=5):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._cancelled = False
        self._download_progress = {}
        self._overall_progress_callback = None
    
    def set_overall_progress_callback(self, callback):
        """Установить callback для общего прогресса"""
        self._overall_progress_callback = callback
    
    def update_download_progress(self, dlc_id, progress, downloaded, total):
        """Обновить прогресс загрузки для конкретного DLC"""
        self._download_progress[dlc_id] = {
            'progress': progress,
            'downloaded': downloaded,
            'total': total
        }
        
        if self._overall_progress_callback:
            total_progress = self._calculate_overall_progress()
            self._overall_progress_callback(total_progress)
    
    def _calculate_overall_progress(self):
        """Рассчитать общий прогресс всех загрузок"""
        if not self._download_progress:
            return 0
        
        total_progress = 0
        count = len(self._download_progress)
        
        for dlc_data in self._download_progress.values():
            total_progress += dlc_data['progress']
        
        return total_progress / count if count > 0 else 0
    
    def cancel_all(self):
        """Отмена всех задач"""
        self._cancelled = True
        self.executor.shutdown(wait=False)

# ================================================================
#                     DLC INSTALLERS (UPDATED)
# ================================================================
class SingleDLCInstaller:
    """Install single-file DLC (ZIP) with progress callbacks"""

    def __init__(self, dlc_id, info, game_path, downloader, extractor, logger):
        self.dlc = dlc_id
        self.info = info
        self.game = game_path
        self.dl = downloader
        self.ex = extractor
        self.logger = logger
        self._progress_callback = None

    def set_progress_callback(self, callback):
        """Set progress callback"""
        self._progress_callback = callback

    def log(self, t):
        if self.logger:
            self.logger.log(f"[{self.dlc}] {t}")

    def run(self):
        temp = None
        try:
            url = self.info.get("url")
            if not url:
                return False, "URL missing"

            temp = os.path.join(tempfile.gettempdir(), f"{self.dlc}_{int(time.time())}.zip")

            self.log("Downloading...")
            dlc_name = f"{self.dlc} - {self.info.get('name', 'Unknown')}"
            
            if self._progress_callback:
                self.dl.set_progress_callback(self._progress_callback)
            
            ok, reason = self.dl.download(url, temp, dlc_name, resume=True)
            if not ok:
                return False, reason

            if os.path.getsize(temp) == 0:
                return False, "Empty file"

            self.log("Extracting...")
            ok, reason = self.ex.extract_zip(temp, self.game)
            if not ok:
                return False, reason

            self.log("Installed")
            return True, "OK"

        except Exception as e:
            return False, str(e)
        finally:
            if temp and os.path.exists(temp):
                try:
                    os.remove(temp)
                except:
                    pass

class MultiPartInstaller:
    """Install multi-part DLC (7z) with progress callbacks"""

    def __init__(self, dlc_id, info, game_path, downloader, extractor, seven_path, logger):
        self.dlc = dlc_id
        self.info = info
        self.game = game_path
        self.dl = downloader
        self.ex = extractor
        self.seven = seven_path
        self.logger = logger
        self._progress_callback = None

    def set_progress_callback(self, callback):
        """Set progress callback"""
        self._progress_callback = callback

    def log(self, t):
        if self.logger:
            self.logger.log(f"[{self.dlc}] {t}")

    def run(self):
        downloaded_files = []
        try:
            if not self.seven or not os.path.exists(self.seven):
                return False, "7z.exe not found"

            parts = self.info.get("parts", [])
            if not parts:
                return False, "No parts"

            total_parts = len(parts)
            for i, url in enumerate(parts):
                name = f"{self.dlc}.7z.{str(i+1).zfill(3)}"
                out = os.path.join(tempfile.gettempdir(), name)

                self.log(f"Downloading part {i+1}/{len(parts)}...")
                dlc_name = f"{self.dlc} Part {i+1}"
                
                part_weight = 100.0 / total_parts
                current_base = i * part_weight
                
                if self._progress_callback:
                    def part_progress(progress, downloaded, total, base=current_base, weight=part_weight):
                        total_progress = base + (progress * weight / 100)
                        self._progress_callback(total_progress, downloaded, total)
                    
                    self.dl.set_progress_callback(part_progress)
                
                ok, reason = self.dl.download(url, out, dlc_name, resume=True)
                if not ok:
                    for f in downloaded_files:
                        try:
                            os.remove(f)
                        except:
                            pass
                    return False, reason

                downloaded_files.append(out)

            part1 = downloaded_files[0]
            self.log("Extracting multipart archive...")

            ok, reason = self.ex.extract_7z(self.seven, part1, self.game)
            if not ok:
                return False, reason

            self.log("Installed")
            return True, "OK"

        except Exception as e:
            return False, str(e)
        finally:
            for f in downloaded_files:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except:
                    pass

# ================================================================
#                     SETTINGS DIALOG
# ================================================================
class SettingsDialog(QDialog):
    """Settings dialog with thread control"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(400, 300)
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
        
        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
    
    def apply_dark_theme(self):
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; }
            QLabel { color: white; }
            QGroupBox {
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QSpinBox, QCheckBox {
                color: white;
                background-color: #2a2a2a;
            }
        """)
    
    def get_settings(self):
        """Get current settings"""
        return {
            'max_threads': self.thread_spin.value(),
            'use_proxy': self.proxy_check.isChecked(),
            'resume_downloads': self.resume_check.isChecked(),
            'cleanup_temp': self.cleanup_check.isChecked()
        }

# ================================================================
#                     LOGGER
# ================================================================
class Logger:
    def __init__(self, widget=None):
        self.widget = widget

    def log(self, text):
        t = time.strftime("[%H:%M:%S]")
        line = f"{t} {text}"

        if self.widget:
            if "ERROR" in text.upper():
                line = f'<font color="red">{line}</font>'
            elif "WARNING" in text.upper():
                line = f'<font color="yellow">{line}</font>'
            elif "SUCCESS" in text.upper():
                line = f'<font color="lightgreen">{line}</font>'
            elif "[DIAGNOSTIC]" in text or "[NETWORK]" in text:
                line = f'<font color="cyan">{line}</font>'
            else:
                line = f'<font color="white">{line}</font>'
            
            self.widget.append(line)
            self.widget.ensureCursorVisible()

# ================================================================
#                     CONFIG
# ================================================================
class ConfigManager:
    def __init__(self):
        self.path = Path.home() / "AppData" / "Local" / "LinuaUpdater" / "config.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self.data = {
                "game_path": "",
                "settings": {
                    "max_threads": 3,
                    "use_proxy": True,
                    "resume_downloads": True,
                    "cleanup_temp": True
                }
            }
            self.save()
        else:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                    if "settings" not in self.data:
                        self.data["settings"] = {
                            "max_threads": 3,
                            "use_proxy": True,
                            "resume_downloads": True,
                            "cleanup_temp": True
                        }
            except:
                self.data = {
                    "game_path": "",
                    "settings": {
                        "max_threads": 3,
                        "use_proxy": True,
                        "resume_downloads": True,
                        "cleanup_temp": True
                    }
                }
                self.save()

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()
    
    def get_settings(self):
        return self.data.get("settings", {})

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Config save failed: {e}")

# ================================================================
#                     DLC DATABASE (FULL WITH WARNINGS)
# ================================================================
class DLCDatabase:
    def __init__(self):
        self.dlc = {
             "EP01": {"name": "Get to Work", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP01/Sims4_DLC_EP01_Get_to_Work.zip"},
            "EP02": {"name": "Get Together", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP02/Sims4_DLC_EP02_Get_Together.zip"},
            "EP03": {"name": "City Living", "requires_manual": True, "manual_reason": "Large file size (5.2GB) requires manual download", "url": ""},
            "EP06": {"name": "Get Famous", "requires_manual": True, "manual_reason": "Copyright restrictions require manual download", "url": ""},
            "EP04": {"name": "Cats and Dogs", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP04/Sims4_DLC_EP04_Cats_and_Dogs.zip"},
            "EP05": {"name": "Seasons", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP05/Sims4_DLC_EP05_Seasons.zip"},
            "EP07": {"name": "Island Living", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP07/Sims4_DLC_EP07_Island_Living.zip"},
            "EP08": {"name": "Discover University", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP08/Sims4_DLC_EP08_Discover_University.zip"},
            "EP09": {"name": "Eco Lifestyle", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP09/Sims4_DLC_EP09_Eco_Lifestyle.zip"},
            "EP10": {"name": "Snowy Escape", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP10/Sims4_DLC_EP10_Snowy_Escape.zip"},
            "EP11": {"name": "Cottage Living", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP11/Sims4_DLC_EP11_Cottage_Living.zip"},
            "EP12": {"name": "High School Years", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP12/Sims4_DLC_EP12_High_School_Years.zip"},
            "EP13": {"name": "Growing Together", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP13/Sims4_DLC_EP13_Growing_Together.zip"},
            "EP14": {"name": "Horse Ranch", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP14/Sims4_DLC_EP14_Horse_Ranch.zip"},
            "EP15": {"name": "For Rent", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP15/Sims4_DLC_EP15_For_Rent.zip"},
            "EP16": {"name": "Lovestruck", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP16/Sims4_DLC_EP16_Lovestruck.zip"},
            "EP17": {"name": "Life and Death", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP17/Sims4_DLC_EP17_Life_and_Death.zip"},
            "EP18": {"name": "Businesses and Hobbies", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP18/Sims4_DLC_EP18_Businesses_and_Hobbies.zip"},
            "EP19": {"name": "Enchanted by Nature", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP19/Sims4_DLC_EP19_Enchanted_by_Nature_Expansion_Pack.zip"},
            "EP20": {"name": "Adventure Awaits", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP20/Sims4_DLC_EP20_Adventure_Awaits_Expansion_Pack.zip"},
            "GP01": {"name": "Outdoor Retreat", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP01/Sims4_DLC_GP01_Outdoor_Retreat.zip"},
            "GP02": {"name": "Spa Day", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP02/Sims4_DLC_GP02_Spa_Day.zip"},
            "GP03": {"name": "Dine Out", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP03/Sims4_DLC_GP03_Dine_Out.zip"},
            "GP04": {"name": "Vampires", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP04/Sims4_DLC_GP04_Vampires.zip"},
            "GP05": {"name": "Parenthood", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP05/Sims4_DLC_GP05_Parenthood.zip"},
            "GP06": {"name": "Jungle Adventure", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP06/Sims4_DLC_GP06_Jungle_Adventure.zip"},
            "GP07": {"name": "StrangerVille", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP07/Sims4_DLC_GP07_StrangerVille.zip"},
            "GP08": {"name": "Realm of Magic", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP08/Sims4_DLC_GP08_Realm_of_Magic.zip"},
            "GP09": {"name": "Star Wars: Journey to Batuu", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP09/Sims4_DLC_GP09_Star_Wars_Journey_to_Batuu.zip"},
            "GP10": {"name": "Dream Home Decorator", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP10/Sims4_DLC_GP10_Dream_Home_Decorator.zip"},
            "GP11": {"name": "My Wedding Stories", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP11/Sims4_DLC_GP11_My_Wedding_Stories.zip"},
            "GP12": {"name": "Werewolves", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/GP12/Sims4_DLC_GP12_Werewolves.zip"},
            "SP01": {"name": "Luxury Party Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP01/Sims4_DLC_SP01_Luxury_Party_Stuff.zip"},
            "SP02": {"name": "Perfect Patio Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP02/Sims4_DLC_SP02_Perfect_Patio_Stuff.zip"},
            "SP03": {"name": "Cool Kitchen Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP03/Sims4_DLC_SP03_Cool_Kitchen_Stuff.zip"},
            "SP04": {"name": "Spooky Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP04/Sims4_DLC_SP04_Spooky_Stuff.zip"},
            "SP05": {"name": "Movie Hangout Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP05/Sims4_DLC_SP05_Movie_Hangout_Stuff.zip"},
            "SP06": {"name": "Romantic Garden Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP06/Sims4_DLC_SP06_Romantic_Garden_Stuff.zip"},
            "SP07": {"name": "Kids Room Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP07/Sims4_DLC_SP07_Kids_Room_Stuff.zip"},
            "SP08": {"name": "Backyard Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP08/Sims4_DLC_SP08_Backyard_Stuff.zip"},
            "SP09": {"name": "Vintage Glamour Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP09/Sims4_DLC_SP09_Vintage_Glamour_Stuff.zip"},
            "SP10": {"name": "Bowling Night Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP10/Sims4_DLC_SP10_Bowling_Night_Stuff.zip"},
            "SP11": {"name": "Fitness Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP11/Sims4_DLC_SP11_Fitness_Stuff.zip"},
            "SP12": {"name": "Toddler Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP12/Sims4_DLC_SP12_Toddler_Stuff.zip"},
            "SP13": {"name": "Laundry Day Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP13/Sims4_DLC_SP13_Laundry_Day_Stuff.zip"},
            "SP14": {"name": "My First Pet Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP14/Sims4_DLC_SP14_My_First_Pet_Stuff.zip"},
            "SP15": {"name": "Moschino Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP15/Sims4_DLC_SP15_Moschino_Stuff.zip"},
            "SP16": {"name": "Tiny Living Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP16/Sims4_DLC_SP16_Tiny_Living_Stuff_Pack.zip"},
            "SP17": {"name": "Nifty Knitting", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP17/Sims4_DLC_SP17_Nifty_Knitting.zip"},
            "SP18": {"name": "Paranormal Stuff", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP18/Sims4_DLC_SP18_Paranormal_Stuff_Pack.zip"},
            "SP20": {"name": "Throwback Fit Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP20/Sims4_DLC_SP20_Throwback_Fit_Kit.zip"},
            "SP21": {"name": "Country Kitchen Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP21/Sims4_DLC_SP21_Country_Kitchen_Kit.zip"},
            "SP22": {"name": "Bust the Dust Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP22/Sims4_DLC_SP22_Bust_the_Dust_Kit.zip"},
            "SP23": {"name": "Courtyard Oasis Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP23/Sims4_DLC_SP23_Courtyard_Oasis_Kit.zip"},
            "SP24": {"name": "Fashion Street Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP24/Sims4_DLC_SP24_Fashion_Street_Kit.zip"},
            "SP25": {"name": "Industrial Loft Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP25/Sims4_DLC_SP25_Industrial_Loft_Kit.zip"},
            "SP26": {"name": "Incheon Arrivals Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP26/Sims4_DLC_SP26_Incheon_Arrivals_Kit.zip"},
            "SP28": {"name": "Modern Menswear Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP28/Sims4_DLC_SP28_Modern_Menswear_Kit.zip"},
            "SP29": {"name": "Blooming Rooms Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP29/Sims4_DLC_SP29_Blooming_Rooms_Kit.zip"},
            "SP30": {"name": "Carnaval Streetwear Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP30/Sims4_DLC_SP30_Carnaval_Streetwear_Kit.zip"},
            "SP31": {"name": "Decor to the Max Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP31/Sims4_DLC_SP31_Decor_to_the_Max_Kit.zip"},
            "SP32": {"name": "Moonlight Chic Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP32/Sims4_DLC_SP32_Moonlight_Chic_Kit.zip"},
            "SP33": {"name": "Little Campers Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP33/Sims4_DLC_SP33_Little_Campers_Kit.zip"},
            "SP34": {"name": "First Fits Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP34/Sims4_DLC_SP34_First_Fits_Kit.zip"},
            "SP35": {"name": "Desert Luxe Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP35/Sims4_DLC_SP35_Desert_Luxe_Kit.zip"},
            "SP36": {"name": "Pastel Pop Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP36/Sims4_DLC_SP36_Pastel_Pop_Kit.zip"},
            "SP37": {"name": "Everyday Clutter Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP37/Sims4_DLC_SP37_Everyday_Clutter_Kit.zip"},
            "SP38": {"name": "Simtimates Collection Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP38/Sims4_DLC_SP38_Simtimates_Collection_Kit.zip"},
            "SP39": {"name": "Bathroom Clutter Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP39/Sims4_DLC_SP39_Bathroom_Clutter_Kit.zip"},
            "SP40": {"name": "Greenhouse Haven Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP40/Sims4_DLC_SP40_Greenhouse_Haven_Kit.zip"},
            "SP41": {"name": "Basement Treasures Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP41/Sims4_DLC_SP41_Basement_Treasures_Kit.zip"},
            "SP42": {"name": "Grunge Revival Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP42/Sims4_DLC_SP42_Grunge_Revival_Kit.zip"},
            "SP43": {"name": "Book Nook Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP43/Sims4_DLC_SP43_Book_Nook_Kit.zip"},
            "SP44": {"name": "Poolside Splash Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP44/Sims4_DLC_SP44_Poolside_Splash_Kit.zip"},
            "SP45": {"name": "Modern Luxe Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP45/Sims4_DLC_SP45_Modern_Luxe_Kit.zip"},
            "SP46": {"name": "Home Chef Hustle Stuff Pack", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP46/Sims4_DLC_SP46_Home_Chef_Hustle_Stuff_Pack.zip"},
            "SP47": {"name": "Castle Estate Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP47/Sims4_DLC_SP47_Castle_Estate_Kit.zip"},
            "SP48": {"name": "Goth Galore Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP48/Sims4_DLC_SP48_Goth_Galore_Kit.zip"},
            "SP49": {"name": "Crystal Creations Stuff Pack", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP49/Sims4_DLC_SP49_Crystal_Creations_Stuff_Pack.zip"},
            "SP50": {"name": "Urban Homage Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP50/Sims4_DLC_SP50_Urban_Homage_Kit.zip"},
            "SP51": {"name": "Party Essentials Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP51/Sims4_DLC_SP51_Party_Essentials_Kit.zip"},
            "SP52": {"name": "Riviera Retreat Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP52/Sims4_DLC_SP52_Riviera_Retreat_Kit.zip"},
            "SP53": {"name": "Cozy Bistro Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP53/Sims4_DLC_SP53_Cozy_Bistro_Kit.zip"},
            "SP54": {"name": "Artist Studio Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP54/Sims4_DLC_SP54_Artist_Studio_Kit.zip"},
            "SP55": {"name": "Storybook Nursery Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP55/Sims4_DLC_SP55_Storybook_Nursery_Kit.zip"},
            "SP56": {"name": "Sweet Slumber Party Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP56/Sims4_DLC_SP56_Sweet_Slumber_Party_Kit.zip"},
            "SP57": {"name": "Cozy Kitsch Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP57/Sims4_DLC_SP57_Cozy_Kitsch_Kit.zip"},
            "SP58": {"name": "Comfy Gamer Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP58/Sims4_DLC_SP58_Comfy_Gamer_Kit.zip"},
            "SP59": {"name": "Secret Sanctuary Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP59/Sims4_DLC_SP59_Secret_Sanctuary_Kit.zip"},
            "SP60": {"name": "Casanova Cave Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP60/Sims4_DLC_SP60_Casanova_Cave_Kit.zip"},
            "SP61": {"name": "Refined Living Room Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP61/Sims4_DLC_SP61_Refined_Living_Room_Kit.zip"},
            "SP62": {"name": "Business Chic Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP62/Sims4_DLC_SP62_Business_Chic_Kit.zip"},
            "SP63": {"name": "Sleek Bathroom Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP63/Sims4_DLC_SP63_Sleek_Bathroom_Kit.zip"},
            "SP64": {"name": "Sweet Allure Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP64/Sims4_DLC_SP64_Sweet_Allure_Kit.zip"},
            "SP65": {"name": "Restoration Workshop Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP65/Sims4_DLC_SP65_Restoration_Workshop_Kit.zip"},
            "SP66": {"name": "Golden Years Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP66/Sims4_DLC_SP66_Golden_Years_Kit.zip"},
            "SP67": {"name": "Kitchen Clutter Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP67/Sims4_DLC_SP67_Kitchen_Clutter_Kit.zip"},
            "SP69": {"name": "Autumn Apparel Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP69/Sims4_DLC_SP69_Autumn_Apparel_Kit.zip"},
            "SP71": {"name": "Grange Mudroom Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP71/Sims4_DLC_SP71_Grange_Mudroom_Kit.zip"},
            "SP72": {"name": "Essential Glam Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP72/Sims4_DLC_SP72_Essential_Glam_Kit.zip"},
            "SP73": {"name": "Modern Retreat Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP73/Sims4_DLC_SP73_Modern_Retreat_Kit.zip"},
            "SP74": {"name": "Garden to Table Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP74/Sims4_DLC_SP74_Garden_to_Table_Kit.zip"},
            "SP70": {"name": "Spongebob Kid's Room Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP70/SP70.zip"},
            "SP68": {"name": "Spongebob's House Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP68/SP68.zip"},
            "SP81": {"name": "Prairie Dreams Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP81/SP81.zip"},
            "FP01": {"name": "Holiday Celebration Pack", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/FP01/Sims4_DLC_FP01_Holiday_Celebration_Pack.zip"},
        }

    def all(self):
        return self.dlc

# ================================================================
#                     DLC SELECTOR WITH WARNINGS
# ================================================================
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
        
        self.info = QLabel(
            "WARNING: EP03 and EP06 require MANUAL download!\n"
            "Select other DLC to install automatically.\n"
            "Already installed DLC are hidden."
        )
        self.info.setWordWrap(True)
        self.info.setStyleSheet("""
            QLabel {
                color: #ffaa00;
                padding: 10px;
                background: #2a2a2a;
                border-radius: 4px;
                border: 1px solid #ffaa00;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.info)
        
        self.check_all = QCheckBox("Select all available")
        self.check_all.setStyleSheet("color: white; font-weight: bold; padding: 10px;")
        self.check_all.checkStateChanged.connect(self.toggle_all)
        layout.addWidget(self.check_all)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #2a2a2a; border: none;")
        layout.addWidget(scroll)
        
        self.container = QWidget()
        self.container.setStyleSheet("background-color: #2a2a2a;")
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
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; }
            QLabel { color: white; padding: 5px; }
            QLineEdit {
                background-color: #0a0a0a;
                color: white;
                border: 1px solid #444;
                padding: 8px;
                border-radius: 4px;
            }
            QCheckBox {
                color: white;
                background-color: #2a2a2a;
                padding: 8px;
                border-radius: 3px;
                margin: 2px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #555;
                background-color: #333;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #0078d7;
                background-color: #0078d7;
            }
            QCheckBox:hover {
                background-color: #333;
            }
            QPushButton {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QPushButton:pressed {
                background-color: #222;
            }
        """)
    
    def toggle_all(self, state):
        """Toggle all visible checkboxes"""
        checked = (state == Qt.CheckState.Checked)
        for dlc_id, cb in self.cbs.items():
            if cb.isVisible() and cb.isEnabled():
                cb.setChecked(checked)
        self.update_install_button()
    
    def populate(self, db, installed):
        """Populate with available DLC"""
        for i in reversed(range(self.layout_c.count())):
            item = self.layout_c.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        self.cbs.clear()
        
        available = [(dlc_id, info) for dlc_id, info in db.items() 
                     if dlc_id.upper() not in installed and dlc_id.upper() not in ["EP03", "EP06"]]
        
        ep03_info = db.get("EP03")
        ep06_info = db.get("EP06")
        
        if not available and not ep03_info and not ep06_info:
            no_dlc = QLabel("ALL DLC ALREADY INSTALLED!")
            no_dlc.setStyleSheet("""
                QLabel {
                    color: #00ff00;
                    padding: 30px;
                    font-size: 16px;
                    font-weight: bold;
                    text-align: center;
                    background: #2a2a2a;
                    border-radius: 10px;
                    margin: 20px;
                    border: 2px solid #00ff00;
                }
            """)
            no_dlc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout_c.addWidget(no_dlc)
            
            info_label = QLabel(
                "All available DLC are already installed.\n\n"
                "For new DLC, check for application updates."
            )
            info_label.setStyleSheet("color: #aaaaaa; padding: 15px; text-align: center;")
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_label.setWordWrap(True)
            self.layout_c.addWidget(info_label)
            
            self.check_all.setVisible(False)
            self.install_btn.setEnabled(False)
            self.install_btn.setText("All installed")
            return
        
        self.check_all.setVisible(True)
        self.install_btn.setEnabled(True)
        
        if ep03_info or ep06_info:
            manual_label = QLabel("DLC REQUIRING MANUAL DOWNLOAD:")
            manual_label.setStyleSheet("""
                QLabel {
                    color: #ff9900;
                    font-weight: bold;
                    font-size: 13px;
                    margin-top: 10px;
                    padding: 8px;
                    background: #332200;
                    border-radius: 4px;
                }
            """)
            self.layout_c.addWidget(manual_label)
            
            if ep03_info:
                ep03_cb = QCheckBox(f"[EP03] {ep03_info['name']} - MANUAL DOWNLOAD REQUIRED")
                ep03_cb.setStyleSheet("color: #ff9900; font-weight: bold; background: #2a2a2a; padding: 10px;")
                ep03_cb.setToolTip(f"Reason: {ep03_info.get('manual_reason', 'Manual download required')}")
                ep03_cb.setEnabled(False)
                ep03_cb.setChecked(False)
                self.layout_c.addWidget(ep03_cb)
                self.cbs["EP03"] = ep03_cb
            
            if ep06_info:
                ep06_cb = QCheckBox(f"[EP06] {ep06_info['name']} - MANUAL DOWNLOAD REQUIRED")
                ep06_cb.setStyleSheet("color: #ff9900; font-weight: bold; background: #2a2a2a; padding: 10px;")
                ep06_cb.setToolTip(f"Reason: {ep06_info.get('manual_reason', 'Manual download required')}")
                ep06_cb.setEnabled(False)
                ep06_cb.setChecked(False)
                self.layout_c.addWidget(ep06_cb)
                self.cbs["EP06"] = ep06_cb
        
        if available:
            separator = QLabel("────────────────────")
            separator.setStyleSheet("color: #555; margin: 10px 0;")
            separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout_c.addWidget(separator)
            
            auto_label = QLabel("DLC AVAILABLE FOR AUTO-INSTALL:")
            auto_label.setStyleSheet("color: #00cc00; font-weight: bold; font-size: 13px; margin-top: 10px;")
            self.layout_c.addWidget(auto_label)
        
        categories = {
            "Expansion Packs": [],
            "Game Packs": [],
            "Stuff Packs": []
        }
        
        for dlc_id, info in available:
            if dlc_id.startswith("EP"):
                categories["Expansion Packs"].append((dlc_id, info))
            elif dlc_id.startswith("GP"):
                categories["Game Packs"].append((dlc_id, info))
            else:
                categories["Stuff Packs"].append((dlc_id, info))
        
        for cat, items in categories.items():
            if not items:
                continue
            
            header = QLabel(f"{cat} ({len(items)})")
            header.setStyleSheet("font-weight: bold; margin-top: 15px; color: #0078d7; font-size: 13px;")
            self.layout_c.addWidget(header)
            
            for dlc_id, info in sorted(items):
                cb = QCheckBox(f"[{dlc_id}] {info['name']}")
                cb.setStyleSheet("color: white; font-size: 11px;")
                cb.stateChanged.connect(self.update_install_button)
                self.layout_c.addWidget(cb)
                self.cbs[dlc_id] = cb
        
        self.layout_c.addStretch()
        self.update_install_button()
    
    def update_install_button(self):
        """Update install button text with count"""
        selected = len([cb for cb in self.cbs.values() if cb.isChecked() and cb.isEnabled()])
        if selected > 0:
            self.install_btn.setText(f"Install Selected ({selected})")
            self.install_btn.setEnabled(True)
        else:
            self.install_btn.setText("Install Selected (0)")
            self.install_btn.setEnabled(False)
    
    def get(self):
        """Get selected DLC IDs (only auto-installable)"""
        return [dlc for dlc, cb in self.cbs.items() 
                if cb.isChecked() and cb.isEnabled() and dlc not in ["EP03", "EP06"]]

# ================================================================
#                     MAIN UI WITH SIMPLE PROGRESS
# ================================================================
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
        
        self.logger = Logger(self.log_text)
        
        self.diagnostics = None
        self.downloader = SmartDownloader(self.logger)
        self.extractor = Extractor(self.logger)
        
        self.install_thread = None
        self.install_worker = None
        
        self.progress_total = 0
        self.progress_done = 0
        self.successful_count = 0
        self.failed_count = 0
        
        self.settings = self.config.get_settings()
        
        self.dlc_check_timer = QTimer()
        self.dlc_check_timer.timeout.connect(self.update_dlc_status)
        
        saved = self.config.get("game_path", "")
        if saved:
            self.path_input.setText(saved)
            self.logger.log(f"[CONFIG] Loaded path: {saved}")
        
        QTimer.singleShot(300, self.run_diagnostics)
        QTimer.singleShot(500, self.auto_detect)
        
        self.dlc_check_timer.start(3000)
        QTimer.singleShot(1000, self.update_dlc_status)
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        
        title = QLabel(f"Linua Updater v{APP_VERSION}")
        title.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 14px;
                padding: 8px;
                color: #0078d7;
                background: #2a2a2a;
                border-radius: 6px;
                text-align: center;
            }
        """)
        layout.addWidget(title)
        
        path_label = QLabel("The Sims 4 folder:")
        path_label.setStyleSheet("color: white; font-weight: bold;")
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
        self.dlc_status.setStyleSheet("""
            QLabel {
                color: #00ff00;
                background: #2a2a2a;
                padding: 6px;
                border-radius: 4px;
                font-size: 11px;
                text-align: center;
                margin: 2px 0;
            }
        """)
        self.dlc_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.dlc_status)
        
        # === ТОЛЬКО ОДИН ПРОГРЕСС-БАР: Прогресс загрузки ===
        self.download_progress = SimpleProgressBar()
        self.download_progress.setVisible(False)
        self.download_progress.setStyleSheet("""
            QProgressBar {
                background-color: #1a1a1a;
                border: 2px solid #333;
                border-radius: 6px;
                text-align: center;
                color: white;
                height: 30px;
                font-weight: bold;
                font-size: 14px;
                font-family: 'Segoe UI', Arial;
            }
            QProgressBar::chunk {
                background-color: #00aa00;
                border-radius: 4px;
                border: 1px solid #008800;
            }
        """)
        layout.addWidget(self.download_progress)
        
        # === ДЕТАЛИ ЗАГРУЗКИ ===
        self.download_detail = SimpleDetailWidget()
        layout.addWidget(self.download_detail)
        
        self.buttons_row = QHBoxLayout()
        
        self.update_btn = QPushButton("Update")
        self.update_btn.clicked.connect(self.on_update)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.on_cancel)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)
    
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        
        self.network_btn = QPushButton("Network Test")
        self.network_btn.clicked.connect(self.show_network_info)
        
        self.buttons_row.addWidget(self.update_btn)
        self.buttons_row.addWidget(self.cancel_btn)
        self.buttons_row.addWidget(self.settings_btn)
        self.buttons_row.addWidget(self.network_btn)
        
        layout.addLayout(self.buttons_row)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #0a0a0a;
                color: #00ff00;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.log_text, 1)
        
        info = QLabel(
            "EP03 City Living & EP06 Get Famous require MANUAL download!"
        )
        info.setWordWrap(True)
        info.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                padding: 10px;
                border-radius: 6px;
                color: white;
                font-size: 11px;
                border-left: 4px solid #ff9900;
            }
        """)
        layout.addWidget(info)
    
    def apply_dark_theme(self):
        css = """
            QMainWindow, QDialog {
                background-color: #1e1e1e;
                color: white;
            }
            QPushButton {
                background-color: #333;
                border: 1px solid #555;
                padding: 8px;
                font-weight: bold;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #444; }
            QPushButton:pressed { background-color: #222; }
            QPushButton:disabled {
                background-color: #222;
                color: #666;
                border: 1px solid #333;
            }
            QLineEdit {
                background-color: #0a0a0a;
                color: white;
                border: 1px solid #444;
                padding: 6px;
                border-radius: 4px;
            }
        """
        self.setStyleSheet(css)
    
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
        
        available = [k for k in self.db.all().keys() 
                    if k.upper() not in installed and k not in ["EP03", "EP06"]]
        
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
            
        self.logger.log("[STARTUP] Testing network connection...")
        
        tool = NetworkDiagnostics(self.logger)
        tool.diagnose()
        self.diagnostics = tool
        
        self.downloader = SmartDownloader(self.logger, self.diagnostics)
        
        if self.diagnostics.can_reach_github:
            self.logger.log("[NETWORK] Direct connection working")
        else:
            self.logger.log("[NETWORK] Connection blocked")
            if self.diagnostics.working_proxies:
                self.logger.log(f"[NETWORK] Found {len(self.diagnostics.working_proxies)} working proxies")
            else:
                self.logger.log("[NETWORK] No proxies found. VPN recommended for RU/UA.")
    
    def show_network_info(self):
        if not self.diagnostics:
            QMessageBox.information(self, "Network Test", "Running diagnostics, please wait...")
            self.run_diagnostics()
            return
        
        msg = "=== NETWORK DIAGNOSTICS ===\n\n"
        
        if self.diagnostics.can_reach_github:
            msg += "Direct connection to GitHub: OK\n"
            msg += "Downloads will use direct connection.\n"
        else:
            msg += "Direct connection to GitHub: BLOCKED\n\n"
            
            if self.diagnostics.working_proxies:
                msg += f"Working proxies found: {len(self.diagnostics.working_proxies)}\n"
                msg += "Application will use them automatically.\n\n"
                msg += "Tested ports: 1080, 8080, 7890, 10808, 8888\n"
            else:
                msg += "No working proxies found\n\n"
                msg += "RECOMMENDATIONS:\n"
                msg += "1. Install Cloudflare WARP: https://1.1.1.1/\n"
                msg += "2. Use VPN service\n"
                msg += "3. Change DNS to 8.8.8.8 or 1.1.1.1\n"
                msg += "4. Try mobile hotspot\n"
        
        QMessageBox.information(self, "Network Diagnostics", msg)
    
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
            self.logger.log("[SETTINGS] Settings saved")
    
    def browse_folder(self):
        self.logger.log("Opening folder browser...")
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select The Sims 4 Folder",
            self.path_input.text() or "C:\\"
        )
        if folder:
            self.path_input.setText(folder)
            self.config.set("game_path", folder)
            self.logger.log(f"[FOLDER] Selected: {folder}")
    
    def auto_detect(self):
        if self.is_closing:
            return
            
        self.logger.log("[DETECT] Searching for The Sims 4...")
        
        drives = ["C", "D", "E", "F", "G"]
        paths = [
            r"\Program Files (x86)\Steam\steamapps\common\The Sims 4",
            r"\Program Files\Steam\steamapps\common\The Sims 4",
            r"\SteamLibrary\steamapps\common\The Sims 4",
            r"\Program Files\EA Games\The Sims 4",
            r"\Program Files (x86)\EA Games\The Sims 4",
            r"\Program Files (x86)\Origin Games\The Sims 4",
        ]
        
        for drive in drives:
            for path in paths:
                full_path = f"{drive}:{path}"
                if os.path.exists(full_path):
                    exe_check = os.path.join(full_path, "Game", "Bin", "TS4_x64.exe")
                    if os.path.exists(exe_check):
                        self.path_input.setText(full_path)
                        self.config.set("game_path", full_path)
                        self.logger.log(f"[DETECT] Found game at: {full_path}")
                        self.update_dlc_status()
                        return
        
        self.logger.log("[DETECT] Game not found automatically. Please select folder manually.")
    
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
                self.logger.log(f"[DETECT] Error scanning DLC: {e}")
        
        return installed
    
    def on_update(self):
        if self.is_closing:
            return
            
        path = self.path_input.text().strip()
        
        if path and os.path.exists(path):
            installed = self.detect_installed(path)
            available = [k for k in self.db.all().keys() 
                        if k.upper() not in installed and k not in ["EP03", "EP06"]]
            
            if not available:
                self.logger.log("All DLC already installed!")
                QMessageBox.information(
                    self,
                    "All Installed!",
                    "All available DLC are already installed!\n\n"
                    "For new DLC, check for application updates."
                )
                return
        
        if not path:
            self.logger.log("[ERROR] Please select a game folder first")
            QMessageBox.warning(self, "No Path", "Please select your Sims 4 folder first.")
            return
        
        if not os.path.exists(path):
            self.logger.log("[ERROR] Path doesn't exist")
            QMessageBox.critical(self, "Invalid Path", "The selected path doesn't exist.")
            return
        
        if AdminElevator.requires_admin(path):
            if not AdminElevator.is_admin():
                self.logger.log("[ADMIN] Path requires administrator privileges")
                
                reply = QMessageBox.question(
                    self,
                    "Administrator Required",
                    f"The selected path requires administrator privileges:\n\n{path}\n\n"
                    "The application needs to restart with elevated privileges.\n"
                    "Click Yes to restart as administrator.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.logger.log("[ADMIN] Restarting with admin rights...")
                    AdminElevator.elevate()
                else:
                    self.logger.log("[ADMIN] User declined elevation")
                return
            else:
                self.logger.log("[ADMIN] Running with admin privileges")
        
        exe_path = os.path.join(path, "Game", "Bin", "TS4_x64.exe")
        if not os.path.exists(exe_path):
            self.logger.log("[WARNING] TS4_x64.exe not found")
            reply = QMessageBox.question(
                self,
                "Invalid Game Folder?",
                "TS4_x64.exe not found in this folder.\n\n"
                "This may not be a valid Sims 4 installation.\n"
                "Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        else:
            self.logger.log("[VALIDATE] Game executable found")
        
        try:
            total, used, free = shutil.disk_usage(path)
            free_gb = free / (1024**3)
            if free_gb < 15:
                self.logger.log(f"[WARNING] Only {free_gb:.1f} GB free space")
                QMessageBox.warning(
                    self,
                    "Low Disk Space",
                    f"Only {free_gb:.1f} GB free space available.\n"
                    "At least 15 GB recommended for DLC installation."
                )
            else:
                self.logger.log(f"[SPACE] {free_gb:.1f} GB free")
        except:
            pass
        
        installed = self.detect_installed(path)
        
        dlg = DLCSelector(self)
        dlg.populate(self.db.all(), installed)
        
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.logger.log("[CANCELLED] DLC selection cancelled")
            return
        
        selected = dlg.get()
        if not selected:
            self.logger.log("[INFO] No DLC selected")
            QMessageBox.information(self, "No Selection", "No DLC selected for installation.")
            return
        
        self.start_parallel_install(selected, path)
    
    def start_parallel_install(self, selected, path):
        self.logger.log(f"[INSTALL] Starting installation of {len(selected)} DLC...")
        self.logger.log(f"[INSTALL] Using {self.settings.get('max_threads', 3)} parallel threads")
        
        self.progress_total = len(selected)
        self.progress_done = 0
        self.successful_count = 0
        self.failed_count = 0
        
        self.download_progress.setVisible(True)
        self.download_progress.setValue(0)
        
        self.download_detail.setVisible(False)
        
        self.update_btn.setText("Installing...")
        self.update_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self.settings_btn.setEnabled(False)
        self.network_btn.setEnabled(False)
        
        self.install_worker = InstallWorker(
            selected, 
            path, 
            max_workers=self.settings.get('max_threads', 3)
        )
        
        self.install_thread = QThread()
        self.install_worker.moveToThread(self.install_thread)
        
        self.install_worker.progress_updated.connect(self.on_progress_updated)
        self.install_worker.overall_progress_updated.connect(self.on_overall_progress_updated)
        self.install_worker.status_updated.connect(self.on_status_updated)
        self.install_worker.download_detail.connect(self.on_download_detail)
        self.install_worker.result_ready.connect(self.on_install_result)
        self.install_worker.started.connect(self.on_install_started)
        self.install_worker.finished.connect(self.on_install_finished)
        
        self.install_thread.started.connect(self.install_worker.run)
        self.install_thread.finished.connect(self.install_thread.deleteLater)
        
        self.install_thread.start()
    
    @pyqtSlot(str, float, int, int)
    def on_progress_updated(self, dlc_id, progress, downloaded, total):
        """Обновить прогресс загрузки"""
        # Устанавливаем целые проценты
        self.download_progress.setValue(int(progress))
        
        if not self.download_progress.isVisible():
            self.download_progress.setVisible(True)
        
        # Обновляем детали
        if total > 0:
            self.download_detail.update_progress(dlc_id, progress, downloaded, total)
    
    @pyqtSlot(float)
    def on_overall_progress_updated(self, progress):
        """Этот метод теперь не нужен - убрали верхний прогресс-бар"""
        pass  # Ничего не делаем
    
    @pyqtSlot(str, str)
    def on_status_updated(self, dlc_id, status):
        self.logger.log(f"[{dlc_id}] {status}")
    
    @pyqtSlot(str)
    def on_download_detail(self, detail):
        self.logger.log(f"[DETAIL] {detail}")
    
    @pyqtSlot(str, bool, str)
    def on_install_result(self, dlc_id, success, message):
        self.progress_done += 1
        
        if success:
            self.successful_count += 1
            self.logger.log(f"SUCCESS: {dlc_id}: {message}")
        else:
            self.failed_count += 1
            self.logger.log(f"FAILED: {dlc_id}: {message}")
        
        remaining = self.progress_total - self.progress_done
        self.logger.log(f"[PROGRESS] {self.progress_done}/{self.progress_total} "
                       f"(Success: {self.successful_count} Failed: {self.failed_count} Remaining: {remaining})")
    
    @pyqtSlot()
    def on_install_started(self):
        self.logger.log("[INSTALL] Installation started")
    
    @pyqtSlot()
    def on_install_finished(self):
        """Завершение установки"""
        self.logger.log("[INSTALL] Installation complete!")
        
        # Устанавливаем 100%
        self.download_progress.setValue(100)
        
        # Показываем финальные детали
        self.download_detail.setText("Installation complete!")
        
        # Сбрасываем UI через 1 секунду
        QTimer.singleShot(1000, self.reset_ui_after_install)
        
        # Показываем результат
        if self.failed_count == 0:
            msg = f"All {self.successful_count} DLC installed successfully!"
            QMessageBox.information(self, "Installation Complete", msg)
        else:
            msg = f"Installation finished with issues:\n\nSuccessful: {self.successful_count}\nFailed: {self.failed_count}\n\nCheck log for details."
            QMessageBox.warning(self, "Installation Complete", msg)
        
        # Обновляем статус DLC
        self.update_dlc_status()
        
        if self.install_thread:
            self.install_thread.quit()
            self.install_thread.wait()
            self.install_thread = None
            self.install_worker = None
    
    def reset_ui_after_install(self):
        """Сбросить UI после установки"""
        if self.is_closing:
            return
        
        # Просто скрываем прогресс-бар
        self.download_progress.setVisible(False)
        self.download_detail.setVisible(False)
        
        # Сбрасываем значения
        self.download_progress.setValue(0)
        
        # Возвращаем кнопки
        self.update_btn.setText("Update")
        self.update_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self.settings_btn.setEnabled(True)
        self.network_btn.setEnabled(True)
    
    def on_cancel(self):
        if self.install_worker:
            self.logger.log("[INSTALL] Cancelling installation...")
            self.install_worker.cancel()
            
            self.update_btn.setText("Cancelling...")
            self.update_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            
            QTimer.singleShot(1000, self.show_cancelled_message)
    
    def show_cancelled_message(self):
        self.logger.log("[INSTALL] Installation cancelled by user")
        QMessageBox.information(self, "Installation Cancelled", "Installation has been cancelled.")
        
        self.reset_ui_after_install()
        self.update_dlc_status()
    
    def closeEvent(self, event):
        self.is_closing = True
        
        self.logger.log("[APP] Shutting down...")
        
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

# ================================================================
#                     ENTRY POINT
# ================================================================

if __name__ == "__main__":
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    if SingleInstanceLock.is_already_running():
        QMessageBox.critical(None, "Already Running", 
                           "Linua Updater is already running.\n"
                           "Check your system tray or task manager.")
        sys.exit(1)
    
    instance_lock = SingleInstanceLock()
    if not instance_lock.acquire():
        QMessageBox.critical(None, "Already Running", 
                           "Linua Updater is already running.\n"
                           "Check your system tray or task manager.")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    app.setApplicationName("Linua Updater")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("l1ntol")
    
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(10, 10, 10))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(50, 50, 50))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 120, 215))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)
    
    config = ConfigManager()
    db = DLCDatabase()
    
    window = LinuaUI(config, db)
    window.show()
    
    exit_code = app.exec()
    
    instance_lock.release()
    
    sys.exit(exit_code)