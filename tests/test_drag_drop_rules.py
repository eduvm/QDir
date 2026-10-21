import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QUrl, QMimeData, QPointF
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PyQt6.QtWidgets import QApplication, QMessageBox

from qdir.color_engine import ColorEngine
from qdir.pane import QDirPane
from qdir.ui_icons import get_drag_cursor_pixmap


class TestDragDropRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        import time
        self.test_dir = tempfile.mkdtemp(prefix="qdir_dnd_test_")
        self.subfolder = os.path.join(self.test_dir, "minha_subpasta")
        os.makedirs(self.subfolder, exist_ok=True)
        self.pane = QDirPane(1, ColorEngine())
        self.pane.navigate_to(self.test_dir)
        for _ in range(30):
            self.app.processEvents()
            time.sleep(0.01)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_drag_cursor_pixmaps(self):
        copy_pm = get_drag_cursor_pixmap("copy")
        move_pm = get_drag_cursor_pixmap("move")

        self.assertFalse(copy_pm.isNull(), "Pixmap de cópia não deve ser nulo")
        self.assertGreater(copy_pm.width(), 0)
        self.assertGreater(copy_pm.height(), 0)

        self.assertFalse(move_pm.isNull(), "Pixmap de mover não deve ser nulo")
        self.assertGreater(move_pm.width(), 0)
        self.assertGreater(move_pm.height(), 0)

    def test_file_table_view_drag_enter_and_move_no_shift(self):
        """Sem Shift (padrão), ação deve ser CopyAction."""
        view = self.pane.table_view
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(os.path.join(self.test_dir, "file.txt"))])

        enter_event = QDragEnterEvent(
            QPointF(10, 10).toPoint(),
            Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        with patch.object(QApplication, "keyboardModifiers", return_value=Qt.KeyboardModifier.NoModifier):
            view.dragEnterEvent(enter_event)
            self.assertEqual(enter_event.dropAction(), Qt.DropAction.CopyAction)

            move_event = QDragMoveEvent(
                QPointF(10, 10).toPoint(),
                Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            view.dragMoveEvent(move_event)
            self.assertEqual(move_event.dropAction(), Qt.DropAction.CopyAction)

    def test_file_table_view_drag_enter_and_move_with_shift(self):
        """Com Shift segurado, ação deve ser MoveAction."""
        view = self.pane.table_view
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(os.path.join(self.test_dir, "file.txt"))])

        enter_event = QDragEnterEvent(
            QPointF(10, 10).toPoint(),
            Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ShiftModifier,
        )

        with patch.object(QApplication, "keyboardModifiers", return_value=Qt.KeyboardModifier.ShiftModifier):
            view.dragEnterEvent(enter_event)
            self.assertEqual(enter_event.dropAction(), Qt.DropAction.MoveAction)

            move_event = QDragMoveEvent(
                QPointF(10, 10).toPoint(),
                Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.ShiftModifier,
            )
            view.dragMoveEvent(move_event)
            self.assertEqual(move_event.dropAction(), Qt.DropAction.MoveAction)

    def test_drop_event_determines_is_move_and_show_confirm(self):
        """
        Valida que:
        - Sem Shift, sem Ctrl: is_move=False, show_confirm=False (copia direto)
        - Com Shift, sem Ctrl: is_move=True, show_confirm=False (move direto)
        - Sem Shift, com Ctrl: is_move=False, show_confirm=True (confirma cópia)
        - Com Shift, com Ctrl: is_move=True, show_confirm=True (confirma movimento)
        """
        view = self.pane.table_view
        mime = QMimeData()
        test_file = os.path.join(self.test_dir, "source.txt")
        with open(test_file, "w") as f:
            f.write("test")
        mime.setUrls([QUrl.fromLocalFile(test_file)])

        scenarios = [
            (Qt.KeyboardModifier.NoModifier, False, False),
            (Qt.KeyboardModifier.ShiftModifier, True, False),
            (Qt.KeyboardModifier.ControlModifier, False, True),
            (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier, True, True),
        ]

        with patch.object(self.pane, "handle_files_dropped") as mock_handle:
            for mods, expected_move, expected_confirm in scenarios:
                mock_handle.reset_mock()
                drop_event = QDropEvent(
                    QPointF(10, 10),
                    Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
                    mime,
                    Qt.MouseButton.LeftButton,
                    mods,
                )
                drop_event.setDropAction(Qt.DropAction.MoveAction if expected_move else Qt.DropAction.CopyAction)

                with patch.object(QApplication, "keyboardModifiers", return_value=mods):
                    view.dropEvent(drop_event)
                    self.app.processEvents()

                mock_handle.assert_called_once()
                args, _ = mock_handle.call_args
                # args: (paths, target_dir, is_move, show_confirm)
                self.assertEqual(args[2], expected_move, f"is_move incorreto para mods={mods}")
                self.assertEqual(args[3], expected_confirm, f"show_confirm incorreto para mods={mods}")

    def test_hover_folder_highlight(self):
        """Valida que o hover sobre subpasta atualiza _drag_hover_row e desmarca ao sair."""
        subfolder = self.subfolder

        view = self.pane.table_view
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(os.path.join(self.test_dir, "origem.txt"))])

        # Acha o índice da subpasta na tabela
        model = view.model()
        root_idx = view.rootIndex()
        folder_row = -1
        for row in range(model.rowCount(root_idx)):
            idx = model.index(row, 0, root_idx)
            src_idx = model.mapToSource(idx)
            if self.pane.fs_model.filePath(src_idx) == subfolder:
                folder_row = row
                break

        self.assertGreaterEqual(folder_row, 0, "Subpasta deve estar presente na tabela")

        # Simula dragMove sobre o retângulo da subpasta
        rect = view.visualRect(model.index(folder_row, 0, root_idx))
        pos = rect.center()

        move_event = QDragMoveEvent(
            pos,
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        view.dragMoveEvent(move_event)
        self.assertEqual(view._drag_hover_row, folder_row, "Linha da pasta deve ser destacada")

        # Simula dragLeave
        from PyQt6.QtGui import QDragLeaveEvent
        leave_event = QDragLeaveEvent()
        view.dragLeaveEvent(leave_event)
        self.assertEqual(view._drag_hover_row, -1, "Destaque deve ser limpo no dragLeave")

    def test_handle_files_dropped_no_confirm_executes_immediately(self):
        """Sem Ctrl (show_confirm=False), não deve abrir diálogo e executa diretamente."""
        dest_dir = os.path.join(self.test_dir, "destino")
        os.makedirs(dest_dir, exist_ok=True)
        src_file = os.path.join(self.test_dir, "arq.txt")
        with open(src_file, "w") as f:
            f.write("conteudo")

        with patch("qdir.pane.copy_or_move_items", return_value=(1, [])) as mock_copy, \
             patch.object(QMessageBox, "exec") as mock_msg_exec:
            self.pane.handle_files_dropped([src_file], dest_dir, is_move=False, show_confirm=False)
            mock_msg_exec.assert_not_called()
            mock_copy.assert_called_once()

    def test_handle_files_dropped_with_confirm_shows_dialog(self):
        """Com Ctrl (show_confirm=True), deve exibir diálogo de confirmação."""
        dest_dir = os.path.join(self.test_dir, "destino")
        os.makedirs(dest_dir, exist_ok=True)
        src_file = os.path.join(self.test_dir, "arq.txt")
        with open(src_file, "w") as f:
            f.write("conteudo")

        with patch("qdir.pane.copy_or_move_items", return_value=(1, [])) as mock_copy, \
             patch.object(QMessageBox, "exec") as mock_msg_exec, \
             patch.object(QMessageBox, "clickedButton") as mock_clicked:
            mock_clicked.return_value = MagicMock()
            # Finge que o usuário clicou 'Não'
            self.pane.handle_files_dropped([src_file], dest_dir, is_move=False, show_confirm=True)
            mock_msg_exec.assert_called_once()
            mock_copy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
