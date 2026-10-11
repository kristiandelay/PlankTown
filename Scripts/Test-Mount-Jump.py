"""Space jumps, air/landing poses and obstacle clearance in standalone and client PIE.
Run outside Play. Set MOUNT_JUMP_NETWORK=True before executing for two players.
"""
import unreal as u
import json
import time
import traceback
from pathlib import Path

mj_network=globals().pop('MOUNT_JUMP_NETWORK',False)
mj_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parents[1]
mj=dict(phase='setup',busy=False,next=0,results=[],deadline=time.monotonic()+120,samples=[])
mj_settings=u.get_default_object(u.load_class(None,'/Script/UnrealEd.LevelEditorPlaySettings'))
assert not u.EditorLevelLibrary.get_pie_worlds(False)
mj_performance=u.get_default_object(u.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
mj['restore_throttle']='True' if 'bThrottleCPUWhenNotForeground = True' in u.CRBlueprintTools.describe_object(mj_performance) else 'False'
assert u.CRBlueprintTools.set_property_text(mj_performance,'bThrottleCPUWhenNotForeground','False')
for key,value in [('PlayNetMode','PIE_ListenServer' if mj_network else 'PIE_Standalone'),('PlayNumberOfClients','2' if mj_network else '1'),('RunUnderOneProcess','True')]:
    assert u.CRBlueprintTools.set_property_text(mj_settings,key,value)

def mj_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if len(worlds)!=(2 if mj_network else 1):return
    pairs=[(w,p) for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if 'TrainingPartner' not in p.get_class().get_name()]
    local=next(((w,p) for w,p in pairs if p.is_locally_controlled() and (not p.has_authority() if mj_network else p.has_authority())),None)
    remote=next(((w,p) for w,p in pairs if p.has_authority() and not p.is_locally_controlled()),None) if mj_network else local
    if not local or not remote:return
    cw,client=local;sw,server=remote
    cm=u.GameplayStatics.get_all_actors_of_class(cw,u.PlankTownMount)
    sm=u.GameplayStatics.get_all_actors_of_class(sw,u.PlankTownMount)
    if cm and sm:return cw,sw,client,server,cm[0],sm[0]

def mj_input(pawn,action,value):
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
        if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    folder='/Game/Baseline/Input/' if action=='Interact' else '/Game/Input/'
    sub.inject_input_vector_for_action(u.load_asset(folder+'IA_'+action),value,[],[])

def mj_phase(phase,now,delay):mj.update(phase=phase,next=now+delay)

def mj_finish(error=None):
    u.unregister_slate_post_tick_callback(mj['handle']);mj['finished']=True
    context=mj_context()
    if context:
        for action in ['Jump','Move','Sprint','Interact']:mj_input(context[2],action,u.Vector())
    out=mj_root/'Artifacts/MountTests'/('jump-network.json' if mj_network else 'jump-standalone.json')
    out.write_text(json.dumps(dict(passed=error is None,error=error,network=mj_network,results=mj['results']),indent=2)+'\n')
    for key,value in [('PlayNetMode','PIE_Standalone'),('PlayNumberOfClients','1')]:u.CRBlueprintTools.set_property_text(mj_settings,key,value)
    u.CRBlueprintTools.set_property_text(mj_performance,'bThrottleCPUWhenNotForeground',mj['restore_throttle'])
    print('MOUNT_JUMP_TEST_COMPLETE',error)

def mj_tick(dt):
    if mj['busy']:return
    mj['busy']=True
    try:
        assert time.monotonic()<mj['deadline'],'Jump test timed out'
        context=mj_context()
        if not context:return
        cw,sw,client,server,cm,sm=context
        now=u.GameplayStatics.get_time_seconds(cw);phase=mj['phase']
        if mj.pop('release_interact',False):mj_input(client,'Interact',u.Vector())
        running=phase in ['accelerate','running_jump']
        mj_input(client,'Move',u.Vector(0,1,0) if running else u.Vector())
        mj_input(client,'Sprint',u.Vector(1,0,0) if running else u.Vector())
        mj_input(client,'Jump',u.Vector(1,0,0) if phase in ['jump','air_check','hold','running_jump','foot_jump'] else u.Vector())
        if phase in ['jump','air_check','hold','running_jump']:
            sa=sm.mesh.get_anim_instance();ca=cm.mesh.get_anim_instance()
            mj['samples'].append(dict(z=sm.get_actor_location().z,vz=sm.get_velocity().z,
                client_z=cm.get_actor_location().z,air=sa.air_weight,client_air=ca.air_weight,
                rise=sa.rising_weight,land=sa.landing_weight,
                foot=sm.mesh.get_socket_transform('front_l_foot',u.RelativeTransformSpace.RTS_COMPONENT).translation.z))
            assert client.riding.is_mounted() and server.riding.is_mounted(),'Rider detached in flight'
            assert client.get_attach_parent_actor()==cm and server.get_attach_parent_actor()==sm
            if phase=='running_jump' and not mj.get('obstacle_spawned') and sm.get_velocity().z>100:
                # Place the fixture at the measured apex after the client's
                # takeoff reaches the server, independent of PIE frame hitches.
                distance=sm.get_velocity().x*sm.get_velocity().z/1323
                wall=u.CRBlueprintTools.spawn_pie_test_actor(sw,u.StaticMeshActor,u.Transform(location=u.Vector(
                    sm.get_actor_location().x+distance,sm.get_actor_location().y,30)))
                wall.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
                wall.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
                wall.set_actor_scale3d(u.Vector(.4,2.5,.6));wall.static_mesh_component.set_collision_profile_name('BlockAll')
                wall.set_actor_label('MountJumpObstacle');mj['obstacle_spawned']=True
        if phase=='foot_jump':mj['foot_z'].append(server.get_actor_location().z)
        if now<mj['next']:return
        if phase=='setup':
            if now<5:return
            sm.set_actor_location(u.Vector(1300,-3600,92),False,True)
            sm.set_actor_rotation(u.Rotator(yaw=0),False);sm.force_net_update()
            server.set_actor_location(u.Vector(1120,-3600,94),False,True)
            client.get_controller().set_control_rotation(u.Rotator(yaw=0))
            server.riding.server_jump()
            mj_phase('mount',now,1.5)
        elif phase=='mount':
            assert abs(sm.get_velocity().z)<1,'Unmounted request moved mount'
            mj_input(client,'Interact',u.Vector(1,0,0));mj['release_interact']=True
            mj_phase('ready',now,1.5)
        elif phase=='ready':
            assert client.riding.is_mounted() and server.riding.is_mounted()
            assert sm.character_movement.is_moving_on_ground()
            mj['ground_z']=sm.get_actor_location().z
            mj['samples']=[]
            mj['jump_deadline']=now+2
            mj_phase('jump',now,0)
        elif phase=='jump':
            if not sm.character_movement.is_falling():
                assert now<mj['jump_deadline'],'Space did not jump the mount'
                return
            assert sm.get_velocity().z>0,'First jump observation missed takeoff'
            mj['vz_before_repeat']=sm.get_velocity().z
            # Probe the authoritative jump guard; use actual E input for the
            # client's reliable dismount RPC (Python calls execute locally).
            server.riding.server_jump()
            mj_input(client,'Interact',u.Vector(1,0,0));mj['release_interact']=True
            mj_phase('air_check',now,.20)
        elif phase=='air_check':
            assert server.riding.is_mounted(),'Dismounted in midair'
            assert sm.get_velocity().z<mj['vz_before_repeat']-40,'Airborne jump reset vertical velocity'
            mj_phase('hold',now,1.3)
        elif phase=='hold':
            samples=mj['samples'];height=max(p['z'] for p in samples)-mj['ground_z']
            assert 65<height<130,('Unexpected jump height',height)
            assert max(p['client_z'] for p in samples)-mj['ground_z']>50,'Client missed jump replication'
            assert max(p['air'] for p in samples)>.9 and max(p['client_air'] for p in samples)>.9
            assert max(p['rise'] for p in samples)>.5 and max(p['land'] for p in samples)>.4
            assert max(p['foot'] for p in samples)-min(p['foot'] for p in samples)>8,'Jump legs stayed rigid'
            assert sm.character_movement.is_moving_on_ground() and abs(sm.get_actor_location().z-mj['ground_z'])<5
            assert sm.mesh.get_anim_instance().air_weight<.01 and sm.mesh.get_anim_instance().landing_weight<.01
            assert max(p['z'] for p in samples[-5:])-mj['ground_z']<5,'Holding Space repeated the jump'
            mj['results'].append(dict(case='Space_jump_rider_attachment_air_and_landing_poses',height_cm=height))
            mj['results'].append('airborne_repeat_and_dismount_rejected_holding_does_not_bunny_hop')
            mj_input(client,'Jump',u.Vector())
            mj_phase('accelerate',now,1.2)
        elif phase=='accelerate':
            assert sm.get_velocity().length()>480
            mj['start_x']=sm.get_actor_location().x;mj['samples']=[];mj['obstacle_spawned']=False
            mj_phase('running_jump',now,1.5)
        elif phase=='running_jump':
            distance=sm.get_actor_location().x-mj['start_x']
            assert distance>500,('Jump did not clear 60cm obstacle',distance)
            assert mj['obstacle_spawned'],'Second Space press did not take off'
            assert max(p['z'] for p in mj['samples'])-mj['ground_z']>65
            assert sm.character_movement.is_moving_on_ground()
            mj['results'].append(dict(case='running_jump_clears_60cm_obstacle_and_lands',distance_cm=distance))
            for actor in u.GameplayStatics.get_all_actors_of_class(sw,u.StaticMeshActor):
                if actor.get_actor_label()=='MountJumpObstacle':actor.destroy_actor()
            mj_input(client,'Jump',u.Vector());mj_input(client,'Move',u.Vector());mj_input(client,'Sprint',u.Vector())
            mj_input(client,'Interact',u.Vector(1,0,0));mj['release_interact']=True
            mj_phase('dismounted',now,1.5)
        elif phase=='dismounted':
            assert not client.riding.is_mounted() and not server.riding.is_mounted()
            server.set_actor_location(u.Vector(900,-3600,94),False,True)
            mj_phase('foot_ready',now,1)
        elif phase=='foot_ready':
            mj['foot_ground']=server.get_actor_location().z;mj['foot_z']=[]
            mj_phase('foot_jump',now,1.5)
        elif phase=='foot_jump':
            assert max(mj['foot_z'])-mj['foot_ground']>30,'Space no longer jumps the player on foot'
            mj['results'].append('dismount_restores_normal_player_Space_jump')
            mj_finish()
    except Exception:mj_finish(traceback.format_exc())
    finally:mj['busy']=False

mj['handle']=u.register_slate_post_tick_callback(mj_tick)
u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_begin_play()
print('MOUNT_JUMP_TEST_STARTED',mj_network)
