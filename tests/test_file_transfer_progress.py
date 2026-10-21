import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from qdir.file_ops import (
    copy_or_move_items,
    format_time_remaining,
    format_size,
    FileTransferWorker,
    FileTransferProgressDialog,
    OperationCancelled,
)
from qdir.main_window import QDirMainWindow


class TestFileTransferProgress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.src_dir = tempfile.mkdtemp(prefix="qdir_transfer_src_")
        self.dst_dir = tempfile.mkdtemp(prefix="qdir_transfer_dst_")

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    def test_format_time_remaining(self):
        self.assertEqual(format_time_remaining(0), "Concluindo...")
        self.assertEqual(format_time_remaining(-10), "Concluindo...")
        self.assertIn("s", format_time_remaining(45))
        self.assertIn("min", format_time_remaining(125))
        self.assertIn("h", format_time_remaining(3700))

    def test_format_size_non_negative(self):
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(-500), "0 B")
        self.assertEqual(format_size(1024), "1.0 KB")
        self.assertEqual(format_size(1024 * 1024 * 1024), "1.00 GB")
        # 14 GB file
        self.assertIn("GB", format_size(14 * 1024 * 1024 * 1024))

    def test_large_64bit_size_no_overflow(self):
        """Verifica que tamanhos maiores que 2GB (64-bit) não sofrem overflow 32-bit no sinal."""
        worker = FileTransferWorker([], is_move=False)
        received = []
        worker.progress_updated.connect(lambda done, total, name, speed, eta: received.append((done, total, speed, eta)))

        # Simula progresso de arquivo de 14 GB (15,032,385,536 bytes)
        size_14gb = 14 * 1024 * 1024 * 1024
        worker.total_bytes = size_14gb
        worker._bytes_copied = 3 * 1024 * 1024 * 1024  # 3 GB (> 2GB signed 32-bit limit)
        worker._start_time = 1000.0
        worker._last_speed_time = 1000.0
        worker._last_speed_bytes = 0
        worker._last_emit_time = 0.0

        worker._emit_progress("large_model.safetensors", force=True)

        self.assertEqual(len(received), 1)
        done, total, speed, eta = received[0]
        self.assertEqual(done, 3 * 1024 * 1024 * 1024)
        self.assertGreater(done, 0)
        self.assertEqual(total, size_14gb)
        self.assertGreater(total, 0)
        self.assertGreaterEqual(speed, 0.0)
        self.assertGreaterEqual(eta, 0.0)

    def test_copy_single_large_file_with_progress(self):
        src_file = os.path.join(self.src_dir, "large_file.bin")
        # 3 MB file to ensure multiple chunks are transferred
        data = b"X" * (3 * 1024 * 1024)
        with open(src_file, "wb") as f:
            f.write(data)

        progress_calls = []

        worker = FileTransferWorker([(src_file, os.path.join(self.dst_dir, "large_file.bin"))], is_move=False)
        worker.progress_updated.connect(lambda done, total, name, speed, eta: progress_calls.append((done, total, name)))
        worker.run()

        self.assertEqual(worker.success_count, 1)
        self.assertEqual(len(worker.errors), 0)
        dst_file = os.path.join(self.dst_dir, "large_file.bin")
        self.assertTrue(os.path.exists(dst_file))
        self.assertEqual(os.path.getsize(dst_file), len(data))
        self.assertGreater(len(progress_calls), 0)
        last_progress = progress_calls[-1]
        self.assertEqual(last_progress[0], len(data))  # bytes_done
        self.assertEqual(last_progress[1], len(data))  # total_bytes

    def test_copy_directory_with_subfolders(self):
        sub_dir = os.path.join(self.src_dir, "nested_folder", "sub")
        os.makedirs(sub_dir, exist_ok=True)
        f1 = os.path.join(self.src_dir, "file1.txt")
        f2 = os.path.join(sub_dir, "file2.txt")
        with open(f1, "w") as f:
            f.write("content 1")
        with open(f2, "w") as f:
            f.write("content 2")

        target_dir = os.path.join(self.dst_dir, "copied_tree")
        count, errors = copy_or_move_items([self.src_dir], self.dst_dir, is_move=False, show_progress=False)

        self.assertEqual(count, 1)
        self.assertEqual(len(errors), 0)
        expected_dst_tree = os.path.join(self.dst_dir, os.path.basename(self.src_dir))
        self.assertTrue(os.path.isdir(expected_dst_tree))
        self.assertTrue(os.path.exists(os.path.join(expected_dst_tree, "file1.txt")))
        self.assertTrue(os.path.exists(os.path.join(expected_dst_tree, "nested_folder", "sub", "file2.txt")))

    def test_move_file(self):
        src_file = os.path.join(self.src_dir, "file_to_move.txt")
        with open(src_file, "w") as f:
            f.write("move me")

        count, errors = copy_or_move_items([src_file], self.dst_dir, is_move=True, show_progress=False)

        self.assertEqual(count, 1)
        self.assertEqual(len(errors), 0)
        dst_file = os.path.join(self.dst_dir, "file_to_move.txt")
        self.assertTrue(os.path.exists(dst_file))
        self.assertFalse(os.path.exists(src_file))

    def test_cancellation_cleans_up_partial_file(self):
        src_file = os.path.join(self.src_dir, "to_cancel.bin")
        # 5 MB file
        with open(src_file, "wb") as f:
            f.write(b"Z" * (5 * 1024 * 1024))

        dst_file = os.path.join(self.dst_dir, "to_cancel.bin")
        worker = FileTransferWorker([(src_file, dst_file)], is_move=False)

        # Cancel immediately on first progress update
        def on_progress(done, total, name, speed, eta):
            worker.cancel()

        worker.progress_updated.connect(on_progress)
        worker.run()

        # Destination file should have been cleaned up because transfer was cancelled mid-way
        self.assertTrue(worker.is_cancelled())
        self.assertFalse(os.path.exists(dst_file))
        self.assertEqual(worker.success_count, 0)

    def test_main_window_status_bar_transfer_progress(self):
        """Verifica que a MainWindow possui o container de progresso na barra de status."""
        win = QDirMainWindow()
        self.assertIsNotNone(win.progress_container)
        self.assertIsNotNone(win.transfer_progress_bar)
        self.assertIsNotNone(win.lbl_transfer_info)
        self.assertIsNotNone(win.btn_transfer_cancel)
        self.assertFalse(win.progress_container.isVisible())

        # Inicia progresso de transferência
        worker = FileTransferWorker([], is_move=False)
        win.start_transfer_progress(worker, is_move=False)
        self.assertTrue(win.progress_container.isVisible())
        self.assertTrue(win.is_transferring)

        # Atualiza progresso
        win.on_transfer_progress_updated(50 * 1024 * 1024, 100 * 1024 * 1024, "video.mp4", 10 * 1024 * 1024, 5.0)
        self.assertEqual(win.transfer_progress_bar.value(), 50)
        self.assertIn("video.mp4", win.lbl_transfer_info.text())
        self.assertIn("10.0 MB/s", win.lbl_transfer_info.text())

        # Finaliza transferência
        win.on_transfer_finished(1, [], False)
        self.assertFalse(win.progress_container.isVisible())
        self.assertFalse(win.is_transferring)
        win.deleteLater()


if __name__ == "__main__":
    unittest.main()
