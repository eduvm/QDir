import os
import sys
import shutil
import tarfile
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from qdir.color_engine import ColorEngine
from qdir.pane import QDirPane
from qdir.file_ops import (
    is_archive_file,
    get_archive_base_name,
    extract_archive,
)


class TestArchiveExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="qdir_archive_test_")
        self.color_engine = ColorEngine()
        self.pane = QDirPane(pane_id=1, color_engine=self.color_engine)
        self.pane.navigate_to(self.test_dir)

    def tearDown(self):
        self.pane.deleteLater()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_is_archive_file(self):
        """Verifica a identificação de extensões de arquivos compactados."""
        zip_path = os.path.join(self.test_dir, "test.zip")
        txt_path = os.path.join(self.test_dir, "test.txt")
        rar_path = os.path.join(self.test_dir, "test.rar")
        targz_path = os.path.join(self.test_dir, "test.tar.gz")

        with open(zip_path, "w") as f:
            f.write("dummy")
        with open(txt_path, "w") as f:
            f.write("dummy")
        with open(rar_path, "w") as f:
            f.write("dummy")
        with open(targz_path, "w") as f:
            f.write("dummy")

        self.assertTrue(is_archive_file(zip_path))
        self.assertTrue(is_archive_file(rar_path))
        self.assertTrue(is_archive_file(targz_path))
        self.assertFalse(is_archive_file(txt_path))
        self.assertFalse(is_archive_file(self.test_dir))  # Pasta não é arquivo compactado
        self.assertFalse(is_archive_file("/caminho/inexistente.zip"))

    def test_get_archive_base_name(self):
        """Verifica remoção correta de extensões compostas e simples."""
        self.assertEqual(get_archive_base_name("projeto.zip"), "projeto")
        self.assertEqual(get_archive_base_name("/caminho/meu_arquivo.tar.gz"), "meu_arquivo")
        self.assertEqual(get_archive_base_name("dados.tar.bz2"), "dados")
        self.assertEqual(get_archive_base_name("fotos.tar.xz"), "fotos")
        self.assertEqual(get_archive_base_name("pacote.tgz"), "pacote")
        self.assertEqual(get_archive_base_name("backup.rar"), "backup")
        self.assertEqual(get_archive_base_name("archive.7z"), "archive")

    def test_extract_here_zip(self):
        """Testa a extração no diretório atual ('Extrair aqui')."""
        zip_path = os.path.join(self.test_dir, "meu_zip.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("arquivo1.txt", "conteudo 1")
            zf.writestr("subpasta/arquivo2.txt", "conteudo 2")

        # Chama extract_archives sem subpasta (Extrair aqui)
        self.pane.extract_archives([zip_path], into_subfolder=False)

        extracted_f1 = os.path.join(self.test_dir, "arquivo1.txt")
        extracted_f2 = os.path.join(self.test_dir, "subpasta", "arquivo2.txt")

        self.assertTrue(os.path.isfile(extracted_f1))
        self.assertTrue(os.path.isfile(extracted_f2))

        with open(extracted_f1, "r") as f:
            self.assertEqual(f.read(), "conteudo 1")

    def test_extract_to_subfolder_zip(self):
        """Testa a extração criando um subdiretório com o nome do arquivo."""
        zip_path = os.path.join(self.test_dir, "projeto_novo.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("info.txt", "dados do projeto")

        # Chama extract_archives com into_subfolder=True
        self.pane.extract_archives([zip_path], into_subfolder=True)

        target_folder = os.path.join(self.test_dir, "projeto_novo")
        self.assertTrue(os.path.isdir(target_folder))

        extracted_file = os.path.join(target_folder, "info.txt")
        self.assertTrue(os.path.isfile(extracted_file))
        with open(extracted_file, "r") as f:
            self.assertEqual(f.read(), "dados do projeto")

    def test_extract_tar_gz(self):
        """Testa extração de tar.gz com subpasta."""
        tar_path = os.path.join(self.test_dir, "pacote.tar.gz")
        dummy_file = os.path.join(self.test_dir, "temp_item.txt")
        with open(dummy_file, "w") as f:
            f.write("conteudo tar")

        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(dummy_file, arcname="item_tar.txt")
        os.remove(dummy_file)

        self.pane.extract_archives([tar_path], into_subfolder=True)

        target_dir = os.path.join(self.test_dir, "pacote")
        self.assertTrue(os.path.isdir(target_dir))
        self.assertTrue(os.path.isfile(os.path.join(target_dir, "item_tar.txt")))


if __name__ == "__main__":
    unittest.main()
