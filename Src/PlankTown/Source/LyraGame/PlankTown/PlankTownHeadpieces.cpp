#include "PlankTownHeadpieces.h"
#include "Baseline/BaselineEquipment.h"
#include "Character/LyraHealthComponent.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Net/UnrealNetwork.h"

namespace
{
void ApplyAppearance(UStaticMeshComponent* Mesh, const FPlankTownHeadpieceState& State)
{
    Mesh->SetStaticMesh(State.Definition ? State.Definition->Mesh : nullptr);
    if (!State.Definition) return;
    const FLinearColor Color = State.Definition->Colors.IsValidIndex(State.ColorIndex)
        ? State.Definition->Colors[State.ColorIndex] : FLinearColor::White;
    for (int32 Index = 0; Index < Mesh->GetNumMaterials(); ++Index)
        if (auto* Material = Mesh->CreateAndSetMaterialInstanceDynamic(Index))
            Material->SetVectorParameterValue(TEXT("Tint"), Color);
}
}

APlankTownHeadpiecePickup::APlankTownHeadpiecePickup()
{
    bReplicates = true;
    SetReplicateMovement(true);
    Collision = CreateDefaultSubobject<UBoxComponent>(TEXT("Collision"));
    SetRootComponent(Collision);
    Collision->InitBoxExtent(FVector(45,45,25));
    Collision->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Collision->SetCollisionObjectType(ECC_WorldDynamic);
    Collision->SetCollisionResponseToAllChannels(ECR_Ignore);
    Collision->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    Collision->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
    DisplayMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("HeadpieceMesh"));
    DisplayMesh->SetupAttachment(Collision);
    DisplayMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void APlankTownHeadpiecePickup::OnConstruction(const FTransform& Transform) { Super::OnConstruction(Transform); OnRep_State(); }
void APlankTownHeadpiecePickup::BeginPlay() { Super::BeginPlay(); OnRep_State(); }

void APlankTownHeadpiecePickup::OnRep_State()
{
    ApplyAppearance(DisplayMesh, State);
    DisplayMesh->SetRelativeScale3D(FVector(State.Size));
    if (State.Definition && State.Definition->Mesh)
    {
        const FBoxSphereBounds Bounds = State.Definition->Mesh->GetBounds();
        DisplayMesh->SetRelativeLocation(-Bounds.Origin * State.Size);
        Collision->SetBoxExtent(Bounds.BoxExtent * State.Size);
    }
}

void APlankTownHeadpiecePickup::LaunchDrop(const FVector& Velocity)
{
    if (!HasAuthority()) return;
    Collision->SetSimulatePhysics(true);
    Collision->SetPhysicsLinearVelocity(Velocity);
    Collision->SetLinearDamping(.8f);
    Collision->SetAngularDamping(2.f);
    ForceNetUpdate();
}

void APlankTownHeadpiecePickup::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ThisClass, State);
}

UPlankTownHeadpieceComponent::UPlankTownHeadpieceComponent()
{
    SetIsReplicatedByDefault(true);
    PrimaryComponentTick.bCanEverTick = true;
}

void UPlankTownHeadpieceComponent::BeginPlay()
{
    Super::BeginPlay();
    WornMesh = NewObject<UStaticMeshComponent>(GetOwner(), TEXT("WornHeadpiece"));
    WornMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    WornMesh->SetCanEverAffectNavigation(false);
    WornMesh->SetupAttachment(GetOwner()->GetRootComponent());
    WornMesh->RegisterComponent();
    OnRep_Equipped();
}

bool UPlankTownHeadpieceComponent::CanUse() const
{
    const auto* Pawn = Cast<APawn>(GetOwner());
    if (!Pawn || !Pawn->GetController()) return false;
    const auto* Equipment = GetOwner()->FindComponentByClass<UBaselineEquipmentComponent>();
    return Equipment && !Equipment->AreHandsBusy();
}

bool UPlankTownHeadpieceComponent::CanReach(const APlankTownHeadpiecePickup* Pickup) const
{
    const auto* Pawn = Cast<APawn>(GetOwner());
    if (!CanUse() || !IsValid(Pickup) || Pickup->IsActorBeingDestroyed() || Pickup->bClaimed
        || !Pickup->State.Definition || !Pickup->State.Definition->Mesh
        || FVector::DistSquared(Pawn->GetActorLocation(), Pickup->GetActorLocation()) > FMath::Square(PickupDistance)) return false;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(HeadpiecePickup), false, Pawn);
    Params.AddIgnoredActor(Pickup);
    FHitResult Hit;
    return !GetWorld()->LineTraceSingleByChannel(Hit, Pawn->GetPawnViewLocation(), Pickup->GetActorLocation(), ECC_Visibility, Params);
}

APlankTownHeadpiecePickup* UPlankTownHeadpieceComponent::FindPickup() const
{
    const auto* Pawn = Cast<APawn>(GetOwner());
    if (!Pawn || !CanUse()) return nullptr;
    const FVector Forward = Pawn->GetControlRotation().Vector();
    APlankTownHeadpiecePickup* Best = nullptr;
    float BestScore = UE_BIG_NUMBER;
    for (TActorIterator<APlankTownHeadpiecePickup> It(GetWorld()); It; ++It)
    {
        if (!CanReach(*It)) continue;
        const FVector Delta = It->GetActorLocation() - Pawn->GetPawnViewLocation();
        const float Dot = FVector::DotProduct(Forward, Delta.GetSafeNormal());
        if (Dot < .1f) continue;
        const float Score = Delta.Size() + (1.f - Dot) * 150.f;
        if (Score < BestScore) { Best = *It; BestScore = Score; }
    }
    return Best;
}

APlankTownHeadpiecePickup* UPlankTownHeadpieceComponent::SpawnDropped(const FPlankTownHeadpieceState& State, const AActor* IgnoredActor)
{
    if (!GetOwner()->HasAuthority() || !State.Definition || !State.Definition->Mesh) return nullptr;
    const auto* Pawn = CastChecked<APawn>(GetOwner());
    const FVector Forward = Pawn->GetControlRotation().Vector().GetSafeNormal2D();
    const FVector Start = Pawn->GetPawnViewLocation();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(HeadpieceDrop), false, Pawn);
    if (IgnoredActor) Params.AddIgnoredActor(IgnoredActor);
    const FVector Extent = State.Definition->Mesh->GetBounds().BoxExtent * State.Size;
    FVector Location, Direction;
    FQuat Rotation;
    bool bFoundSpace = false;
    // A pile of previously dropped hats must not block every later drop.
    // Sweep several nearby directions and keep the item if none is clear.
    for (float Yaw : {0.f, 60.f, -60.f, 120.f, -120.f, 180.f})
    {
        Direction = Forward.RotateAngleAxis(Yaw, FVector::UpVector);
        Rotation = Direction.Rotation().Quaternion();
        Location = Start + Direction * 145.f;
        FHitResult Hit;
        if (GetWorld()->SweepSingleByChannel(Hit, Start, Location, Rotation, ECC_WorldStatic,
            FCollisionShape::MakeBox(Extent), Params))
        {
            if (Hit.bStartPenetrating) continue;
            Location = Hit.Location + Hit.Normal * 2.f;
        }
        if (!GetWorld()->OverlapBlockingTestByChannel(Location, Rotation, ECC_WorldStatic,
            FCollisionShape::MakeBox(Extent), Params)) { bFoundSpace = true; break; }
    }
    if (!bFoundSpace) return nullptr;
    FTransform Transform(Rotation, Location);
    auto* Pickup = GetWorld()->SpawnActorDeferred<APlankTownHeadpiecePickup>(APlankTownHeadpiecePickup::StaticClass(),
        Transform, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!Pickup) return nullptr;
    Pickup->State = State;
    Pickup->FinishSpawning(Transform);
    Pickup->LaunchDrop(Pawn->GetVelocity() + Direction * 110.f + FVector(0,0,90));
    return Pickup;
}

void UPlankTownHeadpieceComponent::ServerPickup_Implementation(APlankTownHeadpiecePickup* Pickup)
{
    if (!CanReach(Pickup)) return;
    if (Equipped.Definition && !SpawnDropped(Equipped, Pickup)) return;
    Pickup->bClaimed = true;
    Equipped = Pickup->State;
    Pickup->Destroy();
    OnRep_Equipped();
    GetOwner()->ForceNetUpdate();
}

void UPlankTownHeadpieceComponent::DropHeadpiece_Implementation()
{
    if (!CanUse() || !SpawnDropped(Equipped)) return;
    Equipped = FPlankTownHeadpieceState();
    OnRep_Equipped();
    GetOwner()->ForceNetUpdate();
}

void UPlankTownHeadpieceComponent::CustomizeHeadpiece_Implementation(int32 ColorIndex, float Size)
{
    if (!CanUse() || !Equipped.Definition || !Equipped.Definition->Colors.IsValidIndex(ColorIndex)
        || !FMath::IsFinite(Size) || Size < .8f || Size > 1.2f) return;
    Equipped.ColorIndex = ColorIndex;
    Equipped.Size = Size;
    OnRep_Equipped();
    GetOwner()->ForceNetUpdate();
}

void UPlankTownHeadpieceComponent::CycleColor()
{
    if (Equipped.Definition && !Equipped.Definition->Colors.IsEmpty())
        CustomizeHeadpiece((Equipped.ColorIndex + 1) % Equipped.Definition->Colors.Num(), Equipped.Size);
}
void UPlankTownHeadpieceComponent::IncreaseSize() { CustomizeHeadpiece(Equipped.ColorIndex, FMath::Clamp(Equipped.Size + .05f, .8f, 1.2f)); }
void UPlankTownHeadpieceComponent::DecreaseSize() { CustomizeHeadpiece(Equipped.ColorIndex, FMath::Clamp(Equipped.Size - .05f, .8f, 1.2f)); }

void UPlankTownHeadpieceComponent::HandleDeath()
{
    if (!GetOwner()->HasAuthority() || !Equipped.Definition) return;
    if (SpawnDropped(Equipped))
    {
        Equipped = FPlankTownHeadpieceState();
        OnRep_Equipped();
        GetOwner()->ForceNetUpdate();
    }
}

void UPlankTownHeadpieceComponent::OnRep_Equipped()
{
    if (!WornMesh) return;
    // Clear overrides so a new definition never inherits the old hat's material.
    WornMesh->EmptyOverrideMaterials();
    ApplyAppearance(WornMesh, Equipped);
    AttachedMesh.Reset();
    RefreshAttachment();
}

void UPlankTownHeadpieceComponent::RefreshAttachment()
{
    if (!WornMesh || !Equipped.Definition) return;
    const auto* Equipment = GetOwner()->FindComponentByClass<UBaselineEquipmentComponent>();
    auto* Mesh = Equipment ? Equipment->GetPresentationMesh() : nullptr;
    if (!IsValid(Mesh) || AttachedMesh == Mesh) return;
    const FName Socket = Mesh->DoesSocketExist(Equipped.Definition->SocketName) ? Equipped.Definition->SocketName : FName(TEXT("head"));
    if (!Mesh->DoesSocketExist(Socket)) return;
    WornMesh->AttachToComponent(Mesh, FAttachmentTransformRules::SnapToTargetNotIncludingScale, Socket);
    FTransform Transform = Equipped.Definition->WearTransform;
    Transform.SetScale3D(Transform.GetScale3D() * Equipped.Size);
    WornMesh->SetRelativeTransform(Transform);
    AttachedMesh = Mesh;
}

void UPlankTownHeadpieceComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaTime, TickType, TickFunction);
    RefreshAttachment();
}

void UPlankTownHeadpieceComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ThisClass, Equipped);
}
