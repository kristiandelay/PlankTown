"""Configure the scout's UE 5.8 retarget operations after importing its rig."""
import unreal as u


def configure_player_retarget(retarget, rig):
    controller = u.IKRetargeterController.get_controller(retarget)
    target = u.RetargetSourceOrTarget.TARGET
    controller.set_ik_rig(target, rig)
    # Changing the asset's default target does not replace the explicit rig
    # references on operations copied from the Manny retargeter.
    for side in (u.RetargetSourceOrTarget.SOURCE, target):
        controller.assign_ik_rig_to_all_ops(side, controller.get_ik_rig(side))
    for index in range(controller.get_num_retarget_ops()):
        name = controller.get_op_name(index)
        controller.auto_map_chains(u.AutoMapChainType.EXACT, True, name)
        # Auto-generated scout chains name the toe chains "Foot".
        for source, destination in (("LeftToe", "LeftFoot"), ("RightToe", "RightFoot")):
            controller.set_source_chain(source, destination, name)
        operation = controller.get_op_controller(index)
        if isinstance(operation, u.IKRetargetBlendToSourceController):
            settings = operation.get_settings()
            chains = list(settings.chains)
            for chain in chains:
                if str(chain.target_chain_name) in ("LeftArm", "RightArm"):
                    # Preserve the scout's shoulder height and limb proportions.
                    # The animation blueprint still blends to source for authored
                    # traversal contact curves; ordinary arm motion stays scaled.
                    chain.blend_to_source = 0.0
            settings.chains = chains
            operation.set_settings(settings)
    assert all(item == rig for item in controller.get_all_target_ik_rigs())
    for pose in controller.get_retarget_poses(target):
        controller.reset_retarget_pose(pose, [], target)
    controller.auto_align_all_bones(target)
    assert u.EditorAssetLibrary.save_loaded_asset(retarget, only_if_is_dirty=False)


if __name__ == "__main__":
    assert not u.EditorLevelLibrary.get_pie_worlds(False), "Stop Play before configuring the retargeter."
    folder = "/Game/PlankTown/Player/JungleTotemScout/"
    configure_player_retarget(
        u.load_asset(folder + "RTG_Manny_to_JungleTotemScout"),
        u.load_asset(folder + "IK_JungleTotemScout"),
    )
    print("PLANKTOWN_RETARGET_CONFIGURED")
