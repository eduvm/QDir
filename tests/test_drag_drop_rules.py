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
from PyQt6.QtWidgets import QApplication

from qdir.color_engine import ColorEngine
from qdir.pane import QDirPane
from qdir.ui_icons import get_drag_cursor_pixmap


class TestDragDropRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="qdir_dnd_test_")
        self.pane = QDirPane(1, ColorEngine())
        self.pane.navigate_to(self.test_dir)

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

    def test_file_table_view_drag_enter_and_move_no_ctrl(self):
        """Sem modificadores, ação deve ser CopyAction."""
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

    def test_file_table_view_drag_enter_and_move_with_ctrl(self):
        """Com Ctrl segurado, ação deve ser MoveAction."""
        view = self.pane.table_view
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(os.path.join(self.test_dir, "file.txt"))])

        enter_event = QDragEnterEvent(
            QPointF(10, 10).toPoint(),
            Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier,
        )

        with patch.object(QApplication, "keyboardModifiers", return_value=Qt.KeyboardModifier.ControlModifier):
            view.dragEnterEvent(enter_event)
            self.assertEqual(enter_event.dropAction(), Qt.DropAction.MoveAction)

            move_event = QDragMoveEvent(
                QPointF(10, 10).toPoint(),
                Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.ControlModifier,
            )
            view.dragMoveEvent(move_event)
            self.assertEqual(move_event.dropAction(), Qt.DropAction.MoveAction)

    def test_drop_event_determines_is_move_correctly(self):
        view = self.pane.table_view
        mime = QMimeData()
        test_file = os.path.join(self.test_dir, "source.txt")
        with open(test_file, "w") as f:
            f.write("test")
        mime.setUrls([QUrl.fromLocalFile(test_file)])

        with patch.object(self.pane, "handle_files_dropped") as mock_handle:
            # 1. Drop sem Ctrl -> is_move=False (Copiar)
            drop_event_copy = QDropEvent(
                QPointF(10, 10),
                Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            drop_event_copy.setDropAction(Qt.DropAction.CopyAction)

            with patch.object(QApplication, "keyboardModifiers", return_value=Qt.KeyboardModifier.NoModifier):
                view.dropEvent(drop_event_copy)
                self.app.processEvents()

            mock_handle.assert_called_once()
            args, _ = mock_handle.call_args
            # args: (paths, target_dir, is_move)
            self.assertFalse(args[2], "Sem Ctrl, is_move deve ser False (Copiar)")

            mock_handle.reset_mock()

            # 2. Drop com Ctrl -> is_move=True (Mover)
            drop_event_move = QDropEvent(
                QPointF(10, 10),
                Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.ControlModifier,
            )
            drop_event_move.setDropAction(Qt.DropAction.MoveAction)

            with patch.object(QApplication, "keyboardModifiers", return_value=Qt.KeyboardModifier.ControlModifier):
                view.dropEvent(drop_event_move)
                self.app.processEvents()

            mock_handle.assert_called_once()
            args, _ = mock_handle.call_args
            self.assertTrue(args[2], "Com Ctrl, is_move deve ser True (Mover)")


if __name__ == "__main__":
    unittest.main()
