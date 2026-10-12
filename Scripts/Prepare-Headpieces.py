"""Reduce Meshy headpieces and export fitted, UV-preserving game meshes."""
import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
# Widths and vertical offsets are in metres, relative to the scout's scalp socket.
# Offsets account for brim/tassel depth; runtime size scales around this pivot.
FITS = {'StrawHat': (1.22, -.08), 'FisherHat': (1.03, -.22),
        'MushroomCap': (.94, -.10), 'FestiveHeaddress': (1.20, -.63),
        'IslandSpiritHelmet': (1.08, -.78)}
selected = set(sys.argv[sys.argv.index('--')+1:]) if '--' in sys.argv else set(FITS)
assert selected <= FITS.keys(), selected - FITS.keys()
report = []
for name, (width, offset) in FITS.items():
    if name not in selected: continue
    folder = ROOT / 'Resources/Headpieces' / name
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(folder / 'Source' / (name + '.fbx')))
    mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
    mesh.name = name
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    source_faces = len(mesh.data.polygons)
    reduction = mesh.modifiers.new('GameMeshReduction', 'DECIMATE')
    reduction.ratio = min(1.0, (24000 if name=='IslandSpiritHelmet' else 16000) / source_faces)
    reduction.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=reduction.name)
    scale = width / mesh.dimensions.x
    for vertex in mesh.data.vertices:
        vertex.co *= scale
        vertex.co.z += offset
        # Center the helmet cavity on the skull; its faceguard extends forward.
        if name=='IslandSpiritHelmet': vertex.co.y -= .10
    material = bpy.data.materials.new('M_' + name)
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = nodes.get('Principled BSDF')
    for channel, socket in [('BaseColor','Base Color'),('Roughness','Roughness'),('Metallic','Metallic'),('Normal','Normal')]:
        node = nodes.new('ShaderNodeTexImage')
        node.image = bpy.data.images.load(str(folder / 'Source' / (name+'_'+channel+'.png')), check_existing=True)
        if channel != 'BaseColor': node.image.colorspace_settings.name = 'Non-Color'
        if channel == 'Normal':
            normal = nodes.new('ShaderNodeNormalMap')
            links.new(node.outputs['Color'], normal.inputs['Color'])
            links.new(normal.outputs['Normal'], shader.inputs[socket])
        else: links.new(node.outputs['Color'], shader.inputs[socket])
    mesh.data.materials.clear()
    mesh.data.materials.append(material)
    for polygon in mesh.data.polygons: polygon.use_smooth = True
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.0
    export = folder / 'Export' / (name + '.fbx')
    export.parent.mkdir(exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / (name + '.blend')))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()
    bpy.ops.export_scene.fbx(filepath=str(export), use_selection=True, object_types={'MESH'},
        axis_forward='-Y', axis_up='Z', apply_unit_scale=True, bake_anim=False, add_leaf_bones=False,
        path_mode='STRIP')
    report.append({'name': name, 'source_triangles': source_faces, 'game_triangles': len(mesh.data.polygons),
                   'width_metres': width, 'scalp_offset_metres': offset})
    if name=='IslandSpiritHelmet': report[-1]['fore_aft_offset_metres'] = -.10
report_path = ROOT / 'Resources/Headpieces/PreparedHeadpieces.json'
previous = json.loads(report_path.read_text()) if report_path.exists() else []
merged = {entry['name']: entry for entry in previous}
merged.update({entry['name']: entry for entry in report})
report_path.write_text(json.dumps(list(merged.values()), indent=2)+'\n', newline='\n')
