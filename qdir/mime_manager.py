"""
Módulo MimeManager do QDir Linux.
Gerencia tipos MIME, descoberta de aplicativos compatíveis (.desktop),
execução de arquivos com aplicativos específicos, e definição de aplicativo
padrão do sistema via especificações FreeDesktop (XDG e GIO).
"""

import configparser
from dataclasses import dataclass, field
import os
import shlex
import shutil
import subprocess
from typing import Dict, List, Optional, Set, Tuple, Union

from PyQt6.QtCore import QMimeDatabase, QMimeType, QUrl
from PyQt6.QtGui import QDesktopServices


@dataclass
class DesktopApp:
    """Representa um aplicativo desktop Linux registrado."""
    desktop_id: str
    name: str
    exec_cmd: str
    icon_name: str = ""
    comment: str = ""
    file_path: str = ""
    mimes: List[str] = field(default_factory=list)
    is_default: bool = False
    is_custom: bool = False

    def display_title(self) -> str:
        """Retorna o título formatado para menus e diálogos."""
        if self.is_default:
            return f"{self.name} (Padrão)"
        return self.name


class MimeManager:
    """Gerenciador de tipos MIME e aplicativos do sistema."""

    _cached_apps: Optional[Dict[str, DesktopApp]] = None
    _cached_mime_map: Optional[Dict[str, Set[str]]] = None

    @classmethod
    def get_mime_database(cls) -> QMimeDatabase:
        return QMimeDatabase()

    @classmethod
    def get_mime_type(cls, filepath: str) -> Tuple[str, str]:
        """
        Retorna o nome do tipo MIME e a descrição amigável para o arquivo.
        Exemplo: ('video/mp4', 'vídeo MPEG-4')
        """
        db = cls.get_mime_database()
        mime: QMimeType = db.mimeTypeForFile(filepath, QMimeDatabase.MatchMode.MatchDefault)
        if mime.isValid() and mime.name() != "application/octet-stream":
            name = mime.name()
            comment = mime.comment() or name
            return name, comment

        name = mime.name() if mime.isValid() else "application/octet-stream"
        comment = mime.comment() or name
        return name, comment

    @classmethod
    def get_desktop_directories(cls) -> List[str]:
        """Retorna a lista de diretórios padrão onde residem arquivos .desktop."""
        dirs = []
        data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        dirs.append(os.path.join(data_home, "applications"))

        data_dirs = os.environ.get("XDG_DATA_DIRS")
        if data_dirs:
            for p in data_dirs.split(":"):
                if p.strip():
                    dirs.append(os.path.join(p.strip(), "applications"))
        else:
            dirs.extend([
                "/usr/local/share/applications",
                "/usr/share/applications",
            ])

        dirs.extend([
            "/var/lib/flatpak/exports/share/applications",
            os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
            "/var/lib/snapd/desktop/applications",
        ])

        unique_dirs = []
        for d in dirs:
            if os.path.isdir(d) and d not in unique_dirs:
                unique_dirs.append(d)
        return unique_dirs

    @classmethod
    def reload_apps_cache(cls):
        """Varre os diretórios do sistema e carrega o catálogo de aplicativos .desktop."""
        apps: Dict[str, DesktopApp] = {}
        mime_map: Dict[str, Set[str]] = {}

        for app_dir in cls.get_desktop_directories():
            try:
                for root, _, files in os.walk(app_dir):
                    for filename in files:
                        if not filename.endswith(".desktop"):
                            continue

                        desktop_id = filename
                        if desktop_id in apps:
                            continue

                        fpath = os.path.join(root, filename)
                        app = cls._parse_desktop_file(fpath, desktop_id)
                        if app:
                            apps[desktop_id] = app
                            for m in app.mimes:
                                m_clean = m.strip().lower()
                                if m_clean:
                                    mime_map.setdefault(m_clean, set()).add(desktop_id)
            except Exception:
                continue

        cls._cached_apps = apps
        cls._cached_mime_map = mime_map

    @classmethod
    def _parse_desktop_file(cls, fpath: str, desktop_id: str) -> Optional[DesktopApp]:
        """Analisa um arquivo .desktop individual e retorna um objeto DesktopApp válido."""
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
                cp.read_file(fp)

            if not cp.has_section("Desktop Entry"):
                return None

            entry_type = cp.get("Desktop Entry", "Type", fallback="Application")
            if entry_type != "Application":
                return None

            no_display = cp.get("Desktop Entry", "NoDisplay", fallback="false").strip().lower() == "true"
            hidden = cp.get("Desktop Entry", "Hidden", fallback="false").strip().lower() == "true"
            if no_display or hidden:
                return None

            name = (
                cp.get("Desktop Entry", "Name[pt_BR]", fallback=None)
                or cp.get("Desktop Entry", "Name[pt]", fallback=None)
                or cp.get("Desktop Entry", "Name", fallback=desktop_id[:-8])
            )

            comment = (
                cp.get("Desktop Entry", "Comment[pt_BR]", fallback=None)
                or cp.get("Desktop Entry", "Comment[pt]", fallback=None)
                or cp.get("Desktop Entry", "Comment", fallback="")
            )

            exec_cmd = cp.get("Desktop Entry", "Exec", fallback="")
            icon_name = cp.get("Desktop Entry", "Icon", fallback="")

            mimes_raw = cp.get("Desktop Entry", "MimeType", fallback="")
            mimes = [m.strip() for m in mimes_raw.split(";") if m.strip()]

            return DesktopApp(
                desktop_id=desktop_id,
                name=name,
                exec_cmd=exec_cmd,
                icon_name=icon_name,
                comment=comment,
                file_path=fpath,
                mimes=mimes,
                is_default=False,
            )
        except Exception:
            return None

    @classmethod
    def get_all_installed_apps(cls) -> List[DesktopApp]:
        """Retorna todos os aplicativos desktop instalados, ordenados alfabeticamente."""
        if cls._cached_apps is None:
            cls.reload_apps_cache()
        apps_list = list(cls._cached_apps.values()) if cls._cached_apps else []
        apps_list.sort(key=lambda a: a.name.lower())
        return apps_list

    @classmethod
    def get_default_app_id_for_mime(cls, mime_type: str) -> Optional[str]:
        """Descobre o desktop_id do aplicativo padrão para o tipo MIME indicado."""
        mime_type = mime_type.strip().lower()

        # 1. Consulta xdg-mime query default
        try:
            out = subprocess.check_output(
                ["xdg-mime", "query", "default", mime_type],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=1,
            ).strip()
            if out and out.endswith(".desktop"):
                return out
        except Exception:
            pass

        # 2. Consulta ~/.config/mimeapps.list
        mimeapps_path = os.path.expanduser("~/.config/mimeapps.list")
        if os.path.exists(mimeapps_path):
            try:
                cp = configparser.ConfigParser(interpolation=None, strict=False)
                with open(mimeapps_path, "r", encoding="utf-8", errors="replace") as fp:
                    cp.read_file(fp)
                if cp.has_section("Default Applications") and cp.has_option("Default Applications", mime_type):
                    val = cp.get("Default Applications", mime_type).strip()
                    val = val.split(";")[0].strip()
                    if val.endswith(".desktop"):
                        return val
            except Exception:
                pass

        # 3. Consulta gio mime
        try:
            out = subprocess.check_output(
                ["gio", "mime", mime_type],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=1,
            )
            for line in out.splitlines():
                line = line.strip()
                if ":" in line and ("padrão" in line.lower() or "default" in line.lower()):
                    val = line.split(":", 1)[1].strip()
                    for ch in ["“", "”", "\"", "'"]:
                        val = val.replace(ch, "")
                    val = val.strip()
                    if val.endswith(".desktop"):
                        return val
        except Exception:
            pass

        return None

    @classmethod
    def get_apps_for_mime(cls, mime_type: str) -> List[DesktopApp]:
        """
        Retorna todos os aplicativos compatíveis com o tipo MIME especificado,
        com o aplicativo padrão no início e marcado com is_default=True.
        """
        if cls._cached_apps is None:
            cls.reload_apps_cache()

        mime_type = mime_type.strip().lower()
        default_id = cls.get_default_app_id_for_mime(mime_type)

        found_ids: Set[str] = set()

        # 1. Consulta gio mime para obter registrados e recomendados
        try:
            out = subprocess.check_output(
                ["gio", "mime", mime_type],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=1,
            )
            for line in out.splitlines():
                line = line.strip()
                if line.endswith(".desktop"):
                    found_ids.add(line)
        except Exception:
            pass

        # 2. Consulta catálogo interno
        if cls._cached_mime_map:
            if mime_type in cls._cached_mime_map:
                found_ids.update(cls._cached_mime_map[mime_type])

            if "/" in mime_type:
                major = mime_type.split("/")[0] + "/*"
                if major in cls._cached_mime_map:
                    found_ids.update(cls._cached_mime_map[major])

            db = cls.get_mime_database()
            q_mime = db.mimeTypeForName(mime_type)
            if q_mime.isValid():
                for alias in q_mime.aliases():
                    alias_clean = alias.strip().lower()
                    if alias_clean in cls._cached_mime_map:
                        found_ids.update(cls._cached_mime_map[alias_clean])

        if default_id:
            found_ids.add(default_id)

        result: List[DesktopApp] = []
        for did in found_ids:
            app = cls._cached_apps.get(did)
            if not app:
                for d in cls.get_desktop_directories():
                    cand = os.path.join(d, did)
                    if os.path.exists(cand):
                        app = cls._parse_desktop_file(cand, did)
                        if app:
                            cls._cached_apps[did] = app
                            break
            if app:
                app_copy = DesktopApp(
                    desktop_id=app.desktop_id,
                    name=app.name,
                    exec_cmd=app.exec_cmd,
                    icon_name=app.icon_name,
                    comment=app.comment,
                    file_path=app.file_path,
                    mimes=app.mimes,
                    is_default=(app.desktop_id == default_id),
                )
                result.append(app_copy)

        result.sort(key=lambda a: (not a.is_default, a.name.lower()))
        return result

    @classmethod
    def get_apps_for_file(cls, filepath: str) -> List[DesktopApp]:
        """Retorna os aplicativos recomendados e compatíveis com o arquivo."""
        mime_name, _ = cls.get_mime_type(filepath)
        return cls.get_apps_for_mime(mime_name)

    @classmethod
    def get_default_app_for_file(cls, filepath: str) -> Optional[DesktopApp]:
        """Retorna o DesktopApp padrão para o arquivo, se existir."""
        mime_name, _ = cls.get_mime_type(filepath)
        default_id = cls.get_default_app_id_for_mime(mime_name)
        if default_id:
            if cls._cached_apps is None:
                cls.reload_apps_cache()
            app = cls._cached_apps.get(default_id)
            if app:
                return DesktopApp(
                    desktop_id=app.desktop_id,
                    name=app.name,
                    exec_cmd=app.exec_cmd,
                    icon_name=app.icon_name,
                    comment=app.comment,
                    file_path=app.file_path,
                    mimes=app.mimes,
                    is_default=True,
                )
        return None

    @classmethod
    def set_default_app_for_mime(cls, desktop_id: str, mime_type: str) -> bool:
        """
        Define o aplicativo desktop_id como o padrão do sistema operacional
        para o tipo MIME indicado.
        Atualiza xdg-mime, gio mime e ~/.config/mimeapps.list.
        """
        desktop_id = desktop_id.strip()
        mime_type = mime_type.strip().lower()
        if not desktop_id.endswith(".desktop"):
            desktop_id += ".desktop"

        success = False

        try:
            res = subprocess.run(
                ["xdg-mime", "default", desktop_id, mime_type],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            if res.returncode == 0:
                success = True
        except Exception:
            pass

        try:
            res = subprocess.run(
                ["gio", "mime", mime_type, desktop_id],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            if res.returncode == 0:
                success = True
        except Exception:
            pass

        try:
            mimeapps_dir = os.path.expanduser("~/.config")
            os.makedirs(mimeapps_dir, exist_ok=True)
            mimeapps_path = os.path.join(mimeapps_dir, "mimeapps.list")

            cp = configparser.ConfigParser(interpolation=None, strict=False)
            if os.path.exists(mimeapps_path):
                with open(mimeapps_path, "r", encoding="utf-8", errors="replace") as fp:
                    cp.read_file(fp)

            if not cp.has_section("Default Applications"):
                cp.add_section("Default Applications")
            cp.set("Default Applications", mime_type, desktop_id)

            if not cp.has_section("Added Associations"):
                cp.add_section("Added Associations")

            existing_added = cp.get("Added Associations", mime_type, fallback="")
            parts = [p.strip() for p in existing_added.split(";") if p.strip()]
            if desktop_id in parts:
                parts.remove(desktop_id)
            parts.insert(0, desktop_id)
            cp.set("Added Associations", mime_type, ";".join(parts) + ";")

            with open(mimeapps_path, "w", encoding="utf-8") as fp:
                cp.write(fp, space_around_delimiters=False)

            success = True
        except Exception:
            pass

        return success

    @classmethod
    def launch_app(cls, app_or_id: Union[DesktopApp, str], filepaths: List[str]) -> bool:
        """
        Executa o aplicativo indicado passando a lista de arquivos.
        Suporta DesktopApp, nome de .desktop ou caminho de executável arbitrário.
        """
        if not filepaths:
            return False

        abs_paths = [os.path.abspath(p) for p in filepaths if os.path.exists(p)]
        if not abs_paths:
            return False

        desktop_id = None
        exec_cmd = None

        if isinstance(app_or_id, DesktopApp):
            desktop_id = app_or_id.desktop_id
            exec_cmd = app_or_id.exec_cmd
        elif isinstance(app_or_id, str):
            if app_or_id.endswith(".desktop"):
                desktop_id = app_or_id
            else:
                exec_cmd = app_or_id

        if desktop_id and shutil.which("gtk-launch"):
            try:
                cmd = ["gtk-launch", desktop_id] + abs_paths
                subprocess.Popen(cmd, start_new_session=True)
                return True
            except Exception:
                pass

        if desktop_id and not exec_cmd:
            if cls._cached_apps is None:
                cls.reload_apps_cache()
            app = cls._cached_apps.get(desktop_id)
            if app:
                exec_cmd = app.exec_cmd

        if exec_cmd:
            try:
                argv = cls._expand_exec_command(exec_cmd, abs_paths)
                if argv:
                    subprocess.Popen(argv, start_new_session=True)
                    return True
            except Exception:
                pass

        if isinstance(app_or_id, str) and not app_or_id.endswith(".desktop"):
            try:
                cmd = [app_or_id] + abs_paths
                subprocess.Popen(cmd, start_new_session=True)
                return True
            except Exception:
                pass

        return False

    @classmethod
    def _expand_exec_command(cls, exec_line: str, paths: List[str]) -> List[str]:
        """
        Expande a string 'Exec' de acordo com a especificação FreeDesktop:
        %f: único arquivo
        %F: múltiplos arquivos
        %u: única URL
        %U: múltiplas URLs
        Remove outros especificadores (%i, %c, %k, etc.).
        """
        tokens = shlex.split(exec_line)
        has_file_spec = False
        expanded: List[str] = []

        urls = [QUrl.fromLocalFile(p).toString() for p in paths]

        for token in tokens:
            if token == "%f":
                expanded.append(paths[0])
                has_file_spec = True
            elif token == "%F":
                expanded.extend(paths)
                has_file_spec = True
            elif token == "%u":
                expanded.append(urls[0])
                has_file_spec = True
            elif token == "%U":
                expanded.extend(urls)
                has_file_spec = True
            elif token.startswith("%"):
                continue
            else:
                if "%f" in token:
                    token = token.replace("%f", paths[0])
                    has_file_spec = True
                if "%u" in token:
                    token = token.replace("%u", urls[0])
                    has_file_spec = True
                expanded.append(token)

        if not has_file_spec:
            expanded.extend(paths)

        return expanded

    @classmethod
    def launch_default(cls, filepath: str) -> bool:
        """
        Abre o arquivo com o aplicativo padrão configurado no sistema / QDir.
        Garante que modificações de padrão feitas no QDir tenham efeito imediato.
        """
        if not os.path.exists(filepath):
            return False

        default_app = cls.get_default_app_for_file(filepath)
        if default_app and cls.launch_app(default_app, [filepath]):
            return True

        if shutil.which("xdg-open"):
            try:
                subprocess.Popen(["xdg-open", filepath], start_new_session=True)
                return True
            except Exception:
                pass

        return QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))
