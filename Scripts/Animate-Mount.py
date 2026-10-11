"""Author quick, articulated quadruped gaits on Moku's existing Blender rig."""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion

ROOT=Path(__file__).resolve().parents[1]
NAME='MokuTheIslandRider';ASSET=ROOT/'Resources/Mount'/NAME
bpy.ops.wm.open_mainfile(filepath=str(ASSET/(NAME+'.blend')))
rig=bpy.data.objects['root'];mesh=bpy.data.objects[NAME];data=rig.data
scene=bpy.context.scene;scene.render.fps=30
rig.animation_data_create();rig.animation_data.action=None
for action in list(bpy.data.actions):bpy.data.actions.remove(action)
legs={}
for prefix in ['front_l','front_r','hind_l','hind_r']:
    legs[prefix]=tuple(data.bones[prefix+'_'+part].head_local.copy() for part in ['upper','lower','foot'])+(data.bones[prefix+'_foot'].tail_local.copy(),)

def orient(name,head,tail):
    ref=data.bones[name]
    rotation=(ref.tail_local-ref.head_local).rotation_difference(tail-head)@ref.matrix_local.to_quaternion()
    rig.pose.bones[name].matrix=Matrix.LocRotScale(head,rotation,Vector((1,1,1)))

def limb(prefix,ankle,pitch):
    hip,knee,rest_ankle,toe=legs[prefix]
    parent=rig.pose.bones[data.bones[prefix+'_upper'].parent.name]
    hip=(parent.matrix@parent.bone.matrix_local.inverted())@hip
    l1=(knee-legs[prefix][0]).length;l2=(rest_ankle-knee).length
    axis=ankle-hip;distance=min(axis.length,l1+l2-.001);direction=axis.normalized()
    bend=Vector((.55 if prefix.endswith('l') else -.55,-1 if prefix.startswith('front') else 1,0))
    bend=(bend-direction*bend.dot(direction)).normalized()
    along=(l1*l1-l2*l2+distance*distance)/(2*distance)
    knee=hip+direction*along+bend*math.sqrt(max(0,l1*l1-along*along))
    ankle=hip+direction*distance
    orient(prefix+'_upper',hip,knee);bpy.context.view_layer.update()
    orient(prefix+'_lower',knee,ankle);bpy.context.view_layer.update()
    orient(prefix+'_foot',ankle,ankle+Quaternion((1,0,0),pitch)@(toe-rest_ankle))

clips=[];settings=[]
for clip,frames,stride,lift,duty in [('Idle',60,0,0,1),('Walk',14,.25,.12,.46),('Run',10,.23,.18,.265)]:
    for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
    action=bpy.data.actions.new(NAME+'_'+clip);rig.animation_data.action=action;action.use_fake_user=True
    # Four distinct contacts in the walk; a gathered, three-beat canter at run.
    offsets=({'hind_l':0,'front_l':.25,'hind_r':.5,'front_r':.75} if clip=='Walk'
        else {'hind_l':0,'hind_r':.10,'front_l':.45,'front_r':.58})
    for frame in range(frames+1):
        scene.frame_set(frame);cycle=frame/frames;phase=cycle*2*math.pi
        for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
        body=rig.pose.bones['body'];body.rotation_mode='QUATERNION'
        if clip=='Idle':
            body.matrix=Matrix.Translation((0,0,.004*math.sin(phase*2)))@data.bones['body'].matrix_local
        else:
            # Crouching leaves room for knee flexion; body motion is in world Z,
            # independent of the fitted body's tilted local axes.
            bob=(.012 if clip=='Walk' else .038)*math.sin(phase*(2 if clip=='Walk' else 1))
            pitch=(.015 if clip=='Walk' else .06)*math.sin(phase)
            roll=(.025 if clip=='Walk' else .018)*math.cos(phase)
            rotation=Quaternion((1,0,0),pitch)@Quaternion((0,1,0),roll)
            transform=Matrix.Translation((0,0,-.08+bob))@data.bones['body'].matrix_local
            body.matrix=Matrix.LocRotScale(transform.translation,rotation@transform.to_quaternion(),Vector((1,1,1)))
        for name,angle in [('neck',(.018 if clip=='Idle' else .055)*math.sin(phase+.6)),
                           ('head',(.025 if clip=='Idle' else .045)*math.sin(phase+1.4))]:
            rig.pose.bones[name].rotation_mode='QUATERNION'
            rig.pose.bones[name].rotation_quaternion=Quaternion((1,0,0),angle)
        for i,name in enumerate(['tail_01','tail_02']):
            rig.pose.bones[name].rotation_mode='QUATERNION'
            rig.pose.bones[name].rotation_quaternion=Quaternion((0,1,0),(.09 if clip=='Idle' else .16)*math.sin(phase-i*.8))
        bpy.context.view_layer.update()
        if stride:
            for prefix,points in legs.items():
                p=(cycle+offsets[prefix])%1
                if p<duty:
                    # Constant backward foot speed during contact matches the
                    # character's travel, with a fast arcing recovery stroke.
                    t=p/duty;y=-stride+2*stride*t;z=0;pitch=-.08*math.sin(math.pi*t)
                else:
                    t=(p-duty)/(1-duty);smooth=t*t*(3-2*t)
                    y=stride-2*stride*smooth;z=lift*math.sin(math.pi*t)**1.2
                    pitch=.55*math.sin(2*math.pi*t)
                target=Vector((points[2].x,points[0].y+y,points[2].z+z))
                limb(prefix,target,pitch)
        for pb in rig.pose.bones:
            pb.rotation_mode='QUATERNION'
            for prop in ['location','rotation_quaternion','scale']:pb.keyframe_insert(prop,frame=frame,group=pb.name)
    clips.append((clip,action,frames))
    settings.append(dict(clip=clip,frames=frames,fps=30,cycles_per_second=30/frames,
        stride_metres=stride*2,lift_metres=lift,stance_fraction=duty,
        nominal_speed_cm_s=0 if not stride else 200*stride/(frames/30*duty)))

# Air poses are blended by vertical velocity in Unreal. Landing compression is
# driven by the actual ground contact, so slopes and ledges do not desync it.
for clip,body_drop,body_pitch,foot_height in [('JumpRise',-.035,-.08,.23),('JumpFall',-.025,.065,.075),('Land',-.11,.015,.09)]:
    action=bpy.data.actions.new(NAME+'_'+clip);rig.animation_data.action=action;action.use_fake_user=True
    for frame in [0,1]:
        scene.frame_set(frame)
        for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
        body=rig.pose.bones['body']
        transform=Matrix.Translation((0,0,body_drop))@data.bones['body'].matrix_local
        body.matrix=Matrix.LocRotScale(transform.translation,Quaternion((1,0,0),body_pitch)@transform.to_quaternion(),Vector((1,1,1)))
        rig.pose.bones['neck'].rotation_quaternion=Quaternion((1,0,0),-body_pitch*.6)
        rig.pose.bones['tail_01'].rotation_quaternion=Quaternion((1,0,0),-.15 if clip=='JumpRise' else .05)
        bpy.context.view_layer.update()
        for prefix,points in legs.items():
            y=points[0].y+(-.045 if prefix.startswith('front') else .045)
            limb(prefix,Vector((points[2].x,y,foot_height)),.22 if clip=='JumpRise' else 0)
        for pb in rig.pose.bones:
            pb.rotation_mode='QUATERNION'
            for prop in ['location','rotation_quaternion','scale']:pb.keyframe_insert(prop,frame=frame,group=pb.name)
    clips.append((clip,action,1))

bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True)
bpy.context.view_layer.objects.active=rig;rig.animation_data.action=None
for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
scene.frame_set(0);bpy.context.view_layer.update()
export=dict(use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,
    axis_forward='-Y',axis_up='Z',use_armature_deform_only=True,bake_anim_use_all_actions=False,
    bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0.0)
bpy.ops.export_scene.fbx(filepath=str(ASSET/'Export'/(NAME+'.fbx')),bake_anim=False,**export)
for clip,action,frames in clips:
    rig.animation_data.action=action;scene.frame_start=0;scene.frame_end=frames
    bpy.ops.export_scene.fbx(filepath=str(ASSET/'Export'/(NAME+'_'+clip+'.fbx')),bake_anim=True,**export)
rig.animation_data.action=clips[0][1];scene.frame_start=0;scene.frame_end=60;scene.frame_set(0)
bpy.ops.file.make_paths_relative();bpy.ops.wm.save_mainfile()
report=json.loads((ASSET/'RigValidation.json').read_text())
report['animations']=[c[0] for c in clips];report['gait_settings']=settings
report.pop('gait_validation',None)
(ASSET/'RigValidation.json').write_text(json.dumps(report,indent=2)+'\n')
print('MOUNT_GAITS_EXPORTED',json.dumps(settings),flush=True)
