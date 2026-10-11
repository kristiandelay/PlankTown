"""PIE regression: arm direction, live motion, and weapon poses on the scout."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal as u

arm_root = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parents[1]
arm_out = arm_root / 'Artifacts/ArmFix'
arm_out.mkdir(parents=True, exist_ok=True)
arm_test = dict(phase='setup', busy=False, deadline=time.monotonic()+120, results=[])
arm_actions = {
    'Move': '/Game/Input/IA_Move', 'Aim': '/Game/Input/IA_Aim',
    'Fire': '/Game/Input/Actions/IA_Weapon_Fire_Auto',
    'Reload': '/Game/Input/Actions/IA_Weapon_Reload',
}


def arm_input(name, value):
    arm_test['input'].inject_input_vector_for_action(u.load_asset(arm_actions[name]), value, [], [])


def arm_position(mesh, bone):
    return mesh.get_socket_transform(bone, u.RelativeTransformSpace.RTS_COMPONENT).translation


def arm_ammo(pawn):
    tag = u.GameplayTag()
    tag.import_text('(TagName="Lyra.ShooterGame.Weapon.MagazineAmmo")')
    return pawn.baseline_equipment.get_active_item().get_stat_tag_stack_count(tag)


def arm_phase(name, now, duration=2.0):
    arm_test.update(phase=name, started=now, duration=duration, samples=[], hands=[], captured=False, reload_sent=False)
    (arm_out/'result.json').write_text(json.dumps(dict(passed=False, status='running',
        phase=name, results=arm_test['results']), indent=2)+'\n')


def arm_finish(error=None):
    u.unregister_slate_post_tick_callback(arm_test['handle'])
    if 'input' in arm_test:
        for name in arm_actions:
            arm_input(name, u.Vector())
    if 'pawn' in arm_test:
        arm_test['pawn'].get_controller().set_view_target_with_blend(arm_test['pawn'], 0)
    for key in ('input', 'pawn', 'camera', 'capture'):
        arm_test.pop(key, None)
    arm_test['finished'] = True
    (arm_out/'result.json').write_text(json.dumps(dict(passed=error is None, error=error,
        results=arm_test['results']), indent=2)+'\n')
    print('PLANKTOWN_ARMS_COMPLETE', error)


def arm_tick(dt):
    if arm_test['busy']:
        return
    arm_test['busy'] = True
    try:
        assert time.monotonic() < arm_test['deadline'], 'Arm animation test timed out'
        worlds = u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:
            return
        world = worlds[0]
        pawn = u.GameplayStatics.get_player_pawn(world, 0)
        if not pawn:
            return
        now = u.GameplayStatics.get_time_seconds(world)
        phase = arm_test['phase']
        if phase == 'setup':
            if now < 4:
                return
            mesh = pawn.baseline_equipment.get_presentation_mesh()
            assert mesh.get_skinned_asset().get_name() == 'JungleTotemScout'
            arm_test['pawn'] = pawn
            arm_test['input'] = next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
                if isinstance(s.get_outer(), u.LocalPlayer)
                and u.GameplayStatics.get_player_controller(s, 0) == pawn.get_controller())
            pawn.set_actor_location(u.Vector(1300,-3200,94), False, True)
            pawn.set_actor_rotation(u.Rotator(yaw=0), False)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            camera = u.CRBlueprintTools.spawn_pie_test_actor(world, u.CameraActor, u.Transform())
            camera.get_component_by_class(u.CameraComponent).set_field_of_view(45)
            pawn.get_controller().set_view_target_with_blend(camera, 0)
            arm_test['camera'] = camera
            arm_phase('idle', now)
            return
        elapsed = now-arm_test['started']
        arm_input('Move', u.Vector(0,1,0) if phase == 'jog' else u.Vector())
        arm_input('Aim', u.Vector(1,0,0) if phase in ('aim','fire','left_shoulder') else u.Vector())
        arm_input('Fire', u.Vector(1,0,0) if phase == 'fire' and elapsed < .8 else u.Vector())
        arm_input('Reload', u.Vector(1,0,0) if phase == 'reload' and not arm_test['reload_sent'] else u.Vector())
        if phase == 'reload':
            arm_test['reload_sent'] = True
        location = pawn.get_actor_location()
        camera = arm_test['camera']
        camera_location = location+u.Vector(400,180,66)
        camera.set_actor_location(camera_location, False, True)
        camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(camera_location, location), False)
        source = pawn.baseline_equipment.get_weapon_animation_mesh()
        visual = pawn.baseline_equipment.get_presentation_mesh()
        if elapsed > .7:
            agreement = []
            for side in ('l','r'):
                for start,end in (('upperarm_','lowerarm_'),('lowerarm_','hand_')):
                    a = arm_position(source,end+side)-arm_position(source,start+side)
                    b = arm_position(visual,end+side)-arm_position(visual,start+side)
                    cosine = (a.x*b.x+a.y*b.y+a.z*b.z)/(a.length()*b.length())
                    assert math.isfinite(cosine)
                    agreement.append(cosine)
                if phase == 'idle':
                    assert arm_position(visual,'upperarm_'+side).z-arm_position(visual,'hand_'+side).z > 20, 'Idle arm is pulled up toward the source hand'
            arm_test['samples'].append(agreement)
            hand = arm_position(visual,'hand_l')
            arm_test['hands'].append([hand.x,hand.y,hand.z])
            if not arm_test['captured']:
                arm_test['capture'] = u.AutomationLibrary.take_high_res_screenshot(1440,1000,str(arm_out/(phase+'.png')),delay=0)
                arm_test['captured'] = True
        if elapsed < arm_test['duration']:
            return
        samples = arm_test['samples']
        assert len(samples) >= 8, (phase, 'Too few animation samples', len(samples))
        means = [sum(row[i] for row in samples)/len(samples) for i in range(4)]
        # Allow differing body proportions and the IK elbow bend, while rejecting
        # mirrored/reversed limbs or hands pulled above the idle shoulder.
        assert min(means) > .65, (phase, means)
        record = dict(case=phase, samples=len(samples), segment_direction_cosines=means)
        if phase == 'jog':
            hands = arm_test['hands']
            travel = math.sqrt(sum((max(p[i] for p in hands)-min(p[i] for p in hands))**2 for i in range(3)))
            assert travel > 8, ('Arm swing is frozen', travel)
            record['hand_motion_cm'] = travel
        if phase in ('aim','left_shoulder'):
            assert pawn.baseline_equipment.is_weapon_ready()
        if phase == 'fire':
            assert arm_ammo(pawn) < arm_test['ammo'], 'Weapon failed to fire'
        if phase == 'reload':
            assert arm_ammo(pawn) == arm_test['ammo'], 'Weapon failed to reload'
        arm_test['results'].append(record)
        if phase == 'idle':
            arm_phase('jog',now)
        elif phase == 'jog':
            arm_input('Move',u.Vector())
            pickup = next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if 'Rifle' in str(a.get_item_name()))
            pickup.set_actor_location(pawn.get_actor_location()+u.Vector(120,0,0),False,True)
            pawn.baseline_equipment.server_pickup(pickup)
            assert pawn.baseline_equipment.get_active_item()
            arm_test['ammo'] = arm_ammo(pawn)
            arm_phase('carry',now)
        elif phase == 'carry': arm_phase('aim',now)
        elif phase == 'aim': arm_phase('fire',now)
        elif phase == 'fire': arm_phase('reload',now,4.5)
        elif phase == 'reload':
            pawn.baseline_equipment.toggle_shoulder()
            arm_phase('left_shoulder',now)
        else:
            pawn.baseline_equipment.toggle_shoulder()
            arm_finish()
    except Exception:
        arm_finish(traceback.format_exc())
    finally:
        arm_test['busy'] = False


assert not u.EditorLevelLibrary.get_pie_worlds(False), 'Start this test outside Play'
arm_test['handle'] = u.register_slate_post_tick_callback(arm_tick)
u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_begin_play()
print('PLANKTOWN_ARMS_STARTED')
