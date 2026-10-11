"""Review Moku's fitted rest pose and gait, and verify exported rig motion."""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'Resources/Mount/MokuTheIslandRider'
OUT=ROOT/'Artifacts/MountPrep'
bpy.ops.wm.open_mainfile(filepath=str(ASSET/'MokuTheIslandRider.blend'))
rig=bpy.data.objects['root'];mesh=bpy.data.objects['MokuTheIslandRider']
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=16
scene.render.resolution_x=1200;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world.color=(.3,.3,.3)
center=Vector((0,0,.85));size=2.4
for direction in [(1,-2,3),(-2,1,2)]:
    bpy.ops.object.light_add(type='AREA',location=center+Vector(direction)*size)
    lamp=bpy.context.object;lamp.rotation_euler=(center-lamp.location).to_track_quat('-Z','Y').to_euler()
    lamp.data.energy=350*size*size;lamp.data.size=size*2
bpy.ops.object.camera_add(location=center+Vector((3,-2,.9))*size)
camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=3.0
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
results=[]
for clip,frame in [('Idle',0),('Walk',3),('Run',2)]:
    action=bpy.data.actions['MokuTheIslandRider_'+clip];rig.animation_data.action=action
    scene.frame_set(frame);bpy.context.view_layer.update()
    scene.render.filepath=str(OUT/(clip+'.png'));bpy.ops.render.render(write_still=True)
    positions=[];knees=[]
    for f in range(int(action.frame_range[0]),int(action.frame_range[1])+1):
        scene.frame_set(f);bpy.context.view_layer.update()
        positions.append({name:list(rig.pose.bones[name+'_foot'].head) for name in ['front_l','front_r','hind_l','hind_r']})
        knees.append({name:math.degrees((rig.pose.bones[name+'_upper'].head-rig.pose.bones[name+'_lower'].head).angle(
            rig.pose.bones[name+'_foot'].head-rig.pose.bones[name+'_lower'].head)) for name in positions[-1]})
    ranges={name:math.sqrt(sum((max(p[name][i] for p in positions)-min(p[name][i] for p in positions))**2 for i in range(3))) for name in positions[0]}
    bends={name:max(p[name] for p in knees)-min(p[name] for p in knees) for name in knees[0]}
    lifts={name:max(p[name][2] for p in positions)-min(p[name][2] for p in positions) for name in positions[0]}
    loop_error=max((Vector(positions[0][name])-Vector(positions[-1][name])).length for name in positions[0])
    assert loop_error<.001,(clip,loop_error)
    if clip!='Idle':
        assert min(ranges.values())>.3,(clip,ranges)
        assert min(bends.values())>25,(clip,bends)
        assert min(lifts.values())>.08,(clip,lifts)
    results.append({'clip':clip,'foot_motion_metres':ranges,'knee_flexion_degrees':bends,'foot_lift_metres':lifts})
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=str(ASSET/'Export/MokuTheIslandRider_Walk.fbx'))
export_rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
export_mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
assert export_rig.animation_data and export_rig.animation_data.action
assert len(export_rig.data.bones)==20
assert all(math.isfinite(c) for v in export_mesh.data.vertices for c in v.co)
report=json.loads((ASSET/'RigValidation.json').read_text())
report['gait_validation']=results
report['fbx_roundtrip_bones']=len(export_rig.data.bones)
report['fbx_roundtrip_animation']=export_rig.animation_data.action.name
(ASSET/'RigValidation.json').write_text(json.dumps(report,indent=2)+'\n')
print('MOUNT_RIG_VALIDATION_COMPLETE',flush=True)
