import ctypes
import sys
from pathlib import Path


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