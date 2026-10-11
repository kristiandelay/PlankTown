"""Two-player PIE: owning-client ride input, replicated seating, and occupancy."""
import unreal as u
import json
import time
import traceback
from pathlib import Path

mn_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parents[1]
mn=dict(phase='setup',busy=False,next=0,results=[],deadline=time.monotonic()+180)
mn_settings=u.get_default_object(u.load_class(None,'/Script/UnrealEd.LevelEditorPlaySettings'))
assert not u.EditorLevelLibrary.get_pie_worlds(False)
for key,value in [('PlayNetMode','PIE_ListenServer'),('PlayNumberOfClients','2'),('RunUnderOneProcess','True')]:
    assert u.CRBlueprintTools.set_property_text(mn_settings,key,value)

def mn_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if len(worlds)!=2:return None
    pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if 'TrainingPartner' not in p.get_class().get_name()]
    client=next((p for p in pawns if p.is_locally_controlled() and not p.has_authority()),None)
    server=next((p for p in pawns if p.has_authority() and not p.is_locally_controlled()),None)
    host=next((p for p in pawns if p.has_authority() and p.is_locally_controlled()),None)
    if not all([client,server,host]):return None
    cw=next(w for w in worlds if client in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter))
    sw=next(w for w in worlds if server in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter))
    cm=u.GameplayStatics.get_all_actors_of_class(cw,u.PlankTownMount)
    sm=u.GameplayStatics.get_all_actors_of_class(sw,u.PlankTownMount)
    if not cm or not sm:return None
    return cw,sw,client,server,host,cm[0],sm[0]

def mn_input(pawn,name,value):
    folder='/Game/Baseline/Input/' if name=='Interact' else '/Game/Input/'
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
        if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(folder+'IA_'+name),value,[],[])

def mn_phase(name,now,delay=1.5):mn.update(phase=name,next=now+delay)

def mn_finish(error=None):
    u.unregister_slate_post_tick_callback(mn['handle']);mn['finished']=True
    context=mn_context()
    if context:
        for action in ['Interact','Move','Sprint']:mn_input(context[2],action,u.Vector())
    report=dict(passed=error is None,error=error,mode='two-player listen-server PIE',results=mn['results'])
    (mn_root/'Artifacts/MountTests/network.json').write_text(json.dumps(report,indent=2)+'\n')
    for key,value in [('PlayNetMode','PIE_Standalone'),('PlayNumberOfClients','1')]:
        u.CRBlueprintTools.set_property_text(mn_settings,key,value)
    print('PLANKTOWN_MOUNT_NETWORK_COMPLETE',error)

def mn_tick(dt):
    if mn['busy']:return
    mn['busy']=True
    try:
        assert time.monotonic()<mn['deadline'],'Mount network test timed out'
        context=mn_context()
        if not context:return
        cw,sw,client,server,host,cm,sm=context
        now=u.GameplayStatics.get_time_seconds(cw);phase=mn['phase']
        if mn.pop('release',False):mn_input(client,'Interact',u.Vector())
        moving=phase in ['walk','run','foot']
        mn_input(client,'Move',u.Vector(0,1,0) if moving else u.Vector())
        mn_input(client,'Sprint',u.Vector(1,0,0) if phase=='run' else u.Vector())
        if phase in ['walk','run']:mn['speeds'].append(sm.get_velocity().length())
        if now<mn['next']:return
        if phase=='setup':
            if now<5:return
            sm.set_actor_location(u.Vector(1300,-3600,92),False,True)
            sm.set_actor_rotation(u.Rotator(yaw=0),False);sm.force_net_update()
            server.set_actor_location(u.Vector(1120,-3600,94),False,True)
            host.set_actor_location(u.Vector(500,-3900,94),False,True)
            client.get_controller().set_control_rotation(u.Rotator(yaw=0))
            hat=next(a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.PlankTownHeadpiecePickup) if a.state.definition.mesh.get_name()=='StrawHat')
            hat.set_actor_location(u.Vector(1140,-3540,110),False,True)
            server.headpieces.server_pickup(hat)
            mn_phase('mount',now,2)
        elif phase=='mount':
            assert client.riding.find_mount()==cm,'Client cannot find mount'
            mn_input(client,'Interact',u.Vector(1,0,0));mn['release']=True
            mn_phase('seated',now,2)
        elif phase=='seated':
            for pawn,mount in [(client,cm),(server,sm)]:
                assert pawn.riding.mounted_mount==mount and mount.rider==pawn
                assert pawn.get_attach_parent_actor()==mount
                assert pawn.character_movement.movement_mode==u.MovementMode.MOVE_NONE
                visual=pawn.baseline_equipment.get_presentation_mesh()
                assert 'Riding' in str(visual.component_tags[0])
                assert (visual.get_socket_location('pelvis')-mount.mesh.get_socket_location('RiderSocket')).length()<20
                assert pawn.headpieces.equipped.definition
            mn['results'].append('client_E_mount_replicates_seated_rider_and_headpiece')
            host.set_actor_location(sm.get_actor_location()+u.Vector(0,190,0),False,True)
            mn_phase('occupied',now,.8)
        elif phase=='occupied':
            host.riding.server_mount(sm)
            assert not host.riding.is_mounted() and sm.rider==server
            host.set_actor_location(u.Vector(500,-3900,94),False,True)
            mn['results'].append('occupied_mount_rejects_second_player')
            mn.update(start=list(sm.get_actor_location().to_tuple()),speeds=[])
            mn_phase('walk',now,2)
        elif phase=='walk':
            distance=(sm.get_actor_location()-u.Vector(*mn['start'])).length()
            assert distance>250 and 200<max(mn['speeds'])<270,(distance,mn['speeds'])
            assert (sm.get_actor_location()-cm.get_actor_location()).length()<100
            assert (server.get_actor_location()-client.get_actor_location()).length()<100
            mn['results'].append(dict(case='client_WASD_drives_authoritative_mount_and_observer',distance_cm=distance))
            mn.update(start=list(sm.get_actor_location().to_tuple()),speeds=[])
            mn_phase('run',now,2)
        elif phase=='run':
            distance=(sm.get_actor_location()-u.Vector(*mn['start'])).length()
            assert distance>650 and 480<max(mn['speeds'])<550
            mn['results'].append(dict(case='client_Shift_replicates_running',distance_cm=distance,peak_speed=max(mn['speeds'])))
            mn_phase('stop',now)
        elif phase=='stop':
            assert sm.get_velocity().length()<5
            mn_input(client,'Interact',u.Vector(1,0,0));mn['release']=True
            mn_phase('dismounted',now,2)
        elif phase=='dismounted':
            for pawn,mount in [(client,cm),(server,sm)]:
                assert not pawn.riding.is_mounted() and not mount.rider
                assert not pawn.get_attach_parent_actor()
                assert pawn.character_movement.movement_mode==u.MovementMode.MOVE_WALKING
                assert 'Riding' not in str(pawn.baseline_equipment.get_presentation_mesh().component_tags[0])
                assert pawn.headpieces.equipped.definition
            assert (server.get_actor_location()-client.get_actor_location()).length()<30
            mn['results'].append('client_E_dismount_replicates_and_restores_on_foot_pose')
            mn['start']=list(server.get_actor_location().to_tuple())
            mn_phase('foot',now,1)
        elif phase=='foot':
            assert (server.get_actor_location()-u.Vector(*mn['start'])).length()>100
            mn['results'].append('client_on_foot_movement_restored')
            mn_input(client,'Move',u.Vector())
            server.set_actor_location(sm.get_actor_location()+u.Vector(-180,0,0),False,True)
            host.set_actor_location(sm.get_actor_location()+u.Vector(0,185,0),False,True)
            mn_phase('contest',now,1)
        elif phase=='contest':
            server.riding.server_mount(sm);host.riding.server_mount(sm)
            mn_phase('winner',now,2)
        elif phase=='winner':
            assert server.riding.mounted_mount==sm and sm.rider==server
            assert client.riding.mounted_mount==cm and cm.rider==client
            assert not host.riding.is_mounted()
            mn['results'].append('simultaneous_requests_have_one_replicated_winner')
            mn_finish()
    except Exception:mn_finish(traceback.format_exc())
    finally:mn['busy']=False

mn['handle']=u.register_slate_post_tick_callback(mn_tick)
u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_begin_play()
print('PLANKTOWN_MOUNT_NETWORK_STARTED')
