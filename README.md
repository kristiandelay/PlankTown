# PlankTown

Unreal Engine 5.8 project based on the Lyra/GASP template, with the Jungle Totem Scout player and four customizable headpieces.

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

## Art sources

`Resources/Player/JungleTotemScout/` contains the untouched normalized `Source/`, editable Auto-Rig Pro `.blend`, game-ready `Export/`, and rig validation report. The supplied character has four digits per hand, all rigged and weighted. ARP uses thumb/middle/ring/pinky names for its four-digit preset. The exported body has 90,000 triangles and at most four influences per vertex.

Each `Resources/Headpieces/<Name>/` folder contains the same source/scene/export separation. Headpiece exports have about 16,000 triangles each. ZIP bytes remain unchanged; `SourceManifest.json` records the original delivery names, source IDs and hashes. Texture names use `_BaseColor`, `_Normal`, `_Metallic`, and `_Roughness`.

Preparation scripts require Blender 5.2 and the installed Auto-Rig Pro add-on. `Fit-PlayerAutoRig.py -- JungleTotemScout` runs in Blender with a viewport; skinning, headpiece preparation, and `Validate-PlayerRig.py` run in background mode. `Import-PlankTownAssets.py` runs inside Unreal and rebuilds the imported assets from the prepared exports.

## Validation

Build with `Scripts/Build-Editor.ps1`. For editor automation, open with `Scripts/Open-Traversal.ps1 -Automation`, then use `python Scripts/Send-Editor.py Scripts/Test-PlankTown.py`. The test starts PIE and exercises the default visual, all four pickups, customization, swaps, physics drops, re-pickup and invalid requests. Run `Test-PlankTown-Motion.py` in that PIE session to check movement and rifle pickup/fire/reload. Stop PIE before running `Test-PlankTown-Network.py`, which starts two-player PIE and checks replicated appearance, client drops and contested pickups. Reports and screenshots are written beneath `Artifacts/PlankTownTests`; the checked-in summary is `Resources/PlankTownValidation.json`.

The original template documentation and test scripts remain in `Docs/` and `Scripts/`. Template tests that assume Manny should be run with the visual override cleared in the Game Animation Widget. Source sample notices remain with the Unreal project.
