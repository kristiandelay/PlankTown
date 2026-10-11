"""Check that the scout visual preserves movement and Lyra weapon actions in PIE."""
import unreal as u
import json
import time
import traceback
from pathlib import Path

pm_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parents[1]
pm={'phase':'setup','next':0,'busy':False,'results':[],'deadline':time.monotonic()+120}

def pm_input(pawn,name,value):
    paths={'Move':'/Game/Input/IA_Move','Aim':'/Game/Input/IA_Aim',
        'Fire':'/Game/Input/Actions/IA_Weapon_Fire_Auto','Reload':'/Game/Input/Actions/IA_Weapon_Reload',
        'Interact':'/Game/Baseline/Input/IA_Interact'}
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
        if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(paths[name]),value,[],[])

def pm_ammo(pawn):
    tag=u.GameplayTag();tag.import_text('(TagName="Lyra.ShooterGame.Weapon.MagazineAmmo")')
    return pawn.baseline_equipment.get_active_item().get_stat_tag_stack_count(tag)

def pm_finish(error=None):
    u.unregister_slate_post_tick_callback(pm['handle'])
    pm['finished']=True
    (pm_root/'Artifacts/PlankTownTests/motion.json').write_text(json.dumps({'passed':error is None,'error':error,'results':pm['results']},indent=2)+'\n')
    print('PLANKTOWN_MOTION_COMPLETE',error)

def pm_tick(dt):
    if pm['busy']:return
    pm['busy']=True
    try:
        assert time.monotonic()<pm['deadline'],'Motion check timed out'
        world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
        pawn=u.GameplayStatics.get_player_pawn(world,0)
        now=u.GameplayStatics.get_time_seconds(world)
        mesh=pawn.baseline_equipment.get_presentation_mesh()
        if pm.pop('release',False):
            for action in ['Interact','Fire','Reload']:pm_input(pawn,action,u.Vector())
        if now<pm['next']:return
        phase=pm['phase']
        if phase=='setup':
            assert mesh.get_skinned_asset().get_name()=='JungleTotemScout'
            pawn.set_actor_location(u.Vector(1300,-3200,94),False,True)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            pm.update(phase='move',start=pawn.get_actor_location(),started=now)
        elif phase=='move':
            if now-pm['started']<1.5:
                pm_input(pawn,'Move',u.Vector(0,1,0))
            else:
                pm_input(pawn,'Move',u.Vector())
                delta=pawn.get_actor_location()-pm['start']
                assert delta.length()>100,delta
                assert mesh.get_socket_location('head').z>pawn.get_actor_location().z
                assert pawn.headpieces.worn_mesh.get_attach_parent()==mesh
                pm['results'].append({'case':'locomotion_with_headpiece','distance_cm':delta.length()})
                pawn.set_actor_location(u.Vector(2100,-1100,94),False,True)
                pawn.get_controller().set_control_rotation(u.Rotator(yaw=0,pitch=-10))
                pm.update(phase='pickup',next=now+1)
        elif phase=='pickup':
            assert pawn.baseline_equipment.find_pickup()
            pm_input(pawn,'Interact',u.Vector(1,0,0))
            pm.update(phase='equipped',next=now+1,release=True)
        elif phase=='equipped':
            assert pawn.baseline_equipment.get_active_item()
            pm['ammo']=pm_ammo(pawn)
            weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
            assert weapon.root_component.get_attach_parent()==mesh
            pm_input(pawn,'Aim',u.Vector(1,0,0))
            pm.update(phase='fire',next=now+.6)
        elif phase=='fire':
            pm_input(pawn,'Fire',u.Vector(1,0,0))
            pm.update(phase='fired',next=now+.5,release=True)
        elif phase=='fired':
            assert pm_ammo(pawn)<pm['ammo']
            pm_input(pawn,'Aim',u.Vector())
            pm_input(pawn,'Reload',u.Vector(1,0,0))
            pm.update(phase='reloaded',next=now+4,release=True)
        elif phase=='reloaded':
            assert pm_ammo(pawn)==pm['ammo']
            pm['results'].append({'case':'rifle_pickup_fire_reload_on_scout_visual','ammo':pm_ammo(pawn)})
            pm_finish()
    except Exception:pm_finish(traceback.format_exc())
    finally:pm['busy']=False

pm['handle']=u.register_slate_post_tick_callback(pm_tick)
print('PLANKTOWN_MOTION_STARTED')
