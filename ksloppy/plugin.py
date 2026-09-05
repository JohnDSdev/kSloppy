"""Krita integration: a non-destructive shape drawing workspace."""
from krita import Krita, Extension
from PyQt5.QtCore import Qt, QPointF, QRectF, QEvent
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QKeySequence
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox, QGraphicsView, QGraphicsScene,
    QShortcut, QMessageBox)
from .geometry import recognize, svg_document

MODES = ['Auto', 'Line', 'Circle', 'Ellipse', 'Rectangle', 'Square', 'Polygon', 'Regular polygon', 'Arc']


class DrawingView(QGraphicsView):
    def __init__(self, owner, background, width, height):
        super().__init__(owner)
        self.owner = owner
        self.setScene(QGraphicsScene(self))
        self.scene().setSceneRect(0, 0, width, height)
        item = self.scene().addPixmap(QPixmap.fromImage(background))
        item.setTransformOriginPoint(0, 0)
        from PyQt5.QtGui import QTransform
        item.setTransform(QTransform.fromScale(width/background.width(), height/background.height()))
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor('#353535'))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.drawing = False
        self.panning = False
        self.tablet = False
        self.items = []
        self.setMinimumSize(400, 300)

    def fit(self):
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def point(self, position):
        p = self.mapToScene(position)
        # Geometry stays in document coordinates at every zoom level.
        return p.x(), p.y()

    def begin(self, position):
        p = self.point(position)
        if not self.sceneRect().contains(QPointF(*p)):
            return
        self.owner.stash()
        self.owner.raw = [p]
        self.owner.current = None
        self.drawing = True
        self.redraw()

    def move(self, position):
        if self.drawing:
            p = self.point(position)
            if not self.owner.raw or ((p[0]-self.owner.raw[-1][0])**2+(p[1]-self.owner.raw[-1][1])**2)>0.1:
                if len(self.owner.raw) < 20000:
                    self.owner.raw.append(p)
            self.redraw()

    def end(self, position):
        self.move(position)
        self.drawing = False
        self.owner.status.setText('Press Enter to perfect this stroke. Choose a shape above to override detection.')

    def mousePressEvent(self, event):
        if self.tablet:
            event.accept(); return
        if event.button() == Qt.MiddleButton:
            self.panning = True; self.pan_pos = event.pos(); event.accept()
        elif event.button() == Qt.LeftButton:
            self.begin(event.pos()); event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.panning:
            delta=event.pos()-self.pan_pos; self.pan_pos=event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-delta.y())
        elif not self.tablet:
            self.move(event.pos())
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button()==Qt.MiddleButton:
            self.panning=False
        elif event.button()==Qt.LeftButton and not self.tablet and self.drawing:
            self.end(event.pos())
        event.accept()

    def viewportEvent(self, event):
        if event.type() in (QEvent.TabletPress,QEvent.TabletMove,QEvent.TabletRelease):
            self.tablet=True
            if event.type()==QEvent.TabletPress:
                self.begin(event.pos())
            elif event.type()==QEvent.TabletMove:
                self.move(event.pos())
            else:
                self.end(event.pos()); self.tablet=False
            event.accept(); return True
        return super().viewportEvent(event)

    def wheelEvent(self, event):
        zoom=self.transform().m11()
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        if 0.002 < zoom*factor < 100:
            self.scale(factor,factor)
        event.accept()

    def redraw(self):
        for item in self.items:
            self.scene().removeItem(item)
        self.items=[]
        shapes=list(self.owner.finished)
        if self.owner.current:
            shapes.append(self.owner.current)
        for shape in shapes:
            self.draw_path(shape.points,shape.closed,False)
        if self.owner.raw and not self.owner.current:
            self.draw_path(self.owner.raw,False,True)

    def draw_path(self, points, closed, rough):
        if not points: return
        path=QPainterPath(QPointF(*points[0]))
        for p in points[1:]: path.lineTo(QPointF(*p))
        if closed: path.closeSubpath()
        color=QColor(self.owner.color)
        color.setAlphaF(self.owner.opacity)
        pen=QPen(color,self.owner.width.value(),Qt.DashLine if rough else Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)
        item=self.scene().addPath(path,pen)
        if closed and self.owner.fill.isChecked() and not rough:
            item.setBrush(color)
        self.items.append(item)


class ShapeDialog(QDialog):
    def __init__(self, view, parent):
        super().__init__(parent)
        self.setWindowTitle('kSloppy — sketch, then perfect')
        self.resize(1100,800)
        self.document=view.document()
        self.raw=[]; self.current=None; self.finished=[]
        self.color=view.foregroundColor().colorForCanvas(view.canvas()).name()
        self.opacity=max(0,min(1,view.paintingOpacity()))
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Draw one shape at a time • Enter: perfect • Ctrl+Enter: apply • Backspace: discard last • Wheel: zoom • Middle drag: pan'))
        row=QHBoxLayout(); layout.addLayout(row)
        self.mode=QComboBox(); self.mode.addItems(MODES)
        row.addWidget(QLabel('Shape')); row.addWidget(self.mode)
        self.sides=QSpinBox(); self.sides.setRange(3,64); self.sides.setValue(6)
        row.addWidget(QLabel('Sides')); row.addWidget(self.sides)
        self.width=QDoubleSpinBox(); self.width.setRange(0.1,1000); self.width.setValue(max(0.1,view.brushSize())); self.width.setSuffix(' px')
        row.addWidget(QLabel('Outline')); row.addWidget(self.width)
        self.fill=QCheckBox('Fill'); row.addWidget(self.fill)
        self.detail=QComboBox(); self.detail.addItems(['Balanced corners','More corners','Fewer corners'])
        row.addWidget(self.detail)
        background=self.document.thumbnail(1800,1800)
        self.drawing_view=DrawingView(self,background,self.document.width(),self.document.height())
        layout.addWidget(self.drawing_view,1)
        self.status=QLabel('Sketch over your artwork. Changes stay in this preview until you apply them.')
        layout.addWidget(self.status)
        buttons=QHBoxLayout(); layout.addLayout(buttons)
        for title,callback in [('Perfect (Enter)',self.perfect),('Discard last',self.discard),('Fit view',self.drawing_view.fit),('Apply shapes',self.apply),('Close',self.reject)]:
            b=QPushButton(title); b.setAutoDefault(False); b.clicked.connect(callback); buttons.addWidget(b)
        for key,callback in [('Return',self.perfect),('Enter',self.perfect),('Ctrl+Return',self.apply),('Ctrl+Enter',self.apply),('Backspace',self.discard)]:
            shortcut=QShortcut(QKeySequence(key),self); shortcut.activated.connect(callback)
        self.mode.currentTextChanged.connect(self.refit)
        self.sides.valueChanged.connect(self.refit)
        self.detail.currentIndexChanged.connect(self.refit)
        self.width.valueChanged.connect(self.drawing_view.redraw)
        self.fill.toggled.connect(self.drawing_view.redraw)
        self.mode.currentTextChanged.connect(lambda text:self.sides.setEnabled(text=='Regular polygon'))
        self.sides.setEnabled(False)

    def showEvent(self,event):
        super().showEvent(event)
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0,self.drawing_view.fit)

    def stash(self):
        if self.current:
            self.finished.append(self.current)
        # Unperfected scribbles are intentionally temporary.

    def perfect(self):
        if self.drawing_view.drawing: return
        try:
            self.current=recognize(self.raw,self.mode.currentText(),self.sides.value(),[0.035,0.018,0.06][self.detail.currentIndex()])
            self.status.setText('{} • draw another to keep it, or Apply shapes. If the guess is wrong, change Shape above.'.format(self.current.name))
        except ValueError as exc:
            self.status.setText(str(exc))
        self.drawing_view.redraw()

    def refit(self,*args):
        if self.raw: self.perfect()

    def discard(self):
        if self.raw or self.current:
            self.raw=[]; self.current=None
        elif self.finished:
            self.finished.pop()
        self.drawing_view.redraw()
        self.status.setText('Last preview stroke discarded.')

    def apply(self):
        if self.drawing_view.drawing: return
        if self.raw and not self.current:
            self.perfect()
            if not self.current: return
        shapes=self.finished+([self.current] if self.current else [])
        if not shapes:
            self.status.setText('Draw a shape first.'); return
        doc=self.document
        if doc not in Krita.instance().documents():
            QMessageBox.warning(self,'kSloppy','The original document has been closed.'); return
        layer=None
        try:
            svg=svg_document(shapes,doc.width(),doc.height(),doc.resolution(),self.color,self.width.value(),self.fill.isChecked(),self.opacity)
            layer=doc.createVectorLayer('kSloppy — '+', '.join(s.name for s in shapes[:3]))
            if not doc.rootNode().addChildNode(layer,None):
                raise RuntimeError('Could not add the shape layer.')
            added=layer.addShapesFromSvg(svg)
            if not added: raise RuntimeError('Krita could not import the SVG shapes.')
            doc.refreshProjection()
            self.raw=[]; self.current=None; self.finished=[]
            self.accept()
        except Exception as exc:
            if layer: layer.remove()
            QMessageBox.warning(self,'kSloppy','Could not apply shapes: '+str(exc))

    def reject(self):
        if self.raw or self.current or self.finished:
            if QMessageBox.question(self,'Discard preview?','Close without applying these shapes?',QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Discard:
                return
        super().reject()


class KSloppyExtension(Extension):
    def setup(self):
        pass

    def createActions(self,window):
        action=window.createAction('ksloppy_draw','kSloppy: Sloppy Shapes','tools/scripts')
        action.setShortcut(QKeySequence('Ctrl+Alt+S'))
        action.triggered.connect(lambda:self.open(window))

    def open(self,window):
        view=window.activeView()
        if not view or not view.document():
            QMessageBox.information(window.qwindow(),'kSloppy','Open or create a document first.'); return
        ShapeDialog(view,window.qwindow()).exec_()
