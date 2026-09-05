"""Generate reproducible before/after artwork from the actual recognizer."""
import importlib.util
import math
from pathlib import Path
import random
import sys
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('geometry',root/'ksloppy'/'geometry.py')
g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
def poly(v):
    return [((1-t/25)*a[0]+t/25*b[0],(1-t/25)*a[1]+t/25*b[1]) for a,b in zip(v,v[1:]+v[:1]) for t in range(25)]+[v[0]]
examples=[('circle',g.curve_shape('',100,100,65,65).points,'Auto'),
 ('ellipse',g.curve_shape('',100,100,80,40,0.5).points,'Auto'),
 ('rectangle',poly([(30,50),(170,50),(170,145),(30,145)]),'Auto'),
 ('hexagon',poly([(100+70*math.cos(i*math.tau/6),100+70*math.sin(i*math.tau/6)) for i in range(6)]),'Regular polygon'),
 ('arc',g.curve_shape('',100,100,65,65,start=0.2,sweep=4.2,closed=False).points,'Arc'),
 ('polygon',poly([(25,30),(170,45),(110,100),(160,170),(30,160)]),'Polygon')]
parts=['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="620" viewBox="0 0 960 620"><rect width="960" height="620" fill="#171b20"/><text x="28" y="40" fill="#f5f1e8" font-family="sans-serif" font-size="24">kSloppy / rough → ready</text>']
for i,(name,pts,mode) in enumerate(examples):
    rng=random.Random(i)
    raw=[(x+rng.uniform(-2.5,2.5),y+rng.uniform(-2.5,2.5)) for x,y in pts]
    s=g.recognize(raw,mode,6)
    x=20+(i%3)*315;y=70+(i//3)*270
    parts.append(f'<g transform="translate({x},{y})"><rect width="300" height="250" rx="12" fill="#232930"/><g transform="translate(47,8)">')
    parts.append(g.Shape('raw',raw,False).svg_element('#797d84',2))
    parts.append(s.svg_element('#b8edc2',2.5))
    parts.append(f'</g><text x="20" y="228" fill="#e9e8e4" font-family="sans-serif" font-size="16">{name}</text></g>')
parts.append('</svg>')
(root/'docs'/'examples.svg').write_text(''.join(parts))
