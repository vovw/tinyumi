"""D405 replacement camera bracket. Millimetres; fit prototype.
uv run --python 3.12 --with cadquery --with trimesh --with numpy --with matplotlib python hardware/realsense_d405/build.py
"""
from pathlib import Path
import json,math
import cadquery as cq
import numpy as np
import trimesh
from OCP.gp import gp_Trsf
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
N=np.array([0.,-2**-.5,2**-.5]);U=np.array([1.,0.,0.]);V=np.cross(N,U);B=np.array([0.,100.,0.])
def transform(s):
 r=np.column_stack([U,V,N]);t=gp_Trsf();t.SetValues(*[v for row in np.column_stack([r,B]) for v in row]);return s.transformShape(cq.Matrix(t))
def box(w,d,h,c):return cq.Workplane('XY').box(w,d,h).translate(tuple(c)).val()
def cyl(r,h,p,d):return cq.Solid.makeCylinder(r,h,cq.Vector(*p),cq.Vector(*d))
def save(s,name):
 assert s.isValid() and len(s.Solids())==1,(name,len(s.Solids()))
 cq.exporters.export(s,str(OUT/(name+'.step')))
 cq.exporters.export(s,str(OUT/(name+'.stl')),tolerance=.035,angularTolerance=.1)
 m=trimesh.load(OUT/(name+'.stl'));assert m.is_watertight and m.volume>0
 return m
# Back pad touches the rear of the camera only; sides, USB Micro-B and front stay open.
pad=cq.Workplane('XY',origin=(0,0,-5)).rect(42,16).extrude(5).edges('|Z').fillet(2).val();pad=transform(pad)
body=transform(box(42,42,23,(0,0,11.5)))
# Extra 2 mm clearance around the body for supports; rear face datum is unchanged.
clearance=transform(box(46,46,26,(0,0,13)))
foot=cq.Workplane('XY',origin=(0,31.5,-5)).rect(54,15).extrude(5).edges('|Z').fillet(2).val()
ribs=[]
for x in [-18.5,14.5]:
 rib=cq.Workplane('YZ',origin=(x,0,0)).polyline([(34,0),(110,0),(110,-25),(65,-25),(34,-5)]).close().extrude(4).val()
 ribs.append(rib.cut(clearance))
s=foot.fuse(pad,*ribs).clean()
# Existing plate insert pair, measured from STEP (40.5708 mm pitch).
for x in [-20.285398483276,20.285398483276]:
 s=s.cut(cyl(1.7,7,(x,29,-6),(0,0,1)))
 s=s.cut(cq.Solid.makeCone(3.2,1.7,1.5,cq.Vector(x,29,-5),cq.Vector(0,0,1)))
# D405 rear pair: 20 mm pitch. M3x8 socket head + 5mm pad = 3mm engagement.
for x in [-10.,10.]:
 p=B+x*U
 s=s.cut(cyl(1.7,7,p-6*N,N))
 # Tool/head access behind pad, never a countersink into the camera datum.
 s=s.cut(cyl(3.5,30,p-35*N,N))
s=s.clean();m=save(s,'d405_mount_assembly')
# Preserve this physical orientation in assembly. Print on its inverted base plane.
printing=s.rotate((0,0,0),(1,0,0),180);bb=printing.BoundingBox();printing=printing.translate((-bb.xmin,-bb.ymin,-bb.zmin))
pm=save(printing,'d405_mount_print')
# Small flat interface gauge checks the expensive camera's screws before the long print.
g=cq.Workplane('XY').rect(34,12).extrude(5).edges('|Z').fillet(2)
for x in [-10,10]:g=g.cut(cq.Workplane('XY').center(x,0).circle(1.7).extrude(5))
save(g.val(),'d405_rear_fit_gauge')
plate=cq.importers.importStep(str(ROOT/'hardware/rail_stops/plate_v6_quest_and_rail_stops.step')).val()
checks={'status':'fit_prototype','mount_valid':s.isValid(),'one_solid':len(s.Solids())==1,'watertight':m.is_watertight,'plate_intersection_mm3':s.intersect(plate).Volume(),'camera_intersection_mm3':s.intersect(body).Volume(),'base_hole_pitch_mm':40.570796966552,'camera_hole_pitch_mm':20,'pad_thickness_mm':5,'camera_screw':'M3x8 socket head, 3mm nominal insertion; maximum 4mm','base_screw':'2x M3x8 90-degree countersunk, 3mm nominal engagement','rear_camera_center_mm':B.tolist(),'view_direction':N.tolist(),'print_bounds_mm':pm.bounds.tolist()}
assert checks['plate_intersection_mm3']<1e-5 and checks['camera_intersection_mm3']<1e-5,checks
# Conservative moving-part band from assembly meshes: new bracket remains below
# the moving jaws near the base; camera body is beyond their Y travel envelope.
checks['camera_min_y_mm']=body.BoundingBox().ymin
checks['moving_assembly_max_y_mm']=35
checks['camera_to_moving_y_gap_mm']=body.BoundingBox().ymin-35
checks['remaining_checks']=['Real camera and USB plug clearance','Full-stroke hand/strap clearance','Print strength and screw fit','Camera extrinsics/intrinsics and marker visibility']
(OUT/'validation.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks,indent=2))
# Export a clearly identified camera envelope and assembly preview for inspection.
cq.exporters.export(body,str(OUT/'D405_ENVELOPE_NOT_FOR_PRINT.step'))
scene=trimesh.Scene()
for name,mesh,color in [('base',trimesh.load(ROOT/'hardware/rail_stops/plate_v6_quest_and_rail_stops.stl'),[175,185,195,255]),('D405 bracket',m,[245,163,40,255])]:
 mesh.visual.face_colors=color;scene.add_geometry(mesh,node_name=name)
cam=trimesh.creation.box(extents=[42,42,23]);T=np.eye(4);T[:3,:3]=np.column_stack([U,V,N]);T[:3,3]=B+11.5*N;cam.apply_transform(T);cam.visual.face_colors=[90,100,110,210];scene.add_geometry(cam,node_name='D405 envelope')
scene.export(str(OUT/'d405_on_base.glb'))
# Simple mechanical overview; actual render, not an invented product picture.
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
fig=plt.figure(figsize=(11,7));ax=fig.add_subplot(111,projection='3d')
for mesh,col,alpha in [(trimesh.load(ROOT/'hardware/rail_stops/plate_v6_quest_and_rail_stops.stl'),'#aab8c5',1),(m,'#e8a132',1),(cam,'#586977',.4)]:
 ax.add_collection3d(Poly3DCollection(mesh.triangles,facecolor=col,edgecolor='none',alpha=alpha))
ax.quiver(*(B+23*N),*(55*N),color='#1677aa',arrow_length_ratio=.12)
ax.set(xlim=(-65,65),ylim=(-40,130),zlim=(-35,110),xlabel='Jaw travel X (mm)',ylabel='Camera side Y (mm)',zlabel='Toward tips Z (mm)');ax.set_box_aspect((130,170,145));ax.view_init(25,-35)
ax.set_title('D405 replacement mount — camera envelope shown translucent')
fig.tight_layout();fig.savefig(OUT/'d405_mount_preview.png',dpi=170);plt.close(fig)
