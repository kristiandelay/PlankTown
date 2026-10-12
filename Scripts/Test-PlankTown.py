"""PIE acceptance checks for the real character, input bindings and all headpieces."""
import unreal as u
import json
import time
import traceback
from pathlib import Path

pt_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parents[1]
pt_out=pt_root/'Artifacts/PlankTownTests'
pt_out.mkdir(parents=True,exist_ok=True)
pt={'phase':'setup','next':0,'index':0,'busy':False,'results':[], 'deadline':time.monotonic()+240}
pt_names=['StrawHat','FisherHat','MushroomCap','FestiveHeaddress','IslandSpiritHelmet']

def pt_input(pawn,name,value):
    folder='/Game/Baseline/Input/' if name=='Interact' else '/Game/PlankTown/Input/'
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
        if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(folder+'IA_'+name),u.Vector(value,0,0),[],[])

def pt_finish(error=None):
    u.unregister_slate_post_tick_callback(pt['handle'])
    pt['finished']=True
    report={'passed':error is None,'error':error,'results':pt['results']}
    (pt_out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PLANKTOWN_TEST_COMPLETE',error)

def pt_tick(dt):
    if pt['busy']: return
    pt['busy']=True
    try:
        assert time.monotonic()<pt['deadline'],'PIE checks timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        world=worlds[0]
        pawn=u.GameplayStatics.get_player_pawn(world,0)
        if not pawn:return
        hats=pawn.headpieces
        now=u.GameplayStatics.get_time_seconds(world)
        if pt.pop('release',False):
            for action in ['Interact','DropHeadpiece','HeadpieceColor','HeadpieceLarger','HeadpieceSmaller']:pt_input(pawn,action,0)
        if now<pt['next']:return
        mesh=pawn.baseline_equipment.get_presentation_mesh()
        phase=pt['phase']
        if phase=='setup':
            if now<4:return
            assert mesh.get_skinned_asset().get_name()=='JungleTotemScout',str(mesh.get_skinned_asset())
            assert mesh.is_visible() and not pawn.baseline_equipment.get_weapon_animation_mesh().is_visible()
            assert mesh.get_anim_instance() and mesh.get_bone_index('thumb_03_l')>=0
            assert mesh.does_socket_exist('HeadpieceSocket')
            assert mesh.get_socket_location('head').z>mesh.get_socket_location('pelvis').z+20,'Retargeted head is not above the hips'
            pickups=u.GameplayStatics.get_all_actors_of_class(world,u.PlankTownHeadpiecePickup)
            assert len(pickups)==len(pt_names),len(pickups)
            pt['results'].append({'case':'default_visual_and_all_pickups','mesh':mesh.get_skinned_asset().get_path_name()})
            pt.update(phase='place')
        elif phase=='place':
            name=pt_names[pt['index']]
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.PlankTownHeadpiecePickup) if a.state.definition.mesh.get_name()==name)
            # Use a clear gym station; keep other hats away from the interaction ray.
            station_y=-2350-pt['index']*220
            pawn.set_actor_location(u.Vector(1800,station_y,94),False,True)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0,pitch=-10))
            pickup.set_actor_location(u.Vector(1940,station_y,100),False,True)
            pt.update(pickup=pickup,phase='pickup',next=now+.7)
        elif phase=='pickup':
            assert hats.find_pickup()==pt['pickup'],'No reachable headpiece'
            pt_input(pawn,'Interact',1)
            pt.update(phase='worn',next=now+.7,release=True)
        elif phase=='worn':
            name=pt_names[pt['index']]
            assert hats.equipped.definition and hats.equipped.definition.mesh.get_name()==name
            assert hats.worn_mesh.get_attach_parent()==mesh
            assert str(hats.worn_mesh.get_attach_socket_name())=='HeadpieceSocket'
            assert hats.worn_mesh.static_mesh==hats.equipped.definition.mesh
            pt_input(pawn,'HeadpieceColor',1)
            pt.update(phase='color',next=now+.5,release=True)
        elif phase=='color':
            assert hats.equipped.color_index==1
            pt_input(pawn,'HeadpieceLarger',1)
            pt.update(phase='size',next=now+.5,release=True)
        elif phase=='size':
            assert abs(hats.equipped.size-1.05)<.001
            assert abs(hats.worn_mesh.get_editor_property('relative_scale3d').x-1.05)<.001
            old=(hats.equipped.color_index,hats.equipped.size)
            hats.customize_headpiece(999,4.0)
            assert (hats.equipped.color_index,hats.equipped.size)==old,'Invalid customization accepted'
            pt['capture']=u.AutomationLibrary.take_high_res_screenshot(1280,800,str(pt_out/(pt_names[pt['index']]+'.png')),delay=0)
            pt.update(phase='drop',next=now+.5)
        elif phase=='drop':
            pt_input(pawn,'DropHeadpiece',1)
            pt.update(phase='dropped',next=now+1,release=True)
        elif phase=='dropped':
            assert not hats.equipped.definition,'Drop failed'
            name=pt_names[pt['index']]
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.PlankTownHeadpiecePickup) if a.state.definition.mesh.get_name()==name)
            assert pickup.state.color_index==1 and abs(pickup.state.size-1.05)<.001,'Dropped style was lost'
            assert pickup.collision.is_simulating_physics()
            location=pickup.get_actor_location()
            pawn.set_actor_location(u.Vector(location.x-135,location.y,94),False,True)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0,pitch=-10))
            pt.update(phase='repick',pickup=pickup,next=now+.5)
        elif phase=='repick':
            assert hats.find_pickup()==pt['pickup']
            pt_input(pawn,'Interact',1)
            pt.update(phase='repicked',next=now+.5,release=True)
        elif phase=='repicked':
            assert hats.equipped.definition
            assert hats.equipped.color_index==1 and abs(hats.equipped.size-1.05)<.001
            pt['results'].append({'case':'pickup_customize_drop_repick','name':pt_names[pt['index']],'color':1,'size':hats.equipped.size})
            pt['index']+=1
            if pt['index']<len(pt_names):pt.update(phase='place',next=now+.1)
            else:pt.update(phase='range',next=now+.1)
        elif phase=='range':
            pickup=u.GameplayStatics.get_all_actors_of_class(world,u.PlankTownHeadpiecePickup)[0]
            saved=hats.equipped.definition
            pawn.set_actor_location(u.Vector(3300,-2900,94),False,True)
            hats.server_pickup(pickup)
            assert hats.equipped.definition==saved,'Out-of-range pickup accepted'
            pt['results'].append({'case':'range_and_invalid_style_rejected'})
            pt_finish()
    except Exception:pt_finish(traceback.format_exc())
    finally:pt['busy']=False

pt['handle']=u.register_slate_post_tick_callback(pt_tick)
u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_begin_play()
print('PLANKTOWN_TEST_STARTED')
