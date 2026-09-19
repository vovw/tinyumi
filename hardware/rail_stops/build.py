"""Four low rail-end stops for tinyumi. Units: mm; prototype dimensions.
uv run --python 3.12 --with cadquery --with trimesh --with matplotlib python hardware/rail_stops/build.py
"""
from pathlib import Path
import json
import cadquery as cq
import trimesh
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

OUT=Path(__file__).resolve().parent; ROOT=OUT.parents[1]
P={'rail_length':100.,'rail_width':9.,'rail_height':6.5,'plate_top':6.,
 'rail_centres_y':22.5,'plate_end_x':51.,'stop_face_x':49.5,'stop_top_z':10.,
 'stop_shoulder_bottom_z':7.8,'bolt_y':24.5,'bolt_z':3.,'insert_od':4.,'insert_depth':5.4}
def box(w,d,h,c):return cq.Workplane('XY').box(w,d,h).translate(c).val()
def export(s,name):
 assert s.isValid() and len(s.Solids())==1,name
 cq.exporters.export(s,str(OUT/(name+'.step')))
 cq.exporters.export(s,str(OUT/(name+'.stl')),tolerance=.04,angularTolerance=.1)
 m=trimesh.load(OUT/(name+'.stl'));m.merge_vertices(digits_vertex=7)
 m.update_faces(m.nondegenerate_faces());m.update_faces(m.unique_faces());m.remove_unreferenced_vertices()
 assert m.is_watertight and m.volume>0,name
 m.export(OUT/(name+'.stl'));return m

# Canonical positive-X / positive-Y stop. The toe catches only the outer carriage shoulder.
# Keeping all material outside |Y|=20.5 clears the moving finger holders.
s=box(3,11,11,(52.5,26,4.5)).fuse(box(4.5,3.4,2.2,(51.75,29.4,8.9)))
s=s.cut(cq.Solid.makeCylinder(1.7,6,cq.Vector(49,24.5,3),cq.Vector(1,0,0)))
s=s.cut(cq.Solid.makeCone(3.2,1.7,1.5,cq.Vector(54,24.5,3),cq.Vector(-1,0,0))).clean()
# A and B are mirrored. Put the broad outer mounting face on the print bed;
# the screw axis is vertical and the small toe grows upward without an overhang.
A=s.translate((-49.5,-20.5,1))
B=A.mirror('XZ').translate((0,11,0))
A=A.rotate((0,0,0),(0,1,0),90).translate((0,0,4.5))
B=B.rotate((0,0,0),(0,1,0),90).translate((0,0,4.5))
ma=export(A,'rail_stop_A_print_2');mb=export(B,'rail_stop_B_print_2')
packed=[]
labels=['A1','B1','B2','A2']
for i,mesh in enumerate([ma,mb,mb,ma]):
 m=mesh.copy();m.apply_translation((19*(i%2),19*(i//2),0));packed.append(m)
 assert abs(m.bounds[0,2])<1e-6 and abs(m.extents[2]-4.5)<1e-6
trimesh.util.concatenate(packed).export(OUT/'rail_stops_four_on_plate.stl')

# Portable 3MF with four distinct named objects; no printer-specific profile.
import zipfile, xml.etree.ElementTree as ET
NS='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
ET.register_namespace('',NS)
model=ET.Element('{'+NS+'}model',{'unit':'millimeter','{http://www.w3.org/XML/1998/namespace}lang':'en-US'})
resources=ET.SubElement(model,'{'+NS+'}resources');build=ET.SubElement(model,'{'+NS+'}build')
for i,(name,m) in enumerate(zip(labels,packed),1):
 obj=ET.SubElement(resources,'{'+NS+'}object',{'id':str(i),'type':'model','name':'Rail stop '+name})
 mesh=ET.SubElement(obj,'{'+NS+'}mesh');vertices=ET.SubElement(mesh,'{'+NS+'}vertices');triangles=ET.SubElement(mesh,'{'+NS+'}triangles')
 for v in m.vertices:ET.SubElement(vertices,'{'+NS+'}vertex',dict(zip(['x','y','z'],[f'{float(x):.7f}' for x in v])))
 for f in m.faces:ET.SubElement(triangles,'{'+NS+'}triangle',dict(zip(['v1','v2','v3'],map(str,f))))
 ET.SubElement(build,'{'+NS+'}item',{'objectid':str(i)})
with zipfile.ZipFile(OUT/'rail_stops_four_flat.3mf','w',zipfile.ZIP_DEFLATED) as z:
 z.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
 z.writestr('_rels/.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
 z.writestr('3D/3dmodel.model',ET.tostring(model,encoding='utf-8',xml_declaration=True))

# Print-layout preview, showing actual top silhouette and screw holes.
fig,axes=plt.subplots(1,2,figsize=(10,5),gridspec_kw={'width_ratios':[2,1]})
from matplotlib.collections import PolyCollection
for name,m in zip(labels,packed):
 up=m.face_normals[:,2]>.01
 axes[0].add_collection(PolyCollection(m.triangles[up,:,:2],facecolors='#d67528',edgecolors='none'))
 centre=m.bounds.mean(axis=0);axes[0].text(centre[0],m.bounds[1,1]+1.2,name,ha='center',fontsize=11)
axes[0].set(xlim=(-3,33),ylim=(-3,35),aspect='equal',title='Four separate parts · 8 mm gaps');axes[0].axis('off')
axes[1].add_collection(PolyCollection(ma.triangles[:,:,[0,2]],facecolors='#d67528',edgecolors='none'))
axes[1].axhline(0,color='#4e626b');axes[1].set(xlim=(-2,13),ylim=(-2,9),aspect='equal',title='Side view · 4.5 mm high');axes[1].axis('off')
fig.suptitle('Rail stops — corrected flat print orientation',fontsize=16)
fig.text(.5,.045,'Broad mounting faces down. Countersinks face the bed. A/B pairs occupy opposite corners.',ha='center',fontsize=10)
fig.savefig(OUT/'rail_stops_print_layout.png',dpi=170,bbox_inches='tight');plt.close(fig)

placed=[s,s.mirror('XZ'),s.mirror('YZ'),s.mirror('XZ').mirror('YZ')]
base_paths={'plate_v6_with_rail_stops':ROOT/'hardware/STEP/plate_v6.step',
 'plate_v6_quest_and_rail_stops':ROOT/'pos-tracking/quest_mount/handumi_v1/plate_v6_handumi_mount.step'}
checks={}
for name,path in base_paths.items():
 original=cq.importers.importStep(str(path)).val();plate=original
 for sx in [-1,1]:
  for sy in [-1,1]:
   bore=cq.Solid.makeCylinder(2,5.4,cq.Vector(sx*51,sy*24.5,3),cq.Vector(-sx,0,0));plate=plate.cut(bore)
 plate=plate.clean();mp=export(plate,name)
 overlaps=[st.intersect(plate).Volume() for st in placed];assert max(overlaps)<1e-6
 checks[name]={'valid_solid':plate.isValid(),'watertight':bool(mp.is_watertight),'stop_intersections_mm3':overlaps}

# Nominal rail and block envelopes use catalog dimensions, not the old simplified GLB block.
rail=box(100,9,6.5,(0,22.5,9.25))
assert s.intersect(rail).Volume()<1e-6
# Front face reaches toe at 49.5 mm, with block still 0.5 mm short of rail end.
L=28.9;limit=49.5-L/2
before=box(L,20,8,(limit-.1,22.5,12))
after=box(L,20,8,(limit+.1,22.5,12))
assert s.intersect(before).Volume()<1e-6
hit=s.intersect(after).Volume();assert hit>0
# Exact adapter CAD bounding minimum; moving holders have |Y| <= 20.020001 in reference assembly.
adapter=cq.importers.importStep(str(ROOT/'hardware/STEP/adapter_v10.step')).val().translate((0,22.5,16))
gap=adapter.BoundingBox().zmin-10;assert gap>0

# Instruction drawing: placement plus an enlarged cutaway through the outer shoulder.
fig=plt.figure(figsize=(12,8),facecolor='#f7f6f2')
fig.text(.045,.94,'RAIL END STOPS',fontsize=25,weight='bold',color='#243741')
fig.text(.045,.895,'Four small stops · one at each end of the two MGN9 rails',fontsize=13,color='#5a6a73')
ax=fig.add_axes([.05,.28,.57,.54]);ax.set_aspect('equal');ax.axis('off')
ax.add_patch(Rectangle((-51,-32.5),102,65,facecolor='#d8dfe1',edgecolor='#7f919a',lw=1.5))
for y in [-22.5,22.5]:
 ax.add_patch(Rectangle((-50,y-4.5),100,9,facecolor='#8398a3'))
 ax.add_patch(Rectangle((-14.45,y-10),28.9,20,facecolor='#3e5664',edgecolor='#203741'))
 for x in [-40,-20,0,20,40]:ax.add_patch(Circle((x,y),1.1,facecolor='#f7f6f2'))
for sx in [-1,1]:
 for sy in [-1,1]:
  xlo=51 if sx==1 else -54;ylo=20.5 if sy==1 else -31.5
  ax.add_patch(Rectangle((xlo,ylo),3,11,facecolor='#d67528'))
  ax.add_patch(Rectangle((49.5 if sx==1 else -54,27.7 if sy==1 else -31.1),4.5,3.4,facecolor='#d67528'))
  label='A' if sx==sy else 'B'
  ax.text(sx*60,sy*26,label,ha='center',va='center',weight='bold',fontsize=15,color='#b05719')
ax.annotate('CAMERA SIDE',xy=(0,33),xytext=(0,44),ha='center',color='#5a6a73',arrowprops={'arrowstyle':'->','color':'#5a6a73'})
ax.set(xlim=(-68,68),ylim=(-40,48))
fig.text(.065,.24,'TOP VIEW   Orange = stops   /   A × 2, B × 2',fontsize=10,color='#5a6a73')
a=fig.add_axes([.69,.4,.26,.38]);a.set_aspect('equal');a.axis('off')
a.add_patch(Rectangle((38,0),13,6,facecolor='#d8dfe1',edgecolor='#7f919a'))
a.add_patch(Rectangle((51,-1),3,11,facecolor='#d67528'))
a.add_patch(Rectangle((49.5,7.8),4.5,2.2,facecolor='#d67528'))
a.add_patch(Rectangle((38,8),11.3,8,facecolor='#3e5664',alpha=.8))
a.plot([38,56],[10.4,10.4],color='#5b9a96',ls='--',lw=1.3)
a.annotate('Jaw adapter passes above',xy=(48,10.4),xytext=(38,20),fontsize=9,arrowprops={'arrowstyle':'->','color':'#5b9a96'},color='#376965')
a.annotate('Carriage hits this toe',xy=(49.5,9),xytext=(38,-6),fontsize=9,arrowprops={'arrowstyle':'->','color':'#b05719'},color='#b05719')
a.set(xlim=(36,61),ylim=(-8,23))
fig.text(.69,.36,'ENLARGED OUTER-SHOULDER SECTION',fontsize=9,weight='bold',color='#5a6a73')
fig.text(.69,.27,'10 mm high stop; 0.4 mm nominal\nclearance below the jaw adapter.',fontsize=11,linespacing=1.6,color='#344b55')
fig.text(.05,.13,'Use the combined Quest + rail-stop plate if printing the controller mount.\nEach stop takes one M3 countersunk screw into a side-facing insert in the plate.',fontsize=11,linespacing=1.6,color='#344b55')
fig.text(.05,.055,'FIT PROTOTYPE  /  Check your carriage shoulder height and gently test all four stops before normal use.',fontsize=10,color='#9c5a26')
fig.savefig(OUT/'rail_stop_placement.png',dpi=170,facecolor=fig.get_facecolor());plt.close(fig)
report={'status':'fit_prototype','parameters_mm':P,'plates':checks,'stops':{'A_watertight':bool(ma.is_watertight),'B_watertight':bool(mb.is_watertight),'each_volume_mm3':float(ma.volume),'quantity':4},'checks':{'rail_interference_mm3':0,'nominal_carriage_contact_mm3':hit,'nominal_carriage_centre_limit_mm':limit,'rail_end_margin_mm':.5,'adapter_z_clearance_mm':gap,'finger_holder_y_clearance_mm':.479999},'unverified':['clone rail and carriage dimensions','actual outer carriage shoulder height','insert and screw fit','impact/retention strength','physical jaw travel']}
report['print_layout']={'orientation':'broad mounting face down','height_mm':4.5,'minimum_xy_gap_mm':8,'footprint_mm':[30,30],'objects':4}
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
