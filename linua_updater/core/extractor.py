import os
import shutil
import subprocess
import zipfile


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
                base_dir = os.path.abspath(out_dir)
                for member in z.infolist():
                    name = member.filename.replace("\\", "/").lstrip("/")
                    if os.path.isabs(name) or name[:2].isalpha() and name[2:3] in (":",):
                        return False, f"Unsafe path in archive: {name}"
                    norm = os.path.normpath(name)
                    if norm == os.pardir or norm.startswith(os.pardir + os.sep):
                        return False, f"Unsafe path in archive: {name}"
                    target = os.path.abspath(os.path.join(base_dir, norm))
                    if target != base_dir and not target.startswith(base_dir + os.sep):
                        return False, f"Unsafe path in archive: {name}"
                    if member.is_dir():
                        os.makedirs(target, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        with z.open(member) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
            return True, "OK"
        except zipfile.BadZipFile:
            return False, "Invalid or corrupted ZIP file"
        except Exception as e:
            return False, str(e)

    def extract_7z(self, seven, archive_path, out_dir):
        try:
            if not os.path.exists(seven):
                return False, "7-Zip not found"
            if not os.path.exists(archive_path):
                return False, "Archive not found"
            os.makedirs(out_dir, exist_ok=True)
            cmd = [seven, "x", archive_path, f"-o{out_dir}", "-y"]
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True, "OK"
        except subprocess.CalledProcessError as e:
            return False, f"7z error: {e.stderr}"
        except subprocess.TimeoutExpired:
            return False, "7z timeout (5 minutes)"
        except Exception as e:
            return False, str(e)
