"""Import prepared source exports, materials, player override, headpieces and inputs."""
import json
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parents[1]
lib = u.EditorAssetLibrary
tools = u.AssetToolsHelpers.get_asset_tools()
assert not u.EditorLevelLibrary.get_pie_worlds(False)

def save(obj):
    if isinstance(obj,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(obj)
        assert not u.CRBlueprintTools.has_blueprint_errors(obj), obj.get_path_name()
    assert lib.save_loaded_asset(obj,only_if_is_dirty=False), obj.get_path_name()

def asset(name,folder,cls,factory):
    return u.load_asset(folder+'/'+name) if lib.does_asset_exist(folder+'/'+name) else tools.create_asset(name,folder,cls,factory)

def duplicate(source,destination):
    return u.load_asset(destination) if lib.does_asset_exist(destination) else lib.duplicate_asset(source,destination)

def cdo(bp): return u.get_default_object(bp.generated_class())

def import_file(filename,folder,name,options=None):
    task=u.AssetImportTask()
    task.filename=str(filename)
    task.destination_path=folder
    task.destination_name=name
    task.automated=True
    task.replace_existing=True
    task.save=True
    if options: task.options=options
    tools.import_asset_tasks([task])
    obj=u.load_asset(folder+'/'+name)
    assert obj,(filename,task.imported_object_paths)
    return obj

u.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
records=[]
for category,names in [('Player',['JungleTotemScout']),('Headpieces',['StrawHat','FisherHat','MushroomCap','FestiveHeaddress'])]:
    for name in names:
        source=ROOT/'Resources'/category/name
        skeletal=category=='Player'
        if skeletal: assert json.loads((source/'RigValidation.json').read_text())['passed']
        folder='/Game/PlankTown/'+category+'/'+name
        textures={}
        for channel in ['BaseColor','Normal','Roughness','Metallic']:
            texture=import_file(source/'Source'/(name+'_'+channel+'.png'),folder+'/Textures',name+'_'+channel)
            texture.set_editor_property('srgb',channel=='BaseColor')
            texture.set_editor_property('max_texture_size',2048)
            if channel=='Normal':
                texture.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_NORMALMAP)
                texture.set_editor_property('flip_green_channel',True)
            elif channel!='BaseColor': texture.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_MASKS)
            save(texture)
            textures[channel]=texture
        material=asset('M_'+name,folder,u.Material,u.MaterialFactoryNew())
        material.set_editor_property('used_with_skeletal_mesh',skeletal)
        u.MaterialEditingLibrary.delete_all_material_expressions(material)
        for index,(channel,prop) in enumerate([('BaseColor',u.MaterialProperty.MP_BASE_COLOR),('Normal',u.MaterialProperty.MP_NORMAL),('Roughness',u.MaterialProperty.MP_ROUGHNESS),('Metallic',u.MaterialProperty.MP_METALLIC)]):
            node=u.MaterialEditingLibrary.create_material_expression(material,u.MaterialExpressionTextureSample,-600,index*220)
            node.texture=textures[channel]
            if channel=='Normal': node.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL
            elif channel!='BaseColor': node.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS
            if channel=='BaseColor':
                tint=u.MaterialEditingLibrary.create_material_expression(material,u.MaterialExpressionVectorParameter,-600,-200)
                tint.set_editor_property('parameter_name','Tint')
                tint.set_editor_property('default_value',u.LinearColor(1,1,1,1))
                multiply=u.MaterialEditingLibrary.create_material_expression(material,u.MaterialExpressionMultiply,-250,0)
                assert u.MaterialEditingLibrary.connect_material_expressions(node,'RGB',multiply,'A')
                assert u.MaterialEditingLibrary.connect_material_expressions(tint,'RGB',multiply,'B')
                assert u.MaterialEditingLibrary.connect_material_property(multiply,'',prop)
            else: assert u.MaterialEditingLibrary.connect_material_property(node,'RGB' if channel=='Normal' else 'R',prop)
        u.MaterialEditingLibrary.recompile_material(material)
        save(material)
        options=u.FbxImportUI()
        kind=u.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else u.FBXImportType.FBXIT_STATIC_MESH
        for key,value in dict(import_mesh=True,import_as_skeletal=skeletal,mesh_type_to_import=kind,
            original_import_type=kind,automated_import_should_detect_type=False,import_animations=False,
            import_materials=False,import_textures=False,create_physics_asset=skeletal).items():
            options.set_editor_property(key,value)
        data=options.skeletal_mesh_import_data if skeletal else options.static_mesh_import_data
        data.set_editor_property('normal_import_method',u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
        if skeletal:
            data.set_editor_property('update_skeleton_reference_pose',False)
            if lib.does_asset_exist(folder+'/'+name+'_Skeleton'):
                options.skeleton=u.load_asset(folder+'/'+name+'_Skeleton')
        else:
            data.set_editor_property('combine_meshes',True)
            data.set_editor_property('auto_generate_collision',True)
        mesh=import_file(source/'Export'/(name+'.fbx'),folder,name,options)
        if skeletal:
            assert isinstance(mesh,u.SkeletalMesh)
            materials=list(mesh.get_editor_property('materials'))
            for slot in materials: slot.set_editor_property('material_interface',material)
            mesh.set_editor_property('materials',materials)
            assert u.get_editor_subsystem(u.SkeletalMeshEditorSubsystem).regenerate_lod(mesh,3,False,False)
            assert u.CRBlueprintTools.create_headpiece_socket(mesh,u.Vector(0,0,174))
            save(mesh.get_editor_property('skeleton'))
            save(mesh.get_editor_property('physics_asset'))
        else:
            assert isinstance(mesh,u.StaticMesh)
            mesh.set_material(0,material)
            factory=u.DataAssetFactory()
            factory.set_editor_property('data_asset_class',u.PlankTownHeadpieceDefinition)
            definition=asset('DA_'+name,folder,u.PlankTownHeadpieceDefinition,factory)
            definition.set_editor_property('display_name',u.Text({'StrawHat':'Straw Hat','FisherHat':'Fisher Hat','MushroomCap':'Mushroom Cap','FestiveHeaddress':'Festive Headdress'}[name]))
            definition.set_editor_property('mesh',mesh)
            # The cap includes an underside/stem: seat its brim on the scalp.
            definition.set_editor_property('wear_transform',u.Transform(location=u.Vector(0,0,-18 if name=='MushroomCap' else 0)))
            save(definition)
            factory=u.BlueprintFactory()
            factory.set_editor_property('parent_class',u.PlankTownHeadpiecePickup)
            pickup=asset('BP_'+name+'_Pickup',folder,u.Blueprint,factory)
            state=cdo(pickup).get_editor_property('state')
            state.set_editor_property('definition',definition)
            cdo(pickup).set_editor_property('state',state)
            save(pickup)
        save(mesh)
        records.append({'name':name,'mesh':mesh.get_path_name(),'material':material.get_path_name()})

name='JungleTotemScout'
folder='/Game/PlankTown/Player/'+name
mesh=u.load_asset(folder+'/'+name)
rig=asset('IK_'+name,folder,u.IKRigDefinition,u.IKRigDefinitionFactory())
controller=u.IKRigController.get_controller(rig)
assert controller.set_skeletal_mesh(mesh)
assert controller.apply_auto_generated_retarget_definition()
assert controller.apply_auto_fbik()
save(rig)
retarget=duplicate('/Game/Baseline/Animations/VisualOverrides/RTG_Manny_to_UE5_Mannequin',folder+'/RTG_Manny_to_'+name)
controller=u.IKRetargeterController.get_controller(retarget)
controller.set_ik_rig(u.RetargetSourceOrTarget.TARGET,rig)
controller.set_preview_mesh(u.RetargetSourceOrTarget.TARGET,mesh)
controller.auto_map_chains(u.AutoMapChainType.FUZZY,True)
for pose in controller.get_retarget_poses(u.RetargetSourceOrTarget.TARGET):
    controller.reset_retarget_pose(pose,[],u.RetargetSourceOrTarget.TARGET)
controller.auto_align_all_bones(u.RetargetSourceOrTarget.TARGET)
save(retarget)
animation=u.load_asset('/Game/Baseline/Animations/ABP_BaselineVisualRetarget')
mapping=cdo(animation).get_editor_property('IKRetargeter_Map')
mapping['RTG_Manny_to_'+name]=retarget
cdo(animation).set_editor_property('IKRetargeter_Map',mapping)
save(animation)
visual=duplicate('/Game/Blueprints/RetargetedCharacters/BP_Manny',folder+'/BP_'+name)
sub=u.get_engine_subsystem(u.SubobjectDataSubsystem)
data=u.SubobjectDataBlueprintFunctionLibrary
seen=set()
for handle in sub.k2_gather_subobject_data_for_blueprint(visual):
    component=data.get_object_for_blueprint(data.get_data(handle),visual)
    if isinstance(component,u.SkeletalMeshComponent) and component.get_path_name() not in seen:
        component.set_editor_property('skeletal_mesh_asset',mesh)
        component.set_editor_property('anim_class',animation.generated_class())
        component.set_editor_property('component_tags',['RTG_Manny_to_'+name])
        seen.add(component.get_path_name())
assert len(seen)==1,seen
save(visual)
catalog=u.load_asset('/Game/Blueprints/GM_Sandbox')
entries=list(cdo(catalog).get_editor_property('VisualOverrides_Soft'))
if not any(entry and entry.get_path_name()==visual.generated_class().get_path_name() for entry in entries):
    entries.append(visual.generated_class())
cdo(catalog).set_editor_property('VisualOverrides_Soft',entries)
save(catalog)
# Default selected visual also remains available through the sample's widget.
pawn=u.load_asset('/Game/Crusader/Characters/B_CRTraversalPawn')
for handle in sub.k2_gather_subobject_data_for_blueprint(pawn):
    component=data.get_object_for_blueprint(data.get_data(handle),pawn)
    if isinstance(component,u.ChildActorComponent) and component.get_name().startswith('SelectedVisualOverride'):
        component.set_editor_property('child_actor_class',visual.generated_class())
save(pawn)

mapping=u.load_asset('/Game/Baseline/Input/IMC_Baseline')
for name,key_name in [('DropHeadpiece','H'),('HeadpieceColor','J'),('HeadpieceLarger','RightBracket'),('HeadpieceSmaller','LeftBracket')]:
    action=asset('IA_'+name,'/Game/PlankTown/Input',u.InputAction,u.InputAction_Factory())
    action.set_editor_property('value_type',u.InputActionValueType.BOOLEAN)
    save(action)
    mapping.unmap_all_keys_from_action(action)
    key=u.Key()
    assert key.import_text(key_name)
    mapping.map_key(action,key)
save(mapping)
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/L_TraversalGym')
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
existing={a.get_actor_label():a for a in actors.get_all_level_actors()}
for index,name in enumerate(['StrawHat','FisherHat','MushroomCap','FestiveHeaddress']):
    label='PlankTown_'+name
    actor=existing.get(label)
    if not actor:
        cls=u.load_class(None,'/Game/PlankTown/Headpieces/'+name+'/BP_'+name+'_Pickup.BP_'+name+'_Pickup_C')
        actor=actors.spawn_actor_from_class(cls,u.Vector(1800+index*160,-1550,100))
        actor.set_actor_label(label)
assert levels.save_current_level()
(ROOT/'Resources/PlankTownImport.json').write_text(json.dumps({'imported':True,'assets':records,'visual_override_index':len(entries)-1},indent=2)+'\n')
print('PLANKTOWN_IMPORT_COMPLETE')
