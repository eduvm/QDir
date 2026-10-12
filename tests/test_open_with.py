"""
Testes automatizados para o recurso 'Abrir com' e gerenciamento de aplicativos padrão no QDir Linux.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QMenu
from PyQt6.QtCore import QPoint
from qdir.color_engine import ColorEngine
from qdir.mime_manager import DesktopApp, MimeManager
from qdir.open_with_dialog import OpenWithDialog
from qdir.pane import QDirPane


class TestOpenWith(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="qdir_open_with_test_")
        self.sample_video = os.path.join(self.test_dir, "video.mp4")
        self.sample_text = os.path.join(self.test_dir, "notes.txt")
        with open(self.sample_video, "w") as f:
            f.write("fake video data")
        with open(self.sample_text, "w") as f:
            f.write("fake text data")

        self.color_engine = ColorEngine()
        self.pane = QDirPane(pane_id=1, color_engine=self.color_engine)
        self.pane.navigate_to(self.test_dir)

    def tearDown(self):
        self.pane.deleteLater()
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_mime_type_detection(self):
        """Verifica a detecção de tipos MIME e descrições para diferentes extensões."""
        mime_video, desc_video = MimeManager.get_mime_type(self.sample_video)
        self.assertEqual(mime_video, "video/mp4")
        self.assertTrue(len(desc_video) > 0)

        mime_text, desc_text = MimeManager.get_mime_type(self.sample_text)
        self.assertEqual(mime_text, "text/plain")
        self.assertTrue(len(desc_text) > 0)

    def test_get_apps_for_file_and_default_flag(self):
        """Verifica se aplicativos são descobertos para o arquivo de vídeo e se o padrão é sinalizado."""
        apps = MimeManager.get_apps_for_file(self.sample_video)
        self.assertIsInstance(apps, list)
        self.assertTrue(len(apps) > 0, "Deveria encontrar ao menos 1 aplicativo para video/mp4 no sistema")

        # Verifica se o primeiro é o padrão (se houver padrão)
        has_default = any(a.is_default for a in apps)
        if has_default:
            self.assertTrue(apps[0].is_default)
            self.assertIn("(Padrão)", apps[0].display_title())

    def test_set_default_app_for_mime_isolated(self):
        """Testa a escrita de preferência padrão em um ambiente isolado com mock de ~/.config/mimeapps.list."""
        fake_config_dir = os.path.join(self.test_dir, "fake_config")
        fake_mimeapps = os.path.join(fake_config_dir, "mimeapps.list")

        with patch("os.path.expanduser", return_value=fake_config_dir):
            success = MimeManager.set_default_app_for_mime("mpv.desktop", "video/mp4")
            self.assertTrue(success)
            self.assertTrue(os.path.exists(fake_mimeapps))

            with open(fake_mimeapps, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("[Default Applications]", content)
            self.assertIn("video/mp4=mpv.desktop", content)
            self.assertIn("[Added Associations]", content)
            self.assertIn("video/mp4=mpv.desktop;", content)

    def test_expand_exec_command(self):
        """Verifica a expansão de argumentos %f, %F, %u, %U da especificação FreeDesktop."""
        paths = [self.sample_video, self.sample_text]

        # %f (único arquivo)
        res1 = MimeManager._expand_exec_command("vlc --started-from-file %f", paths)
        self.assertEqual(res1, ["vlc", "--started-from-file", self.sample_video])

        # %F (múltiplos arquivos)
        res2 = MimeManager._expand_exec_command("mpv %F", paths)
        self.assertEqual(res2, ["mpv", self.sample_video, self.sample_text])

        # Sem códigos (deve anexar os arquivos)
        res3 = MimeManager._expand_exec_command("subl", paths)
        self.assertEqual(res3, ["subl", self.sample_video, self.sample_text])

    @patch("subprocess.Popen")
    def test_launch_app_execution(self, mock_popen):
        """Testa o disparo de execução de aplicativo com argumentos."""
        app = DesktopApp(
            desktop_id="test.desktop",
            name="Test Player",
            exec_cmd="testplayer %f",
            icon_name="",
        )
        success = MimeManager.launch_app(app, [self.sample_video])
        self.assertTrue(success)
        mock_popen.assert_called()

    def test_open_with_dialog_ui(self):
        """Testa o diálogo OpenWithDialog, preenchimento de categorias, filtro de busca e seleção."""
        dlg = OpenWithDialog([self.sample_video])
        self.assertEqual(dlg.mime_type, "video/mp4")
        self.assertTrue(dlg.group_rec.childCount() > 0)

        # Testa filtro de busca
        dlg._filter_apps("vlc")
        # Se VLC existir, o grupo de recomendados deve continuar visível
        self.assertFalse(dlg.group_rec.isHidden())

        dlg._filter_apps("")  # Limpa busca

        # Testa seleção
        sel_app = dlg.get_selected_app()
        self.assertIsNotNone(sel_app)
        self.assertTrue(dlg.btn_open.isEnabled())

        # Testa alternância de checkbox padrão
        self.assertFalse(dlg.chk_default.isChecked())
        dlg.chk_default.setChecked(True)
        self.assertTrue(dlg.chk_default.isChecked())

        dlg.deleteLater()

    def test_context_menu_has_open_with_for_files(self):
        """Verifica se o menu de contexto cria o submenu 'Abrir com' quando um arquivo está selecionado."""
        # Força seleção do arquivo de vídeo no painel
        self.pane.get_selected_paths = MagicMock(return_value=[self.sample_video])

        # Intercepta QMenu.exec para inspecionar as ações adicionadas sem abrir a janela modal
        created_menu_actions = []

        real_qmenu = QMenu
        captured_menus = []

        class InterceptedMenu(real_qmenu):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                captured_menus.append(self)

            def exec(self, *args, **kwargs):
                return None

        with patch("qdir.pane.QMenu", InterceptedMenu):
            self.pane.show_context_menu(QPoint(10, 10))

        self.assertTrue(len(captured_menus) > 0)
        menu_instance = captured_menus[0]
        for act in menu_instance.actions():
            created_menu_actions.append(act.text())
            if act.menu():
                for sub_act in act.menu().actions():
                    created_menu_actions.append(f"  -> {sub_act.text()}")

        # Deve conter 'Abrir' e 'Abrir com'
        self.assertIn("Abrir", created_menu_actions)
        self.assertIn("Abrir com", created_menu_actions)
        # O submenu de 'Abrir com' deve conter a opção de diálogo
        self.assertIn("  -> Escolher outro aplicativo...", created_menu_actions)


if __name__ == "__main__":
    unittest.main()
