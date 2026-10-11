"""Import Moku, its gaits, saddle socket, rider pose and traversal-gym spawn."""
import json
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parents[1]
NAME='MokuTheIslandRider'
SOURCE=ROOT/'Resources/Mount'/NAME
FOLDER='/Game/PlankTown/Mounts/'+NAME
lib=u.EditorAssetLibrary;tools=u.AssetToolsHelpers.get_asset_tools()
assert not u.EditorLevelLibrary.get_pie_worlds(False)
assert json.loads((SOURCE/'RigValidation.json').read_text())['passed']

def asset(name,folder,cls,factory):
    return u.load_asset(folder+'/'+name) if lib.does_asset_exist(folder+'/'+name) else tools.create_asset(name,folder,cls,factory)

def save(obj):
    if isinstance(obj,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(obj)
        assert not u.CRBlueprintTools.has_blueprint_errors(obj),obj.get_path_name()
    assert lib.save_loaded_asset(obj,only_if_is_dirty=False),obj.get_path_name()

def import_file(file,folder,name,options=None):
    task=u.AssetImportTask();task.filename=str(file);task.destination_path=folder;task.destination_name=name
    task.automated=True;task.replace_existing=True;task.save=True
    if options:task.options=options
    tools.import_asset_tasks([task])
    obj=u.load_asset(folder+'/'+name)
    assert obj,(file,task.imported_object_paths)
    return obj

u.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
textures={}
for channel in ['BaseColor','Normal','Roughness','Metallic']:
    texture=import_file(SOURCE/'Source'/(NAME+'_'+channel+'.png'),FOLDER+'/Textures',NAME+'_'+channel)
    texture.srgb=channel=='BaseColor';texture.max_texture_size=2048
    if channel=='Normal':
        texture.compression_settings=u.TextureCompressionSettings.TC_NORMALMAP;texture.flip_green_channel=True
    elif channel!='BaseColor':texture.compression_settings=u.TextureCompressionSettings.TC_MASKS
    save(texture);textures[channel]=texture
material=asset('M_'+NAME,FOLDER,u.Material,u.MaterialFactoryNew())
material.set_editor_property('used_with_skeletal_mesh',True)
u.MaterialEditingLibrary.delete_all_material_expressions(material)
for i,(channel,prop) in enumerate([('BaseColor',u.MaterialProperty.MP_BASE_COLOR),('Normal',u.MaterialProperty.MP_NORMAL),('Roughness',u.MaterialProperty.MP_ROUGHNESS),('Metallic',u.MaterialProperty.MP_METALLIC)]):
    node=u.MaterialEditingLibrary.create_material_expression(material,u.MaterialExpressionTextureSample,-400,i*200)
    node.texture=textures[channel]
    if channel=='Normal':node.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL
    elif channel!='BaseColor':node.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS
    assert u.MaterialEditingLibrary.connect_material_property(node,'RGB' if channel in ['BaseColor','Normal'] else 'R',prop)
u.MaterialEditingLibrary.recompile_material(material);save(material)
options=u.FbxImportUI()
for key,value in dict(import_mesh=True,import_as_skeletal=True,mesh_type_to_import=u.FBXImportType.FBXIT_SKELETAL_MESH,
    original_import_type=u.FBXImportType.FBXIT_SKELETAL_MESH,automated_import_should_detect_type=False,
    import_animations=False,import_materials=False,import_textures=False,create_physics_asset=True).items():options.set_editor_property(key,value)
options.skeletal_mesh_import_data.normal_import_method=u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
if lib.does_asset_exist(FOLDER+'/'+NAME+'_Skeleton'):options.skeleton=u.load_asset(FOLDER+'/'+NAME+'_Skeleton')
mesh=import_file(SOURCE/'Export'/(NAME+'.fbx'),FOLDER,NAME,options)
materials=list(mesh.get_editor_property('materials'))
for slot in materials:slot.material_interface=material
mesh.set_editor_property('materials',materials)
assert u.get_editor_subsystem(u.SkeletalMeshEditorSubsystem).regenerate_lod(mesh,3,False,False)
assert u.CRBlueprintTools.configure_mount_socket(mesh)
skeleton=mesh.get_editor_property('skeleton')
save(mesh);save(skeleton);save(mesh.get_editor_property('physics_asset'))
clips={}
for name in ['Idle','Walk','Run','JumpRise','JumpFall','Land']:
    options=u.FbxImportUI()
    for key,value in dict(import_mesh=False,import_as_skeletal=True,mesh_type_to_import=u.FBXImportType.FBXIT_ANIMATION,
        original_import_type=u.FBXImportType.FBXIT_ANIMATION,automated_import_should_detect_type=False,
        import_animations=True,import_materials=False,import_textures=False,skeleton=skeleton).items():options.set_editor_property(key,value)
    options.anim_sequence_import_data.set_editor_property('animation_length',u.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
    options.anim_sequence_import_data.set_editor_property('use_default_sample_rate',True)
    clips[name]=import_file(SOURCE/'Export'/(NAME+'_'+name+'.fbx'),FOLDER+'/Animations','A_'+NAME+'_'+name,options)
    assert isinstance(clips[name],u.AnimSequence)
    save(clips[name])
factory=u.BlendSpaceFactory1D();factory.target_skeleton=skeleton
blend=asset('BS_'+NAME,FOLDER+'/Animations',u.BlendSpace1D,factory)
factory=u.AnimBlueprintFactory();factory.set_editor_property('target_skeleton',skeleton);factory.set_editor_property('parent_class',u.PlankTownMountAnimInstance)
animation=asset('ABP_'+NAME,FOLDER+'/Animations',u.AnimBlueprint,factory)
assert u.CRBlueprintTools.build_mount_animation(animation,blend,clips['Idle'],clips['Walk'],clips['Run'],clips['JumpRise'],clips['JumpFall'],clips['Land'])
save(blend);save(animation)
factory=u.BlueprintFactory();factory.set_editor_property('parent_class',u.PlankTownMount)
blueprint=asset('BP_'+NAME,FOLDER,u.Blueprint,factory)
default=u.get_default_object(blueprint.generated_class())
default.mesh.set_skeletal_mesh_asset(mesh)
default.mesh.set_anim_instance_class(animation.generated_class())
default.character_movement.jump_z_velocity=520
default.character_movement.gravity_scale=1.35
default.character_movement.air_control=.35
default.capsule_component.set_collision_response_to_channel(u.CollisionChannel.ECC_CAMERA,u.CollisionResponseType.ECR_IGNORE)
default.mesh.set_collision_response_to_channel(u.CollisionChannel.ECC_CAMERA,u.CollisionResponseType.ECR_IGNORE)
save(blueprint)

manny=u.load_asset('/Game/Characters/UE5_Mannequins/Meshes/SKM_Manny')
factory=u.AnimSequenceFactory();factory.set_editor_property('target_skeleton',manny.get_editor_property('skeleton'));factory.set_editor_property('preview_skeletal_mesh',manny)
rider_pose=asset('A_Manny_RidingMoku',FOLDER+'/Animations',u.AnimSequence,factory)
assert u.CRBlueprintTools.build_riding_pose(manny,rider_pose);save(rider_pose)
driver=u.load_asset('/Game/Baseline/Animations/ABP_BaselineManny')
assert u.CRBlueprintTools.build_riding_overlay(driver,rider_pose);save(driver)
# Seated legs follow the authored rider pose; world-space foot contacts belong
# to walking on the ground. Use a separate retarget profile while mounted.
scout='/Game/PlankTown/Player/JungleTotemScout/'
tag='RTG_Manny_to_JungleTotemScout_Riding'
retarget=u.load_asset(scout+tag) if lib.does_asset_exist(scout+tag) else lib.duplicate_asset(scout+'RTG_Manny_to_JungleTotemScout',scout+tag)
controller=u.IKRetargeterController.get_controller(retarget)
for i in range(controller.get_num_retarget_ops()):
    if str(controller.get_op_name(i)) in ['Run IK Rig','Pole Vector Alignment']:controller.set_retarget_op_enabled(i,False)
save(retarget)
visual=u.load_asset('/Game/Baseline/Animations/ABP_BaselineVisualRetarget')
default=u.get_default_object(visual.generated_class())
mapping=default.get_editor_property('IKRetargeter_Map');mapping[tag]=retarget
default.set_editor_property('IKRetargeter_Map',mapping);save(visual)
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/L_TraversalGym')
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
mount=next((a for a in actors.get_all_level_actors() if a.get_actor_label()=='PlankTown_Moku'),None)
if not mount:
    mount=actors.spawn_actor_from_class(blueprint.generated_class(),u.Vector(2100,-2050,93),u.Rotator(yaw=180))
    mount.set_actor_label('PlankTown_Moku')
mount.capsule_component.set_collision_response_to_channel(u.CollisionChannel.ECC_CAMERA,u.CollisionResponseType.ECR_IGNORE)
mount.mesh.set_collision_response_to_channel(u.CollisionChannel.ECC_CAMERA,u.CollisionResponseType.ECR_IGNORE)
assert levels.save_current_level()
(SOURCE/'UnrealImport.json').write_text(json.dumps(dict(imported=True,mesh=mesh.get_path_name(),
    blueprint=blueprint.get_path_name(),animations={n:a.get_path_name() for n,a in clips.items()},
    level='/Game/Maps/L_TraversalGym',actor='PlankTown_Moku',controls='E mount/dismount, WASD ride, Shift run, Space jump'),indent=2)+'\n')
print('PLANKTOWN_MOUNT_IMPORT_COMPLETE')
