from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette


def apply_dark_palette(app):
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

MAIN_STYLESHEET = "QMainWindow,QDialog{background-color:#1e1e1e;color:white;}QPushButton{background-color:#333;border:1px solid #555;padding:8px;font-weight:bold;color:white;border-radius:4px;}QPushButton:hover{background-color:#444;}QPushButton:pressed{background-color:#222;}QPushButton:disabled{background-color:#222;color:#666;border:1px solid #333;}QLineEdit{background-color:#0a0a0a;color:white;border:1px solid #444;padding:6px;border-radius:4px;}"