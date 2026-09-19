"""Editable concept, mm. Controller fit and base interface are provisional.

Run: uv run --python 3.12 --with cadquery --with trimesh --with matplotlib python build_concept.py
"""
from pathlib import Path
import json
import cadquery as cq
import trimesh
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

OUT = Path(__file__).resolve().parent
# These are design inputs, NOT measured controller dimensions.
P = dict(base_pitch=40.57, base_width=56., base_depth=24., base_thickness=6.,
         screw_clearance=3.4, reach=62., saddle_rx=19., saddle_ry=17.,
         wall=4., saddle_bottom=25., saddle_height=48., strap_width=10.)

def box(x,y,z,c):
    return cq.Workplane('XY').box(x,y,z).translate(c)

# Two independent fasteners stop flange rotation. Match real interface before use.
base = box(P['base_width'],24,6,(0,0,3))
for x in [-P['base_pitch']/2,P['base_pitch']/2]:
    hole = cq.Solid.makeCylinder(P['screw_clearance']/2,12,cq.Vector(x,0,-3),cq.Vector(0,0,1))
    base = base.cut(hole)

# Broad bridge and paired triangular webs instead of the slender marker stalk.
bridge = box(28,53,6,(0,26,20))
for x in [-12,8]:
    web = cq.Workplane('YZ',origin=(x,0,0)).polyline([(0,3),(0,20),(51,20)]).close().extrude(4)
    bridge = bridge.union(web)

# Open half-elliptical cradle: sample fit surface, replace with measured sections.
cy=P['reach']; z0=P['saddle_bottom']; ht=P['saddle_height']
outer=cq.Workplane('XY',origin=(0,cy,z0)).ellipse(P['saddle_rx']+4,P['saddle_ry']+4).extrude(ht)
inner=cq.Workplane('XY',origin=(0,cy,z0-1)).ellipse(P['saddle_rx'],P['saddle_ry']).extrude(ht+2)
cradle=outer.cut(inner).intersect(box(80,50,ht+4,(0,cy-25,z0+ht/2)))
# Back web carries the saddle to the bridge, while leaving its bottom open.
spine=box(18,7,55,(0,cy-20,45.5))
cradle=cradle.union(spine)
for side in [-1,1]:
    ear=box(9,8,ht,(side*23.5,cy-3,z0+ht/2))
    for z in [z0+10,z0+ht-10]:
        ear=ear.cut(box(3,12,P['strap_width']+1,(side*24,cy-3,z)))
    cradle=cradle.union(ear)
mount=base.union(bridge).union(cradle).clean()
assert mount.val().isValid() and len(mount.solids().vals())==1
cq.exporters.export(mount,str(OUT/'quest_mount_CONCEPT.step'))
cq.exporters.export(mount,str(OUT/'quest_mount_CONCEPT.stl'),tolerance=0.08,angularTolerance=0.12)
mesh=trimesh.load(OUT/'quest_mount_CONCEPT.stl')
assert mesh.is_watertight and mesh.volume>0

# Separate, intentionally simplified controller envelope for visual explanation.
grip=cq.Workplane('XY',origin=(0,cy,17)).ellipse(17.5,15.5).extrude(65)
head=cq.Workplane('XY',origin=(0,cy,82)).ellipse(30,25).extrude(12)
envelope=grip.union(head)
cq.exporters.export(envelope,str(OUT/'controller_ENVELOPE_NOT_FOR_FIT.stl'))
em=trimesh.load(OUT/'controller_ENVELOPE_NOT_FOR_FIT.stl')

fig=plt.figure(figsize=(14,9),facecolor='#f6f5f1')
fig.text(.045,.94,'QUEST / tinyumi',fontsize=26,weight='bold',color='#172b37')
fig.text(.045,.895,'Touch Plus rigid mount · concept v0',fontsize=15,color='#52636c')
ax=fig.add_axes([.02,.13,.64,.72],projection='3d',computed_zorder=False)
ax.set_facecolor('#f6f5f1')
def draw(m,color,alpha=1):
    tris=m.triangles
    # Flat shading preserves readable CAD facets without invented geometry.
    n=m.face_normals
    light=np.array([-.4,-.7,1]); light/=np.linalg.norm(light)
    brightness=.58+.42*np.maximum(0,n@light)
    import matplotlib.colors as mc
    rgb=np.array(mc.to_rgb(color))
    colors=np.column_stack([brightness[:,None]*rgb,np.full(len(tris),alpha)])
    ax.add_collection3d(Poly3DCollection(tris,facecolors=colors,edgecolors='none'))
draw(mesh,'#168f9b')
draw(em,'#cbd2d4',.27)
# Two retention bands shown schematically around the controller body.
for z in [35,63]:
    band=(cq.Workplane('XY',origin=(0,cy,z-5)).ellipse(24,20)
          .ellipse(22.5,18.5).extrude(10))
    cq.exporters.export(band,str(OUT/'_band.stl'))
    draw(trimesh.load(OUT/'_band.stl'),'#293b46',.8)
(OUT/'_band.stl').unlink()
ax.set(xlim=(-52,52),ylim=(-10,100),zlim=(0,110))
ax.set_box_aspect((104,110,110)); ax.view_init(elev=24,azim=-48);ax.set_axis_off()
items=[('01  RIGID BASE','Two M3 clearance holes; 40.57 mm nominal pitch.\nCheck actual plate access and screw engagement.'),
       ('02  BRACED BRIDGE','Short, wide support with two webs.\nNo controller on the long marker-ball stalk.'),
       ('03  OPEN CRADLE','Two retention bands; controller bottom open.\nReplace sample contour with measured contact pads.'),
       ('04  TRACKING CLEARANCE','Face and tracking regions must stay visible.\nCheck buttons, hand, jaws and wrist-camera view.')]
for i,(title,body) in enumerate(items):
    y=.79-i*.145
    fig.text(.66,y,title,fontsize=12,weight='bold',color='#16818d')
    fig.text(.66,y-.049,body,fontsize=10.5,linespacing=1.6,color='#344956')
fig.text(.05,.115,'TEAL: proposed printed mount   /   GREY: schematic controller   /   DARK: retention bands',fontsize=10,color='#52636c')
fig.text(.05,.06,'DESIGN STUDY — not fit-verified. Controller shape and placement are illustrative; no tracking or load validation yet.',fontsize=10,color='#9c5a26')
fig.savefig(OUT/'quest_mount_concept.png',dpi=170,facecolor=fig.get_facecolor())
plt.close(fig)
report={'status':'concept_only_not_fit_verified','parameters_mm':P,
        'cad_valid':mount.val().isValid(),'solid_count':len(mount.solids().vals()),
        'stl_watertight':bool(mesh.is_watertight),'volume_mm3':float(mesh.volume),
        'bounds_mm':mesh.bounds.tolist(),
        'estimated_petg_mass_g_at_100pct_solid':float(mesh.volume/1000*1.27),
        'controller_envelope':'Illustrative; not measured Touch Plus geometry',
        'unverified':['controller fit and tracking-emitter clearance','mount-to-plate interface and screw access',
                      'hand and full jaw sweep clearance','camera field of view','strength and deflection','pose accuracy']}
(OUT/'concept_validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
