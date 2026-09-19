from pathlib import Path
import json, zipfile, math, sys
import numpy as np
import trimesh
import manifold3d
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
NS='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
E.register_namespace('',NS)
q=lambda n:f'{{{NS}}}{n}'
# Trim the original closed reference solids with robust solid operations.
# The older illustration-only cut meshes are deliberately not used.
for side in ['left', 'right']:
 source=trimesh.load(ROOT/f'hardware/reference/i2rt_linear_4310/tip_{side}.stl')
 source.apply_scale(1000)
 solid=manifold3d.Manifold(manifold3d.Mesh(np.asarray(source.vertices,dtype=np.float32),np.asarray(source.faces,dtype=np.uint32)))
 solid=solid.trim_by_plane([0,0,-1],145.61)
 result=solid.to_mesh()
 tip=trimesh.Trimesh(np.asarray(result.vert_properties)[:,:3],np.asarray(result.tri_verts))
 assert tip.is_watertight and tip.volume > 0
 tip.export(OUT/f'tip_{side}_prototype.stl')
D405='--d405' in sys.argv
items=[]
def add(name,path,rotate=False,plate=0):
 m=trimesh.load(ROOT/path)
 if rotate:m.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,[1,0,0]))
 m.apply_translation(-m.bounds[0]); assert m.is_watertight, name
 items.append(dict(name=name,mesh=m,plate=plate,source=str(path)))
add('Updated base - Quest and stops','hardware/rail_stops/plate_v6_quest_and_rail_stops.stl')
for i in range(2):
 add(f'Jaw adapter {i+1}','hardware/STL/adapter_v10.stl')
 add(f'Finger holder {i+1}','hardware/STL/handle_v13.stl',True)
 add(f'L bracket {i+1}','hardware/STL/L_bracket_v3.stl',True)
for i in range(4):add(f'Pinion v{i} - fit test',f'hardware/STL/pinion_z18_deep_v{i}.stl')
if D405:
 add('RealSense D405 camera mount','hardware/realsense_d405/d405_mount_print.stl')
else:
 add('Fisheye camera mount','hardware/STL/YAM_linear_gripper_fisheye_camera_mount.stl',True)
for side in 'AB':
 for i in range(2):add(f'Rail stop {side}{i+1}',f'hardware/rail_stops/rail_stop_{side}_print_2.stl')
for side in ['left','right']:add(f'{side.title()} fingertip - PROTOTYPE',f'bambu/full_rebuild/tip_{side}_prototype.stl',True,1)
# Keep bed margins and 10mm gaps. Explicit rows make layout repeatable.
for plate in [0,1]:
 x=y=12.;rowheight=0.
 for item in sorted([i for i in items if i['plate']==plate],key=lambda i:-i['mesh'].extents[1]):
  w,h,_=item['mesh'].extents
  if x+w>244:x=12.;y+=rowheight+10;rowheight=0.
  if y+h>244:raise ValueError('Layout exceeds plate')
  item['xy']=(x+plate*307.2,y);x+=w+10;rowheight=max(rowheight,h)
model=E.Element(q('model'),{'unit':'millimeter'})
E.SubElement(model,q('metadata'),{'name':'Application'}).text='BambuStudio-02.05.00.66'
E.SubElement(model,q('metadata'),{'name':'BambuStudio:3mfVersion'}).text='1'
res=E.SubElement(model,q('resources'));build=E.SubElement(model,q('build'))
config=E.Element('config')
for idx,it in enumerate(items,1):
 it['id']=idx;m=it['mesh'];obj=E.SubElement(res,q('object'),{'id':str(idx),'type':'model','name':it['name']});mesh=E.SubElement(obj,q('mesh'))
 vs=E.SubElement(mesh,q('vertices'));ts=E.SubElement(mesh,q('triangles'))
 for v in m.vertices:E.SubElement(vs,q('vertex'),dict(zip(['x','y','z'],[f'{c:.7f}' for c in v])))
 for f in m.faces:E.SubElement(ts,q('triangle'),dict(zip(['v1','v2','v3'],map(str,f))))
 x,y=it['xy'];E.SubElement(build,q('item'),{'objectid':str(idx),'transform':f'1 0 0 0 1 0 0 0 1 {x} {y} 0','printable':'1'})
 ob=E.SubElement(config,'object',{'id':str(idx)})
 for key,value in [('name',it['name']),('extruder','1')]:E.SubElement(ob,'metadata',{'key':key,'value':value})
 part=E.SubElement(ob,'part',{'id':str(idx),'subtype':'normal_part'})
 E.SubElement(part,'metadata',{'key':'name','value':it['name']})
for p in [0,1]:
 pl=E.SubElement(config,'plate')
 for key,value in [('plater_id',str(p+1)),('plater_name',['Complete gripper body','Prototype fingertips'][p]),('locked','false')]:E.SubElement(pl,'metadata',{'key':key,'value':value})
 for it in [i for i in items if i['plate']==p]:
  ins=E.SubElement(pl,'model_instance')
  for key,value in [('object_id',str(it['id'])),('instance_id','0'),('identify_id',str(it['id']))]:E.SubElement(ins,'metadata',{'key':key,'value':value})
with zipfile.ZipFile(ROOT/'hardware/rail_stops/quest_plate_and_stops_A1_PETG.3mf') as z:settings=json.loads(z.read('Metadata/project_settings.config'))
settings.update(support_type='normal(auto)',support_style='snug',support_interface_top_layers='3',support_interface_spacing='0.3',sparse_infill_pattern='gyroid')
with zipfile.ZipFile(OUT/('tinyumi_full_rebuild_D405_A1_PETG.3mf' if D405 else 'tinyumi_full_rebuild_A1_PETG.3mf'),'w',zipfile.ZIP_DEFLATED) as z:
 z.writestr('3D/3dmodel.model',E.tostring(model,encoding='utf-8',xml_declaration=True))
 z.writestr('Metadata/model_settings.config',E.tostring(config,encoding='utf-8',xml_declaration=True))
 z.writestr('Metadata/project_settings.config',json.dumps(settings))
 z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
 z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
manifest=[dict(name=i['name'],source=i['source'],plate=i['plate']+1,xy=i['xy'],size=i['mesh'].extents.tolist(),watertight=i['mesh'].is_watertight) for i in items]
(OUT/('manifest_D405.json' if D405 else 'manifest.json')).write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
