"""
ColorEngine do QDir.
Gerencia regras de coloração de arquivos com base no padrão [Filter2] do Q-Dir.ini.
Aplica cores e estilos (negrito, itálico) através de um QStyledItemDelegate.
"""

from dataclasses import dataclass
import copy
import fnmatch
import json
import os
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QModelIndex, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemDelegate,
    QLineEdit,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)


def is_valid_hex_color(s: Optional[str]) -> bool:
    if not s or s == "-1" or len(s) != 6:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in s)


@dataclass
class ColorRule:
    pattern: str
    enabled: bool = True
    color_hex: Optional[str] = None
    bg_color_hex: Optional[str] = None
    bold: bool = False
    italic: bool = False
    strikeout: bool = False

    def matches(self, filename: str, is_dir: bool, is_hidden: bool) -> bool:
        if not self.enabled:
            return False

        pat = self.pattern.strip()
        if pat == "#DIR":
            return is_dir
        if pat == "#Hidden":
            return is_hidden

        if is_dir:
            # Não aplica padrões de arquivo a diretórios
            return False

        # Suporta múltiplos padrões separados por ponto-e-vírgula ou vírgula
        sub_patterns = [p.strip() for p in pat.replace(",", ";").split(";") if p.strip()]
        lower_name = filename.lower()
        for p in sub_patterns:
            if fnmatch.fnmatch(lower_name, p.lower()):
                return True
        return False


class ColorEngine:
    """Carrega regras do Q-Dir.ini ou usa conjunto padrão do Q-Dir."""

    DEFAULT_RULES = [
        ColorRule("#Hidden", True, color_hex="888888", italic=True),
        ColorRule("#DIR", True, color_hex="008800", bold=True),
        ColorRule("*.zip;*.rar;*.gz;*.7z;*.tar;*.xz;*.bz2", True, color_hex="00AA00"),
        ColorRule("*.mp*;*.avi;*.wma;*.mkv;*.mp4;*.webm;*.flac;*.wav", True, color_hex="DD0058"),
        ColorRule("*.jpg;*.jpeg;*.png;*.gif;*.bmp;*.ico;*.svg;*.webp", True, color_hex="BB00BB"),
        ColorRule("*.html;*.htm;*.url;*.css;*.json;*.xml;*.yaml;*.yml", True, color_hex="2080C0"),
        ColorRule("*.pdf;*.doc;*.docx;*.rtf;*.xls;*.xlsx;*.odt;*.csv", True, color_hex="BB8844"),
        ColorRule("*.py;*.rs;*.cpp;*.hpp;*.h;*.c;*.go;*.js;*.ts;*.sh", True, color_hex="007ACC", bold=True),
        ColorRule("*.exe;*.dll;*.bat;*.bin;*.so;*.AppImage", True, color_hex="DD2222", bold=True),
    ]

    @staticmethod
    def get_config_path() -> str:
        cfg_dir = os.path.expanduser("~/.config/qdir")
        os.makedirs(cfg_dir, exist_ok=True)
        return os.path.join(cfg_dir, "color_rules.json")

    def __init__(self, ini_path: Optional[str] = None):
        self.rules: List[ColorRule] = []
        # 1. Prioriza regras personalizadas salvas pelo usuário em ~/.config/qdir/color_rules.json
        if not self.load_from_json():
            # 2. Se não houver JSON salvo, tenta ler do Q-Dir.ini original
            if ini_path and os.path.exists(ini_path):
                self.load_from_ini(ini_path)
            else:
                # 3. Padrão inicial do QDir
                self.rules = [copy.copy(r) for r in self.DEFAULT_RULES]

    def load_from_json(self, path: Optional[str] = None) -> bool:
        """Carrega regras salvas do arquivo JSON de configuração."""
        json_path = path or self.get_config_path()
        if os.path.isfile(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    rules = []
                    for item in data:
                        rules.append(ColorRule(
                            pattern=item.get("pattern", ""),
                            enabled=item.get("enabled", True),
                            color_hex=item.get("color_hex"),
                            bg_color_hex=item.get("bg_color_hex"),
                            bold=item.get("bold", False),
                            italic=item.get("italic", False),
                            strikeout=item.get("strikeout", False),
                        ))
                    self.rules = rules
                    return True
            except Exception as e:
                print(f"[ColorEngine] Erro ao carregar regras de {json_path}: {e}")
        return False

    def save_to_json(self, path: Optional[str] = None) -> bool:
        """Salva as regras atuais no arquivo JSON de configuração."""
        json_path = path or self.get_config_path()
        try:
            data = []
            for r in self.rules:
                data.append({
                    "pattern": r.pattern,
                    "enabled": r.enabled,
                    "color_hex": r.color_hex,
                    "bg_color_hex": r.bg_color_hex,
                    "bold": r.bold,
                    "italic": r.italic,
                    "strikeout": r.strikeout,
                })
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ColorEngine] Erro ao salvar regras em {json_path}: {e}")
            return False

    def load_from_ini(self, ini_path: str):
        """Lê seção [Filter2] de um arquivo Q-Dir.ini (UTF-16LE ou UTF-8)."""
        rules = []
        text = ""
        for enc in ["utf-16-le", "utf-8", "latin1"]:
            try:
                with open(ini_path, "r", encoding=enc) as f:
                    text = f.read()
                break
            except Exception:
                continue

        in_filter2 = False
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                in_filter2 = (line == "[Filter2]")
                continue

            if in_filter2 and "=" in line:
                # Exemplo: 1 = *.zip;*.rar;*.gz;*.7z;=1=00AA00=-1=1=-1=0
                parts = line.split("=", 1)[1].split("=")
                if len(parts) >= 2:
                    pat = parts[0]
                    enabled = (parts[1] == "1") if len(parts) > 1 else True
                    raw_fg = parts[2] if len(parts) > 2 else None
                    raw_bg = parts[3] if len(parts) > 3 else None
                    color_hex = raw_fg if is_valid_hex_color(raw_fg) else None
                    bg_color_hex = raw_bg if is_valid_hex_color(raw_bg) else None
                    bold = (parts[4] == "1") if len(parts) > 4 else False
                    italic = (parts[5] == "1") if len(parts) > 5 else False
                    strikeout = (parts[6] == "1") if len(parts) > 6 else False

                    # Arquivos ocultos devem ser atenuados (cinza/itálico) e nunca com fundo preto
                    if pat == "#Hidden":
                        if not color_hex:
                            color_hex = "888888"
                        bg_color_hex = None
                        italic = True

                    rules.append(ColorRule(
                        pattern=pat,
                        enabled=enabled,
                        color_hex=color_hex,
                        bg_color_hex=bg_color_hex,
                        bold=bold,
                        italic=italic,
                        strikeout=strikeout,
                    ))

        if rules:
            self.rules = rules
        else:
            self.rules = list(self.DEFAULT_RULES)

    def get_style_for_file(self, filename: str, is_dir: bool, is_hidden: bool):
        """Retorna tupla (fg_color, bg_color, bold, italic, strikeout) ou None."""
        for rule in self.rules:
            if rule.matches(filename, is_dir, is_hidden):
                fg = QColor(f"#{rule.color_hex}") if (rule.color_hex and is_valid_hex_color(rule.color_hex)) else None
                bg = QColor(f"#{rule.bg_color_hex}") if (rule.bg_color_hex and is_valid_hex_color(rule.bg_color_hex)) else None
                return fg, bg, rule.bold, rule.italic, rule.strikeout
        return None, None, False, False, False


class QDirColorDelegate(QStyledItemDelegate):
    """Delegate do Qt para renderizar itens de arquivo com cores customizadas do Q-Dir."""

    def __init__(self, color_engine: ColorEngine, parent=None):
        super().__init__(parent)
        self.color_engine = color_engine

    def initStyleOption(self, option: QStyleOptionViewItem, index):
        super().initStyleOption(option, index)
        if not index.isValid():
            return

        model = index.model()
        # Se for proxy model ou QFileSystemModel
        source_index = index
        while hasattr(model, "mapToSource"):
            source_index = model.mapToSource(source_index)
            model = model.sourceModel()

        file_info = None
        if hasattr(model, "fileInfo"):
            file_info = model.fileInfo(source_index)

        if file_info is None:
            return

        filename = file_info.fileName()
        is_dir = file_info.isDir()
        is_hidden = file_info.isHidden() or filename.startswith(".")

        fg, bg, bold, italic, strikeout = self.color_engine.get_style_for_file(filename, is_dir, is_hidden)

        # Não sobrepõe a cor se o item estiver selecionado
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if fg and fg.isValid() and not is_selected:
            option.palette.setColor(option.palette.ColorRole.Text, fg)
            option.palette.setColor(option.palette.ColorRole.WindowText, fg)

        if bg and bg.isValid() and not is_selected:
            option.backgroundBrush = QBrush(bg)

        font = option.font
        changed = False
        if bold:
            font.setBold(True)
            changed = True
        if italic:
            font.setItalic(True)
            changed = True
        if strikeout:
            font.setStrikeOut(True)
            changed = True
        if changed:
            option.font = font

        # Se o item estiver recortado (Ctrl+X), atenua visualmente (opacidade ~50%)
        file_path = file_info.absoluteFilePath()
        from qdir.clipboard_manager import QDirClipboard
        if QDirClipboard.is_cut_path(file_path):
            option.state &= ~QStyle.StateFlag.State_Enabled
            dimmed_text = option.palette.color(option.palette.ColorRole.Text)
            dimmed_text.setAlpha(120)
            option.palette.setColor(option.palette.ColorRole.Text, dimmed_text)
            option.palette.setColor(option.palette.ColorRole.WindowText, dimmed_text)

    def createEditor(self, parent, option, index):
        if not index.isValid() or index.column() != 0:
            return None

        model = index.model()
        source_index = index
        while hasattr(model, "mapToSource"):
            source_index = model.mapToSource(source_index)
            model = model.sourceModel()

        if hasattr(model, "fileName") and model.fileName(source_index.siblingAtColumn(0)) == "..":
            return None

        is_dir = False
        if hasattr(model, "isDir"):
            is_dir = model.isDir(source_index)

        editor = RenameLineEdit(is_dir=is_dir, parent=parent)
        editor.navigate_requested.connect(lambda direction: self.on_navigate(editor, direction, index))
        return editor

    def setEditorData(self, editor: QWidget, index: QModelIndex):
        if isinstance(editor, RenameLineEdit):
            val = index.model().data(index, Qt.ItemDataRole.EditRole) or index.model().data(index, Qt.ItemDataRole.DisplayRole)
            editor.setText(str(val))
            # Seleciona o nome base sem extensão logo na abertura do editor
            QTimer.singleShot(0, editor.select_cycle)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model, index: QModelIndex):
        if isinstance(editor, RenameLineEdit):
            new_text = editor.text().strip()
            old_text = model.data(index, Qt.ItemDataRole.EditRole) or model.data(index, Qt.ItemDataRole.DisplayRole)
            if new_text and new_text != old_text:
                model.setData(index, new_text, Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor: QWidget, option, index: QModelIndex):
        editor.setGeometry(option.rect)

    def on_navigate(self, editor, direction: int, index: QModelIndex):
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.NoHint)
        table = self.parent()
        if not table or not hasattr(table, "model"):
            return
        proxy = table.model()
        root_idx = table.rootIndex()
        row_count = proxy.rowCount(root_idx)
        new_row = index.row() + direction

        while 0 <= new_row < row_count:
            candidate_idx = proxy.index(new_row, 0, root_idx)
            src_idx = proxy.mapToSource(candidate_idx)
            if hasattr(table, "pane") and table.pane.fs_model.fileName(src_idx.siblingAtColumn(0)) != "..":
                table.setCurrentIndex(candidate_idx)
                QTimer.singleShot(0, lambda idx=candidate_idx: table.edit(idx))
                break
            new_row += direction


class RenameLineEdit(QLineEdit):
    """Editor inline de renomeação inspirado no Double Commander com alternância de seleção e setas Cima/Baixo."""

    navigate_requested = pyqtSignal(int)  # -1 para Cima, +1 para Baixo

    def __init__(self, is_dir: bool = False, parent=None):
        super().__init__(parent)
        self.is_dir = is_dir
        self.cycle_state = 0
        self.setStyleSheet("""
            QLineEdit {
                background: palette(base);
                color: palette(text);
                border: 1px solid palette(highlight);
                border-radius: 2px;
                padding: 1px 2px;
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
            }
        """)

    def select_cycle(self):
        text = self.text()
        if self.is_dir or "." not in text or (text.startswith(".") and text.count(".") == 1):
            self.selectAll()
            return

        base, ext = os.path.splitext(text)
        if self.cycle_state == 0:
            # 1º F2: Seleciona apenas o nome base (sem a extensão e sem o ponto)
            self.setSelection(0, len(base))
        elif self.cycle_state == 1:
            # 2º F2: Seleciona apenas a extensão (sem o ponto)
            self.setSelection(len(base) + 1, len(ext) - 1)
        elif self.cycle_state == 2:
            # 3º F2: Seleciona o nome completo
            self.selectAll()

    def next_cycle(self):
        text = self.text()
        if self.is_dir or "." not in text or (text.startswith(".") and text.count(".") == 1):
            self.selectAll()
            return
        self.cycle_state = (self.cycle_state + 1) % 3
        self.select_cycle()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_F2:
            self.next_cycle()
            event.accept()
            return
        elif key == Qt.Key.Key_Down:
            self.navigate_requested.emit(1)
            event.accept()
            return
        elif key == Qt.Key.Key_Up:
            self.navigate_requested.emit(-1)
            event.accept()
            return
        super().keyPressEvent(event)


