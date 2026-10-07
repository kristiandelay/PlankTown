# Lyra GASP 5.8 Template

A reusable Unreal Engine **5.8.3** project combining Lyra with the Game Animation Sample's CMC locomotion and traversal. Start in `/Game/Maps/L_TraversalGym`.

## Get started

Install Unreal Engine 5.8.3, the Visual Studio C++ tools required by Unreal, Git, and Git LFS. The project includes approximately 8 GB of assets stored in Git LFS.

```powershell
git lfs install
git clone git@github.com:kristiandelay/LyraGasp5.8Template.git
cd LyraGasp5.8Template
git lfs pull
powershell -ExecutionPolicy Bypass -File Scripts/Build-Editor.ps1
```

Open `Open-Traversal.cmd`, then press Play. If Unreal is installed elsewhere, pass `-EngineRoot` to the build/open PowerShell scripts.

The Unreal project is `src/LyraStarterGame.uproject`. Native Lyra module names and existing asset paths are retained so serialized references remain valid.

## Included

- Motion-matched movement, sliding, jumping, vaulting, mantling and climbing.
- Lyra inventory, rifle/pistol/shotgun pickups, firing, reloading and combat death/respawn.
- Aim offsets, shooting while sliding, and shoulder switching with mirrored weapon poses and actual hand transfer.
- Physics Control, passive ragdolls, pose-matched recovery and paired shove/tackle/takedown interactions.
- Six character visual overrides through the Game Animation Widget, preserving weapon animations and reloads.
- Standalone and two-player PIE validation scripts, with recorded validation manifests under `resources/`.

The source samples' original documentation and notices remain in `src/`. Build outputs, caches and local editor data are excluded from version control.

## Controls and maintenance

See [BaselineTemplate.txt](docs/BaselineTemplate.txt) for controls, authoring order and tests, and [TraversalSetup.txt](docs/TraversalSetup.txt) for integration details.

Use **E** to pick up a weapon, **RMB** to aim, **LMB** to fire, **R** to reload and **Q** to switch shoulder/weapon hand. The gym includes training partners and traversal obstacles.

Validation manifests describe the checks performed on the source baseline. Detailed `Artifacts/` logs and screenshots are local outputs; rerunning the scripts creates new reports in your copy. Packaged builds and networking under latency/loss need project-specific validation.

## Create an independent project

Use the clone/export workflow for this LFS-backed baseline. GitHub's built-in
"Use this template" feature [does not support repositories containing Git LFS files](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository).

```powershell
python Scripts/New-BaselineProject.py C:/Development/Game/MyNextProject --name "My Next Project"
```

The exporter requires a new or empty destination, generates a fresh project ID, and copies the source, assets, maintenance scripts and validation records without Git history or generated files. Initialize a new Git repository and install Git LFS in that copy before its first commit.
