"""Round-trip the FBX, verify skin/finger chains, render rest and articulated poses."""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
NAME = 'JungleTotemScout'
FOLDER = ROOT / 'Resources/Player' / NAME
OUT = ROOT / 'Artifacts/CharacterPrep' / NAME
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=str(FOLDER / 'Export' / (NAME + '.fbx')))
rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
groups = {g.index:g.name for g in mesh.vertex_groups}
weighted = {}
unweighted = 0
max_influences = 0
for vertex in mesh.data.vertices:
    influences = [(groups[g.group],g.weight) for g in vertex.groups if g.weight > 1e-5]
    if not influences: unweighted += 1
    assert abs(sum(w for _,w in influences)-1) < .002
    max_influences = max(max_influences,len(influences))
    for bone,weight in influences: weighted[bone] = weighted.get(bone,0)+1
assert unweighted == 0
assert max_influences <= 4
chains = {}
for side in ['l','r']:
    for finger in ['thumb','middle','ring','pinky']:
        bones = [f'{finger}_{i:02d}_{side}' for i in [1,2,3]]
        assert all(b in rig.data.bones for b in bones), bones
        assert all(weighted.get(b,0)>0 for b in bones), bones
        chains[f'{finger}_{side}'] = {b:weighted[b] for b in bones}
assert rig.name == 'root' or 'root' in rig.data.bones, 'Missing FBX skeleton root'
for bone in ['pelvis','head','hand_l','hand_r','foot_l','foot_r']:
    assert bone in rig.data.bones, bone
mat = bpy.data.materials.new('M_'+NAME)
mat.use_nodes = True
nodes, links = mat.node_tree.nodes,mat.node_tree.links
shader=nodes.get('Principled BSDF')
for channel,socket in [('BaseColor','Base Color'),('Normal','Normal'),('Roughness','Roughness')]:
    node=nodes.new('ShaderNodeTexImage')
    node.image=bpy.data.images.load(str(FOLDER/'Source'/(NAME+'_'+channel+'.png')))
    if channel!='BaseColor': node.image.colorspace_settings.name='Non-Color'
    if channel=='Normal':
        normal=nodes.new('ShaderNodeNormalMap')
        links.new(node.outputs['Color'],normal.inputs['Color'])
        links.new(normal.outputs['Normal'],shader.inputs[socket])
    else: links.new(node.outputs['Color'],shader.inputs[socket])
mesh.data.materials.clear()
mesh.data.materials.append(mat)
points=[mesh.matrix_world @ Vector(p) for p in mesh.bound_box]
lo=Vector([min(v[i] for v in points) for i in range(3)])
hi=Vector([max(v[i] for v in points) for i in range(3)])
center=(lo+hi)/2
size=max(hi-lo)
bpy.ops.object.camera_add(location=center+Vector((0,-size*2.5,size*.08)))
camera=bpy.context.object
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=size*1.25
scene=bpy.context.scene
scene.camera=camera
scene.world.color=(.3,.3,.3)
for pos in [(1,-2,3),(-2,-1,1)]:
    bpy.ops.object.light_add(type='AREA',location=center+Vector(pos)*size)
    light=bpy.context.object
    light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    light.data.energy=350*size*size
    light.data.size=size*2
scene.render.engine='CYCLES'
scene.cycles.samples=24
scene.render.resolution_x=1000
scene.render.resolution_y=1000
scene.render.resolution_percentage=100
scene.render.filepath=str(OUT/'RigRest.png')
bpy.ops.render.render(write_still=True)
deps=bpy.context.evaluated_depsgraph_get()
before=[v.co.copy() for v in mesh.evaluated_get(deps).data.vertices]
for side in ['l','r']:
    for finger in ['thumb','middle','ring','pinky']:
        for i in [1,2,3]:
            bone=rig.pose.bones[f'{finger}_{i:02d}_{side}']
            bone.rotation_mode='XYZ'
            bone.rotation_euler.x=math.radians(35 if side=='l' else -35)
bpy.context.view_layer.update()
after=[v.co.copy() for v in mesh.evaluated_get(deps).data.vertices]
changed=sum((a-b).length>1e-5 for a,b in zip(after,before))
assert changed>500, ('Finger controls failed to deform mesh', changed)
scene.render.filepath=str(OUT/'RigFingerCurl.png')
bpy.ops.render.render(write_still=True)
report={'passed':True,'name':NAME,'bones':len(rig.data.bones),'vertices':len(mesh.data.vertices),
        'unweighted_vertices':unweighted,'max_influences':max_influences,'finger_chains':chains,
        'finger_pose_vertices_changed':changed,'mesh_bounds_metres':{'min':list(lo),'max':list(hi)},
        'anatomy':'Four digits per hand: thumb and three fingers. ARP four-digit names are thumb/middle/ring/pinky.'}
(FOLDER/'RigValidation.json').write_text(json.dumps(report,indent=2)+'\n')
print('RIG_VALIDATED',json.dumps(report))
