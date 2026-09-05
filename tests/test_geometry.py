import importlib.util
import math
from pathlib import Path
import random
import sys
import unittest
import xml.etree.ElementTree as ET
spec=importlib.util.spec_from_file_location('geometry',Path(__file__).parents[1]/'ksloppy'/'geometry.py')
g=importlib.util.module_from_spec(spec); sys.modules[spec.name]=g; spec.loader.exec_module(g)


def noisy(points,seed=9,amount=0.7):
    r=random.Random(seed)
    return [(x+r.uniform(-amount,amount),y+r.uniform(-amount,amount)) for x,y in points]


def polygon(vertices):
    return [((1-t/30)*a[0]+t/30*b[0],(1-t/30)*a[1]+t/30*b[1]) for a,b in zip(vertices,vertices[1:]+vertices[:1]) for t in range(30)]+[vertices[0]]


class GeometryTests(unittest.TestCase):
    def test_circle(self):
        p=noisy(g.curve_shape('Circle',150,120,80,80).points)
        result=g.recognize(p)
        self.assertEqual(result.name,'Circle')
        self.assertLess(abs(result.curve[2]-80),2)

    def test_rotated_ellipse(self):
        p=noisy(g.curve_shape('Ellipse',150,120,110,45,0.63).points)
        result=g.recognize(p)
        self.assertEqual(result.name,'Ellipse')
        self.assertLess(result.error,0.012)

    def test_line(self):
        p=noisy([(x,2*x+10) for x in range(100)])
        self.assertEqual(g.recognize(p).name,'Line')

    def test_arc_both_directions(self):
        for sweep in (1.7,-2.3,4.0):
            p=noisy(g.curve_shape('Arc',170,150,100,100,start=0.4,sweep=sweep,closed=False).points)
            s=g.recognize(p)
            self.assertEqual(s.name,'Arc')
            self.assertAlmostEqual(s.curve[-1],sweep,delta=0.1)
            self.assertIn(' A ',s.svg_element())

    def test_square(self):
        p=noisy(polygon([(20,20),(140,20),(140,140),(20,140)]))
        s=g.recognize(p,'Square')
        edges=[g.dist(a,b) for a,b in zip(s.points,s.points[1:]+s.points[:1])]
        self.assertLess(max(edges)-min(edges),1e-6)
        self.assertIn(g.recognize(p).name,('Square','Regular 4-gon','Rectangle'))

    def test_rotated_rectangle_and_seam(self):
        pts=polygon([(20,20),(200,20),(200,100),(20,100)])[:-1]
        pts=pts[15:]+pts[:15];pts.append(pts[0])
        p=noisy([(x*0.8-y*0.6,x*0.6+y*0.8) for x,y in pts])
        s=g.recognize(p)
        self.assertEqual(s.name,'Rectangle')
        self.assertLess(s.error,0.02)

    def test_regular_polygons(self):
        for n in (3,5,6,8):
            vertices=[(150+100*math.cos(i*math.tau/n),150+100*math.sin(i*math.tau/n)) for i in range(n)]
            p=noisy(polygon(vertices))
            s=g.recognize(p,'Regular polygon',n)
            self.assertEqual(len(s.points),n)
            edges=[g.dist(a,b) for a,b in zip(s.points,s.points[1:]+s.points[:1])]
            self.assertLess(max(edges)-min(edges),1e-6)
            auto=g.recognize(p)
            self.assertIn('gon',auto.name)

    def test_concave_polygon(self):
        p=noisy(polygon([(0,0),(200,0),(80,80),(200,170),(0,170)]))
        s=g.recognize(p,'Polygon')
        self.assertEqual(len(s.points),5)
        self.assertLess(s.error,0.02)

    def test_degenerate(self):
        for p in ([],[(1,1)]*30,[(float('nan'),0)]*5):
            with self.assertRaises(ValueError):g.recognize(p)

    def test_resolution_svg(self):
        s=g.recognize([(0,0),(30,30),(60,60)],'Line')
        xml=g.svg_document([s],600,300,300,'#ff1122',5)
        root=ET.fromstring(xml)
        self.assertEqual(root.attrib['width'],'144.0pt')
        self.assertEqual(root.attrib['viewBox'],'0 0 600 300')
        self.assertEqual(root[0].attrib['stroke-width'],'5.00000')

    def test_large_translation(self):
        p=noisy(g.curve_shape('Circle',200000,350000,80,80).points)
        self.assertEqual(g.recognize(p).name,'Circle')

    def test_polygon_64(self):
        p=g.curve_shape('Circle',150,150,100,100).points
        self.assertEqual(len(g.recognize(p,'Regular polygon',64).points),64)

if __name__=='__main__': unittest.main()
