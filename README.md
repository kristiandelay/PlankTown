# PlankTown

Unreal Engine 5.8 project based on the Lyra/GASP template, with the Jungle Totem Scout player, four customizable headpieces, and the rideable Moku mount.

Open `Src/PlankTown/PlankTown.uproject` or `Open-Traversal.cmd`, then press Play. The scout is the default visual override in the traversal gym and is also available in the Game Animation Widget. Native Lyra module names and inherited content paths are retained to preserve asset references.

## Setup

Install Unreal Engine 5.8, its Visual Studio C++ prerequisites, Git, and Git LFS.

```powershell
git lfs install
git clone git@github.com:kristiandelay/PlankTown.git
cd PlankTown
git lfs pull
powershell -ExecutionPolicy Bypass -File Scripts/Build-Editor.ps1
```

The entire workspace belongs to this repository. Unreal assets, FBX exports, Blender scenes, textures, and source ZIPs use LFS. Build products and local validation artifacts are ignored. `template` identifies the original LyraGasp5.8Template repository.

## Headpieces

Straw Hat, Fisher Hat, Mushroom Cap, and Festive Headdress pickups are placed beside the gym's equipment area.

| Key | Action |
| --- | --- |
| E | Pick up a reachable weapon or headpiece in front of you; aim at a hat to select it |
| H | Drop the worn headpiece |
| J | Cycle headpiece color |
| [ / ] | Decrease / increase headpiece size, from 80% to 120% |
| G / Tab | Drop / switch weapon |
| WASD / Shift / C / Space | Move / sprint / crouch or slide / jump or traverse |

Equipping another headpiece drops the previous one. Color and size travel with each item through drops and pickups. Items and worn appearance replicate, with server checks for distance, visibility, character state, and valid customization. Hat sizing is authored for the scout; other visual overrides can supply their own `HeadpieceSocket`.

Add a headpiece by creating a `PlankTownHeadpieceDefinition` data asset and a pickup Blueprint based on `PlankTownHeadpiecePickup`. The definition contains its mesh, palette, socket and wear transform. Materials use the `Tint` vector parameter.

## Riding Moku

Moku the Island Rider stands beside the equipment and headpiece area in the traversal gym. Approach and face Moku, then press **E** to mount. Use **WASD** to steer relative to the camera, **Shift** to run, and **E** again to dismount. The scout sits in the saddle and keeps its headpiece and inventory. Combat and traversal actions are suspended while riding.

Mounting, movement, occupancy and dismounting are server-authoritative and replicate to other players. Only one player can ride each mount. Dismounting searches for clear ground on either side and behind or ahead; if every exit is blocked, the HUD asks you to move to clear ground. Removing the mount or killing the rider releases the attachment.

The camera ignores Moku's capsule and mesh, so orbiting the rider does not push the camera into the saddle. World geometry still blocks the camera and the mount's movement.

`BP_MokuTheIslandRider` lives in `Content/PlankTown/Mounts/MokuTheIslandRider`. Its native mount class exposes walk/run speeds, the saddle socket, and rider height for tuning. The animation blend space uses 0, 240 and 520 cm/s for idle, walk and run. The scout switches to a seated retarget profile while riding and restores its walking profile on exit.

## Art sources

`Resources/Player/JungleTotemScout/` contains the untouched normalized `Source/`, editable Auto-Rig Pro `.blend`, game-ready `Export/`, and rig validation report. The supplied character has four digits per hand, all rigged and weighted. ARP uses thumb/middle/ring/pinky names for its four-digit preset. The exported body has 90,000 triangles and at most four influences per vertex.

Each `Resources/Headpieces/<Name>/` folder contains the same source/scene/export separation. Headpiece exports have about 16,000 triangles each. ZIP bytes remain unchanged; `SourceManifest.json` records the original delivery names, source IDs and hashes. Texture names use `_BaseColor`, `_Normal`, `_Metallic`, and `_Roughness`.

`Resources/Mount/MokuTheIslandRider/` contains Moku's normalized source files, editable Blender scene, skeletal FBX and idle/walk/run exports. Its fitted 20-bone quadruped rig includes three joints per leg, neck, head, tail and saddle, with automatic weights refined around the saddle. The game mesh has 100,000 triangles, no unweighted vertices and at most four influences per vertex; Unreal also has two reduced LODs. The four-beat walk and three-beat running canter use articulated knees, lifting/toe motion, body sway and head/tail follow-through. Foot contact timing matches the movement speeds.

Preparation scripts require Blender 5.2 and the installed Auto-Rig Pro add-on. `Fit-PlayerAutoRig.py -- JungleTotemScout` runs in Blender with a viewport; skinning, headpiece preparation, and `Validate-PlayerRig.py` run in background mode. `Import-PlankTownAssets.py` runs inside Unreal and rebuilds the imported assets from the prepared exports.

The import calls `Configure-PlayerRetarget.py` to assign the scout rig to every UE 5.8 retarget operation, map its toe chains, and align its rest pose. Ordinary arm animation preserves the scout's proportions; traversal contact curves can still blend toward the source hands. Run this configuration script outside Play to update the retargeter without reimporting the artwork.

For Moku, run `Prepare-Mount.py` in Blender background mode to rebuild the fitted rig, weights and exports. Run `Animate-Mount.py` to update only its three gaits without skinning again, then `Validate-MountRig.py` to render and check all four legs, knee flexion, loop continuity and FBX round-trip. `Import-Mount.py` runs inside Unreal outside Play and imports the mount, its animation blueprint, seated rider pose and gym placement. The mount pipeline uses Blender's built-in tools and does not require Auto-Rig Pro.

## Validation

Build with `Scripts/Build-Editor.ps1`. For editor automation, open with `Scripts/Open-Traversal.ps1 -Automation`, then use `python Scripts/Send-Editor.py Scripts/Test-PlankTown.py`. The test starts PIE and exercises the default visual, all four pickups, customization, swaps, physics drops, re-pickup and invalid requests. Run `Test-PlankTown-Motion.py` in that PIE session to check movement and rifle pickup/fire/reload. Stop PIE before running `Test-PlankTown-Network.py`, which starts two-player PIE and checks replicated appearance, client drops and contested pickups. Reports and screenshots are written beneath `Artifacts/PlankTownTests`; the checked-in summary is `Resources/PlankTownValidation.json`.

Run `Test-PlankTown-Arms.py` outside Play to check actual shoulder/elbow/wrist motion in idle, jogging, rifle carry, aiming, firing, reloading, and both shoulder stances. It compares limb directions with the animated source, rejects raised idle arms and frozen arm swing, and captures each pose under `Artifacts/ArmFix`.

Run `Test-Mount.py` outside Play for mounting with E, preserved headpieces, saddle alignment, all four animated legs, walking/running, steering, wall collision, obstructed exits, dismounting and mount removal. Stop Play before `Test-Mount-Network.py`, which checks two-player client control, replicated seating, dismounting and competing mount requests. Reports go to `Artifacts/MountTests`; checked-in results are in `Resources/Mount/MokuTheIslandRider/GameplayValidation.json`.

The original template documentation and test scripts remain in `Docs/` and `Scripts/`. Template tests that assume Manny should be run with the visual override cleared in the Game Animation Widget. Source sample notices remain with the Unreal project.
