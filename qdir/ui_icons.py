"""
Gerador de Ícones da Interface (UI Icons) do QDir Linux.
Produz ícones vetoriais de alto contraste que se adaptam automaticamente à paleta
ativa (tema escuro ou claro), incluindo estados ativos e desabilitados.
"""

from typing import Optional, Union

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QApplication


def _get_adaptive_color(custom_color: Optional[Union[QColor, str]] = None) -> QColor:
    """Determina a cor ideal do ícone baseada na luminância da paleta atual."""
    if custom_color is not None:
        return QColor(custom_color)

    app = QApplication.instance()
    if app:
        pal = app.palette()
        # Avalia a luminância do botão/janela
        bg = pal.color(pal.ColorRole.Button)
        lum = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
        # Se fundo escuro, ícone branco de alto contraste; se fundo claro, cinza escuro
        return QColor(255, 255, 255) if lum < 135 else QColor(34, 34, 34)

    return QColor(255, 255, 255)


def get_ui_icon(icon_name: str, color: Optional[Union[QColor, str]] = None, size: int = 24) -> QIcon:
    """
    Gera um QIcon vetorial nítido e adaptativo para a interface.
    
    Tipos suportados:
    - 'back': seta/chevron para a esquerda
    - 'fwd': seta/chevron para a direita
    - 'up': seta/chevron para cima (subir pasta)
    - 'refresh': seta circular de recarregamento
    - 'terminal': prompt de comando '>_'
    - 'export': bandeja com seta para exportação
    - 'session': disquete / salvar sessão
    """
    base_color = _get_adaptive_color(color)
    icon_name = icon_name.lower().strip()

    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(base_color)
    pen.setWidthF(2.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    w, h = float(size), float(size)

    if icon_name in ("back", "arrow_back", "left"):
        path = QPainterPath()
        path.moveTo(w * 0.62, h * 0.25)
        path.lineTo(w * 0.35, h * 0.5)
        path.lineTo(w * 0.62, h * 0.75)
        p.drawPath(path)

    elif icon_name in ("fwd", "forward", "arrow_forward", "right"):
        path = QPainterPath()
        path.moveTo(w * 0.38, h * 0.25)
        path.lineTo(w * 0.65, h * 0.5)
        path.lineTo(w * 0.38, h * 0.75)
        p.drawPath(path)

    elif icon_name in ("up", "arrow_up"):
        path = QPainterPath()
        path.moveTo(w * 0.25, h * 0.62)
        path.lineTo(w * 0.5, h * 0.35)
        path.lineTo(w * 0.75, h * 0.62)
        p.drawPath(path)

    elif icon_name in ("refresh", "reload"):
        pen.setWidthF(1.8)
        p.setPen(pen)
        rect = QRectF(w * 0.18, h * 0.18, w * 0.64, h * 0.64)
        p.drawArc(rect, int(35 * 16), int(280 * 16))
        # Ponta de flecha no final do arco
        p.setBrush(QBrush(base_color))
        arrow = QPainterPath()
        arrow.moveTo(w * 0.72, h * 0.18)
        arrow.lineTo(w * 0.86, h * 0.38)
        arrow.lineTo(w * 0.64, h * 0.35)
        arrow.closeSubpath()
        p.drawPath(arrow)

    elif icon_name in ("terminal", "term"):
        pen.setWidthF(2.0)
        p.setPen(pen)
        path = QPainterPath()
        path.moveTo(w * 0.22, h * 0.28)
        path.lineTo(w * 0.44, h * 0.5)
        path.lineTo(w * 0.22, h * 0.72)
        p.drawPath(path)
        p.drawLine(QPointF(w * 0.52, h * 0.72), QPointF(w * 0.78, h * 0.72))

    elif icon_name in ("export", "save_export"):
        pen.setWidthF(1.8)
        p.setPen(pen)
        # Bandeja
        tray = QPainterPath()
        tray.moveTo(w * 0.2, h * 0.55)
        tray.lineTo(w * 0.2, h * 0.8)
        tray.lineTo(w * 0.8, h * 0.8)
        tray.lineTo(w * 0.8, h * 0.55)
        p.drawPath(tray)
        # Seta para cima
        p.drawLine(QPointF(w * 0.5, h * 0.65), QPointF(w * 0.5, h * 0.2))
        path = QPainterPath()
        path.moveTo(w * 0.32, h * 0.38)
        path.lineTo(w * 0.5, h * 0.2)
        path.lineTo(w * 0.68, h * 0.38)
        p.drawPath(path)

    elif icon_name in ("session", "save_session", "disk"):
        pen.setWidthF(1.8)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(w * 0.2, h * 0.2, w * 0.6, h * 0.6), 2, 2)
        p.fillRect(QRectF(w * 0.35, h * 0.2, w * 0.3, h * 0.25), base_color)
        p.drawRect(QRectF(w * 0.3, h * 0.55, w * 0.4, h * 0.25))

    p.end()

    # Monta o QIcon com estado Normal e Disabled (com opacidade balanceada)
    icon = QIcon()
    icon.addPixmap(pix, QIcon.Mode.Normal)

    # Estado desabilitado legível (35% de opacidade em vez de invisível/preto)
    dis_pix = QPixmap(size, size)
    dis_pix.fill(Qt.GlobalColor.transparent)
    dp = QPainter(dis_pix)
    dp.setOpacity(0.35)
    dp.drawPixmap(0, 0, pix)
    dp.end()
    icon.addPixmap(dis_pix, QIcon.Mode.Disabled)

    return icon
