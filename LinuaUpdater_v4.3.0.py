# ================================================================
#                       LINUA UPDATER v4.3.0 LTS
#     By l1ntol • Long Term Support • Full Featured Edition
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
from collections import deque
import logging
from logging.handlers import RotatingFileHandler

if sys.platform != "win32":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, pyqtSlot, QObject
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QFileDialog,
    QLabel, QPushButton, QTextEdit, QVBoxLayout,
    QHBoxLayout, QWidget, QLineEdit, QCheckBox,
    QScrollArea, QMessageBox, QProgressBar, QSpinBox, QGroupBox, QGridLayout
)
from PyQt6.QtGui import QFont, QPalette, QColor

APP_VERSION = "4.3.0"
GITHUB_REPO = "l1ntol/linua-updater"
VERSION_CHECK_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/version.json"

class ImprovedLogger:
    def __init__(self, widget=None):
        self.widget = widget
        self._setup_file_logger()
    
    def _setup_file_logger(self):
        log_dir = Path.home() / "AppData" / "Local" / "LinuaUpdater" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "updater.log"
        
        self.file_logger = logging.getLogger("LinuaUpdater")
        self.file_logger.setLevel(logging.DEBUG)
        
        if not self.file_logger.handlers:
            handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            self.file_logger.addHandler(handler)
    
    def log(self, text, level="INFO"):
        timestamp = time.strftime("[%H:%M:%S]")
        
        if level == "ERROR":
            self.file_logger.error(text)
        elif level == "WARNING":
            self.file_logger.warning(text)
        elif level == "DEBUG":
            self.file_logger.debug(text)
        else:
            self.file_logger.info(text)
        
        if self.widget:
            line = f"{timestamp} {text}"
            
            if "ERROR" in text.upper() or "FAILED" in text.upper():
                line = f'<font color="#ff6b6b">{line}</font>'
            elif "WARNING" in text.upper():
                line = f'<font color="#ffd93d">{line}</font>'
            elif "SUCCESS" in text.upper() or "Complete" in text or "OK" in text:
                line = f'<font color="#6bcf7f">{line}</font>'
            elif "Network" in text or "Proxy" in text:
                line = f'<font color="#4dabf7">{line}</font>'
            elif "Downloading" in text:
                line = f'<font color="#a78bfa">{line}</font>'
            else:
                line = f'<font color="#e9ecef">{line}</font>'
            
            self.widget.append(line)
            self.widget.ensureCursorVisible()
    
    def export_logs(self):
        """Export logs to desktop"""
        try:
            log_dir = Path.home() / "AppData" / "Local" / "LinuaUpdater" / "logs"
            log_file = log_dir / "updater.log"
            
            if log_file.exists():
                desktop = Path.home() / "Desktop"
                export_name = f"LinuaUpdater_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                export_path = desktop / export_name
                
                shutil.copy(log_file, export_path)
                return True, str(export_path)
            else:
                return False, "No log file found"
        except Exception as e:
            return False, str(e)

class SimpleProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_percent = -1
    
    def setValue(self, value):
        value = max(0, min(100, int(value)))
        if value != self._last_percent:
            self._last_percent = value
            super().setValue(value)
            self.setFormat(f"{value}%")

class SimpleDetailWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QLabel { color: #cccccc; font-size: 11px; padding: 2px; text-align: center; }")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setVisible(False)
    
    def update_progress(self, dlc_id, percent, downloaded, total):
        if total > 0:
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            text = f"Downloading {dlc_id}: {int(percent)}% ({mb_downloaded:.1f}MB/{mb_total:.1f}MB)"
            self.setText(text)
            self.setVisible(True)

class InstallationStats:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.downloads = {}
        self.errors = []
        self.total_bytes = 0
        self.total_time = 0
    
    def start(self):
        self.start_time = time.time()
    
    def record_download(self, dlc_id, size_bytes, duration_sec):
        speed_mbps = (size_bytes / (1024 * 1024)) / duration_sec if duration_sec > 0 else 0
        self.downloads[dlc_id] = {'size_mb': size_bytes / (1024 * 1024), 'duration_sec': duration_sec, 'speed_mbps': speed_mbps}
        self.total_bytes += size_bytes
        self.total_time += duration_sec
    
    def record_error(self, dlc_id, error_msg):
        self.errors.append({'dlc_id': dlc_id, 'error': error_msg, 'timestamp': datetime.now().isoformat()})
    
    def finish(self):
        self.end_time = time.time()
    
    def get_summary(self):
        if not self.start_time or not self.end_time:
            return None
        total_duration = self.end_time - self.start_time
        avg_speed = (self.total_bytes / (1024 * 1024)) / self.total_time if self.total_time > 0 else 0
        return {
            'total_dlc': len(self.downloads),
            'total_size_mb': self.total_bytes / (1024 * 1024),
            'total_duration_sec': total_duration,
            'avg_speed_mbps': avg_speed,
            'successful': len(self.downloads),
            'failed': len(self.errors),
            'errors': self.errors
        }

class UpdateChecker(QObject):
    update_available = pyqtSignal(str, str)
    no_update = pyqtSignal()
    check_failed = pyqtSignal(str)
    
    def __init__(self, logger=None):
        super().__init__()
        self.logger = logger
        self.cache_file = Path.home() / "AppData" / "Local" / "LinuaUpdater" / "update_cache.json"
        self.cache_duration = 129600  # 36 hours in seconds
    
    def log(self, text, level="INFO"):
        if self.logger:
            self.logger.log(text, level)
    
    def _load_cache(self):
        """Load cached update check result"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                    cached_time = cache.get('timestamp', 0)
                    current_time = time.time()
                    
                    # Check if cache is still valid
                    if current_time - cached_time < self.cache_duration:
                        return cache
        except:
            pass
        return None
    
    def _save_cache(self, latest_version, download_url):
        """Save update check result to cache"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache = {
                'timestamp': time.time(),
                'latest_version': latest_version,
                'download_url': download_url
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache, f)
        except Exception as e:
            self.log(f"Failed to save update cache: {e}", "DEBUG")
    
    def check_for_updates(self):
        """Check for updates using version.json (no API rate limits)"""
        try:
            # Try to use cached result first
            cache = self._load_cache()
            if cache:
                latest_version = cache.get('latest_version', '')
                download_url = cache.get('download_url', '')
                self.log(f"Using cached update info (age: {int((time.time() - cache['timestamp']) / 60)} min)", "DEBUG")
                
                if latest_version and self._compare_versions(latest_version, APP_VERSION):
                    self.update_available.emit(latest_version, download_url)
                else:
                    self.no_update.emit()
                return
            
            # Perform actual check
            self.log("Checking for updates...", "INFO")
            response = requests.get(VERSION_CHECK_URL, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get('version', '').replace('v', '')
                download_url = data.get('download_url', '')
                
                self.log(f"Latest version: {latest_version}, Current: {APP_VERSION}", "DEBUG")
                
                # Save to cache
                self._save_cache(latest_version, download_url)
                
                if latest_version and self._compare_versions(latest_version, APP_VERSION):
                    self.update_available.emit(latest_version, download_url)
                else:
                    self.no_update.emit()
            else:
                self.check_failed.emit(f"HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            self.check_failed.emit("Timeout")
        except requests.exceptions.ConnectionError:
            self.check_failed.emit("Connection error")
        except Exception as e:
            self.check_failed.emit(str(e))
    
    def _compare_versions(self, latest, current):
        """Compare version strings (returns True if latest > current)"""
        try:
            latest_parts = [int(x) for x in latest.split('.')]
            current_parts = [int(x) for x in current.split('.')]
            
            for l, c in zip(latest_parts, current_parts):
                if l > c:
                    return True
                elif l < c:
                    return False
            
            return len(latest_parts) > len(current_parts)
        except:
            return False

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

class MetadataCache:
    def __init__(self):
        cache_dir = Path.home() / "AppData" / "Local" / "LinuaUpdater"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = cache_dir / "metadata_cache.json"
        self.cache = self._load()
    
    def _load(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def get(self, dlc_id):
        return self.cache.get(dlc_id)
    
    def set(self, dlc_id, metadata):
        self.cache[dlc_id] = {'metadata': metadata, 'cached_at': datetime.now().isoformat()}
        self._save()
    
    def _save(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Cache save error: {e}")

class DownloadQueue:
    def __init__(self):
        queue_dir = Path.home() / "AppData" / "Local" / "LinuaUpdater"
        queue_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = queue_dir / "download_queue.json"
        self.queue = self._load()
    
    def _load(self):
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def add(self, dlc_id, url, progress=0):
        self.queue[dlc_id] = {'url': url, 'progress': progress, 'added': datetime.now().isoformat()}
        self._save()
    
    def update_progress(self, dlc_id, progress):
        if dlc_id in self.queue:
            self.queue[dlc_id]['progress'] = progress
            self._save()
    
    def remove(self, dlc_id):
        if dlc_id in self.queue:
            del self.queue[dlc_id]
            self._save()
    
    def get_incomplete(self):
        return {k: v for k, v in self.queue.items() if v.get('progress', 0) < 100}
    
    def _save(self):
        try:
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(self.queue, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Queue save error: {e}")


# ======================================================================
# PAUSE/RESUME STATE - v4.3.0 Feature
# ======================================================================

# ============================================
# PAUSE/RESUME COMPONENT FOR v4.3.0
# ============================================
class DownloadState:
    """Saves download state for pause/resume functionality"""
    def __init__(self):
        self.state_file = Path.home() / "AppData" / "Local" / "LinuaUpdater" / "download_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
    def save_state(self, dlc_ids, completed, failed):
        """Save current download state"""
        state = {
            'timestamp': time.time(),
            'total': dlc_ids,
            'completed': completed,
            'failed': failed,
            'remaining': [dlc for dlc in dlc_ids if dlc not in completed and dlc not in failed]
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            return True
        except:
            return False
    def load_state(self):
        """Load saved download state"""
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            # Check if state is recent (less than 24 hours old)
            if time.time() - state.get('timestamp', 0) > 86400:
                return None
            return state
        except:
            return None
    def clear_state(self):
        """Clear saved state"""
        try:
            if self.state_file.exists():
                self.state_file.unlink()
        except:
            pass
# Modified InstallWorker to support pause/resume


class SingleInstanceLock:
    def __init__(self, port=12345):
        self.port = port
        self.socket = None
        self.is_locked = False
    
    def acquire(self):
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
        if self.socket:
            self.socket.close()
            self.is_locked = False
    
    @staticmethod
    def is_already_running(port=12345):
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

class AdminElevator:
    @staticmethod
    def is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    @staticmethod
    def requires_admin(path):
        if not path:
            return False
        path_lower = path.lower()
        admin_paths = [r"c:\program files", r"c:\program files (x86)", r"c:\windows", r"c:\programdata"]
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
    def elevate():
        try:
            if getattr(sys, 'frozen', False):
                script = sys.executable
                params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
            else:
                script = sys.executable
                params = f'"{sys.argv[0]}"'
                if len(sys.argv) > 1:
                    params += ' ' + ' '.join(sys.argv[1:])
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", script, params, None, 1)
            if ret > 32:
                sys.exit(0)
            return False
        except Exception as e:
            print(f"Admin elevation failed: {e}")
            return False

class NetworkDiagnostics:
    def __init__(self, logger=None):
        self.logger = logger
        self.can_reach_github = False
        self.proxy_needed = False
        self.working_proxies = []
        self.recommended_solution = "unknown"
        self.is_russia = False
    
    def log(self, msg, level="INFO"):
        if self.logger:
            self.logger.log(msg, level)
    
    def detect_region(self):
        try:
            response = requests.get("https://ipapi.co/json/", timeout=5)
            data = response.json()
            country_code = data.get('country_code', '')
            if country_code in ['RU', 'UA', 'BY']:
                self.is_russia = True
                return True
        except:
            pass
        return False
    
    def test_connection(self, url, timeout=5):
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            return response.status_code < 400
        except:
            return False
    
    def test_proxy(self, proxy_dict):
        try:
            start = time.time()
            response = requests.get("https://github.com", proxies=proxy_dict, timeout=10, verify=False)
            elapsed = (time.time() - start) * 1000
            return response.status_code < 400, elapsed
        except:
            return False, 0
    
    def diagnose(self):
        self.detect_region()
        self.can_reach_github = self.test_connection("https://github.com")
        raw_ok = self.test_connection("https://raw.githubusercontent.com")
        
        if self.can_reach_github and raw_ok:
            self.log("Network check: OK (direct connection)")
            self.recommended_solution = "direct"
            self.proxy_needed = False
            return
        
        self.log("Network check: blocked, searching for proxy...")
        self.proxy_needed = True
        
        test_proxies = [
            {"http": "socks5://127.0.0.1:1080", "https": "socks5://127.0.0.1:1080"},
            {"http": "http://127.0.0.1:8080", "https": "http://127.0.0.1:8080"},
            {"http": "socks5://127.0.0.1:7890", "https": "socks5://127.0.0.1:7890"},
            {"http": "socks5://127.0.0.1:10808", "https": "socks5://127.0.0.1:10808"},
            {"http": "http://127.0.0.1:8888", "https": "http://127.0.0.1:8888"},
            {"http": "http://127.0.0.1:1087", "https": "http://127.0.0.1:1087"},
        ]
        
        for proxy in test_proxies:
            is_working, speed = self.test_proxy(proxy)
            if is_working:
                self.working_proxies.append(proxy)
                self.log(f"Proxy found: {speed:.0f}ms")
        
        if self.working_proxies:
            self.recommended_solution = "proxy"
        else:
            self.recommended_solution = "vpn_needed"
            self.log("No proxies found. Install VPN or Cloudflare WARP", "WARNING")
    
    def get_recommendation(self):
        if self.recommended_solution == "direct":
            return "Direct connection working"
        elif self.recommended_solution == "proxy":
            return f"Using proxy ({len(self.working_proxies)} found)"
        else:
            return "Connection blocked. Install Cloudflare WARP: https://1.1.1.1/"


class SmartDownloader:
    def __init__(self, logger, diagnostics=None):
        self.logger = logger
        self.diagnostics = diagnostics
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Linua-Updater/4.2'})
        self._cancelled = False
        self._progress_callback = None
        self.min_speed_threshold = 50 * 1024  # 50 KB/s minimum speed
        self.speed_check_duration = 10  # Check speed after 10 seconds
    
    def set_progress_callback(self, callback):
        self._progress_callback = callback
    
    def set_proxy(self, proxy_dict):
        if proxy_dict:
            self.session.proxies = proxy_dict
        else:
            self.session.proxies = {}
    
    def cancel(self):
        self._cancelled = True
    
    def download(self, url, out_path, dlc_name=None, resume=False, expected_size=None):
        display = dlc_name or url
        temp_path = out_path + ".part"
        downloaded = 0
        
        if resume and os.path.exists(temp_path):
            downloaded = os.path.getsize(temp_path)
            self.logger.log(f"Resuming download: {downloaded / (1024*1024):.1f}MB")
        
        success, msg = self._try_download_with_retry(url, out_path, temp_path, downloaded, expected_size)
        if success:
            return True, "OK"
        
        if self.diagnostics and self.diagnostics.working_proxies:
            for proxy in self.diagnostics.working_proxies:
                self.set_proxy(proxy)
                success, msg = self._try_download_with_retry(url, out_path, temp_path, downloaded, expected_size)
                if success:
                    return True, "Downloaded via proxy"
        
        mirrors = {"github.com": "mirror.ghproxy.com/https://github.com", "raw.githubusercontent.com": "raw.fastgit.org"}
        for domain, mirror in mirrors.items():
            if domain in url:
                mirror_url = url.replace(domain, mirror)
                self.set_proxy(None)
                success, msg = self._try_download_with_retry(mirror_url, out_path, temp_path, downloaded, expected_size)
                if success:
                    return True, "Downloaded via mirror"
        
        return False, "All download attempts failed"
    
    def _try_download_with_retry(self, url, out_path, temp_path, start_byte=0, expected_size=None, max_retries=3):
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = min(2 ** attempt, 10)
                    time.sleep(delay)
                success, msg = self._try_download(url, out_path, temp_path, start_byte, expected_size)
                if success:
                    return True, "OK"
                if "corrupted" in msg.lower() or "invalid" in msg.lower():
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    start_byte = 0
            except Exception as e:
                if attempt == max_retries - 1:
                    return False, str(e)
        return False, "Max retries exceeded"
    
    def _try_download(self, url, out_path, temp_path, start_byte=0, expected_size=None):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            headers = {}
            if start_byte > 0:
                headers['Range'] = f'bytes={start_byte}-'
            with self.session.get(url, stream=True, timeout=30, verify=False, headers=headers) as r:
                r.raise_for_status()
                
                # Use expected_size if Content-Length is not available
                total_size = int(r.headers.get('content-length', 0))
                if total_size == 0 and expected_size:
                    total_size = expected_size
                
                total_size += start_byte
                if total_size > 10 * 1024 * 1024 * 1024:
                    return False, "File too large (>10GB)"
                
                mode = 'ab' if start_byte > 0 else 'wb'
                with open(temp_path, mode) as f:
                    downloaded = start_byte
                    start_time = time.time()
                    last_check_time = start_time
                    last_check_bytes = downloaded
                    
                    for chunk in r.iter_content(chunk_size=256*1024):
                        if self._cancelled:
                            return False, "Cancelled"
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Calculate current speed
                            current_time = time.time()
                            elapsed = current_time - last_check_time
                            
                            # Check speed every second
                            if elapsed >= 1.0:
                                bytes_since_check = downloaded - last_check_bytes
                                current_speed = bytes_since_check / elapsed
                                
                                # If speed is too slow for more than speed_check_duration seconds, abort
                                if current_time - start_time > self.speed_check_duration:
                                    if current_speed < self.min_speed_threshold:
                                        self.logger.log(f"Speed too slow: {current_speed/1024:.1f} KB/s (min: {self.min_speed_threshold/1024:.1f} KB/s)")
                                        return False, "Speed too slow, trying alternative"
                                
                                last_check_time = current_time
                                last_check_bytes = downloaded
                            
                            if total_size > 0 and self._progress_callback:
                                progress = (downloaded / total_size) * 100
                                self._progress_callback(progress, downloaded, total_size)
                
                if total_size > 0:
                    actual_size = os.path.getsize(temp_path)
                    # Only check size if we have Content-Length from server
                    if int(r.headers.get('content-length', 0)) > 0 and actual_size != total_size:
                        return False, f"Size mismatch: expected {total_size}, got {actual_size}"
                if os.path.exists(temp_path):
                    shutil.move(temp_path, out_path)
                if total_size > 0 and self._progress_callback:
                    self._progress_callback(100, downloaded, total_size)
                return True, "OK"
        except requests.exceptions.Timeout:
            return False, "Timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection error"
        except Exception as e:
            return False, str(e)

class SevenZipFinder:
    POSSIBLE_LOCATIONS = ["7z.exe", "7za.exe", r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files\7-Zip\7za.exe", r"C:\Program Files (x86)\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7za.exe"]
    
    def __init__(self, logger):
        self.logger = logger
    
    def find(self):
        # 1. Check in same directory as executable
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        local = os.path.join(exe_dir, "7z.exe")
        if os.path.exists(local):
            return local
        
        # 2. Check common installation paths
        for p in self.POSSIBLE_LOCATIONS:
            if os.path.exists(p):
                return p
        
        # 3. Check system PATH using 'where' command
        try:
            if sys.platform == "win32":
                result = subprocess.run(["where", "7z"], capture_output=True, text=True, shell=True)
            else:
                result = subprocess.run(["which", "7z"], capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                if os.path.exists(path):
                    return path
        except:
            pass
        
        # 4. Check PATH environment variable manually
        try:
            path_env = os.environ.get('PATH', '')
            for path_dir in path_env.split(os.pathsep):
                for exe_name in ['7z.exe', '7za.exe']:
                    candidate = os.path.join(path_dir, exe_name)
                    if os.path.exists(candidate):
                        return candidate
        except:
            pass
        
        self.logger.log("7-Zip not found. Install from https://www.7-zip.org/ and add to PATH", "WARNING")
        return None

class Extractor:
    def __init__(self, logger):
        self.logger = logger
    
    def log(self, text, level="INFO"):
        if self.logger:
            self.logger.log(text, level)
    
    def extract_zip(self, file, out_dir):
        try:
            os.makedirs(out_dir, exist_ok=True)
            if not zipfile.is_zipfile(file):
                return False, "Not a valid ZIP file"
            with zipfile.ZipFile(file, "r") as z:
                bad_file = z.testzip()
                if bad_file:
                    return False, f"Corrupted file in archive: {bad_file}"
                total = len(z.infolist())
                for member in z.infolist():
                    z.extract(member, out_dir)
            return True, "OK"
        except zipfile.BadZipFile:
            return False, "Invalid or corrupted ZIP file"
        except Exception as e:
            return False, str(e)
    
    def extract_7z(self, seven, archive_path, out_dir):
        try:
            if not os.path.exists(seven):
                return False, "7z.exe not found"
            if not os.path.exists(archive_path):
                return False, "Archive not found"
            os.makedirs(out_dir, exist_ok=True)
            cmd = [seven, "x", archive_path, f"-o{out_dir}", "-y"]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
            return True, "OK"
        except subprocess.CalledProcessError as e:
            return False, f"7z error: {e.stderr}"
        except subprocess.TimeoutExpired:
            return False, "7z timeout (5 minutes)"
        except Exception as e:
            return False, str(e)

class ParallelInstallManager:
    def __init__(self, max_workers=5):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._cancelled = False
        self._download_progress = {}
        self._overall_progress_callback = None
    
    def set_overall_progress_callback(self, callback):
        self._overall_progress_callback = callback
    
    def update_download_progress(self, dlc_id, progress, downloaded, total):
        self._download_progress[dlc_id] = {'progress': progress, 'downloaded': downloaded, 'total': total}
        if self._overall_progress_callback:
            total_progress = self._calculate_overall_progress()
            self._overall_progress_callback(total_progress)
    
    def _calculate_overall_progress(self):
        if not self._download_progress:
            return 0
        total_progress = sum(d['progress'] for d in self._download_progress.values())
        count = len(self._download_progress)
        return total_progress / count if count > 0 else 0
    
    def cancel_all(self):
        self._cancelled = True
        self.executor.shutdown(wait=False, cancel_futures=True)

class SingleDLCInstaller:
    def __init__(self, dlc_id, info, game_path, downloader, extractor, logger, stats=None):
        self.dlc = dlc_id
        self.info = info
        self.game = game_path
        self.dl = downloader
        self.ex = extractor
        self.logger = logger
        self.stats = stats
        self._progress_callback = None
        self._start_time = None
    
    def set_progress_callback(self, callback):
        self._progress_callback = callback
    
    def log(self, text, level="INFO"):
        if self.logger:
            self.logger.log(f"{self.dlc}: {text}", level)
    
    def run(self):
        temp = None
        try:
            self._start_time = time.time()
            url = self.info.get("url")
            if not url:
                return False, "URL missing"
            
            expected_size = self.info.get("size")  # Get size from database if available
            
            temp = os.path.join(tempfile.gettempdir(), f"{self.dlc}_{int(time.time())}.zip")
            self.log("Starting download...")
            dlc_name = f"{self.dlc} - {self.info.get('name', 'Unknown')}"
            if self._progress_callback:
                self.dl.set_progress_callback(self._progress_callback)
            ok, reason = self.dl.download(url, temp, dlc_name, resume=True, expected_size=expected_size)
            if not ok:
                if self.stats:
                    self.stats.record_error(self.dlc, reason)
                return False, reason
            if not os.path.exists(temp):
                return False, "Downloaded file not found"
            file_size = os.path.getsize(temp)
            if file_size == 0:
                return False, "Downloaded file is empty"
            if file_size < 1024:
                return False, "Downloaded file too small (corrupted?)"
            self.log("Extracting...")
            ok, reason = self.ex.extract_zip(temp, self.game)
            if not ok:
                if self.stats:
                    self.stats.record_error(self.dlc, reason)
                return False, reason
            if self.stats:
                duration = time.time() - self._start_time
                self.stats.record_download(self.dlc, file_size, duration)
            self.log("Complete")
            return True, "OK"
        except Exception as e:
            if self.stats:
                self.stats.record_error(self.dlc, str(e))
            return False, str(e)
        finally:
            if temp and os.path.exists(temp):
                try:
                    os.remove(temp)
                except:
                    pass

class MultiPartInstaller:
    def __init__(self, dlc_id, info, game_path, downloader, extractor, seven_path, logger, stats=None):
        self.dlc = dlc_id
        self.info = info
        self.game = game_path
        self.dl = downloader
        self.ex = extractor
        self.seven = seven_path
        self.logger = logger
        self.stats = stats
        self._progress_callback = None
        self._start_time = None
    
    def set_progress_callback(self, callback):
        self._progress_callback = callback
    
    def log(self, text, level="INFO"):
        if self.logger:
            self.logger.log(f"{self.dlc}: {text}", level)
    
    def run(self):
        downloaded_files = []
        total_size = 0
        try:
            self._start_time = time.time()
            if not self.seven or not os.path.exists(self.seven):
                return False, "7z.exe not found"
            parts = self.info.get("parts", [])
            if not parts:
                return False, "No parts defined"
            total_parts = len(parts)
            for i, url in enumerate(parts):
                name = f"{self.dlc}.7z.{str(i+1).zfill(3)}"
                out = os.path.join(tempfile.gettempdir(), name)
                self.log(f"Downloading part {i+1}/{total_parts}...")
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
                    if self.stats:
                        self.stats.record_error(self.dlc, f"Part {i+1} failed: {reason}")
                    return False, f"Part {i+1} failed: {reason}"
                if not os.path.exists(out):
                    return False, f"Part {i+1} not found after download"
                part_size = os.path.getsize(out)
                if part_size == 0:
                    return False, f"Part {i+1} is empty"
                total_size += part_size
                downloaded_files.append(out)
            part1 = downloaded_files[0]
            self.log("Extracting multipart archive...")
            ok, reason = self.ex.extract_7z(self.seven, part1, self.game)
            if not ok:
                if self.stats:
                    self.stats.record_error(self.dlc, reason)
                return False, reason
            if self.stats:
                duration = time.time() - self._start_time
                self.stats.record_download(self.dlc, total_size, duration)
            self.log("Complete")
            return True, "OK"
        except Exception as e:
            if self.stats:
                self.stats.record_error(self.dlc, str(e))
            return False, str(e)
        finally:
            for f in downloaded_files:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except:
                    pass

class InstallWorker(QObject):
    progress_updated = pyqtSignal(str, float, int, int)
    overall_progress_updated = pyqtSignal(float)
    status_updated = pyqtSignal(str, str)
    download_detail = pyqtSignal(str)
    started = pyqtSignal()
    finished = pyqtSignal()
    result_ready = pyqtSignal(str, bool, str)
    stats_ready = pyqtSignal(dict)
    
    def __init__(self, dlc_ids, game_path, max_workers=3):
        super().__init__()
        self.dlc_ids = dlc_ids
        self.game_path = game_path
        self.max_workers = max_workers
        self._cancelled = False
        self.parallel_manager = None
        self.logger = ImprovedLogger()
        self.db = DLCDatabase()
        self.downloader = SmartDownloader(self.logger)
        self.extractor = Extractor(self.logger)
        self.stats = InstallationStats()
        self.download_progress = {}
    
    def cancel(self):
        self._cancelled = True
        if self.parallel_manager:
            self.parallel_manager.cancel_all()
        if self.downloader:
            self.downloader.cancel()
    
    def run(self):
        try:
            self.started.emit()
            self.stats.start()
            total_dlc = len(self.dlc_ids)
            installed_dlc = set()
            self.overall_progress_updated.emit(0)
            self.parallel_manager = ParallelInstallManager(max_workers=self.max_workers)
            self.parallel_manager.set_overall_progress_callback(lambda progress: self.overall_progress_updated.emit(progress))
            for dlc_id in self.dlc_ids:
                if self._cancelled:
                    break
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
                        installer = MultiPartInstaller(dlc_id, info, self.game_path, self.downloader, self.extractor, seven_path, self.logger, self.stats)
                    else:
                        installer = SingleDLCInstaller(dlc_id, info, self.game_path, self.downloader, self.extractor, self.logger, self.stats)
                    installer.set_progress_callback(lambda progress, downloaded, total, dlc=dlc_id: self._handle_progress(dlc, progress, downloaded, total))
                    success, message = installer.run()
                    if success:
                        installed_dlc.add(dlc_id)
                    self.result_ready.emit(dlc_id, success, message)
                except Exception as e:
                    self.logger.log(f"{dlc_id}: ERROR - {str(e)}", "ERROR")
                    self.result_ready.emit(dlc_id, False, f"Error: {str(e)}")
            self.stats.finish()
            summary = self.stats.get_summary()
            if summary:
                self.stats_ready.emit(summary)
            self.overall_progress_updated.emit(100)
            self.finished.emit()
        except Exception as e:
            self.logger.log(f"CRITICAL ERROR: {str(e)}", "ERROR")
            self.result_ready.emit("SYSTEM", False, f"Worker error: {str(e)}")
            self.finished.emit()
    
    def _handle_progress(self, dlc_id, progress, downloaded, total):
        self.progress_updated.emit(dlc_id, progress, downloaded, total)
        if total > 0:
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            detail = f"Downloading {dlc_id}: {progress:.1f}% ({mb_downloaded:.1f}MB/{mb_total:.1f}MB)"
            self.download_detail.emit(detail)

class SettingsDialog(QDialog):
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
        self.setStyleSheet("QDialog{background-color:#1e1e1e;}QLabel{color:white;}QGroupBox{color:white;border:1px solid #555;border-radius:5px;margin-top:10px;padding-top:10px;}QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 5px 0 5px;}QSpinBox,QCheckBox{color:white;background-color:#2a2a2a;}")
    
    def get_settings(self):
        return {'max_threads': self.thread_spin.value(), 'use_proxy': self.proxy_check.isChecked(), 'resume_downloads': self.resume_check.isChecked(), 'cleanup_temp': self.cleanup_check.isChecked()}

class ConfigManager:
    def __init__(self):
        self.path = Path.home() / "AppData" / "Local" / "LinuaUpdater" / "config.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.data = {"game_path": "", "settings": {"max_threads": 3, "use_proxy": True, "resume_downloads": True, "cleanup_temp": True}}
            self.save()
        else:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                    if "settings" not in self.data:
                        self.data["settings"] = {"max_threads": 3, "use_proxy": True, "resume_downloads": True, "cleanup_temp": True}
            except:
                self.data = {"game_path": "", "settings": {"max_threads": 3, "use_proxy": True, "resume_downloads": True, "cleanup_temp": True}}
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
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Config save failed: {e}")



# ======================================================================
# DISK SPACE CHECKER - v4.3.0 Feature
# ======================================================================

class DiskSpaceChecker:
    """Check and calculate disk space requirements"""
    
    # Approximate sizes in bytes (will be updated with real data)
    DLC_SIZES = {
        "EP01": 1900000000,  # ~1.9 GB
        "EP02": 2100000000,  # ~2.1 GB
        "EP03": 2635798353,  # Known from database
        "EP04": 2800000000,
        "EP05": 2200000000,
        "EP06": 2807534837,  # Known from database
        "EP07": 2100000000,
        "EP08": 2300000000,
        "EP09": 1900000000,
        "EP10": 2400000000,
        "EP11": 2200000000,
        "EP12": 2100000000,
        "EP13": 2000000000,
        "EP14": 2300000000,
        "EP15": 1800000000,
        "EP16": 1900000000,
        "EP17": 2400000000,
        "EP18": 2100000000,
        "EP19": 1800000000,
        "EP20": 1900000000,
        "EP21": 2553349168,  # Known from database
        # Game Packs ~800MB-1.5GB
        "GP01": 800000000,
        "GP02": 850000000,
        "GP03": 900000000,
        "GP04": 1000000000,
        "GP05": 750000000,
        "GP06": 1100000000,
        "GP07": 900000000,
        "GP08": 1000000000,
        "GP09": 1200000000,
        "GP10": 950000000,
        "GP11": 1000000000,
        "GP12": 950000000,
        # Stuff Packs ~100-300MB
        "SP01": 150000000,
        "SP02": 100000000,
        "SP03": 120000000,
        "SP04": 110000000,
        "SP05": 130000000,
        "SP06": 140000000,
        "SP07": 160000000,
        "SP08": 100000000,
        "SP09": 150000000,
        "SP10": 180000000,
        "SP11": 120000000,
        "SP12": 110000000,
        "SP13": 130000000,
        "SP14": 100000000,
        "SP15": 140000000,
        "SP16": 110000000,
        "SP17": 120000000,
        "SP18": 150000000,
        # Kits ~50-100MB
        "SP20": 80000000,
        "SP21": 70000000,
        "SP22": 60000000,
        "SP23": 75000000,
        "SP24": 65000000,
        "SP25": 70000000,
        "SP26": 80000000,
        "SP28": 75000000,
        "SP29": 70000000,
        "SP30": 80000000,
    }
    
    @staticmethod
    def get_dlc_size(dlc_id):
        """Get estimated size for a DLC"""
        # Try to get exact size from database first
        db = DLCDatabase()
        info = db.all().get(dlc_id)
        if info and 'size' in info:
            return info['size']
        
        # Fall back to estimates
        return DiskSpaceChecker.DLC_SIZES.get(dlc_id, 500000000)  # Default 500MB
    
    @staticmethod
    def calculate_required_space(dlc_ids):
        """Calculate total space needed for selected DLC"""
        total = 0
        for dlc_id in dlc_ids:
            total += DiskSpaceChecker.get_dlc_size(dlc_id)
        
        # Add 10% buffer for temporary files
        return int(total * 1.1)
    
    @staticmethod
    def get_free_space(path):
        """Get free disk space at path"""
        try:
            total, used, free = shutil.disk_usage(path)
            return free
        except:
            return 0
    
    @staticmethod
    def check_space(dlc_ids, game_path):
        """Check if there's enough space for installation"""
        required = DiskSpaceChecker.calculate_required_space(dlc_ids)
        available = DiskSpaceChecker.get_free_space(game_path)
        
        return {
            'required_bytes': required,
            'available_bytes': available,
            'required_gb': required / (1024**3),
            'available_gb': available / (1024**3),
            'enough_space': available >= required,
            'shortage_gb': max(0, (required - available) / (1024**3))
        }
    
    @staticmethod
    def format_size(bytes_size):
        """Format bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"


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
        title = QLabel("⚠️ Insufficient Disk Space")
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


class DLCDatabase:
    def __init__(self):
        self.dlc = {
            "EP01": {"name": "Get to Work", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP01/Sims4_DLC_EP01_Get_to_Work.zip"},
            "EP02": {"name": "Get Together", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP02/Sims4_DLC_EP02_Get_Together.zip"},
            "EP03": {
                "name": "City Living",
                "parts": [
                    "https://github.com/l1ntol/lunia-dlc/releases/download/EP03/EP03.7z.001",
                    "https://github.com/l1ntol/lunia-dlc/releases/download/EP03/EP03.7z.002"
                ]
            },
            "EP04": {"name": "Cats and Dogs", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP04/Sims4_DLC_EP04_Cats_and_Dogs.zip"},
            "EP05": {"name": "Seasons", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/EP05/Sims4_DLC_EP05_Seasons.zip"},
            "EP06": {
                "name": "Get Famous",
                "parts": [
                    "https://github.com/l1ntol/lunia-dlc/releases/download/EP06/EP06.7z.001",
                    "https://github.com/l1ntol/lunia-dlc/releases/download/EP06/EP06.7z.002"
                ]
            },
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
            "EP21": {
                "name": "Royalty & Legacy",
                "parts": [
                    "https://github.com/l1ntol/lunia-dlc/releases/download/EP21/EP21.7z.001",
                    "https://github.com/l1ntol/lunia-dlc/releases/download/EP21/EP21.7z.002"
                ]
            },
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
            "SP68": {"name": "Spongebob's House Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP68/SP68.zip"},
            "SP69": {"name": "Autumn Apparel Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP69/Sims4_DLC_SP69_Autumn_Apparel_Kit.zip"},
            "SP70": {"name": "Spongebob Kid's Room Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP70/SP70.zip"},
            "SP71": {"name": "Grange Mudroom Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP71/Sims4_DLC_SP71_Grange_Mudroom_Kit.zip"},
            "SP72": {"name": "Essential Glam Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP72/Sims4_DLC_SP72_Essential_Glam_Kit.zip"},
            "SP73": {"name": "Modern Retreat Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP73/Sims4_DLC_SP73_Modern_Retreat_Kit.zip"},
            "SP74": {"name": "Garden to Table Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP74/Sims4_DLC_SP74_Garden_to_Table_Kit.zip"},
            "SP76": {"name": "Silver Screen Style Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP76/SP76.zip"},
            "SP77": {"name": "Tea Time Solarium Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP77/SP77.zip"},
            "SP81": {"name": "Prairie Dreams Kit", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/SP81/SP81.zip"},
            "FP01": {"name": "Holiday Celebration Pack", "url": "https://github.com/l1ntol/lunia-dlc/releases/download/FP01/Sims4_DLC_FP01_Holiday_Celebration_Pack.zip"},
        }
    
    def all(self):
        return self.dlc


    DLC_SIZES = {
        "EP01": 1900000000,  # ~1.9 GB
        "EP02": 2100000000,  # ~2.1 GB
        "EP03": 2635798353,  # Known from database
        "EP04": 2800000000,
        "EP05": 2200000000,
        "EP06": 2807534837,  # Known from database
        "EP07": 2100000000,
        "EP08": 2300000000,
        "EP09": 1900000000,
        "EP10": 2400000000,
        "EP11": 2200000000,
        "EP12": 2100000000,
        "EP13": 2000000000,
        "EP14": 2300000000,
        "EP15": 1800000000,
        "EP16": 1900000000,
        "EP17": 2400000000,
        "EP18": 2100000000,
        "EP19": 1800000000,
        "EP20": 1900000000,
        "EP21": 2553349168,  # Known from database
        # Game Packs ~800MB-1.5GB
        "GP01": 800000000,
        "GP02": 850000000,
        "GP03": 900000000,
        "GP04": 1000000000,
        "GP05": 750000000,
        "GP06": 1100000000,
        "GP07": 900000000,
        "GP08": 1000000000,
        "GP09": 1200000000,
        "GP10": 950000000,
        "GP11": 1000000000,
        "GP12": 950000000,
        # Stuff Packs ~100-300MB
        "SP01": 150000000,
        "SP02": 100000000,
        "SP03": 120000000,
        "SP04": 110000000,
        "SP05": 130000000,
        "SP06": 140000000,
        "SP07": 160000000,
        "SP08": 100000000,
        "SP09": 150000000,
        "SP10": 180000000,
        "SP11": 120000000,
        "SP12": 110000000,
        "SP13": 130000000,
        "SP14": 100000000,
        "SP15": 140000000,
        "SP16": 110000000,
        "SP17": 120000000,
        "SP18": 150000000,
        # Kits ~50-100MB
        "SP20": 80000000,
        "SP21": 70000000,
        "SP22": 60000000,
        "SP23": 75000000,
        "SP24": 65000000,
        "SP25": 70000000,
        "SP26": 80000000,
        "SP28": 75000000,
        "SP29": 70000000,
        "SP30": 80000000,
    }
    @staticmethod
    def get_dlc_size(dlc_id):
        """Get estimated size for a DLC"""
        # Try to get exact size from database first
        db = DLCDatabase()
        info = db.all().get(dlc_id)
        if info and 'size' in info:
            return info['size']
        # Fall back to estimates
        return DiskSpaceChecker.DLC_SIZES.get(dlc_id, 500000000)  # Default 500MB
    @staticmethod
    def calculate_required_space(dlc_ids):
        """Calculate total space needed for selected DLC"""
        total = 0
        for dlc_id in dlc_ids:
            total += DiskSpaceChecker.get_dlc_size(dlc_id)
        # Add 10% buffer for temporary files
        return int(total * 1.1)
    @staticmethod
    def get_free_space(path):
        """Get free disk space at path"""
        try:
            total, used, free = shutil.disk_usage(path)
            return free
        except:
            return 0
    @staticmethod
    def check_space(dlc_ids, game_path):
        """Check if there's enough space for installation"""
        required = DiskSpaceChecker.calculate_required_space(dlc_ids)
        available = DiskSpaceChecker.get_free_space(game_path)
        return {
            'required_bytes': required,
            'available_bytes': available,
            'required_gb': required / (1024**3),
            'available_gb': available / (1024**3),
            'enough_space': available >= required,
            'shortage_gb': max(0, (required - available) / (1024**3))
        }
    @staticmethod
    def format_size(bytes_size):
        """Format bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
class GameDetector:
    @staticmethod
    def find_from_registry():
        try:
            import winreg
            paths_to_check = []
            registry_keys = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Maxis\The Sims 4", "Install Dir"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Maxis\The Sims 4", "Install Dir"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\EA Games\The Sims 4", "Install Dir"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\EA Games\The Sims 4", "Install Dir"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Maxis\The Sims 4", "Install Dir"),
            ]
            for hkey, subkey, value_name in registry_keys:
                try:
                    key = winreg.OpenKey(hkey, subkey)
                    value, _ = winreg.QueryValueEx(key, value_name)
                    winreg.CloseKey(key)
                    if value and os.path.exists(value):
                        paths_to_check.append(value)
                except:
                    continue
            return paths_to_check
        except:
            return []
    
    @staticmethod
    def find_game():
        found_paths = []
        registry_paths = GameDetector.find_from_registry()
        for path in registry_paths:
            exe_check = os.path.join(path, "Game", "Bin", "TS4_x64.exe")
            if os.path.exists(exe_check):
                found_paths.append(path)
        drives = ["C", "D", "E", "F", "G", "H"]
        search_paths = [
            r"\Program Files (x86)\Steam\steamapps\common\The Sims 4",
            r"\Program Files\Steam\steamapps\common\The Sims 4",
            r"\SteamLibrary\steamapps\common\The Sims 4",
            r"\Program Files\EA Games\The Sims 4",
            r"\Program Files (x86)\EA Games\The Sims 4",
            r"\Program Files (x86)\Origin Games\The Sims 4",
            r"\Program Files\Origin Games\The Sims 4",
            r"\Games\The Sims 4",
            r"\EA Games\The Sims 4",
            r"\Origin Games\The Sims 4",
        ]
        for drive in drives:
            for path in search_paths:
                full_path = f"{drive}:{path}"
                if full_path not in found_paths and os.path.exists(full_path):
                    exe_check = os.path.join(full_path, "Game", "Bin", "TS4_x64.exe")
                    if os.path.exists(exe_check):
                        found_paths.append(full_path)
        return found_paths[0] if found_paths else None

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
        
        # FIXED: Removed EP03/EP06 exclusion
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
        # FIXED: Removed EP03/EP06 exclusion
        return [dlc for dlc, cb in self.cbs.items() if cb.isChecked() and cb.isEnabled()]



# ======================================================================
# UNINSTALLER - v4.3.0 Feature
# ======================================================================

# UNINSTALLER COMPONENT FOR v4.3.0
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
class UninstallWorker(QObject):
    """Worker thread for uninstalling DLC"""
    progress_updated = pyqtSignal(int, int)  # current, total
    dlc_removed = pyqtSignal(str, bool, str)  # dlc_id, success, message
    finished = pyqtSignal()
    def __init__(self, dlc_ids, game_path, logger):
        super().__init__()
        self.dlc_ids = dlc_ids
        self.game_path = game_path
        self.logger = logger
        self._cancelled = False
    def cancel(self):
        self._cancelled = True
    def run(self):
        """Uninstall selected DLC"""
        total = len(self.dlc_ids)
        for i, dlc_id in enumerate(self.dlc_ids):
            if self._cancelled:
                break
            self.progress_updated.emit(i + 1, total)
            success, message = self.uninstall_dlc(dlc_id)
            self.dlc_removed.emit(dlc_id, success, message)
        self.finished.emit()
    def uninstall_dlc(self, dlc_id):
        """Uninstall a single DLC by deleting its folder"""
        try:
            dlc_path = os.path.join(self.game_path, dlc_id)
            if not os.path.exists(dlc_path):
                return False, f"DLC folder not found: {dlc_path}"
            if not os.path.isdir(dlc_path):
                return False, f"Not a directory: {dlc_path}"
            # Delete the DLC folder
            self.logger.log(f"Uninstalling {dlc_id}...", "INFO")
            shutil.rmtree(dlc_path)
            self.logger.log(f"{dlc_id}: Removed successfully", "INFO")
            return True, "OK"
        except PermissionError:
            return False, "Permission denied - try running as administrator"
        except Exception as e:
            return False, str(e)


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
        QTimer.singleShot(100, self.check_for_updates)
        QTimer.singleShot(300, self.run_diagnostics)
        QTimer.singleShot(500, self.auto_detect)
        self.dlc_check_timer.start(3000)
        QTimer.singleShot(1000, self.update_dlc_status)
    
    def check_for_updates(self):
        """Check for updates on startup"""
        self.update_checker = UpdateChecker(self.logger)  # Pass logger
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.no_update.connect(lambda: self.logger.log("No updates available"))
        self.update_checker.check_failed.connect(
            lambda err: self.logger.log(f"Update check failed: {err}", "WARNING")
        )
        QTimer.singleShot(0, self.update_checker.check_for_updates)
    
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
            "<a href='https://www.donationalerts.com/r/lintol' style='color:#ffd700;'>DonationAlerts</a>"
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setStyleSheet("QLabel{background-color:#2a2a2a;padding:10px;border-radius:6px;"
                   "color:#ffd700;font-size:11px;border-left:4px solid #ffd700;}")
        layout.addWidget(info)
    
    def apply_dark_theme(self):
        css = "QMainWindow,QDialog{background-color:#1e1e1e;color:white;}QPushButton{background-color:#333;border:1px solid #555;padding:8px;font-weight:bold;color:white;border-radius:4px;}QPushButton:hover{background-color:#444;}QPushButton:pressed{background-color:#222;}QPushButton:disabled{background-color:#222;color:#666;border:1px solid #333;}QLineEdit{background-color:#0a0a0a;color:white;border:1px solid #444;padding:6px;border-radius:4px;}"
        self.setStyleSheet(css)
    
    def export_logs(self):
        """Export logs to desktop"""
        success, result = self.logger.export_logs()
        if success:
            QMessageBox.information(self, "Logs Exported", f"Logs exported to:\n{result}")
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
        # FIXED: Removed EP03/EP06 exclusion
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
        tool = NetworkDiagnostics(self.logger)
        tool.diagnose()
        self.diagnostics = tool
        self.downloader = SmartDownloader(self.logger, self.diagnostics)
    
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
            # FIXED: Use self.db.all().items() instead of db.items()
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
        try:
            total, used, free = shutil.disk_usage(path)
            free_gb = free / (1024**3)
            if free_gb < 15:
                self.logger.log(f"Low disk space: {free_gb:.1f} GB", "WARNING")
                QMessageBox.warning(self, "Low Disk Space", f"Only {free_gb:.1f} GB free space available.\nAt least 15 GB recommended for DLC installation.")
            else:
                self.logger.log(f"Free space: {free_gb:.1f} GB")
        except:
            pass
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
        self.download_detail.setVisible(False)
        self.update_btn.setVisible(False)
        self.uninstall_btn.setVisible(False)
        self.pause_btn.setVisible(True)
        self.pause_btn.setEnabled(True)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self.settings_btn.setEnabled(False)
        self.export_logs_btn.setEnabled(False)
        self.install_worker = InstallWorker(selected, path, max_workers=self.settings.get('max_threads', 3))
        self.install_thread = QThread()
        self.install_worker.moveToThread(self.install_thread)
        self.install_worker.progress_updated.connect(self.on_progress_updated)
        self.install_worker.overall_progress_updated.connect(self.on_overall_progress_updated)
        self.install_worker.status_updated.connect(self.on_status_updated)
        self.install_worker.download_detail.connect(self.on_download_detail)
        self.install_worker.result_ready.connect(self.on_install_result)
        self.install_worker.started.connect(self.on_install_started)
        self.install_worker.finished.connect(self.on_install_finished)
        self.install_worker.stats_ready.connect(self.on_stats_ready)
        self.install_thread.started.connect(self.install_worker.run)
        self.install_thread.finished.connect(self.install_thread.deleteLater)
        self.install_thread.start()
    
    @pyqtSlot(str, float, int, int)
    def on_progress_updated(self, dlc_id, progress, downloaded, total):
        self.download_progress.setValue(int(progress))
        if not self.download_progress.isVisible():
            self.download_progress.setVisible(True)
        if total > 0:
            self.download_detail.update_progress(dlc_id, progress, downloaded, total)
    
    @pyqtSlot(float)
    def on_overall_progress_updated(self, progress):
        pass
    
    @pyqtSlot(str, str)
    def on_status_updated(self, dlc_id, status):
        pass
    
    @pyqtSlot(str)
    def on_download_detail(self, detail):
        pass
    
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
        if self.install_worker and hasattr(self.install_worker, 'pause'):
            self.install_worker.pause()
            self.pause_btn.setText("Resume")
            self.pause_btn.clicked.disconnect()
            self.pause_btn.clicked.connect(self.on_resume)
            self.logger.log("Installation paused", "WARNING")
    
    def on_resume(self):
        """Handle resume button click"""
        if self.install_worker and hasattr(self.install_worker, 'resume'):
            self.install_worker.resume()
            self.pause_btn.setText("Pause")
            self.pause_btn.clicked.disconnect()
            self.pause_btn.clicked.connect(self.on_pause)
            self.logger.log("Resuming installation...", "INFO")
    
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

if __name__ == "__main__":
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    if SingleInstanceLock.is_already_running():
        QMessageBox.critical(None, "Already Running", "Linua Updater is already running.\nCheck your system tray or task manager.")
        sys.exit(1)
    instance_lock = SingleInstanceLock()
    if not instance_lock.acquire():
        QMessageBox.critical(None, "Already Running", "Linua Updater is already running.\nCheck your system tray or task manager.")
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