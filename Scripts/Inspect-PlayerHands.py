import bpy
from pathlib import Path
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
source = ROOT / 'Resources/Player/JungleTotemScout/Source/JungleTotemScout.fbx'
bpy.ops.import_scene.fbx(filepath=str(source))
mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
mat = bpy.data.materials.new('Clay')
mat.diffuse_color = (.55,.55,.55,1)
mesh.data.materials.clear()
mesh.data.materials.append(mat)
center = Vector((.75, 0, .88))
scene = bpy.context.scene
bpy.ops.object.camera_add(location=(.75,0,3))
camera=bpy.context.object
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=.60
scene.camera=camera
scene.render.engine='BLENDER_WORKBENCH'
scene.display.shading.light='STUDIO'
scene.display.shading.show_shadows=True
scene.display.shading.show_cavity=True
scene.render.resolution_x=1000
scene.render.resolution_y=1000
scene.render.resolution_percentage=100
scene.render.filepath=str(ROOT/'Artifacts/SourceReview/PlayerHandTop.png')
bpy.ops.render.render(write_still=True)
camera.location=Vector((.75,-.4,2.2))
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(ROOT/'Artifacts/SourceReview/PlayerHandAngle.png')
bpy.ops.render.render(write_still=True)
