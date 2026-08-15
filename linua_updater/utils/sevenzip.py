import os
import subprocess
import sys


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