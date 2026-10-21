import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from qdir.color_engine import ColorEngine
from qdir.pane import QDirPane
from qdir.main_window import QDirMainWindow

class TestTabLocking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="qdir_test_")
        self.sub1 = os.path.join(self.test_dir, "sub1")
        self.sub2 = os.path.join(self.sub1, "sub2")
        os.makedirs(self.sub2, exist_ok=True)
        self.color_engine = ColorEngine()
        self.pane = QDirPane(pane_id=1, color_engine=self.color_engine)
        self.pane.navigate_to(self.test_dir)

    def tearDown(self):
        self.pane.deleteLater()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_initial_state(self):
        self.assertEqual(self.pane.tabs.count(), 1)
        self.assertFalse(self.pane.is_tab_locked(0))
        base_name = os.path.basename(self.test_dir)
        self.assertEqual(self.pane.tabs.tabText(0), base_name)

    def test_tab_lock_and_subdirectories_navigation(self):
        # 1. Bloquear aba na pasta raiz
        self.pane.set_tab_locked(0, True)
        self.assertTrue(self.pane.is_tab_locked(0))
        base_name = os.path.basename(self.test_dir)
        self.assertEqual(self.pane.tabs.tabText(0), f"🔒 {base_name}")

        # 2. Navegar para subdiretório permitido
        self.pane.navigate_to(self.sub1)
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.sub1))
        # Título da aba DEVE continuar sendo o nome fixo da raiz
        self.assertEqual(self.pane.tabs.tabText(0), f"🔒 {base_name}")

        # 3. Navegar para sub-subdiretório permitido
        self.pane.navigate_to(self.sub2)
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.sub2))
        self.assertEqual(self.pane.tabs.tabText(0), f"🔒 {base_name}")

        # 4. Subir (go_up) até a raiz
        self.pane.go_up()
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.sub1))
        self.pane.go_up()
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.test_dir))

        # 5. Tentar subir ALÉM da raiz (deve ignorar)
        self.pane.go_up()
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.test_dir))

        # 6. Tentar navegar diretamente para fora da raiz (deve ignorar)
        parent_dir = os.path.dirname(self.test_dir)
        self.pane.navigate_to(parent_dir)
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.test_dir))
        self.pane.navigate_to("/tmp")
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.test_dir))

    def test_locked_tab_cannot_be_closed(self):
        # Adicionar segunda aba para permitir fechamento
        self.pane.add_tab(self.sub1)
        self.assertEqual(self.pane.tabs.count(), 2)

        # Bloquear a aba 0
        self.pane.set_tab_locked(0, True)
        self.assertTrue(self.pane.is_tab_locked(0))

        # Tentar fechar a aba 0
        self.pane.on_tab_close(0)
        # Deve ser ignorado, contagem permanece 2
        self.assertEqual(self.pane.tabs.count(), 2)

        # Desbloquear aba 0 e tentar fechar novamente
        self.pane.set_tab_locked(0, False)
        self.assertFalse(self.pane.is_tab_locked(0))
        self.pane.on_tab_close(0)
        self.assertEqual(self.pane.tabs.count(), 1)

    def test_persistence_of_locked_tabs(self):
        win = QDirMainWindow()
        test_cfg = os.path.join(self.test_dir, "test_settings.json")
        win.get_settings_path = lambda: test_cfg

        p0 = win.panes[0]
        p0.set_tab_locked(0, False)
        while p0.tabs.count() > 1:
            p0.tabs.removeTab(p0.tabs.count() - 1)
        p0.navigate_to(self.test_dir)
        p0.set_tab_locked(0, True)
        p0.navigate_to(self.sub1)

        win.save_settings()
        self.assertTrue(os.path.exists(test_cfg))

        win2 = QDirMainWindow()
        win2.get_settings_path = lambda: test_cfg
        win2.load_settings()

        p0_restored = win2.panes[0]
        self.assertTrue(p0_restored.is_tab_locked(0))
        self.assertEqual(os.path.realpath(p0_restored.current_path), os.path.realpath(self.sub1))
        base_name = os.path.basename(self.test_dir)
        self.assertEqual(p0_restored.tabs.tabText(0), f"🔒 {base_name}")

        p0_restored.go_up()
        self.assertEqual(os.path.realpath(p0_restored.current_path), os.path.realpath(self.test_dir))
        p0_restored.go_up()
        self.assertEqual(os.path.realpath(p0_restored.current_path), os.path.realpath(self.test_dir))

        win.deleteLater()
        win2.deleteLater()

    def test_locked_tab_external_symlink_navigation(self):
        """
        Valida que links simbólicos apontando para diretórios fora da raiz bloqueada
        (ex: em outro disco) e seus subdiretórios podem ser navegados normalmente,
        enquanto a subida além da raiz e acessos fora do link continuam bloqueados.
        """
        # Cria diretório externo (simulando outro disco/pasta fora da raiz bloqueada)
        ext_disk = tempfile.mkdtemp(prefix="qdir_ext_disk_")
        try:
            ext_models = os.path.join(ext_disk, "models_ext")
            ext_sub = os.path.join(ext_models, "sub_layer")
            os.makedirs(ext_sub, exist_ok=True)

            # Cria link simbólico dentro de self.test_dir apontando para ext_models
            symlink_path = os.path.join(self.test_dir, "symlink_models")
            os.symlink(ext_models, symlink_path)

            # 1. Bloqueia aba na pasta raiz
            self.pane.set_tab_locked(0, True)
            self.assertTrue(self.pane.is_tab_locked(0))
            base_name = os.path.basename(self.test_dir)

            # 2. Navega para dentro do link simbólico
            self.pane.navigate_to(symlink_path)
            self.assertEqual(os.path.abspath(self.pane.current_path), os.path.abspath(symlink_path))
            self.assertEqual(self.pane.tabs.tabText(0), f"🔒 {base_name}")

            # 3. Navega para subdiretório dentro do link simbólico
            sub_in_symlink = os.path.join(symlink_path, "sub_layer")
            self.pane.navigate_to(sub_in_symlink)
            self.assertEqual(os.path.abspath(self.pane.current_path), os.path.abspath(sub_in_symlink))

            # 4. Sobe (go_up) um nível: deve ir para a pasta do link simbólico
            self.pane.go_up()
            self.assertEqual(os.path.abspath(self.pane.current_path), os.path.abspath(symlink_path))

            # 5. Sobe (go_up) mais um nível: deve voltar para a raiz bloqueada
            self.pane.go_up()
            self.assertEqual(os.path.abspath(self.pane.current_path), os.path.abspath(self.test_dir))

            # 6. Tenta subir além da raiz bloqueada: deve permanecer na raiz bloqueada
            self.pane.go_up()
            self.assertEqual(os.path.abspath(self.pane.current_path), os.path.abspath(self.test_dir))

            # 7. Tenta navegar diretamente para pasta externa não vinculada: deve ignorar
            unlinked_dir = tempfile.mkdtemp(prefix="qdir_unlinked_")
            try:
                self.pane.navigate_to(unlinked_dir)
                self.assertEqual(os.path.abspath(self.pane.current_path), os.path.abspath(self.test_dir))
            finally:
                shutil.rmtree(unlinked_dir, ignore_errors=True)

            # 8. Navegação pelo caminho físico do link deve ser traduzida para o caminho lógico
            self.pane.navigate_to(ext_sub)
            self.assertEqual(os.path.abspath(self.pane.current_path), os.path.abspath(sub_in_symlink))

            # 9. Teste de histórico (Voltar e Avançar)
            self.pane.go_back()
            self.assertEqual(os.path.abspath(self.pane.current_path), os.path.abspath(self.test_dir))
            self.pane.go_forward()
            self.assertEqual(os.path.abspath(self.pane.current_path), os.path.abspath(sub_in_symlink))

        finally:
            shutil.rmtree(ext_disk, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
