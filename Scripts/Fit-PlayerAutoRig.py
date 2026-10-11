"""Run in a task-owned Blender UI process for ARP's viewport-based AI fitting."""
import bpy
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = sys.argv[sys.argv.index('--')+1]
ASSET = ROOT / 'Resources/Player' / NAME
OUT = ROOT / 'Artifacts/CharacterPrep' / NAME
OUT.mkdir(parents=True, exist_ok=True)


def run():
    try:
        bpy.context.preferences.use_preferences_save = False
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.import_scene.fbx(filepath=str(ASSET / 'Source' / (NAME + '.fbx')))
        mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
        mesh.name = NAME
        bpy.context.view_layer.objects.active = mesh
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        mesh.data.calc_loop_triangles()
        source_triangles = len(mesh.data.loop_triangles)
        modifier = mesh.modifiers.new('GameMeshReduction', 'DECIMATE')
        modifier.ratio = min(1.0, 90000 / source_triangles)
        modifier.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        print('GAME_MESH_READY', NAME, source_triangles, len(mesh.data.polygons), flush=True)
        scene = bpy.context.scene
        scene.unit_settings.system = 'METRIC'
        scene.unit_settings.scale_length = 1.0
        scene.arp_smart_type = 'BODY'
        scene.arp_smart_preset_settings = 'UE5'
        scene.arp_fingers_enable = True
        scene.arp_fingers_to_detect = 4
        scene.arp_smart_fingers_engine = 'AI'
        window = bpy.context.window_manager.windows[0]
        area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
        region = next(r for r in area.regions if r.type == 'WINDOW')
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.id.get_selected_objects('EXEC_DEFAULT')
            print('ARP_SMART_BODY_START', flush=True)
            bpy.ops.arp.guess_markers('EXEC_DEFAULT')
            markers = {o.name: list(o.location) for o in bpy.data.objects if o.name.endswith('_loc')}
            (OUT / 'body-markers.json').write_text(json.dumps(markers, indent=2))
            assert all(n + '_loc' in bpy.data.objects for n in ['chin','foot','hand','neck','root','shoulder']), markers
            print('ARP_SMART_FINGERS_START', flush=True)
            bpy.ops.arp.guess_fingers('EXEC_DEFAULT')
            markers = {o.name: list(o.location) for o in bpy.data.objects if '_loc' in o.name}
            (OUT / 'finger-markers.json').write_text(json.dumps(markers, indent=2))
            assert 'thumb1_loc' in bpy.data.objects, 'ARP could not detect finger landmarks.'
            print('ARP_AUTO_DETECT_START', flush=True)
            bpy.ops.id.go_detect('EXEC_DEFAULT')
            rig = bpy.context.active_object
            assert rig and rig.type == 'ARMATURE'
            print('ARP_MATCH_START', flush=True)
            bpy.ops.arp.match_to_rig('EXEC_DEFAULT')
            if bpy.context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
        references = {b.name: {'head': list(b.head_local), 'tail': list(b.tail_local)}
                      for b in rig.data.bones if '_ref' in b.name}
        (OUT / 'arp-reference-bones.json').write_text(json.dumps(references, indent=2))
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / (NAME + '-ARP-Fit.blend')))
        (OUT / 'arp-fit-result.json').write_text(json.dumps({'passed': True, 'rig': rig.name,
               'source_triangles': source_triangles, 'game_triangles': len(mesh.data.polygons),
               'bones': len(rig.data.bones)}, indent=2))
        print('ARP_FIT_COMPLETE', NAME, flush=True)
    except Exception:
        error = traceback.format_exc()
        (OUT / 'arp-fit-result.json').write_text(json.dumps({'passed': False, 'error': error}, indent=2))
        print(error, flush=True)
    finally:
        bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(run, first_interval=1.0)
