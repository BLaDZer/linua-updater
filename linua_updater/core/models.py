import threading
import time
from datetime import datetime


class InstallationStats:
    def __init__(self):
        self.lock = threading.Lock()
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
        with self.lock:
            self.downloads[dlc_id] = {'size_mb': size_bytes / (1024 * 1024), 'duration_sec': duration_sec, 'speed_mbps': speed_mbps}
            self.total_bytes += size_bytes
            self.total_time += duration_sec
    
    def record_error(self, dlc_id, error_msg):
        with self.lock:
            self.errors.append({'dlc_id': dlc_id, 'error': error_msg, 'timestamp': datetime.now().isoformat()})
    
    def finish(self):
        with self.lock:
            self.end_time = time.time()
    
    def get_summary(self):
        with self.lock:
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