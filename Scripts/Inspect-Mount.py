"""Render the normalized mount delivery before fitting its quadruped rig."""
import bpy
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
NAME = 'MokuTheIslandRider'
source = ROOT/'Resources/Mount'/NAME/'Source'
out = ROOT/'Artifacts/MountPrep'
out.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=str(source/(NAME+'.fbx')))
meshes = [o for o in bpy.context.scene.objects if o.type=='MESH']
points = [o.matrix_world@Vector(p) for o in meshes for p in o.bound_box]
lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
center = (lo+hi)/2
size = max(hi-lo)
(out/'source.json').write_text(json.dumps({'min':list(lo),'max':list(hi),
    'meshes':[{'name':o.name,'vertices':len(o.data.vertices),'polygons':len(o.data.polygons)} for o in meshes]},indent=2))
for mesh in meshes:
    mat = bpy.data.materials.new(NAME)
    mat.use_nodes = True
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = bpy.data.images.load(str(source/(NAME+'_BaseColor.png')))
    mat.node_tree.links.new(node.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    mesh.data.materials.clear();mesh.data.materials.append(mat)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 12
scene.world.color = (.35,.35,.35)
scene.render.resolution_x = scene.render.resolution_y = 1100
scene.render.resolution_percentage = 100
for direction in [(1,-2,3),(-2,1,2)]:
    bpy.ops.object.light_add(type='AREA',location=center+Vector(direction)*size)
    lamp=bpy.context.object
    lamp.rotation_euler=(center-lamp.location).to_track_quat('-Z','Y').to_euler()
    lamp.data.energy=350*size*size;lamp.data.size=size*2
bpy.ops.object.camera_add()
camera=bpy.context.object;scene.camera=camera
camera.data.type='ORTHO';camera.data.ortho_scale=size*1.15
for label,direction in [('front',(0,-3,.2)),('side',(3,0,.2)),('rear',(0,3,.2)),('angle',(2,-3,1.4))]:
    camera.location=center+Vector(direction)*size
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out/(label+'.png'))
    bpy.ops.render.render(write_still=True)
print('MOUNT_SOURCE_REVIEW_COMPLETE',flush=True)
