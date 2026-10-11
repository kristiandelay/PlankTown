"""Make all prepared scenes portable without re-running skinning or reduction."""
import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for scene in (ROOT/'Resources').rglob('*.blend'):
    bpy.ops.wm.open_mainfile(filepath=str(scene))
    for material in list(bpy.data.materials):
        if material.users == 0: bpy.data.materials.remove(material)
    for image in list(bpy.data.images):
        if image.users == 0: bpy.data.images.remove(image)
    bpy.ops.file.make_paths_relative()
    missing=[image.filepath for image in bpy.data.images if image.source=='FILE' and image.filepath and not Path(bpy.path.abspath(image.filepath)).exists()]
    assert not missing,(str(scene),missing)
    bpy.ops.wm.save_mainfile()
