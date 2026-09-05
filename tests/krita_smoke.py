"""Executed inside the real Krita Python runtime by tests/run_krita_smoke.py."""
import json
import os
from pathlib import Path
import traceback
from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtTest import QTest
from krita import Krita


def run():
    output=Path(os.environ['KSLOPPY_TEST_OUTPUT'])
    output.mkdir(parents=True,exist_ok=True)
    app=Krita.instance()
    try:
        from ksloppy.plugin import ShapeDialog
        from ksloppy.geometry import curve_shape
        assert app.action('ksloppy_draw') is not None, 'Plugin action was not registered'
        results=[]
        for dpi in (72,300):
            doc=app.createDocument(600,400,'kSloppy smoke','RGBA','U8','',dpi)
            window=app.activeWindow()
            window.addView(doc)
            view=window.activeView()
            view.setBrushSize(4)
            view.setPaintingOpacity(1)
            dialog=ShapeDialog(view,window.qwindow())
            dialog.show()
            QTest.qWait(100)
            canvas=dialog.drawing_view
            canvas.fit()
            # Real Qt mouse events go through the viewport and scene coordinate mapping.
            pts=curve_shape('Circle',200,180,70,70).points
            first=canvas.mapFromScene(*pts[0])
            QTest.mousePress(canvas.viewport(),Qt.LeftButton,Qt.NoModifier,first)
            for p in pts[1:]:
                QTest.mouseMove(canvas.viewport(),canvas.mapFromScene(*p),1)
            QTest.mouseRelease(canvas.viewport(),Qt.LeftButton,Qt.NoModifier,canvas.mapFromScene(*pts[-1]))
            assert len(dialog.raw)>20, 'Mouse stroke was not captured'
            dialog.perfect()
            assert dialog.current and dialog.current.name=='Circle', 'Circle recognition failed'
            # Stroke coordinate invariance after zoom.
            canvas.scale(1.5,1.5)
            mapped=canvas.point(canvas.mapFromScene(200,180))
            assert abs(mapped[0]-200)<2 and abs(mapped[1]-180)<2
            dialog.grab().save(str(output/('preview-%s.png'%dpi)))
            dialog.apply()
            doc.waitForDone()
            layers=[n for n in doc.rootNode().childNodes() if n.type()=='vectorlayer']
            assert len(layers)==1,'Apply did not create a vector layer'
            shapes=layers[0].shapes()
            assert len(shapes)==1,'SVG did not produce one shape'
            rect=shapes[0].boundingBox()
            # Shape coordinates are points; document coordinates are pixels.
            center=rect.center()
            assert abs(center.x()*dpi/72-200)<3,(dpi,center.x())
            assert abs(center.y()*dpi/72-180)<3,(dpi,center.y())
            assert abs(rect.width()*dpi/72-140)<12,(dpi,rect.width())
            doc.setBatchmode(True)
            assert doc.saveAs(str(output/('shapes-%s.kra'%dpi)))
            results.append({'dpi':dpi,'shape_count':len(shapes),'center_px':[center.x()*dpi/72,center.y()*dpi/72]})
            doc.close()
        (output/'result.json').write_text(json.dumps({'ok':True,'krita':app.version(),'checks':results},indent=2))
    except BaseException:
        (output/'result.json').write_text(json.dumps({'ok':False,'traceback':traceback.format_exc()},indent=2))
    finally:
        QTimer.singleShot(0,lambda:os._exit(0))
