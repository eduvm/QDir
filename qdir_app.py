#!/usr/bin/env python3
"""
QDir Linux - Quad Explorer para Linux.
Ponto de entrada da aplicação.
"""

import sys
import os

# Adiciona o diretório atual ao sys.path para garantir imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from qdir.theme_manager import setup_qt_environment, apply_system_theme
from qdir.main_window import QDirMainWindow


def main():
    setup_qt_environment()

    app = QApplication(sys.argv)
    app.setApplicationName("QDir Linux")
    app.setOrganizationName("QDir")

    # Aplica configurações do Qt6 Settings (qt6ct) / tema do sistema
    apply_system_theme(app)

    window = QDirMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
