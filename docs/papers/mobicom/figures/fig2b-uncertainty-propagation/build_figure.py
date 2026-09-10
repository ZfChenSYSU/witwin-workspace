"""Editable figure 2(b), based on manuscript section 4.4 (2026-09-08)."""
from pathlib import Path
import xml.etree.ElementTree as E
import base64, zlib

OUT = Path(__file__).parent
WIDTH, HEIGHT = 1880, 1000
BLUE, GREEN, CYAN, BEIGE, GRAY, RED = '#378CE6', '#66B82F', '#CFF0F1', '#F1E6D4', '#F0F0F0', '#DC391D'
svg = E.Element('svg', xmlns='http://www.w3.org/2000/svg', width=str(WIDTH), height=str(HEIGHT), viewBox=f'0 0 {WIDTH} {HEIGHT}')
E.SubElement(svg, 'title').text = 'Fig. 2(b): Geometry uncertainty propagation for RF calibration'
E.SubElement(svg, 'desc').text = ('Front-facing observations and geometry calibration define a fixed, feasible position distribution. '
 'Alternative positions at the same time are each evaluated using ray tracing, fixed phone pose, room geometry, body proxy, '
 'assembly, and one shared set of static parameters theta. Each prediction is compared with the same training CSI. '
 'Losses are averaged over equally weighted accepted samples, then summed over training times with regularization to update '
 'theta only. Geometry receives no CSI feedback. Theta is frozen for held-out prediction.')
E.SubElement(svg, 'rect', width=str(WIDTH), height=str(HEIGHT), fill='white')
mx = E.Element('mxfile', host='app.diagrams.net')
d = E.SubElement(mx, 'diagram', id='fig2b', name='Fig. 2(b) — DEPTH-MARG')
model = E.SubElement(d, 'mxGraphModel', dx=str(WIDTH), dy=str(HEIGHT), grid='0', page='1', pageScale='1', pageWidth=str(WIDTH), pageHeight=str(HEIGHT), background='#FFFFFF', shadow='0')
root = E.SubElement(model, 'root')
E.SubElement(root, 'mxCell', id='0')
E.SubElement(root, 'mxCell', id='1', parent='0')

def cell(ident, x, y, w, h, style, value=''):
 c=E.SubElement(root, 'mxCell', id=ident, value=value, style=style, vertex='1', parent='1')
 E.SubElement(c, 'mxGeometry', x=str(x), y=str(y), width=str(w), height=str(h), attrib={'as':'geometry'})

def rect(ident,x,y,w,h,fill,stroke='#000000',sw=3.5,r=10):
 E.SubElement(svg,'rect',id=ident,x=str(x),y=str(y),width=str(w),height=str(h),rx=str(r),fill=fill,stroke=stroke,attrib={'stroke-width':str(sw)})
 cell(ident,x,y,w,h,f'rounded=1;absoluteArcSize=1;arcSize={r*2};fillColor={fill};strokeColor={stroke};strokeWidth={sw};html=1;shadow=0;')

def label(ident,text,cx,cy,w,size=30,bold=False,color='#000000',align='center'):
 attrs={'id':ident,'x':str(cx),'y':str(cy),'fill':color,'font-family':'Times New Roman, Times, serif','font-size':str(size),'font-weight':'700' if bold else '400','text-anchor':'middle' if align=='center' else 'start','dominant-baseline':'central'}
 t=E.SubElement(svg,'text',attrs)
 frag=E.fromstring('<label>'+text+'</label>')
 t.text=frag.text
 for child in frag:
  at={}
  if child.tag in ('sub','sup'):
   at={'baseline-shift':'sub' if child.tag=='sub' else 'super','font-size':'70%'}
  elif child.tag=='i': at={'font-style':'italic'}
  elif child.tag=='b': at={'font-weight':'700'}
  span=E.SubElement(t,'tspan',at);span.text=child.text;span.tail=child.tail
 x=cx-w/2 if align=='center' else cx
 cell(ident,x,cy-size*.75,w,size*1.5,f'text;html=1;whiteSpace=wrap;align={align};verticalAlign=middle;spacing=0;fillColor=none;strokeColor=none;fontFamily=Times New Roman;fontSize={size};fontStyle={1 if bold else 0};fontColor={color};',text)

def polygon(ident,pts,fill):
 E.SubElement(svg,'polygon',id=ident,points=' '.join(f'{x},{y}' for x,y in pts),fill=fill,stroke='#000000',attrib={'stroke-width':'2','stroke-linejoin':'miter'})
 x=min(a for a,b in pts);y=min(b for a,b in pts);w=max(a for a,b in pts)-x;h=max(b for a,b in pts)-y
 shape=E.Element('shape',name=ident,w=str(w),h=str(h),aspect='variable',strokewidth='inherit')
 E.SubElement(shape,'connections')
 path=E.SubElement(E.SubElement(shape,'background'),'path')
 for i,(a,b) in enumerate(pts):E.SubElement(path,'move' if i==0 else 'line',x=str(a-x),y=str(b-y))
 E.SubElement(path,'close');E.SubElement(E.SubElement(shape,'foreground'),'fillstroke')
 compressor=zlib.compressobj(wbits=-15)
 raw=E.tostring(shape,encoding='utf-8')
 encoded=base64.b64encode(compressor.compress(raw)+compressor.flush()).decode()
 cell(ident,x,y,w,h,f'shape=stencil({encoded});fillColor={fill};strokeColor=#000000;strokeWidth=2;html=1;shadow=0;')

def arrow(ident,x1,y1,x2,y2,fill=BEIGE,shaft=18,head=38,tip=20):
 import math
 length=math.hypot(x2-x1,y2-y1);ux=(x2-x1)/length;uy=(y2-y1)/length;vx=-uy;vy=ux
 local=[(0,-shaft/2),(length-tip,-shaft/2),(length-tip,-head/2),(length,0),(length-tip,head/2),(length-tip,shaft/2),(0,shaft/2)]
 polygon(ident,[(round(x1+a*ux+b*vx,3),round(y1+a*uy+b*vy,3)) for a,b in local],fill)

# The spatial layout follows the user's reference; all arrows and labels are separate vector objects.
rect('input-band',30,40,1820,190,GRAY,'none',0)
rect('propagation-band',30,250,1820,390,GRAY,'none',0)
rect('optimization-band',30,660,1820,280,GRAY,'none',0)

rect('visual-input',60,80,310,120,BLUE)
label('visual-title','Front-facing observations',215,118,290,27,True,'#FFFFFF')
label('calibration-title','&amp; geometry calibration',215,162,290,27,True,'#FFFFFF')
arrow('visual-to-distribution',370,140,440,140,CYAN)
rect('distribution',440,80,280,120,CYAN)
label('distribution-title','Position distribution',580,106,265,29,True)
label('distribution-symbol','p<sub>t</sub>(r | vision)',580,145,260,30)
label('distribution-subtitle','Mean + calibrated covariance',580,180,264,21)

rect('fixed-context',790,80,440,120,BEIGE)
label('context-title','Fixed context',1010,105,420,30,True)
label('context-pose','Phone pose, room geometry,',1010,143,420,28)
label('context-assembly','body proxy &amp; assembly',1010,179,420,28)

rect('training-csi',1510,80,300,120,BLUE)
label('csi-title','Training CSI',1660,105,280,30,True,'#FFFFFF')
label('csi-symbol','y<sub>t</sub> = φ(s<sub>t</sub>)',1660,143,280,31,False,'#FFFFFF')
label('csi-reuse','Same observation for all k',1660,180,280,23,False,'#FFFFFF')

arrow('distribution-to-samples',580,200,580,285,CYAN,20,42)
arrow('context-to-tracer',1010,200,1010,285,BEIGE,20,42)
arrow('csi-to-losses',1660,200,1660,285,BLUE,20,42)

label('first-propagation','Geometry → channels',65,280,335,29,True,RED,align='left')
label('alternative-note-1','Alternative body positions',65,370,330,26,align='left')
label('alternative-note-2','at the same time t',65,406,330,26,align='left')
label('alternative-note-3','Feasible samples from p<sub>t</sub>',65,477,330,25,align='left')
label('alternative-note-4','Reused across θ iterations',65,513,330,25,align='left')

rect('samples-container',440,285,280,320,CYAN)
label('samples-title','Possible geometries',580,311,260,28,True)
rect('tracer',790,285,440,320,BEIGE)
label('tracer-title','Per-sample ray tracing',1010,322,418,33,True)
label('tracer-action-1','Recompute visible paths',1010,382,410,29)
label('tracer-action-2','at each possible position',1010,420,410,29)
label('tracer-formula','f<sub>t</sub><sup>(k)</sup>(θ) = φ(F<sub>θ</sub>(q<sub>t</sub>, r<sub>t</sub><sup>(k)</sup>, …))',1010,481,420,28)
label('tracer-shared-geometry-1','One geometry sample spans',1010,543,410,25)
label('tracer-shared-geometry-2','all subcarriers &amp; channels',1010,577,410,25)
label('predictions-title','Predictions',1380,305,175,28,True)
rect('losses-container',1510,285,300,320,CYAN)
label('losses-title','Per-sample losses',1660,313,280,30,True)

for i,(k,cy) in enumerate([('1',370),('2',465),('K',560)]):
 rect(f'sample-{i}',470,cy-30,220,60,'#FFFFFF',sw=2.5)
 label(f'sample-label-{i}',f'r<sub>t</sub><sup>({k})</sup>',580,cy,200,34)
 arrow(f'sample-to-tracer-{i}',720,cy,790,cy,CYAN)
 arrow(f'tracer-to-prediction-{i}',1230,cy,1300,cy,BEIGE)
 rect(f'prediction-{i}',1300,cy-30,160,60,CYAN,sw=2.5)
 label(f'prediction-label-{i}',f'f<sub>t</sub><sup>({k})</sup>(θ)',1380,cy,146,31)
 arrow(f'prediction-to-loss-{i}',1460,cy,1510,cy,CYAN,16,34,17)
 label(f'loss-label-{i}',f'ℓ(y<sub>t</sub>, f<sub>t</sub><sup>({k})</sup>(θ))',1660,cy,276,30)
for ident,cx in [('sample',580),('prediction',1380),('loss',1660)]:
 label(ident+'-ellipsis','⋮',cx,514,40,27)

label('second-propagation','Channels → calibration loss',65,701,680,31,True,RED,align='left')
label('loss-order-note','Compute losses first, then average.',65,755,660,29,True,align='left')
label('geometry-boundary-note','CSI updates θ only; geometry stays fixed.',65,803,670,27,align='left')
label('heldout-note','Freeze θ for held-out prediction.',65,850,660,27,align='left')
label('sampling-note','K geometry samples ≠ K independent measurements.',65,897,680,25,align='left')

arrow('losses-to-expectation',1660,605,1660,700,GREEN,24,48,23)
rect('expected-loss',1300,700,510,90,GREEN)
label('expected-loss-title','Expected loss at time t',1555,727,490,31,True,'#FFFFFF')
label('expected-loss-formula','L<sub>t</sub>(θ) ≈ (1/K) Σ<sub>k=1…K</sub> ℓ<sub>t</sub><sup>(k)</sup>(θ)',1555,767,490,30,False,'#FFFFFF')
arrow('expectation-to-update',1555,790,1555,825,GREEN,17,34,17)
rect('parameter-update',1300,825,510,90,CYAN)
label('update-title','Aggregate training times &amp; update θ',1555,850,490,29,True)
label('update-objective','min<sub>θ∈Θ</sub>  Σ<sub>t∈train</sub> L<sub>t</sub>(θ) + λR(θ)',1555,890,490,29)
arrow('update-to-shared-theta',1300,870,1230,870,BEIGE,20,40)
rect('shared-theta',790,825,440,90,BEIGE)
label('shared-theta-title','Shared static parameters θ',1010,854,420,32,True)
label('shared-theta-note','One parameter set for all samples',1010,889,420,25)
arrow('theta-to-tracer',1010,825,1010,605,BEIGE,24,48,24)
label('feedback-label','θ feedback',1120,748,170,26)

label('figure-caption','Fig. 2(b): Geometry uncertainty propagation for RF calibration',940,972,1780,35,True)
E.indent(mx)
E.ElementTree(mx).write(OUT/'fig2b-uncertainty-propagation.drawio',encoding='utf-8',xml_declaration=True)
E.ElementTree(svg).write(OUT/'fig2b-uncertainty-propagation.svg',encoding='utf-8',xml_declaration=True)
E.ElementTree(model).write(OUT/'fig2b-uncertainty-propagation.mxgraph.xml',encoding='utf-8')
print('Wrote editable draw.io XML and text-preserving SVG.')
