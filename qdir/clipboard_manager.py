"""
Gerenciador de Área de Transferência (Clipboard) para o QDir.
Suporta Copiar (Ctrl+C), Recortar (Ctrl+X) e Colar (Ctrl+V)
integrado ao padrão Linux Desktop (x-special/gnome-copied-files e text/uri-list).
"""

import os
from typing import List, Set, Tuple

from PyQt6.QtCore import QMimeData, QObject, QUrl, pyqtSignal
from PyQt6.QtWidgets import QApplication


class _ClipboardManager(QObject):
    clipboard_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._cut_paths: Set[str] = set()

    def copy(self, paths: List[str]):
        """Copia caminhos para o clipboard do sistema."""
        valid_paths = [os.path.abspath(p) for p in paths if os.path.exists(p)]
        if not valid_paths:
            return

        self._cut_paths.clear()

        cb = QApplication.clipboard()
        md = QMimeData()
        urls = [QUrl.fromLocalFile(p) for p in valid_paths]
        md.setUrls(urls)
        md.setText("\n".join(valid_paths))

        gnome_payload = ("copy\n" + "\n".join(u.toString() for u in urls)).encode("utf-8")
        md.setData("x-special/gnome-copied-files", gnome_payload)
        cb.setMimeData(md)
        self.clipboard_changed.emit()

    def cut(self, paths: List[str]):
        """Recorta caminhos para o clipboard do sistema."""
        valid_paths = [os.path.abspath(p) for p in paths if os.path.exists(p)]
        if not valid_paths:
            return

        self._cut_paths = set(valid_paths)

        cb = QApplication.clipboard()
        md = QMimeData()
        urls = [QUrl.fromLocalFile(p) for p in valid_paths]
        md.setUrls(urls)
        md.setText("\n".join(valid_paths))

        gnome_payload = ("cut\n" + "\n".join(u.toString() for u in urls)).encode("utf-8")
        md.setData("x-special/gnome-copied-files", gnome_payload)
        cb.setMimeData(md)
        self.clipboard_changed.emit()

    def is_cut_path(self, path: str) -> bool:
        """Verifica se um caminho está marcado como recortado."""
        if not self._cut_paths:
            return False
        return os.path.abspath(path) in self._cut_paths

    def get_cut_paths(self) -> Set[str]:
        return set(self._cut_paths)

    def has_files(self) -> bool:
        """Verifica se o clipboard contém arquivos válidos."""
        cb = QApplication.clipboard()
        md = cb.mimeData()
        if md is None:
            return False
        if md.hasFormat("x-special/gnome-copied-files") or md.hasUrls():
            return True
        if md.hasText():
            text = md.text().strip()
            if text and any(os.path.exists(line) for line in text.splitlines()):
                return True
        return False

    def get_files(self) -> Tuple[List[str], bool]:
        """
        Retorna (lista_de_caminhos, is_move).
        Lê formatos nativos (GNOME/FreeDesktop, URLs e texto).
        """
        cb = QApplication.clipboard()
        md = cb.mimeData()
        if md is None:
            return [], False

        is_move = False
        paths: List[str] = []

        # 1. Tenta formato padrão GNOME/FreeDesktop (x-special/gnome-copied-files)
        if md.hasFormat("x-special/gnome-copied-files"):
            try:
                raw = bytes(md.data("x-special/gnome-copied-files")).decode("utf-8")
                lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
                if lines:
                    op = lines[0].lower()
                    if op == "cut":
                        is_move = True
                    for line in lines[1:]:
                        u = QUrl(line)
                        if u.isLocalFile():
                            paths.append(u.toLocalFile())
            except Exception:
                pass

        # 2. Se não achou pelo formato gnome, tenta hasUrls
        if not paths and md.hasUrls():
            for u in md.urls():
                if u.isLocalFile():
                    paths.append(u.toLocalFile())
            if self._cut_paths and any(os.path.abspath(p) in self._cut_paths for p in paths):
                is_move = True

        # 3. Se não achou, tenta texto simples
        if not paths and md.hasText():
            for line in md.text().strip().splitlines():
                clean = line.strip()
                if clean.startswith("file://"):
                    u = QUrl(clean)
                    if u.isLocalFile():
                        paths.append(u.toLocalFile())
                elif os.path.exists(clean):
                    paths.append(os.path.abspath(clean))

        # Filtra apenas caminhos existentes
        valid = [os.path.abspath(p) for p in paths if os.path.exists(p)]
        return valid, is_move

    def clear_cut(self):
        """Limpa o estado de recorte após a colagem."""
        self._cut_paths.clear()
        self.clipboard_changed.emit()


# Instância global para uso na aplicação
QDirClipboard = _ClipboardManager()
