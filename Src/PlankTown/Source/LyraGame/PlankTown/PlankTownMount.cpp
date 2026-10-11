#include "PlankTownMount.h"
#include "Baseline/BaselineEquipment.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Crusader/CRTraversalCharacter.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Net/UnrealNetwork.h"

APlankTownMount::APlankTownMount()
{
    PrimaryActorTick.bCanEverTick = true;
    bReplicates = true;
    SetReplicateMovement(true);
    SetNetUpdateFrequency(30.f);
    DisplayName = FText::FromString(TEXT("Moku"));
    GetCapsuleComponent()->InitCapsuleSize(75.f, 88.f);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Camera,ECR_Ignore);
    GetMesh()->SetRelativeLocation(FVector(0,0,-88));
    GetMesh()->SetRelativeRotation(FRotator(0,-90,0));
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    GetMesh()->SetCollisionResponseToChannel(ECC_Camera,ECR_Ignore);
    GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    auto* Move = GetCharacterMovement();
    Move->bRunPhysicsWithNoController = true;
    Move->bOrientRotationToMovement = true;
    Move->RotationRate = FRotator(0,180,0);
    Move->MaxWalkSpeed = WalkSpeed;
    Move->MaxAcceleration = 700.f;
    Move->BrakingDecelerationWalking = 900.f;
    Move->MaxStepHeight = 38.f;
    Move->SetWalkableFloorAngle(42.f);
    bUseControllerRotationYaw = false;
}

void APlankTownMount::SetRideInput(const FVector2D& Input, float Yaw, bool bSprint)
{
    RideInput = Input.GetClampedToMaxSize(1.f);
    RideYaw = FRotator::NormalizeAxis(Yaw);
    bRunRequested = bSprint;
    LastInputTime = GetWorld()->GetTimeSeconds();
}

void APlankTownMount::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!HasAuthority()) return;
    if (!IsValid(Rider) || !Rider->Riding || Rider->Riding->MountedMount != this)
    {
        Rider = nullptr;
        RideInput = FVector2D::ZeroVector;
    }
    if (GetWorld()->GetTimeSeconds()-LastInputTime > .35) RideInput = FVector2D::ZeroVector;
    GetCharacterMovement()->MaxWalkSpeed = bRunRequested && Rider ? RunSpeed : WalkSpeed;
    const FRotationMatrix Heading(FRotator(0,RideYaw,0));
    AddMovementInput(Heading.GetUnitAxis(EAxis::X),RideInput.Y,true);
    AddMovementInput(Heading.GetUnitAxis(EAxis::Y),RideInput.X,true);
}

void APlankTownMount::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Reason==EEndPlayReason::Destroyed && HasAuthority() && IsValid(Rider) && Rider->Riding) Rider->Riding->MountRemoved();
    Super::EndPlay(Reason);
}

void APlankTownMount::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ThisClass,Rider);
}

void UPlankTownMountAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
    Super::NativeUpdateAnimation(DeltaSeconds);
    const auto* Pawn = TryGetPawnOwner();
    Speed = FMath::FInterpTo(Speed,Pawn ? Pawn->GetVelocity().Size2D() : 0.f,DeltaSeconds,8.f);
}

UPlankTownRiderComponent::UPlankTownRiderComponent()
{
    SetIsReplicatedByDefault(true);
    PrimaryComponentTick.bCanEverTick = true;
}

bool UPlankTownRiderComponent::CanMount(const APlankTownMount* Mount) const
{
    const auto* Pawn = Cast<ACRTraversalCharacter>(GetOwner());
    if (!Pawn || !Pawn->GetController() || MountedMount || !IsValid(Mount) || Mount->Rider
        || Mount->IsActorBeingDestroyed() || !Pawn->CanUseMovementActions()
        || Pawn->BaselineEquipment->AreHandsBusy() || !Pawn->GetCharacterMovement()->IsMovingOnGround()
        || !Mount->GetCharacterMovement()->IsMovingOnGround()
        || FVector::DistSquared(Pawn->GetActorLocation(),Mount->GetActorLocation()) > FMath::Square(MountDistance)) return false;
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(MountReach),false,Pawn);
    Params.AddIgnoredActor(Mount);
    return !GetWorld()->LineTraceSingleByChannel(Hit,Pawn->GetPawnViewLocation(),
        Mount->GetActorLocation(),ECC_Visibility,Params);
}

APlankTownMount* UPlankTownRiderComponent::FindMount() const
{
    const auto* Pawn = Cast<APawn>(GetOwner());
    if (!Pawn || MountedMount) return nullptr;
    APlankTownMount* Best = nullptr;
    float BestScore = UE_BIG_NUMBER;
    const FVector Forward = Pawn->GetControlRotation().Vector().GetSafeNormal2D();
    for (TActorIterator<APlankTownMount> It(GetWorld()); It; ++It)
    {
        if (!CanMount(*It)) continue;
        const FVector Delta = It->GetActorLocation()-Pawn->GetActorLocation();
        const float Dot = FVector::DotProduct(Forward,Delta.GetSafeNormal2D());
        if (Dot < .1f) continue;
        const float Score = Delta.Size()+(1.f-Dot)*150.f;
        if (Score<BestScore) { Best=*It; BestScore=Score; }
    }
    return Best;
}

void UPlankTownRiderComponent::Interact()
{
    if (MountedMount) ServerDismount();
    else if (auto* Mount=FindMount()) ServerMount(Mount);
}

void UPlankTownRiderComponent::ServerMount_Implementation(APlankTownMount* Mount)
{
    if (!CanMount(Mount)) return;
    auto* Pawn=CastChecked<ACRTraversalCharacter>(GetOwner());
    Mount->Rider=Pawn;
    MountedMount=Mount;
    Pawn->UnCrouch();
    Pawn->GetCharacterMovement()->StopMovementImmediately();
    Mount->SetRideInput(FVector2D::ZeroVector,Mount->GetActorRotation().Yaw,false);
    ApplyMountedState();
    LastInteractionResult=TEXT("Mounted Moku");
    Mount->ForceNetUpdate();Pawn->ForceNetUpdate();
}

bool UPlankTownRiderComponent::FindDismountLocation(FVector& Location) const
{
    const auto* Pawn=CastChecked<ACRTraversalCharacter>(GetOwner());
    if (!MountedMount) return false;
    const auto* Capsule=Pawn->GetCapsuleComponent();
    const float Radius=Capsule->GetScaledCapsuleRadius(),Half=Capsule->GetScaledCapsuleHalfHeight();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(MountDismount),false,Pawn);
    Params.AddIgnoredActor(MountedMount);
    for (float Yaw : {90.f,-90.f,135.f,-135.f,180.f,0.f})
    {
        const FVector Direction=MountedMount->GetActorForwardVector().RotateAngleAxis(Yaw,FVector::UpVector);
        const FVector Test=MountedMount->GetActorLocation()+Direction*185.f;
        FHitResult Floor;
        if (!GetWorld()->LineTraceSingleByChannel(Floor,Test+FVector(0,0,120),Test-FVector(0,0,250),ECC_Visibility,Params)
            || Floor.ImpactNormal.Z < .7f) continue;
        const FVector Candidate=Floor.ImpactPoint+FVector(0,0,Half+3.f);
        if (!GetWorld()->OverlapBlockingTestByChannel(Candidate,FQuat::Identity,ECC_Pawn,
            FCollisionShape::MakeCapsule(Radius,Half),Params)) { Location=Candidate;return true; }
    }
    return false;
}

void UPlankTownRiderComponent::Dismount(bool bForce)
{
    if (!GetOwner()->HasAuthority() || !MountedMount) return;
    auto* Pawn=CastChecked<ACRTraversalCharacter>(GetOwner());
    FVector Location;
    if (!FindDismountLocation(Location))
    {
        if (!bForce) { LastInteractionResult=TEXT("Move to clear ground to dismount");return; }
        Location=Pawn->GetActorLocation()+FVector(0,0,100);
    }
    auto* Mount=MountedMount.Get();
    Mount->SetRideInput(FVector2D::ZeroVector,Mount->GetActorRotation().Yaw,false);
    Mount->Rider=nullptr;
    MountedMount=nullptr;
    ApplyMountedState();
    Pawn->SetActorLocation(Location,false,nullptr,ETeleportType::TeleportPhysics);
    Pawn->GetCharacterMovement()->StopMovementImmediately();
    Mount->ForceNetUpdate();Pawn->ForceNetUpdate();
    LastInteractionResult=TEXT("Dismounted");
}

void UPlankTownRiderComponent::ServerDismount_Implementation() { Dismount(false); }
void UPlankTownRiderComponent::HandleDeath() { Dismount(true); }
void UPlankTownRiderComponent::MountRemoved() { Dismount(true); }

void UPlankTownRiderComponent::ApplyMountedState()
{
    auto* Pawn=Cast<ACRTraversalCharacter>(GetOwner());
    if (!Pawn) return;
    if (MountedMount)
    {
        if (AppliedMount==MountedMount) return;
        Pawn->GetCharacterMovement()->DisableMovement();
        Pawn->GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Pawn->AttachToComponent(MountedMount->GetMesh(),FAttachmentTransformRules::SnapToTargetNotIncludingScale,MountedMount->SeatSocket);
        Pawn->SetActorRelativeLocation(FVector(0,0,MountedMount->RiderHeightOffset));
        // The mesh points along local +Y; its seat socket is authored actor-forward.
        Pawn->SetActorRelativeRotation(FRotator::ZeroRotator);
        if (Pawn->HasAuthority()) Pawn->SetReplicateMovement(false);
        AppliedMount=MountedMount;
        bAppliedMounted=true;
    }
    else if (bAppliedMounted)
    {
        Pawn->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
        Pawn->GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Pawn->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
        if (Pawn->HasAuthority()) Pawn->SetReplicateMovement(true);
        AppliedMount.Reset();
        bAppliedMounted=false;
    }
    UpdateRidingRetarget();
    LocalInput=FVector2D::ZeroVector;bLocalSprint=false;SendInputIn=0.f;
}

void UPlankTownRiderComponent::OnRep_MountedMount() { ApplyMountedState(); }

void UPlankTownRiderComponent::UpdateRidingRetarget()
{
    const auto* Pawn=Cast<ACRTraversalCharacter>(GetOwner());
    auto* Visual=Pawn ? Pawn->BaselineEquipment->GetPresentationMesh() : nullptr;
    if (!Visual || Visual->ComponentTags.IsEmpty()) return;
    const FName WalkingTag(TEXT("RTG_Manny_to_JungleTotemScout"));
    const FName RidingTag(TEXT("RTG_Manny_to_JungleTotemScout_Riding"));
    const FName Desired=MountedMount ? RidingTag : WalkingTag;
    if ((Visual->ComponentTags[0]==WalkingTag || Visual->ComponentTags[0]==RidingTag) && Visual->ComponentTags[0]!=Desired)
    {
        Visual->ComponentTags[0]=Desired;
        Visual->ReinitializeAnimNodes();
    }
}

void UPlankTownRiderComponent::ServerRideInput_Implementation(FVector2D Input,float Yaw,bool bSprint)
{
    if (!MountedMount || MountedMount->Rider!=GetOwner() || !FMath::IsFinite(Input.X)
        || !FMath::IsFinite(Input.Y) || !FMath::IsFinite(Yaw)) return;
    MountedMount->SetRideInput(Input,Yaw,bSprint);
}

void UPlankTownRiderComponent::InputMove(const FInputActionValue& Value) { LocalInput=Value.Get<FVector2D>(); }
void UPlankTownRiderComponent::InputMoveReleased(const FInputActionValue&) { LocalInput=FVector2D::ZeroVector; }
void UPlankTownRiderComponent::InputSprint(const FInputActionValue&) { bLocalSprint=true; }
void UPlankTownRiderComponent::InputSprintReleased(const FInputActionValue&) { bLocalSprint=false; }

void UPlankTownRiderComponent::TickComponent(float DeltaTime,ELevelTick TickType,FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime,TickType,ThisTickFunction);
    if (!MountedMount) return;
    ApplyMountedState();
    UpdateRidingRetarget();
    const auto* Pawn=Cast<APawn>(GetOwner());
    if (!Pawn || !Pawn->IsLocallyControlled()) return;
    SendInputIn-=DeltaTime;
    if (SendInputIn<=0.f)
    {
        ServerRideInput(LocalInput,Pawn->GetControlRotation().Yaw,bLocalSprint);
        SendInputIn=.05f;
    }
}

void UPlankTownRiderComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (GetOwner()->HasAuthority() && IsValid(MountedMount))
    {
        MountedMount->Rider=nullptr;
        MountedMount->SetRideInput(FVector2D::ZeroVector,0,false);
        MountedMount->ForceNetUpdate();
    }
    Super::EndPlay(Reason);
}

void UPlankTownRiderComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ThisClass,MountedMount);
    DOREPLIFETIME_CONDITION(ThisClass,LastInteractionResult,COND_OwnerOnly);
}
