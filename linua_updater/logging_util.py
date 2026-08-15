import logging
import os
import shutil
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import QStandardPaths

from linua_updater.paths import AppPaths


def _reveal_in_explorer(path):
    """Cross-platform helper to reveal a file/folder in the file explorer"""
    try:
        directory = path.parent if path.is_file() else path
        if sys.platform == "win32":
            os.system(f'explorer /select, "{path}"')
        elif sys.platform == "darwin":
            os.system(f'open -R "{path}"')
        else:
            os.system(f'xdg-open "{directory}"')
    except Exception:
        pass

class ImprovedLogger:
    def __init__(self, widget=None):
        self.widget = widget
        self._setup_file_logger()
    
    def _setup_file_logger(self):
        AppPaths.ensure()
        log_dir = AppPaths.LOG_DIR
        log_file = AppPaths.LOG_FILE
        
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
    
    def export_logs(self, target_path=None):
        """Export logs to a robust default location."""
        try:
            log_dir = AppPaths.LOG_DIR
            log_file = AppPaths.LOG_FILE
            
            if not log_file.exists():
                return False, "No log file found"
            
            # Resolve target path with fallbacks
            if target_path is None:
                # 1. Real Desktop via QStandardPaths (returns str; may be empty)
                desktop_str = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
                desktop = Path(desktop_str) if desktop_str else Path.home()
                if not desktop.exists():
                    # 2. Fallback to home directory
                    desktop = Path.home()
                # 3. Final fallback to application log directory
                if not desktop.exists():
                    desktop = log_dir
                
                export_name = f"LinuaUpdater_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                export_path = desktop / export_name
            else:
                export_path = Path(target_path)
            
            # Create parent directory
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy(log_file, export_path)
            
            # Reveal file in file explorer
            _reveal_in_explorer(export_path)
            return True, str(export_path)
        except Exception as e:
            return False, str(e)