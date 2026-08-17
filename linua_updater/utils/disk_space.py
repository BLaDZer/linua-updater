import shutil
from typing import Any, Dict, List

from linua_updater.constants import SIZE_ESTIMATES
from linua_updater.core.database import DLCDatabase


class DiskSpaceChecker:
    """Check and calculate disk space requirements"""

    @staticmethod
    def get_dlc_size(dlc_id: str) -> int:
        """Get estimated size for a DLC"""
        db = DLCDatabase()
        info = db.get(dlc_id)
        size = info.getSize() if info else None
        if size:
            return size
        return SIZE_ESTIMATES.get(dlc_id, 500000000)

    @staticmethod
    def calculate_required_space(dlc_ids: List[str]) -> int:
        """Calculate total space needed for selected DLC"""
        total = 0
        for dlc_id in dlc_ids:
            total += DiskSpaceChecker.get_dlc_size(dlc_id)

        # Add 10% buffer for temporary files
        return int(total * 1.1)

    @staticmethod
    def get_free_space(path: str) -> int:
        """Get free disk space at path"""
        try:
            total, used, free = shutil.disk_usage(path)
            return free
        except:
            return 0

    @staticmethod
    def check_space(dlc_ids: List[str], game_path: str) -> Dict[str, Any]:
        """Check if there's enough space for installation"""
        required = DiskSpaceChecker.calculate_required_space(dlc_ids)
        available = DiskSpaceChecker.get_free_space(game_path)

        return {
            "required_bytes": required,
            "available_bytes": available,
            "required_gb": required / (1024**3),
            "available_gb": available / (1024**3),
            "enough_space": available >= required,
            "shortage_gb": max(0, (required - available) / (1024**3)),
        }

    @staticmethod
    def format_size(bytes_size: float) -> str:
        """Format bytes to human readable"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
