"""Dependency-free single-stroke fitting. Coordinates are document pixels."""
import math
from dataclasses import dataclass
from xml.sax.saxutils import escape


def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def segment_distance(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    t = max(0, min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy or 1)))
    return dist(p, (a[0]+t*dx, a[1]+t*dy))


def resample(points, count=160):
    clean = [points[0]] if points else []
    for p in points[1:]:
        if dist(p, clean[-1]) > 1e-8:
            clean.append(p)
    if len(clean) < 2:
        return clean
    lengths = [0.0]
    for a, b in zip(clean, clean[1:]):
        lengths.append(lengths[-1]+dist(a, b))
    result, j = [], 1
    for i in range(count):
        target = lengths[-1]*i/(count-1)
        while j < len(clean)-1 and lengths[j] < target:
            j += 1
        t = (target-lengths[j-1])/(lengths[j]-lengths[j-1])
        a, b = clean[j-1], clean[j]
        result.append((a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])))
    return result


def simplify(p, tolerance):
    if len(p) < 3:
        return p
    d, i = max((segment_distance(v, p[0], p[-1]), i) for i, v in enumerate(p[1:-1], 1))
    if d <= tolerance:
        return [p[0], p[-1]]
    return simplify(p[:i+1], tolerance)[:-1]+simplify(p[i:], tolerance)


def solve(matrix, vector):
    a = [list(row)+[value] for row, value in zip(matrix, vector)]
    n = len(a)
    for i in range(n):
        j = max(range(i, n), key=lambda j: abs(a[j][i]))
        a[i], a[j] = a[j], a[i]
        if abs(a[i][i]) < 1e-10:
            raise ValueError('Degenerate fit')
        pivot = a[i][i]
        a[i] = [v/pivot for v in a[i]]
        for j in range(n):
            if j != i:
                factor = a[j][i]
                a[j] = [v-factor*w for v, w in zip(a[j], a[i])]
    return [row[-1] for row in a]


def least_squares(rows, values):
    n = len(rows[0])
    return solve([[sum(r[i]*r[j] for r in rows) for j in range(n)] for i in range(n)],
                 [sum(r[i]*v for r, v in zip(rows, values)) for i in range(n)])


def circle_fit(p):
    cx = sum(x for x, y in p)/len(p)
    cy = sum(y for x, y in p)/len(p)
    q = [(x-cx, y-cy) for x, y in p]
    a, b, c = least_squares([[2*x, 2*y, 1] for x, y in q], [x*x+y*y for x, y in q])
    return cx+a, cy+b, math.sqrt(max(0, c+a*a+b*b))


def path_error(p, vertices, closed):
    edges = list(zip(vertices, vertices[1:]))
    if closed:
        edges.append((vertices[-1], vertices[0]))
    return math.sqrt(sum(min(segment_distance(v, a, b) for a, b in edges)**2 for v in p)/len(p))


@dataclass
class Shape:
    name: str
    points: list
    closed: bool
    error: float = 0.0
    # Ellipses and arcs retain exact SVG geometry, not a faceted approximation.
    curve: tuple = ()  # cx, cy, rx, ry, rotation radians, start, sweep

    def svg_element(self, color='#000000', width=4.0, fill=False, opacity=1.0):
        style = 'stroke="{}" stroke-width="{:.5f}" fill="{}" stroke-linecap="round" stroke-linejoin="round" opacity="{:.5f}"'.format(
            escape(color, {'"': '&quot;'}), width, color if fill and self.closed else 'none', opacity)
        if self.curve:
            cx, cy, rx, ry, angle, start, sweep = self.curve
            rotation = math.degrees(angle)
            if self.closed:
                return '<ellipse cx="{}" cy="{}" rx="{}" ry="{}" transform="rotate({} {} {})" {}/>'.format(cx, cy, rx, ry, rotation, cx, cy, style)
            a, b = self.points[0], self.points[-1]
            return '<path d="M {} {} A {} {} {} {} {} {} {}" {}/>'.format(*a, rx, ry, rotation, int(abs(sweep)>math.pi), int(sweep>0), *b, style)
        data = 'M '+' L '.join('{:.5f} {:.5f}'.format(*p) for p in self.points)
        return '<path d="{}{}" {}/>'.format(data, ' Z' if self.closed else '', style)


def curve_shape(name, cx, cy, rx, ry, angle=0, start=0, sweep=2*math.pi, closed=True):
    ca, sa = math.cos(angle), math.sin(angle)
    points = []
    for i in range(161):
        t = start+sweep*i/160
        x, y = rx*math.cos(t), ry*math.sin(t)
        points.append((cx+ca*x-sa*y, cy+sa*x+ca*y))
    return Shape(name, points, closed, curve=(cx, cy, rx, ry, angle, start, sweep))


def recognize(raw, mode='Auto', sides=6, tolerance=0.035):
    if len(raw) < 3 or not all(math.isfinite(v) for p in raw for v in p):
        raise ValueError('Draw a longer stroke first.')
    p = resample(raw)
    span = math.hypot(max(x for x,y in p)-min(x for x,y in p), max(y for x,y in p)-min(y for x,y in p))
    if span < 2:
        raise ValueError('That stroke is too small to fit.')
    closed = dist(p[0], p[-1]) < span*0.22
    candidates = []
    line = Shape('Line', [p[0], p[-1]], False)
    line.error = path_error(p, line.points, False)/span
    if mode == 'Line' or (mode == 'Auto' and line.error < 0.025):
        return line
    try:
        cx, cy, radius = circle_fit(p)
        if not closed and mode in ('Auto', 'Arc'):
            angles = [math.atan2(y-cy, x-cx) for x,y in p]
            sweep = sum((b-a+math.pi)%(2*math.pi)-math.pi for a,b in zip(angles, angles[1:]))
            arc = curve_shape('Arc', cx, cy, radius, radius, start=angles[0], sweep=sweep, closed=False)
            arc.error = math.sqrt(sum((dist(v,(cx,cy))-radius)**2 for v in p)/len(p))/span
            if 0.15 < abs(sweep) < 2*math.pi-0.03 and (mode == 'Arc' or arc.error < 0.035):
                return arc
        circle = curve_shape('Circle', cx, cy, radius, radius)
        circle.error = path_error(p, circle.points, True)/span
        candidates.append(circle)
    except ValueError:
        if mode in ('Circle', 'Arc'):
            raise ValueError('Draw a more curved stroke for this shape.')
    # Search orientation, fitting an axis-aligned conic in each rotated frame.
    mx, my = sum(x for x,y in p)/len(p), sum(y for x,y in p)/len(p)
    for step in range(36):
        angle = step*math.pi/36
        ca, sa = math.cos(angle), math.sin(angle)
        q = [((ca*(x-mx)+sa*(y-my))/span, (-sa*(x-mx)+ca*(y-my))/span) for x,y in p]
        try:
            a,b,c,d = least_squares([[x*x,y*y,x,y] for x,y in q], [1]*len(q))
            if a <= 0 or b <= 0:
                continue
            x0,y0 = -c/(2*a),-d/(2*b)
            k = 1+a*x0*x0+b*y0*y0
            rx,ry = math.sqrt(k/a)*span,math.sqrt(k/b)*span
            if min(rx,ry) < span*0.03 or max(rx,ry) > span*2:
                continue
            e = curve_shape('Ellipse', mx+span*(ca*x0-sa*y0), my+span*(sa*x0+ca*y0), rx, ry, angle)
            e.error = path_error(p,e.points,True)/span
            candidates.append(e)
        except ValueError:
            pass
    if mode in ('Circle','Ellipse'):
        options = [c for c in candidates if c.name == mode]
        if not options:
            raise ValueError('Could not fit that shape. Try drawing it again.')
        return min(options,key=lambda c:c.error)
    # Split the closed loop away from its arbitrary start point, then simplify.
    if closed or mode in ('Polygon','Regular polygon','Rectangle','Square'):
        split = max(range(len(p)), key=lambda i: dist(p[0],p[i]))
        vertices = simplify(p[:split+1],span*tolerance)[:-1]+simplify(p[split:]+[p[0]],span*tolerance)[:-1]
        # Remove redundant seam vertices (e.g. starting halfway along a side).
        changed = True
        while changed and len(vertices)>3:
            changed = False
            for i in range(len(vertices)):
                if segment_distance(vertices[i],vertices[i-1],vertices[(i+1)%len(vertices)]) < span*tolerance:
                    vertices.pop(i); changed = True; break
        polygon = Shape('{}-sided polygon'.format(len(vertices)), vertices, True)
        polygon.error = path_error(p,vertices,True)/span
        if mode == 'Polygon':
            return polygon
        # Minimum-area oriented rectangle from all inferred edge directions.
        rectangles=[]
        for v,w in zip(vertices,vertices[1:]+vertices[:1]):
            ang=math.atan2(w[1]-v[1],w[0]-v[0]); ca,sa=math.cos(ang),math.sin(ang)
            q=[(ca*x+sa*y,-sa*x+ca*y) for x,y in p]
            lo,hi=min(x for x,y in q),max(x for x,y in q)
            bot,top=min(y for x,y in q),max(y for x,y in q)
            if mode=='Square':
                r=((hi-lo)+(top-bot))/4; xx=(lo+hi)/2; yy=(bot+top)/2
                lo,hi,bot,top=xx-r,xx+r,yy-r,yy+r
            pts=[(ca*x-sa*y,sa*x+ca*y) for x,y in [(lo,bot),(hi,bot),(hi,top),(lo,top)]]
            shape=Shape('Square' if mode=='Square' else 'Rectangle',pts,True)
            shape.error=path_error(p,pts,True)/span
            rectangles.append(shape)
        if mode in ('Rectangle','Square'):
            return min(rectangles,key=lambda c:c.error)
        n = max(3,min(64,int(sides))) if mode=='Regular polygon' else len(vertices)
        if 3<=n<=64:
            cx=sum(x for x,y in vertices)/len(vertices); cy=sum(y for x,y in vertices)/len(vertices)
            r=sum(dist(v,(cx,cy)) for v in vertices)/len(vertices)
            regular=[]
            for step in range(90):
                angle=step*2*math.pi/(n*90)
                pts=[(cx+r*math.cos(angle+i*2*math.pi/n),cy+r*math.sin(angle+i*2*math.pi/n)) for i in range(n)]
                s=Shape('Regular {}-gon'.format(n),pts,True); s.error=path_error(p,pts,True)/span;regular.append(s)
            best=min(regular,key=lambda c:c.error)
            if mode=='Regular polygon':
                return best
            if best.error < 0.02:
                candidates.append(best)
        if len(vertices)==4:
            candidates += rectangles
            square=recognize(raw,'Square',sides,tolerance)
            if square.error<0.022:
                candidates.append(square)
        polygon.error += 0.008 # Prefer a mathematical primitive when equally plausible.
        candidates.append(polygon)
        # Circle bias prevents near-round ellipses being overfit.
        for c in candidates:
            if c.name=='Ellipse': c.error += 0.003
        return min(candidates,key=lambda c:c.error)
    if mode == 'Arc':
        raise ValueError('Could not fit an arc. Try a single curved stroke.')
    pts=simplify(p,span*tolerance)
    return Shape('Polyline',pts,False,path_error(p,pts,False)/span)


def svg_document(shapes, width, height, dpi, color, stroke_width, fill=False, opacity=1):
    # Explicit physical size is essential: Krita stores vector coordinates in points.
    body=''.join(s.svg_element(color,stroke_width,fill,opacity) for s in shapes)
    return '<svg xmlns="http://www.w3.org/2000/svg" width="{}pt" height="{}pt" viewBox="0 0 {} {}">{}</svg>'.format(width*72/dpi,height*72/dpi,width,height,body)
