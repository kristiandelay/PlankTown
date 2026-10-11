"""Render source geometry and report dimensions before rigging/fitting."""
import bpy
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Artifacts/SourceReview'
OUT.mkdir(parents=True, exist_ok=True)
report = {}
for source in sorted((ROOT / 'Resources').rglob('Source/*.fbx')):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(source))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    points = [o.matrix_world @ Vector(p) for o in meshes for p in o.bound_box]
    lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center = (lo + hi) / 2
    size = max(hi - lo)
    report[source.stem] = {'min': list(lo), 'max': list(hi), 'meshes': [
        {'name': o.name, 'vertices': len(o.data.vertices), 'polygons': len(o.data.polygons)} for o in meshes]}
    for o in meshes:
        mat = bpy.data.materials.new(source.stem)
        mat.use_nodes = True
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(str(source.with_name(source.stem + '_BaseColor.png')))
        mat.node_tree.links.new(tex.outputs['Color'], mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        o.data.materials.clear()
        o.data.materials.append(mat)
    bpy.ops.object.camera_add(location=center + Vector((0, -size * 2.5, size * .05)))
    camera = bpy.context.object
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = size * 1.15
    scene = bpy.context.scene
    scene.camera = camera
    scene.world.color = (.3, .3, .3)
    for position in [(1, -2, 3), (-2, -1, 1)]:
        bpy.ops.object.light_add(type='AREA', location=center + Vector(position) * size)
        lamp = bpy.context.object
        lamp.rotation_euler = (center - lamp.location).to_track_quat('-Z', 'Y').to_euler()
        lamp.data.energy = 350 * size * size
        lamp.data.shape = 'DISK'
        lamp.data.size = size * 2
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 12
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(OUT / (source.stem + '.png'))
    bpy.ops.render.render(write_still=True)
(OUT / 'dimensions.json').write_text(json.dumps(report, indent=2))
