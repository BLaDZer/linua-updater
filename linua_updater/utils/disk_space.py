import shutil
from typing import Any, Dict, List

from linua_updater.constants import GB, KB, MB, SIZE_ESTIMATES
from linua_updater.core.database import DLCDatabase

DEFAULT_DLC_SIZE_FALLBACK = 500 * MB
SPACE_BUFFER_FACTOR = 1.1


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
        return SIZE_ESTIMATES.get(dlc_id, DEFAULT_DLC_SIZE_FALLBACK)

    @staticmethod
    def calculate_required_space(dlc_ids: List[str]) -> int:
        """Calculate total space needed for selected DLC"""
        total = 0
        for dlc_id in dlc_ids:
            total += DiskSpaceChecker.get_dlc_size(dlc_id)

        # Add buffer for temporary files
        return int(total * SPACE_BUFFER_FACTOR)

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
            "required_gb": required / GB,
            "available_gb": available / GB,
            "enough_space": available >= required,
            "shortage_gb": max(0, (required - available) / GB),
        }

    @staticmethod
    def format_size(bytes_size: float) -> str:
        """Format bytes to human readable"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_size < KB:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= KB
        return f"{bytes_size:.1f} PB"
