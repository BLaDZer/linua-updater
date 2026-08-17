from typing import Any, Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from linua_updater.core.diagnostics import NetworkDiagnostics


class DiagnosticsWorker(QObject):
    result_ready = pyqtSignal(object)

    def __init__(self, network: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self.network = network or {}

    def run(self) -> None:
        tool = NetworkDiagnostics(
            None, region_api=self.network.get("region_api"), proxy_ports=self.network.get("proxy_ports")
        )
        tool.diagnose()
        self.result_ready.emit(tool)
