import sys

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPainter, QSurfaceFormat, QFocusEvent
from PyQt5.QtWidgets import QGraphicsView, QRubberBand, QOpenGLWidget, QFormLayout, QSizePolicy

def isRemoteSession():
    """Detect Remote session in windows"""

    if sys.platform.startswith('win'):
        # See https://msdn.microsoft.com/en-us/library/aa380798%28v=vs.85%29.aspx
        from win32api import GetSystemMetrics # pylint: disable=import-error
        if GetSystemMetrics(0x1000) != 0:  # 0x1000 is SM_REMOTESESSION
            return True
    return False


class MiniMapGraphicsView(QGraphicsView):

    def __init__(self, parent):
        super().__init__(parent)
        
        self._drag_start_pos = None
        
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(200, 200)
        self.viewport().setFixedSize(self.contentsRect().size())
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setInteractive(False)
        self.setFocusProxy(parent)
        
        self.band = QRubberBand(QRubberBand.Rectangle, self)
        self.band.hide()
        
    def centerOn(self, pos):
        if self.band.isVisible():
            self.parent().centerOn(self.mapToScene(pos))
            rect = self.band.geometry()
            rect.moveCenter(pos)
            self.band.setGeometry(rect)
        
    def mousePressEvent(self, event):
        if self.band.isVisible() and event.button() == Qt.LeftButton:
            rect = self.band.geometry()
            if event.pos() in rect:
                self._drag_start_pos = event.pos()
            else:
                self.centerOn(event.pos())
    
    def mouseMoveEvent(self, event):
        if self.band.isVisible() and event.buttons() == Qt.MouseButtons(Qt.LeftButton) and self._drag_start_pos is not None:
            self.centerOn(event.pos())
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.band.isVisible():
            self.viewport().unsetCursor()
            self._drag_start_pos = None

    def adjustRubberband(self):
        rect = self.parent().mapToScene(self.parent().rect()).boundingRect()
        if not rect.contains(self.scene().sceneRect()):
            rect = self.mapFromScene(rect).boundingRect()
            self.band.setGeometry(rect)
            self.band.show()
        else:
            self.band.hide()
        
    def zoomToFit(self):
        self.fitInView(self.scene().sceneRect().adjusted(-20, -20, 20, 20), Qt.KeepAspectRatio)


class NetworkView(QGraphicsView):

    focusedIn = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        if not isRemoteSession():
            fmt = QSurfaceFormat()
            fmt.setSamples(4)
            self.setViewport(QOpenGLWidget())
            self.viewport().setFormat(fmt)
            self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        else:
            self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)

        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setFormAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.minimap = MiniMapGraphicsView(self)
        layout.addWidget(self.minimap)
        self.setLayout(layout)

        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setOptimizationFlags(QGraphicsView.DontSavePainterState | QGraphicsView.DontAdjustForAntialiasing)

        self.setStyleSheet(
            """NetworkView:focus {
                border: 3px solid palette(highlight);
            }""")
        
    def setScene(self, scene):
        super().setScene(scene)
        self.minimap.setScene(scene)
        
        # Connect events
        scene.scaleChanged.connect(self.on_scale_changed)
        scene.layoutChanged.connect(self.on_layout_changed)
            
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.itemAt(event.pos()):
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        elif event.button() == Qt.RightButton:
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.setRubberBandSelectionMode(Qt.IntersectsItemBoundingRect)
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        
        if event.button() == Qt.LeftButton:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().unsetCursor()
        elif event.button() == Qt.RightButton:
            self.setDragMode(QGraphicsView.NoDrag)

    def mouseMoveEvent(self, event):
        if self.dragMode() == QGraphicsView.ScrollHandDrag:
            self.minimap.adjustRubberband()

        super().mouseMoveEvent(event)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.minimap.adjustRubberband()

    def focusInEvent(self, event: QFocusEvent):
        super().focusInEvent(event)
        self.focusedIn.emit()

    def on_scale_changed(self):
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-30, -30, 30, 30))
        self.minimap.zoomToFit()

    def on_layout_changed(self):
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-30, -30, 30, 30))
        self.zoomToFit()
        self.minimap.zoomToFit()
        
    def translate(self, x, y):
        super().translate(x, y)
        self.minimap.adjustRubberband()
        
    def scale(self, factor_x, factor_y):
        super().scale(factor_x, factor_y)
        self.minimap.adjustRubberband()
                
    def zoomToFit(self):
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
        self.minimap.adjustRubberband()
        
    def wheelEvent(self, event):
        self.scaleView(2**(event.angleDelta().y() / 240.0))

    def scaleView(self, scaleFactor):
        self.scale(scaleFactor, scaleFactor)
        
    def updateVisibleItems(self):
        for item in self.items(self.viewport().rect()):
            item.update()
