"""Bind an ARP Smart fit, preserve the control rig, and export UE5 bones."""
import bpy
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = sys.argv[sys.argv.index('--') + 1]
ASSET = ROOT / 'Resources/Player' / NAME
OUT = ROOT / 'Artifacts/CharacterPrep' / NAME
bpy.context.preferences.use_preferences_save = False

try:
    bpy.ops.wm.open_mainfile(filepath=str(OUT / (NAME + '-ARP-Fit.blend')))
    bpy.context.preferences.use_preferences_save = False
    mesh = bpy.data.objects[NAME]
    rig = bpy.data.objects['rig']
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    scene = bpy.context.scene
    scene.arp_bind_engine = 'HEAT_MAP'
    scene.arp_bind_split = True
    scene.arp_bind_preserve = False
    print('ARP_BIND_START', NAME, flush=True)
    bpy.ops.arp.bind_to_rig('EXEC_DEFAULT')
    print('ARP_BIND_FINISHED', flush=True)
    mesh = bpy.data.objects[NAME]
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=0.001, keep_single=True)
    bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    deform = {b.name for b in rig.data.bones if b.use_deform}
    groups = {g.index: g.name for g in mesh.vertex_groups}
    unweighted = []
    counts = {}
    for v in mesh.data.vertices:
        weights = [(groups[g.group], g.weight) for g in v.groups if groups[g.group] in deform and g.weight > 0.00001]
        if not weights:
            unweighted.append(v.index)
        for name, weight in weights:
            counts[name] = counts.get(name, 0) + 1
    assert not unweighted, ('Unweighted vertices', len(unweighted), unweighted[:20])
    assert any(m.type == 'ARMATURE' and m.object == rig for m in mesh.modifiers)
    material = bpy.data.materials.new('M_' + NAME)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader = nodes.get('Principled BSDF')
    for channel, socket in [('BaseColor', 'Base Color'), ('Metallic', 'Metallic'), ('Roughness', 'Roughness'), ('Normal', 'Normal')]:
        node = nodes.new('ShaderNodeTexImage')
        node.label = channel
        node.image = bpy.data.images.load(str(ASSET / 'Source' / (NAME + '_' + channel + '.png')), check_existing=True)
        if channel != 'BaseColor':
            node.image.colorspace_settings.name = 'Non-Color'
        if channel == 'Normal':
            normal = nodes.new('ShaderNodeNormalMap')
            links.new(node.outputs['Color'], normal.inputs['Color'])
            links.new(normal.outputs['Normal'], shader.inputs[socket])
        else:
            links.new(node.outputs['Color'], shader.inputs[socket])
        if channel == 'BaseColor':
            nodes.active = node
    mesh.data.materials.clear()
    mesh.data.materials.append(material)
    for polygon in mesh.data.polygons:
        polygon.use_smooth = True
    scene.arp_export_rig_type = 'HUMANOID'
    scene.arp_engine_type = 'UNREAL'
    scene.arp_ue4 = False
    scene.arp_rename_for_ue = True
    scene.arp_export_twist = True
    scene.arp_mannequin_axes = True
    scene.arp_ue_ik = True
    scene.arp_units_x100 = True
    scene.arp_bake_anim = False
    scene.arp_export_rig_name = 'root'
    scene.arp_ge_sel_only = True
    bpy.context.preferences.addons['bl_ext.superhivemarket_com.auto_rig_pro'].preferences.show_export_popup = False
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    export = ASSET / 'Export' / (NAME + '.fbx')
    export.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ASSET / (NAME + '.blend')))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()
    bpy.ops.arp.arp_export_fbx_panel('EXEC_DEFAULT', filepath=str(export))
    assert export.is_file() and export.stat().st_size > 100000
    report = {'passed': True, 'name': NAME, 'vertices': len(mesh.data.vertices),
              'triangles': len(mesh.data.polygons), 'unweighted': len(unweighted),
              'influence_counts': counts, 'export_bytes': export.stat().st_size}
    (OUT / 'arp-skin-result.json').write_text(json.dumps(report, indent=2))
    print('ARP_SKIN_EXPORT_COMPLETE', NAME, flush=True)
except Exception:
    error = traceback.format_exc()
    (OUT / 'arp-skin-result.json').write_text(json.dumps({'passed': False, 'error': error}, indent=2))
    print(error, flush=True)
    raise
