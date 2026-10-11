"""Fit, skin and animate Moku's four-legged rig in Blender background mode."""
import bpy
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
NAME = 'MokuTheIslandRider'
ASSET = ROOT/'Resources/Mount'/NAME
OUT = ROOT/'Artifacts/MountPrep'
OUT.mkdir(parents=True, exist_ok=True)
(ASSET/'Export').mkdir(exist_ok=True)
bpy.context.preferences.use_preferences_save = False
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=str(ASSET/'Source'/(NAME+'.fbx')))
mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
mesh.name=NAME
bpy.context.view_layer.objects.active=mesh
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
mesh.data.calc_loop_triangles();source_triangles=len(mesh.data.loop_triangles)
reduction=mesh.modifiers.new('GameMeshReduction','DECIMATE')
reduction.ratio=100000/source_triangles;reduction.use_collapse_triangulate=True
bpy.ops.object.modifier_apply(modifier=reduction.name)
print('MOUNT_REDUCED',len(mesh.data.polygons),flush=True)

data=bpy.data.armatures.new(NAME+'_Skeleton')
rig=bpy.data.objects.new('root',data);bpy.context.collection.objects.link(rig)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
def bone(name,head,tail,parent=None,deform=True):
    b=data.edit_bones.new(name);b.head=head;b.tail=tail;b.use_deform=deform
    if parent:b.parent=data.edit_bones[parent]
    return b
bone('root',(0,0,0),(0,0,.18),deform=False)
bone('body',(0,.28,.50),(0,-.27,.58),'root')
bone('chest',(0,-.27,.58),(0,-.62,.85),'body')
bone('neck',(0,-.62,.85),(0,-.66,1.30),'chest')
bone('head',(0,-.66,1.30),(0,-.89,1.54),'neck')
bone('saddle',(0,.03,.90),(0,.03,1.03),'body')
bone('tail_01',(0,.45,.49),(0,.84,.54),'body')
bone('tail_02',(0,.84,.54),(0,1.13,.78),'tail_01')
legs={}
for label,y,sign_y in [('front',-.51,-1),('hind',.46,1)]:
    for side,sign_x in [('l',1),('r',-1)]:
        prefix=label+'_'+side
        hip=Vector((sign_x*.32,y,.40))
        knee=Vector((sign_x*.42,y+sign_y*.10,.23))
        ankle=Vector((sign_x*.44,y+sign_y*.16,.09))
        toe=ankle+Vector((0,-.12,-.055))
        bone(prefix+'_upper',hip,knee,'chest' if label=='front' else 'body')
        bone(prefix+'_lower',knee,ankle,prefix+'_upper')
        bone(prefix+'_foot',ankle,toe,prefix+'_lower')
        legs[prefix]=(hip,knee,ankle,toe)
bpy.ops.object.mode_set(mode='OBJECT')
rig.show_in_front=True;data.display_type='OCTAHEDRAL'
mesh.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print('MOUNT_AUTO_WEIGHTS_COMPLETE',flush=True)

# Keep the saddle and its cloth/rope fittings rigid on the body. Heat weights
# otherwise let short hind legs pull nearby saddle ornaments through the flank.
groups={g.name:g for g in mesh.vertex_groups}
deform=[b for b in data.bones if b.use_deform]
def segment_distance(point,a,b):
    delta=b-a;t=max(0,min(1,(point-a).dot(delta)/delta.length_squared))
    return (point-(a+t*delta)).length
repaired=0
for v in mesh.data.vertices:
    x,y,z=v.co
    selected=None
    if -.29<y<.40 and z>.58: selected='saddle'
    if selected:
        for g in list(v.groups):mesh.vertex_groups[g.group].remove([v.index])
        groups[selected].add([v.index],1.0,'REPLACE')
    elif not any(g.weight>.00001 for g in v.groups):
        nearest=min(deform,key=lambda b:segment_distance(v.co,b.head_local,b.tail_local))
        groups[nearest.name].add([v.index],1.0,'REPLACE');repaired+=1
bpy.context.view_layer.objects.active=mesh
bpy.ops.object.vertex_group_clean(group_select_mode='ALL',limit=.002,keep_single=True)
bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL',limit=4)
bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL',lock_active=False)
mat=bpy.data.materials.new('M_'+NAME);mat.use_nodes=True
nodes=mat.node_tree.nodes;links=mat.node_tree.links;shader=nodes.get('Principled BSDF')
for channel,socket in [('BaseColor','Base Color'),('Normal','Normal'),('Roughness','Roughness'),('Metallic','Metallic')]:
    tex=nodes.new('ShaderNodeTexImage');tex.label=channel
    tex.image=bpy.data.images.load(str(ASSET/'Source'/(NAME+'_'+channel+'.png')))
    if channel!='BaseColor':tex.image.colorspace_settings.name='Non-Color'
    if channel=='Normal':
        normal=nodes.new('ShaderNodeNormalMap');links.new(tex.outputs['Color'],normal.inputs['Color'])
        links.new(normal.outputs['Normal'],shader.inputs[socket])
    else:links.new(tex.outputs['Color'],shader.inputs[socket])
mesh.data.materials.clear();mesh.data.materials.append(mat)
for polygon in mesh.data.polygons:polygon.use_smooth=True

scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.render.fps=30
weights={b.name:0 for b in deform};unweighted=0;maximum=0
for v in mesh.data.vertices:
    influences=[g for g in v.groups if mesh.vertex_groups[g.group].name in weights and g.weight>.00001]
    maximum=max(maximum,len(influences));unweighted+=not influences
    for g in influences:weights[mesh.vertex_groups[g.group].name]+=1
assert unweighted==0 and maximum<=4
assert all(weights[p+'_'+part]>20 for p in legs for part in ['upper','lower','foot'])
for material in list(bpy.data.materials):
    if material.users==0:bpy.data.materials.remove(material)
for image in list(bpy.data.images):
    if image.users==0:bpy.data.images.remove(image)
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/(NAME+'.blend')))
bpy.ops.file.make_paths_relative();bpy.ops.wm.save_mainfile()
report=dict(passed=True,source_triangles=source_triangles,triangles=len(mesh.data.polygons),
    vertices=len(mesh.data.vertices),bones=len(data.bones),unweighted_vertices=unweighted,
    max_influences=maximum,repaired_vertices=repaired,influence_counts=weights,
    saddle_position_metres=[0,.03,1.0])
(ASSET/'RigValidation.json').write_text(json.dumps(report,indent=2)+'\n')
exec(compile((ROOT/'Scripts/Animate-Mount.py').read_text(),str(ROOT/'Scripts/Animate-Mount.py'),'exec'))
