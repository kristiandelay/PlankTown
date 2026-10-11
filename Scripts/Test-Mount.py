"""Standalone PIE: mount controls, seated pose, gaits, collision and safe exits."""
import unreal as u
import json
import math
import time
import traceback
from pathlib import Path

mt_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parents[1]
mt_out=mt_root/'Artifacts/MountTests';mt_out.mkdir(exist_ok=True)
mt=dict(phase='setup',busy=False,deadline=time.monotonic()+180,results=[],next=0)
mt_paths={'Interact':'/Game/Baseline/Input/IA_Interact','Move':'/Game/Input/IA_Move','Sprint':'/Game/Input/IA_Sprint'}

def mt_input(pawn,name,value):
    subsystem=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
        if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    subsystem.inject_input_vector_for_action(u.load_asset(mt_paths[name]),value,[],[])

def mt_phase(name,now,delay):
    mt.update(phase=name,next=now+delay)

def mt_finish(error=None):
    u.unregister_slate_post_tick_callback(mt['handle'])
    for world in u.EditorLevelLibrary.get_pie_worlds(False):
        pawn=u.GameplayStatics.get_player_pawn(world,0)
        if pawn:
            for action in mt_paths:mt_input(pawn,action,u.Vector())
            pawn.get_controller().set_view_target_with_blend(pawn,0)
    mt['finished']=True
    (mt_out/'standalone.json').write_text(json.dumps(dict(passed=error is None,error=error,results=mt['results']),indent=2)+'\n')
    print('PLANKTOWN_MOUNT_TEST_COMPLETE',error)

def mt_tick(dt):
    if mt['busy']:return
    mt['busy']=True
    try:
        assert time.monotonic()<mt['deadline'],'Mount test timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        world=worlds[0];pawn=u.GameplayStatics.get_player_pawn(world,0)
        if not pawn:return
        mounts=u.GameplayStatics.get_all_actors_of_class(world,u.PlankTownMount)
        mount=mounts[0] if mounts else None
        now=u.GameplayStatics.get_time_seconds(world);phase=mt['phase']
        if mt.pop('release',False):mt_input(pawn,'Interact',u.Vector())
        moving=phase in ['walk','run','turn','wall','player_walk']
        mt_input(pawn,'Move',u.Vector(0,1,0) if moving else u.Vector())
        mt_input(pawn,'Sprint',u.Vector(1,0,0) if phase in ['run','turn','wall'] else u.Vector())
        if phase in ['walk','run']:
            mt['speeds'].append(mount.get_velocity().length())
            mt['feet'].append({b:list(mount.mesh.get_socket_transform(b,u.RelativeTransformSpace.RTS_COMPONENT).translation.to_tuple()) for b in ['front_l_foot','front_r_foot','hind_l_foot','hind_r_foot']})
        if now<mt['next']:return
        if phase=='setup':
            if now<4:return
            assert mount and mount.mesh.get_skinned_asset()
            assert isinstance(mount.mesh.get_anim_instance(),u.PlankTownMountAnimInstance)
            mount.set_actor_location(u.Vector(1300,-3600,92),False,True)
            mount.set_actor_rotation(u.Rotator(yaw=0),False)
            pawn.set_actor_location(u.Vector(600,-3600,94),False,True)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            assert mount.capsule_component.get_collision_response_to_channel(u.CollisionChannel.ECC_CAMERA)==u.CollisionResponseType.ECR_IGNORE
            assert mount.capsule_component.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN)==u.CollisionResponseType.ECR_BLOCK
            start=mount.get_actor_location()-u.Vector(250,0,0);end=start+u.Vector(700,0,0)
            channel=u.TraceTypeQuery.TRACE_TYPE_QUERY2  # Engine's Camera trace channel.
            assert not u.SystemLibrary.sphere_trace_single(world,start,end,14,channel,False,[pawn],u.DrawDebugTrace.NONE),'Mount blocks the camera sweep'
            wall=u.CRBlueprintTools.spawn_pie_test_actor(world,u.StaticMeshActor,u.Transform(location=mount.get_actor_location()+u.Vector(350,0,0)))
            wall.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
            wall.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
            wall.set_actor_scale3d(u.Vector(.5,3,3));wall.static_mesh_component.set_collision_profile_name('BlockAll')
            assert u.SystemLibrary.sphere_trace_single(world,start,end,14,channel,False,[pawn],u.DrawDebugTrace.NONE),'Camera missed wall behind mount'
            wall.destroy_actor()
            mt['results'].append('camera_sweep_ignores_mount_but_hits_wall_behind_it')
            pawn.riding.server_mount(mount)
            assert not pawn.riding.is_mounted(),'Remote mount request was accepted'
            pawn.set_actor_location(u.Vector(1120,-3600,94),False,True)
            hat=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.PlankTownHeadpiecePickup) if a.state.definition.mesh.get_name()=='StrawHat')
            hat.set_actor_location(u.Vector(1140,-3540,110),False,True)
            pawn.headpieces.server_pickup(hat)
            assert pawn.headpieces.equipped.definition
            mt_phase('mount',now,.8)
        elif phase=='mount':
            assert pawn.riding.find_mount()==mount
            mt_input(pawn,'Interact',u.Vector(1,0,0));mt['release']=True
            mt_phase('seated',now,1)
        elif phase=='seated':
            assert pawn.riding.mounted_mount==mount and mount.rider==pawn
            assert pawn.get_attach_parent_actor()==mount
            assert pawn.character_movement.movement_mode==u.MovementMode.MOVE_NONE
            assert pawn.baseline_equipment.get_weapon_animation_mesh().get_anim_instance().riding_weight>.99
            visual=pawn.baseline_equipment.get_presentation_mesh()
            assert 'Riding' in str(visual.component_tags[0])
            assert (visual.get_socket_location('pelvis')-mount.mesh.get_socket_location('RiderSocket')).length()<15
            assert pawn.get_actor_scale3d().distance(u.Vector(1,1,1))<.01
            assert pawn.headpieces.worn_mesh.get_attach_parent()==visual
            assert pawn.headpieces.equipped.definition
            mt['results'].append('distance_rejected_E_mount_seated_pose_hat_preserved')
            mt.update(start=list(mount.get_actor_location().to_tuple()),speeds=[],feet=[])
            mt_phase('walk',now,2)
        elif phase=='walk':
            distance=(mount.get_actor_location()-u.Vector(*mt['start'])).length()
            assert distance>250,('WASD did not drive mount',distance)
            assert max(mt['speeds'])>200 and max(mt['speeds'])<270
            motion={b:max(p[b][1] for p in mt['feet'])-min(p[b][1] for p in mt['feet']) for b in mt['feet'][0]}
            assert min(motion.values())>5,('Frozen leg animation',motion)
            mt['results'].append(dict(case='walk_four_animated_legs',distance_cm=distance,foot_travel_cm=motion))
            mt.update(start=list(mount.get_actor_location().to_tuple()),speeds=[],feet=[])
            mt_phase('run',now,2)
        elif phase=='run':
            distance=(mount.get_actor_location()-u.Vector(*mt['start'])).length()
            assert distance>650 and max(mt['speeds'])>480 and max(mt['speeds'])<550,(distance,max(mt['speeds']))
            mt['results'].append(dict(case='shift_run',distance_cm=distance,peak_speed=max(mt['speeds'])))
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=90))
            mt_phase('turn',now,1)
        elif phase=='turn':
            assert abs(mount.get_actor_rotation().yaw-90)<15,mount.get_actor_rotation()
            mt['results'].append('steering_turns_mount_and_rider')
            mt_phase('stop',now,1.2)
        elif phase=='stop':
            assert mount.get_velocity().length()<5
            mt['results'].append('release_input_stops_mount')
            # Place a blocking wall ahead, then drive into it.
            location=mount.get_actor_location()
            wall=u.CRBlueprintTools.spawn_pie_test_actor(world,u.StaticMeshActor,u.Transform(location=location+u.Vector(0,260,30)))
            wall.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
            wall.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
            wall.set_actor_scale3d(u.Vector(5,.6,3))
            wall.static_mesh_component.set_collision_profile_name('BlockAll')
            wall.set_actor_label('MountTestWall')
            mt['wall_y']=wall.get_actor_location().y
            mt_phase('wall',now,1.5)
        elif phase=='wall':
            assert mount.get_actor_location().y<mt['wall_y']-85,'Mount passed through the wall'
            for actor in u.GameplayStatics.get_all_actors_of_class(world,u.StaticMeshActor):
                if actor.get_actor_label()=='MountTestWall':actor.destroy_actor()
            mt['results'].append('mount_blocks_against_world_collision')
            mt_phase('prepare_exit',now,1)
        elif phase=='prepare_exit':
            for yaw in [90,-90,135,-135,180,0]:
                direction=mount.get_actor_forward_vector().rotate_angle_axis(yaw,u.Vector(0,0,1))
                location=mount.get_actor_location()+direction*185+u.Vector(0,0,20)
                blocker=u.CRBlueprintTools.spawn_pie_test_actor(world,u.StaticMeshActor,u.Transform(location=location))
                blocker.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
                blocker.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
                blocker.set_actor_scale3d(u.Vector(1.2,1.2,4))
                blocker.static_mesh_component.set_collision_profile_name('BlockAll')
                blocker.set_actor_label('MountExitBlocker')
            pawn.riding.server_dismount()
            assert pawn.riding.is_mounted(),'Dismounted inside obstructed space'
            assert pawn.riding.last_interaction_result=='Move to clear ground to dismount'
            for actor in u.GameplayStatics.get_all_actors_of_class(world,u.StaticMeshActor):
                if actor.get_actor_label()=='MountExitBlocker':actor.destroy_actor()
            mt_input(pawn,'Interact',u.Vector(1,0,0));mt['release']=True
            mt_phase('dismounted',now,1)
        elif phase=='dismounted':
            assert not pawn.riding.is_mounted() and not mount.rider
            assert not pawn.get_attach_parent_actor()
            assert pawn.character_movement.movement_mode==u.MovementMode.MOVE_WALKING
            assert 'Riding' not in str(pawn.baseline_equipment.get_presentation_mesh().component_tags[0])
            assert pawn.headpieces.equipped.definition
            mt['results'].append('blocked_exit_rejected_clear_E_exit_restores_player')
            mt['player_start']=list(pawn.get_actor_location().to_tuple())
            mt_phase('player_walk',now,1)
        elif phase=='player_walk':
            assert (pawn.get_actor_location()-u.Vector(*mt['player_start'])).length()>100
            mt['results'].append('on_foot_movement_restored')
            mt_input(pawn,'Move',u.Vector())
            pawn.set_actor_location(mount.get_actor_location()-mount.get_actor_forward_vector()*180,False,True)
            mt_phase('remount',now,1)
        elif phase=='remount':
            pawn.riding.server_mount(mount)
            assert pawn.riding.is_mounted()
            mount.destroy_actor()
            mt_phase('removed',now,1)
        elif phase=='removed':
            assert not pawn.riding.is_mounted() and not pawn.get_attach_parent_actor()
            assert pawn.character_movement.movement_mode==u.MovementMode.MOVE_WALKING
            mt['results'].append('destroyed_mount_releases_rider')
            mt_finish()
    except Exception:mt_finish(traceback.format_exc())
    finally:mt['busy']=False

assert not u.EditorLevelLibrary.get_pie_worlds(False)
mt['handle']=u.register_slate_post_tick_callback(mt_tick)
u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_begin_play()
print('PLANKTOWN_MOUNT_TEST_STARTED')
