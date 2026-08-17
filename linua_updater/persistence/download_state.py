import json
import time
from typing import Any, Dict, List, Optional

from linua_updater.constants import CACHE_TIMESTAMP_KEY, JSON_INDENT
from linua_updater.paths import AppPaths


class DownloadState:
    """Saves download state for pause/resume functionality"""

    def __init__(self) -> None:
        AppPaths.ensure()
        self.state_file = AppPaths.DOWNLOAD_STATE_FILE

    def save_state(self, dlc_ids: List[str], completed: List[str], failed: List[str], game_path: Optional[str] = None) -> bool:
        """Save current download state"""
        state = {
            CACHE_TIMESTAMP_KEY: time.time(),
            "total": dlc_ids,
            "completed": completed,
            "failed": failed,
            "game_path": game_path,
            "remaining": [dlc for dlc in dlc_ids if dlc not in completed and dlc not in failed],
        }
        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=JSON_INDENT)
            return True
        except:
            return False

    def load_state(self) -> Optional[Dict[str, Any]]:
        """Load saved download state"""
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file) as f:
                state = json.load(f)
            if not isinstance(state, dict):
                return None
            # Check if state is recent (less than 24 hours old)
            if time.time() - state.get(CACHE_TIMESTAMP_KEY, 0) > AppPaths.DOWNLOAD_STATE_DURATION:
                return None
            return state
        except:
            return None

    def clear_state(self) -> None:
        """Clear saved state"""
        try:
            if self.state_file.exists():
                self.state_file.unlink()
        except:
            pass
