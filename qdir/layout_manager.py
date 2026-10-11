"""
LayoutManager do QDir.
Implementa os 12 layouts multi-painel do Q-Dir original, permitindo alternar
instantaneamente entre configurações de 1, 2, 3 e 4 painéis mantendo o estado
e abas abertas de cada painel sem recarregar.
"""

from typing import List, Optional

from PyQt6.QtCore import QDir, QModelIndex, Qt, pyqtSignal
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from qdir.pane import QDirPane


class LayoutManager(QWidget):
    """Gerenciador central dos 12 layouts e divisores (splitters) do QDir."""

    layout_changed = pyqtSignal(int)

    LAYOUT_NAMES = [
        "4-Quad (2x2)",
        "3-Tri (1 Topo, 2 Embaixo)",
        "3-Tri (2 Topo, 1 Embaixo)",
        "3-Tri (1 Esquerda, 2 Direita)",
        "3-Tri (2 Esquerda, 1 Direita)",
        "4-Quad Vertical (4 Colunas)",
        "4-Quad Horizontal (4 Linhas)",
        "3-Tri Vertical (3 Colunas)",
        "3-Tri Horizontal (3 Linhas)",
        "2-Dual Vertical (2 Colunas)",
        "2-Dual Horizontal (2 Linhas)",
        "1-Single (Painel Único)",
    ]

    def __init__(self, panes: List[QDirPane], parent=None):
        super().__init__(parent)
        self.panes = panes
        self.current_layout_id: int = 0
        self.current_tree_mode: int = 0  # 0: Sem Árvores, 1: 4 Árvores, 2: 1 Compartilhada

        self.root_layout = QHBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # Divisor principal que suporta Árvore Compartilhada na esquerda + Container dos Painéis
        self.outer_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.shared_tree = QTreeView()
        self.shared_tree.setHeaderHidden(True)
        self.shared_model = QFileSystemModel(self)
        self.shared_model.setRootPath("")
        self.shared_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives)
        self.shared_tree.setModel(self.shared_model)
        for col in range(1, 4):
            self.shared_tree.setColumnHidden(col, True)
        self.shared_tree.clicked.connect(self.on_shared_tree_clicked)
        self.shared_tree.hide()

        self.container_widget = QWidget()
        self.container_layout = QVBoxLayout(self.container_widget)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)

        self.outer_splitter.addWidget(self.shared_tree)
        self.outer_splitter.addWidget(self.container_widget)
        self.outer_splitter.setStretchFactor(0, 0)
        self.outer_splitter.setStretchFactor(1, 1)

        self.root_layout.addWidget(self.outer_splitter)

        # Monta o layout inicial (4-Quad 2x2)
        self.apply_layout(0)

    def on_shared_tree_clicked(self, index: QModelIndex):
        if index.isValid():
            path = self.shared_model.filePath(index)
            # Navega o painel ativo visível
            target_pane = next((p for p in self.panes if p.is_active and p.isVisible()), None)
            if not target_pane:
                target_pane = next((p for p in self.panes if p.isVisible()), self.panes[0])
            target_pane.navigate_to(path)

    def apply_layout(self, layout_id: int):
        """Reorganiza os 4 painéis nos splitters conforme o layout escolhido."""
        if layout_id < 0 or layout_id >= len(self.LAYOUT_NAMES):
            layout_id = 0

        self.current_layout_id = layout_id

        # 1. Desanexa os painéis do layout anterior sem destruí-los
        for pane in self.panes:
            pane.setParent(None)

        # Limpa o container_layout
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        p1, p2, p3, p4 = self.panes

        # Determina quais painéis devem estar visíveis
        visible_panes = self._get_visible_panes_for_layout(layout_id)
        for i, pane in enumerate(self.panes):
            pane.setVisible(i in visible_panes)

        # Constrói a árvore de splitters para o layout selecionado
        layout_widget = self._build_splitter_tree(layout_id, p1, p2, p3, p4)
        self.container_layout.addWidget(layout_widget)

        self.layout_changed.emit(layout_id)

    def _get_visible_panes_for_layout(self, layout_id: int) -> List[int]:
        if layout_id in (0, 5, 6):
            return [0, 1, 2, 3]
        elif layout_id in (1, 2, 3, 4, 7, 8):
            return [0, 1, 2]
        elif layout_id in (9, 10):
            return [0, 1]
        elif layout_id == 11:
            return [0]
        return [0, 1, 2, 3]

    def _build_splitter_tree(self, layout_id: int, p1, p2, p3, p4) -> QWidget:
        H = Qt.Orientation.Horizontal
        V = Qt.Orientation.Vertical

        if layout_id == 0:
            # 4-Quad 2x2
            main_split = QSplitter(H)
            left_split = QSplitter(V)
            right_split = QSplitter(V)

            left_split.addWidget(p1)
            left_split.addWidget(p2)
            right_split.addWidget(p3)
            right_split.addWidget(p4)

            main_split.addWidget(left_split)
            main_split.addWidget(right_split)
            main_split.setSizes([500, 500])
            left_split.setSizes([400, 400])
            right_split.setSizes([400, 400])
            return main_split

        elif layout_id == 1:
            # 3-Tri (1 Topo, 2 Embaixo)
            main_split = QSplitter(V)
            bottom_split = QSplitter(H)
            bottom_split.addWidget(p2)
            bottom_split.addWidget(p3)

            main_split.addWidget(p1)
            main_split.addWidget(bottom_split)
            main_split.setSizes([400, 400])
            return main_split

        elif layout_id == 2:
            # 3-Tri (2 Topo, 1 Embaixo)
            main_split = QSplitter(V)
            top_split = QSplitter(H)
            top_split.addWidget(p1)
            top_split.addWidget(p2)

            main_split.addWidget(top_split)
            main_split.addWidget(p3)
            main_split.setSizes([400, 400])
            return main_split

        elif layout_id == 3:
            # 3-Tri (1 Esquerda, 2 Direita)
            main_split = QSplitter(H)
            right_split = QSplitter(V)
            right_split.addWidget(p2)
            right_split.addWidget(p3)

            main_split.addWidget(p1)
            main_split.addWidget(right_split)
            main_split.setSizes([500, 500])
            return main_split

        elif layout_id == 4:
            # 3-Tri (2 Esquerda, 1 Direita)
            main_split = QSplitter(H)
            left_split = QSplitter(V)
            left_split.addWidget(p1)
            left_split.addWidget(p2)

            main_split.addWidget(left_split)
            main_split.addWidget(p3)
            main_split.setSizes([500, 500])
            return main_split

        elif layout_id == 5:
            # 4-Quad Vertical (4 colunas)
            main_split = QSplitter(H)
            main_split.addWidget(p1)
            main_split.addWidget(p2)
            main_split.addWidget(p3)
            main_split.addWidget(p4)
            main_split.setSizes([250, 250, 250, 250])
            return main_split

        elif layout_id == 6:
            # 4-Quad Horizontal (4 faixas)
            main_split = QSplitter(V)
            main_split.addWidget(p1)
            main_split.addWidget(p2)
            main_split.addWidget(p3)
            main_split.addWidget(p4)
            main_split.setSizes([200, 200, 200, 200])
            return main_split

        elif layout_id == 7:
            # 3-Tri Vertical (3 colunas)
            main_split = QSplitter(H)
            main_split.addWidget(p1)
            main_split.addWidget(p2)
            main_split.addWidget(p3)
            main_split.setSizes([333, 333, 333])
            return main_split

        elif layout_id == 8:
            # 3-Tri Horizontal (3 faixas)
            main_split = QSplitter(V)
            main_split.addWidget(p1)
            main_split.addWidget(p2)
            main_split.addWidget(p3)
            main_split.setSizes([250, 250, 250])
            return main_split

        elif layout_id == 9:
            # 2-Dual Vertical (2 colunas)
            main_split = QSplitter(H)
            main_split.addWidget(p1)
            main_split.addWidget(p2)
            main_split.setSizes([500, 500])
            return main_split

        elif layout_id == 10:
            # 2-Dual Horizontal (2 faixas)
            main_split = QSplitter(V)
            main_split.addWidget(p1)
            main_split.addWidget(p2)
            main_split.setSizes([400, 400])
            return main_split

        elif layout_id == 11:
            # 1-Single (Painel 1 apenas)
            container = QWidget()
            box = QVBoxLayout(container)
            box.setContentsMargins(0, 0, 0, 0)
            box.addWidget(p1)
            return container

        return QWidget()

    def set_tree_mode(self, mode: int):
        """0: Sem Árvores, 1: 4 Árvores (individuais), 2: 1 Árvore Compartilhada."""
        self.current_tree_mode = mode
        if mode == 0:
            self.shared_tree.hide()
            for pane in self.panes:
                pane.set_tree_visible(False)
        elif mode == 1:
            self.shared_tree.hide()
            for pane in self.panes:
                pane.set_tree_visible(True)
        elif mode == 2:
            for pane in self.panes:
                pane.set_tree_visible(False)
            self.shared_tree.show()
            self.outer_splitter.setSizes([200, 800])
            for col in range(1, 4):
                self.shared_tree.setColumnHidden(col, True)
            target_pane = next((p for p in self.panes if p.is_active and p.isVisible()), None)
            if not target_pane:
                target_pane = next((p for p in self.panes if p.isVisible()), self.panes[0])
            tree_idx = self.shared_model.index(target_pane.current_path)
            self.shared_tree.setCurrentIndex(tree_idx)
            self.shared_tree.scrollTo(tree_idx)

    def sync_shared_tree(self, path: str):
        if self.current_tree_mode == 2 and self.shared_tree.isVisible():
            tree_idx = self.shared_model.index(path)
            self.shared_tree.setCurrentIndex(tree_idx)
            self.shared_tree.scrollTo(tree_idx)
            for col in range(1, 4):
                self.shared_tree.setColumnHidden(col, True)
