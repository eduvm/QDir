"""
Diálogo de Configuração de Regras de Cores (Filter2) do QDir Linux.
Permite editar padrões, cores de texto (FG), cores de fundo (BG),
estilos de fonte (negrito/itálico), adicionar, remover, reordenar,
salvar em JSON e aplicar em tempo real aos painéis.
"""

from typing import Callable, List, Optional
import copy

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QWidget,
    QColorDialog,
    QMessageBox,
    QAbstractItemView,
)

from qdir.color_engine import ColorEngine, ColorRule, is_valid_hex_color


def _get_contrast_color(color: QColor) -> str:
    """Calcula se o texto sobre a cor deve ser branco ou preto para melhor legibilidade."""
    lum = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
    return "#000000" if lum > 140 else "#ffffff"


class ColorRulesDialog(QDialog):
    """Diálogo completo de gerenciamento de regras de coloração de arquivos."""

    def __init__(
        self,
        color_engine: ColorEngine,
        on_apply: Optional[Callable[[], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.color_engine = color_engine
        self.on_apply = on_apply

        self.setWindowTitle("Configuração de Regras de Cores (Filter2) - QDir")
        self.resize(780, 520)

        # Cópia de trabalho das regras
        self.working_rules: List[ColorRule] = [
            copy.copy(r) for r in self.color_engine.rules
        ]

        self._build_ui()
        self._populate_table()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        # Rótulo explicativo
        lbl_hint = QLabel(
            "Defina cores e estilos por extensão ou atributo (#DIR para pastas, #Hidden para ocultos).\n"
            "As regras do topo da lista têm prioridade sobre as regras inferiores."
        )
        lbl_hint.setStyleSheet("font-size: 11px; color: palette(window-text);")
        main_layout.addWidget(lbl_hint)

        # Barra de Ações da Lista (Adicionar, Remover, Mover, Restaurar)
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(6)

        btn_add = QPushButton(" + Adicionar ")
        btn_add.setToolTip("Adicionar nova regra")
        btn_add.clicked.connect(self._add_rule)
        tools_layout.addWidget(btn_add)

        btn_remove = QPushButton(" - Remover ")
        btn_remove.setToolTip("Remover regra selecionada")
        btn_remove.clicked.connect(self._remove_selected_rule)
        tools_layout.addWidget(btn_remove)

        tools_layout.addSpacing(12)

        btn_up = QPushButton(" ▲ Subir ")
        btn_up.setToolTip("Mover regra selecionada para cima (aumentar prioridade)")
        btn_up.clicked.connect(self._move_rule_up)
        tools_layout.addWidget(btn_up)

        btn_down = QPushButton(" ▼ Descer ")
        btn_down.setToolTip("Mover regra selecionada para baixo")
        btn_down.clicked.connect(self._move_rule_down)
        tools_layout.addWidget(btn_down)

        tools_layout.addStretch(1)

        btn_reset = QPushButton(" ↺ Restaurar Padrões ")
        btn_reset.setToolTip("Restaurar as regras de cores padrão originais do Q-Dir")
        btn_reset.clicked.connect(self._restore_defaults)
        tools_layout.addWidget(btn_reset)

        main_layout.addLayout(tools_layout)

        # Tabela de Regras
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Ativo",
            "Padrão / Extensões",
            "Cor do Texto",
            "Cor de Fundo",
            "Negrito",
            "Itálico",
            "Amostra Visual",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setDefaultSectionSize(32)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 120)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 120)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 60)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 60)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 140)

        self.table.itemChanged.connect(self._on_item_changed)
        main_layout.addWidget(self.table)

        # Botões Inferiores (Aplicar, Salvar, Cancelar)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)

        btn_apply = QPushButton("Aplicar")
        btn_apply.setToolTip("Salva e aplica as alterações nos painéis abertos sem fechar")
        btn_apply.clicked.connect(self._apply_changes)
        btn_layout.addWidget(btn_apply)

        btn_save = QPushButton("Salvar")
        btn_save.setDefault(True)
        btn_save.setStyleSheet("font-weight: bold;")
        btn_save.clicked.connect(self._save_and_close)
        btn_layout.addWidget(btn_save)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        main_layout.addLayout(btn_layout)

    def _populate_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.working_rules))

        for row, rule in enumerate(self.working_rules):
            # 0. Ativo
            item_enabled = QTableWidgetItem()
            item_enabled.setCheckState(Qt.CheckState.Checked if rule.enabled else Qt.CheckState.Unchecked)
            item_enabled.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 0, item_enabled)

            # 1. Padrão
            item_pattern = QTableWidgetItem(rule.pattern)
            item_pattern.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, item_pattern)

            # 2. Cor do Texto
            self.table.setCellWidget(row, 2, self._create_color_cell_widget(row, is_fg=True))

            # 3. Cor de Fundo
            self.table.setCellWidget(row, 3, self._create_color_cell_widget(row, is_fg=False))

            # 4. Negrito
            item_bold = QTableWidgetItem()
            item_bold.setCheckState(Qt.CheckState.Checked if rule.bold else Qt.CheckState.Unchecked)
            item_bold.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 4, item_bold)

            # 5. Itálico
            item_italic = QTableWidgetItem()
            item_italic.setCheckState(Qt.CheckState.Checked if rule.italic else Qt.CheckState.Unchecked)
            item_italic.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 5, item_italic)

            # 6. Amostra
            item_preview = QTableWidgetItem()
            item_preview.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 6, item_preview)

            self._update_preview_cell(row)

        self.table.blockSignals(False)

    def _create_color_cell_widget(self, row: int, is_fg: bool) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        rule = self.working_rules[row]
        current_hex = rule.color_hex if is_fg else rule.bg_color_hex

        btn_color = QPushButton()
        btn_color.setFixedHeight(24)
        btn_color.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        btn_clear = QPushButton("✕")
        btn_clear.setFixedSize(22, 24)
        btn_clear.setToolTip("Limpar / Padrão")
        btn_clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._style_color_button(btn_color, current_hex, is_fg)

        def on_color_click():
            initial = QColor(f"#{current_hex}") if (current_hex and is_valid_hex_color(current_hex)) else QColor("#ffffff")
            title = "Escolha a Cor do Texto" if is_fg else "Escolha a Cor de Fundo"
            color = QColorDialog.getColor(initial, self, title)
            if color.isValid():
                hex_str = color.name().lstrip("#").upper()
                if is_fg:
                    self.working_rules[row].color_hex = hex_str
                else:
                    self.working_rules[row].bg_color_hex = hex_str
                self._style_color_button(btn_color, hex_str, is_fg)
                self._update_preview_cell(row)

        def on_clear_click():
            if is_fg:
                self.working_rules[row].color_hex = None
            else:
                self.working_rules[row].bg_color_hex = None
            self._style_color_button(btn_color, None, is_fg)
            self._update_preview_cell(row)

        btn_color.clicked.connect(on_color_click)
        btn_clear.clicked.connect(on_clear_click)

        layout.addWidget(btn_color, stretch=1)
        layout.addWidget(btn_clear)
        return widget

    def _style_color_button(self, btn: QPushButton, hex_code: Optional[str], is_fg: bool):
        if hex_code and is_valid_hex_color(hex_code):
            col = QColor(f"#{hex_code}")
            text_color = _get_contrast_color(col)
            btn.setText(f"#{hex_code}")
            btn.setStyleSheet(
                f"background-color: #{hex_code}; color: {text_color}; "
                f"font-weight: bold; border: 1px solid rgba(0,0,0,0.3); border-radius: 3px;"
            )
        else:
            default_label = "Padrão" if is_fg else "Nenhum"
            btn.setText(default_label)
            btn.setStyleSheet("font-style: italic; color: palette(window-text);")

    def _update_preview_cell(self, row: int):
        if row >= len(self.working_rules):
            return

        rule = self.working_rules[row]
        item = self.table.item(row, 6)
        if not item:
            return

        pat = rule.pattern.strip()
        if pat == "#DIR":
            preview_text = "📁 [Pasta Exemplo]"
        elif pat == "#Hidden":
            preview_text = "👁️ .oculto_exemplo"
        else:
            first_ext = pat.split(";")[0].replace("*", "arquivo").strip()
            preview_text = first_ext if first_ext else "arquivo.ext"

        item.setText(preview_text)

        # Fonte
        font = QFont(self.table.font())
        font.setBold(rule.bold)
        font.setItalic(rule.italic)
        item.setFont(font)

        # Cor do Texto
        if rule.color_hex and is_valid_hex_color(rule.color_hex):
            item.setForeground(QColor(f"#{rule.color_hex}"))
        else:
            item.setForeground(self.palette().color(self.palette().ColorRole.Text))

        # Cor de Fundo
        if rule.bg_color_hex and is_valid_hex_color(rule.bg_color_hex):
            item.setBackground(QColor(f"#{rule.bg_color_hex}"))
        else:
            item.setBackground(QColor(Qt.GlobalColor.transparent))

    def _on_item_changed(self, item: QTableWidgetItem):
        row = item.row()
        col = item.column()
        if row >= len(self.working_rules):
            return

        rule = self.working_rules[row]
        if col == 0:
            rule.enabled = (item.checkState() == Qt.CheckState.Checked)
        elif col == 1:
            rule.pattern = item.text().strip()
        elif col == 4:
            rule.bold = (item.checkState() == Qt.CheckState.Checked)
        elif col == 5:
            rule.italic = (item.checkState() == Qt.CheckState.Checked)

        self._update_preview_cell(row)

    def _add_rule(self):
        new_rule = ColorRule(
            pattern="*.ext",
            enabled=True,
            color_hex="007ACC",
            bold=False,
            italic=False,
        )
        self.working_rules.append(new_rule)
        self._populate_table()
        new_row = len(self.working_rules) - 1
        self.table.selectRow(new_row)
        item = self.table.item(new_row, 1)
        if item:
            self.table.editItem(item)

    def _remove_selected_rule(self):
        curr_row = self.table.currentRow()
        if 0 <= curr_row < len(self.working_rules):
            del self.working_rules[curr_row]
            self._populate_table()
            next_row = min(curr_row, len(self.working_rules) - 1)
            if next_row >= 0:
                self.table.selectRow(next_row)

    def _move_rule_up(self):
        curr_row = self.table.currentRow()
        if curr_row > 0:
            self.working_rules[curr_row - 1], self.working_rules[curr_row] = (
                self.working_rules[curr_row],
                self.working_rules[curr_row - 1],
            )
            self._populate_table()
            self.table.selectRow(curr_row - 1)

    def _move_rule_down(self):
        curr_row = self.table.currentRow()
        if 0 <= curr_row < len(self.working_rules) - 1:
            self.working_rules[curr_row], self.working_rules[curr_row + 1] = (
                self.working_rules[curr_row + 1],
                self.working_rules[curr_row],
            )
            self._populate_table()
            self.table.selectRow(curr_row + 1)

    def _restore_defaults(self):
        reply = QMessageBox.question(
            self,
            "Restaurar Padrões",
            "Deseja restaurar todas as regras para a configuração padrão original do Q-Dir?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.working_rules = [copy.copy(r) for r in ColorEngine.DEFAULT_RULES]
            self._populate_table()

    def _sync_rules_from_table(self):
        """Garante que qualquer texto digitado na tabela seja sincronizado."""
        for row in range(min(self.table.rowCount(), len(self.working_rules))):
            item_pat = self.table.item(row, 1)
            if item_pat:
                self.working_rules[row].pattern = item_pat.text().strip()

    def _apply_changes(self):
        self._sync_rules_from_table()
        self.color_engine.rules = [copy.copy(r) for r in self.working_rules]
        self.color_engine.save_to_json()
        if self.on_apply:
            self.on_apply()

    def _save_and_close(self):
        self._apply_changes()
        self.accept()
