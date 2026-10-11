"""Two-player PIE: owning-client RPCs, observers, contested pickup and style persistence."""
import unreal as u
import time
import json
import traceback
from pathlib import Path

pn_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parents[1]
pn={'phase':'setup','next':0,'busy':False,'results':[],'deadline':time.monotonic()+180}
pn_settings=u.get_default_object(u.load_class(None,'/Script/UnrealEd.LevelEditorPlaySettings'))
for key,value in [('PlayNetMode','PIE_ListenServer'),('PlayNumberOfClients','2'),('RunUnderOneProcess','True')]:
    assert u.CRBlueprintTools.set_property_text(pn_settings,key,value)

def pn_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if len(worlds)!=2:return None
    pawns=[p for world in worlds for p in u.GameplayStatics.get_all_actors_of_class(world,u.CRTraversalCharacter) if 'TrainingPartner' not in p.get_class().get_name()]
    client=next((p for p in pawns if p.is_locally_controlled() and not p.has_authority()),None)
    server=next((p for p in pawns if p.has_authority() and not p.is_locally_controlled()),None)
    host=next((p for p in pawns if p.has_authority() and p.is_locally_controlled()),None)
    if not all([client,server,host]):return None
    client_world=next(w for w in worlds if client in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter))
    server_world=next(w for w in worlds if server in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter))
    return client_world,server_world,client,server,host

def pn_input(pawn,name,value):
    folder='/Game/Baseline/Input/' if name=='Interact' else '/Game/PlankTown/Input/'
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
        if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(folder+'IA_'+name),u.Vector(value,0,0),[],[])

def pn_finish(error=None):
    u.unregister_slate_post_tick_callback(pn['handle'])
    pn['finished']=True
    report={'passed':error is None,'error':error,'mode':'two-player listen-server PIE','results':pn['results']}
    (pn_root/'Artifacts/PlankTownTests/network.json').write_text(json.dumps(report,indent=2)+'\n')
    for key,value in [('PlayNetMode','PIE_Standalone'),('PlayNumberOfClients','1')]:
        u.CRBlueprintTools.set_property_text(pn_settings,key,value)
    print('PLANKTOWN_NETWORK_COMPLETE',error)

def pn_tick(dt):
    if pn['busy']:return
    pn['busy']=True
    try:
        assert time.monotonic()<pn['deadline'],'Network checks timed out'
        context=pn_context()
        if not context:return
        cw,sw,client,server,host=context
        now=u.GameplayStatics.get_time_seconds(cw)
        if pn.pop('release',False):
            for action in ['Interact','DropHeadpiece','HeadpieceColor','HeadpieceLarger']:pn_input(client,action,0)
        if now<pn['next']:return
        ch,sh=client.headpieces,server.headpieces
        phase=pn['phase']
        if phase=='setup':
            if now<5:return
            host.set_actor_location(u.Vector(2500,-2900,94),False,True)
            server.set_actor_location(u.Vector(1800,-2350,94),False,True)
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.PlankTownHeadpiecePickup) if a.state.definition.mesh.get_name()=='StrawHat')
            pickup.set_actor_location(u.Vector(1940,-2350,100),False,True)
            pickup.force_net_update()
            client.get_controller().set_control_rotation(u.Rotator(yaw=0,pitch=-10))
            pn.update(phase='pickup',next=now+2)
        elif phase=='pickup':
            assert ch.find_pickup(),'Client cannot find replicated pickup'
            pn_input(client,'Interact',1)
            pn.update(phase='equipped',next=now+2,release=True)
        elif phase=='equipped':
            assert ch.equipped.definition and ch.equipped.definition==sh.equipped.definition
            assert ch.worn_mesh.static_mesh==sh.worn_mesh.static_mesh
            assert ch.worn_mesh.get_attach_parent()==client.baseline_equipment.get_presentation_mesh()
            assert sh.worn_mesh.get_attach_parent()==server.baseline_equipment.get_presentation_mesh()
            assert len(u.GameplayStatics.get_all_actors_of_class(cw,u.PlankTownHeadpiecePickup))==3
            pn['results'].append('owning_client_pickup_and_observer_attachment')
            pn_input(client,'HeadpieceColor',1)
            pn.update(phase='color',next=now+1,release=True)
        elif phase=='color':
            assert ch.equipped.color_index==sh.equipped.color_index==1
            pn_input(client,'HeadpieceLarger',1)
            pn.update(phase='style',next=now+1,release=True)
        elif phase=='style':
            assert abs(ch.equipped.size-1.05)<.001 and abs(sh.equipped.size-1.05)<.001
            for hats in [ch,sh]:
                tint=hats.worn_mesh.get_material(0).get_vector_parameter_value('Tint')
                assert abs(tint.r-.35)<.001 and abs(tint.b-1)<.001
            pn['results'].append('color_material_and_size_replicated')
            ch.customize_headpiece(-1,float('nan'))
            pn.update(phase='invalid',next=now+1)
        elif phase=='invalid':
            assert sh.equipped.color_index==1 and abs(sh.equipped.size-1.05)<.001
            pn_input(client,'DropHeadpiece',1)
            pn.update(phase='dropped',next=now+2,release=True)
        elif phase=='dropped':
            assert not ch.equipped.definition and not sh.equipped.definition
            for world in [cw,sw]:
                pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.PlankTownHeadpiecePickup) if a.state.definition.mesh.get_name()=='StrawHat')
                assert pickup.state.color_index==1 and abs(pickup.state.size-1.05)<.001
            pn['results'].append('client_drop_and_world_style_replicated')
            location=pickup.get_actor_location()
            server.set_actor_location(u.Vector(location.x-130,location.y,94),False,True)
            host.set_actor_location(u.Vector(location.x-130,location.y+40,94),False,True)
            # Sequential requests in one server tick model contention for the same item.
            sh.server_pickup(pickup)
            host.headpieces.server_pickup(pickup)
            pn.update(phase='contested',next=now+2)
        elif phase=='contested':
            assert sh.equipped.definition and ch.equipped.definition
            assert not host.headpieces.equipped.definition,'One world pickup was duplicated'
            assert ch.equipped.color_index==1 and abs(ch.equipped.size-1.05)<.001
            pn['results'].append('contested_pickup_has_one_winner_and_preserves_style')
            pn_finish()
    except Exception:pn_finish(traceback.format_exc())
    finally:pn['busy']=False

pn['handle']=u.register_slate_post_tick_callback(pn_tick)
u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_begin_play()
print('PLANKTOWN_NETWORK_STARTED')
