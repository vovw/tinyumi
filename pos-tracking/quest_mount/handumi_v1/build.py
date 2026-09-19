"""Modified HandUMI supports, Apache-2.0; upstream originals are in source/.
Run with uv run --python 3.12 --with cadquery --with trimesh --with matplotlib python build.py
Millimetres. Preserve original ring surfaces; replace only mounting end.
"""
from pathlib import Path
import json, hashlib
import cadquery as cq
from OCP.gp import gp_Trsf
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
P={'bolt_pitch':16.,'hole_y':-28.,'boss_width':30.,'boss_depth':12.,'boss_height':4.,
   'insert_bore':4.,'insert_depth':5.4,'tab_thickness':5.,'ring_tilt_degrees':45.}
def box(w,d,h,c):return cq.Workplane('XY').box(w,d,h).translate(c)
def transform(shape,rows):
 t=gp_Trsf();t.SetValues(*[v for row in rows for v in row]);return shape.transformShape(cq.Matrix(t))
def rounded(w,d,h,z,y=0):return cq.Workplane('XY',origin=(0,y,z)).rect(w,d).extrude(h).edges('|Z').fillet(2)
def save(shape,name):
 cq.exporters.export(shape,str(OUT/(name+'.step')))
 cq.exporters.export(shape,str(OUT/(name+'.stl')),tolerance=.05,angularTolerance=.1)
 m=trimesh.load(OUT/(name+'.stl'))
 # Drop zero-area/duplicate tessellation triangles; retain valid CAD surface.
 m.merge_vertices(digits_vertex=7)
 m.update_faces(m.nondegenerate_faces())
 m.update_faces(m.unique_faces())
 m.remove_unreferenced_vertices()
 m.export(OUT/(name+'.stl'))
 assert shape.isValid() and len(shape.Solids())==1 and m.is_watertight and m.volume>0,name
 return m

plate_orig=cq.importers.importStep(str(ROOT/'hardware/STEP/plate_v6.step')).val()
boss=rounded(30,12,4,-4,-26.5).val()
plate=plate_orig.fuse(boss)
for x in [-8,8]:
 bore=cq.Solid.makeCylinder(2,5.4,cq.Vector(x,-28,-4),cq.Vector(0,0,1))
 plate=plate.cut(bore)
plate=plate.clean(); pm=save(plate,'plate_v6_handumi_mount')
# Rails and mechanism remain unchanged above the original underside plane.
original_above=plate_orig.intersect(box(200,200,50,(0,0,27)).val())
modified_above=plate.intersect(box(200,200,50,(0,0,27)).val())
assert abs(original_above.Volume()-modified_above.Volume())<1e-5

c=np.sqrt(.5)
# Ring face points up and back toward the operator. Mount is on the camera-opposite edge.
placement=[[1,0,0,0],[0,-c,c,-28],[0,-c,-c,-10]]
mounts={};rings={};normalized={};checks={}
scene=trimesh.load(ROOT/'output/models/yam_umi_assembled_with_tips.glb')
components={k:m.copy() for k,m in scene.geometry.items()}
for m in components.values():m.apply_scale(1000)

for side in ['right','left']:
 src=cq.importers.importStep(str(OUT/'source'/f'{side}_controller_support.step')).val()
 if side=='right':
  norm=transform(src,[[1,0,0,-22.939026770111],[0,1,0,-16],[0,0,1,7]])
  cut=9.
 else:
  norm=transform(src,[[1,0,0,-2.2111106327345],[0,0,-1,34.1296772358573],[0,1,0,2]])
  cut=9.5
 normalized[side]=norm
 # Trim upstream mounting fork ahead of the controller contact opening.
 ring=norm.intersect(box(150,150,150,(0,cut+75,0)).val())
 assert ring.isValid() and len(ring.Solids())==1 and ring.Volume()>0.65*src.Volume()
 # A short solid neck joins the retained ring to the new plate tab.
 neck=box(20,cut+3.5,8,(0,(cut-.5)/2,0)).val()
 ring_world=transform(ring,placement)
 stem=transform(neck,placement)
 tab=rounded(30,12,5,-9,-28).val()
 mount=ring_world.fuse(stem).fuse(tab)
 for x in [-8,8]:
  mount=mount.cut(cq.Solid.makeCylinder(1.7,8,cq.Vector(x,-28,-10),cq.Vector(0,0,1)))
  mount=mount.cut(cq.Solid.makeCone(3.2,1.7,1.5,cq.Vector(x,-28,-9),cq.Vector(0,0,1)))
  mount=mount.cut(cq.Solid.makeCylinder(3.3,31,cq.Vector(x,-28,-40),cq.Vector(0,0,1)))
 cleaned=mount.clean()
 if cleaned.isValid():mount=cleaned
 m=save(mount,f'handumi_yam_{side}_support'); mounts[side]=mount;rings[side]=ring_world
 # Exact CAD check with modified stationary plate; intended mating face has zero volume.
 overlap=mount.intersect(plate).Volume()
 assert overlap<1e-5,(side,'plate collision',overlap)
 # Every non-plate part in the existing reference assembly has disjoint AABBs.
 # Expand X over the entire plate width for moving parts as a conservative jaw-travel check.
 # This does not model the human hand or unmodelled cables/controller.
 collision=[]; margins={}
 for name,part in components.items():
  if name=='main_plate':continue
  b=part.bounds.copy()
  if name.startswith(('carriage','adapter','finger_','official_yam_tip','tip_screw')):b[:,0]=[-102,102]
  d=np.maximum(b[0]-m.bounds[1],m.bounds[0]-b[1]);sep=float(np.max(d))
  if sep<=0:collision.append(name)
  margins[name]=round(sep,3)
 checks[side]={'cad_valid':mount.isValid(),'solid_count':len(mount.Solids()),'stl_watertight':bool(m.is_watertight),
  'volume_mm3':float(m.volume),'bounds_mm':m.bounds.tolist(),'plate_intersection_mm3':overlap,
  'conservative_assembly_aabb_candidates':collision,'separation_mm_by_component':margins,
  'retained_upstream_volume_mm3':ring.Volume(),'upstream_volume_mm3':src.Volume(),'ring_trim_local_y_mm':cut,'controller_fit':'upstream contour retained; Touch Plus fit not physically verified'}

# Render with per-triangle depth sorting across all objects for clean occlusion.
def mesh_of(s):
 v,f=s.tessellate(.12,.12);return trimesh.Trimesh(np.array([x.toTuple() for x in v]),np.array(f),process=False)
def render(ax,items,elev=22,az=-60):
 az=np.deg2rad(az);el=np.deg2rad(elev)
 eye=np.array([np.cos(el)*np.cos(az),np.cos(el)*np.sin(az),np.sin(el)])
 u=np.array([-np.sin(az),np.cos(az),0]);v=np.cross(eye,u)
 tris=[];cols=[]
 import matplotlib.colors as mc
 for m,col in items:
  tri=m.triangles;light=np.array([-.3,-.4,.866]);light/=np.linalg.norm(light)
  b=.58+.42*np.maximum(0,m.face_normals@light)
  tris.append(tri);cols.append(b[:,None]*np.array(mc.to_rgb(col)))
 t=np.concatenate(tris);color=np.concatenate(cols);order=np.argsort(t.mean(axis=1)@eye)
 from matplotlib.collections import PolyCollection
 projected=np.stack([t@u,t@v],axis=-1)
 ax.add_collection(PolyCollection(projected[order],facecolors=color[order],edgecolors='none'))
 lo=projected.reshape(-1,2).min(axis=0);hi=projected.reshape(-1,2).max(axis=0);gap=(hi-lo)*.08
 ax.set(xlim=(lo[0]-gap[0],hi[0]+gap[0]),ylim=(lo[1]-gap[1],hi[1]+gap[1]));ax.set_aspect('equal');ax.axis('off')

fig=plt.figure(figsize=(15,10),facecolor='#f6f5f1')
fig.text(.04,.94,'HANDUMI MOUNT FOR tinyumi',fontsize=25,weight='bold',color='#20353f')
fig.text(.04,.895,'Original controller ring + short mounting tab + two screws',fontsize=14,color='#53636b')
a=fig.add_axes([.025,.41,.29,.34]);render(a,[(mesh_of(normalized['right']),'#aeb8bc')],35,-65)
fig.text(.05,.79,'01  ORIGINAL HANDUMI',fontsize=11,weight='bold',color='#53636b')
# Display adapted part in a ring-oriented view, separate from assembly coordinates.
a=fig.add_axes([.33,.41,.29,.34]);render(a,[(mesh_of(mounts['right']),'#168b92')],25,-115)
fig.text(.355,.79,'02  YAM ADAPTATION',fontsize=11,weight='bold',color='#168b92')
a=fig.add_axes([.64,.20,.34,.55])
Rv=np.array([[1,0,0],[0,0,-1],[0,1,0]])
items=[]
for name,m in components.items():
 m=m.copy()
 if name=='main_plate':m=pm.copy()
 m.vertices=m.vertices@Rv.T
 col='#adb6b9' if not name.startswith(('official_yam_tip','camera_')) else '#45535b'
 items.append((m,col))
mm=mesh_of(mounts['right']);mm.vertices=mm.vertices@Rv.T;items.append((mm,'#168b92'))
render(a,items,24,55)
fig.text(.68,.79,'03  ON THE GRIPPER',fontsize=11,weight='bold',color='#53636b')
fig.text(.055,.34,'Their contoured ring is retained.\nThe fork that fits HandUMI is removed.',fontsize=12,linespacing=1.6,color='#344b55')
fig.text(.36,.34,'One compact tab replaces the fork.\nNo tall cradle or separate brace.',fontsize=12,linespacing=1.6,color='#344b55')
fig.text(.05,.19,'A small underside pad on the revised plate takes two M3 inserts.\nThe support sits on the edge opposite the camera, tilted back toward the operator.',fontsize=12,linespacing=1.6,color='#344b55')
fig.text(.05,.075,'FIT PROTOTYPE  /  Left and right STEP + STL included. Real controller fit, hand clearance and tracking still need a physical check.',fontsize=10,color='#9c5a26')
fig.savefig(OUT/'handumi_yam_mount.png',dpi=160,facecolor=fig.get_facecolor());plt.close(fig)
# Isolated hero and a coloured assembly for inspection.
fig,ax=plt.subplots(figsize=(8,7));render(ax,[(mesh_of(mounts['right']),'#168b92')],25,-115);fig.savefig(OUT/'support_detail.png',dpi=180,transparent=True);plt.close(fig)
assembled=trimesh.Scene()
for name,m in components.items():
 m=pm.copy() if name=='main_plate' else m.copy();m.visual.face_colors=[170,181,188,255];m.apply_scale(.001);assembled.add_geometry(m,geom_name=name)
m=mesh_of(mounts['right']);m.visual.face_colors=[22,139,146,255];m.apply_scale(.001);assembled.add_geometry(m,geom_name='handumi_yam_right_support');assembled.export(OUT/'yam_with_handumi_mount.glb')
report={'status':'fit_prototype','source_commit':'fc7462ad1ed58c0c8538f6c7dbb732211d088ca8','parameters_mm':P,
 'plate':{'cad_valid':plate.isValid(),'watertight':bool(pm.is_watertight),'top_above_z2_unchanged':True},'supports':checks,
 'unverified':['actual Touch Plus fit in upstream rings','controller body/head clearance','human hand and wrist clearance','tracking visibility','screw and insert fit','loaded stiffness'],
 'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'source').glob('*.step')}}
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
