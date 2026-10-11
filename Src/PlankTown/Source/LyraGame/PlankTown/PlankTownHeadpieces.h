#pragma once

#include "Components/ActorComponent.h"
#include "Engine/DataAsset.h"
#include "GameFramework/Actor.h"
#include "PlankTownHeadpieces.generated.h"

class UBoxComponent;
class UStaticMesh;
class UStaticMeshComponent;
class USkeletalMeshComponent;

/** Author new headpieces by creating one definition and a pickup using it. */
UCLASS(BlueprintType)
class LYRAGAME_API UPlankTownHeadpieceDefinition : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FText DisplayName;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UStaticMesh> Mesh;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FName SocketName = TEXT("HeadpieceSocket");
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FTransform WearTransform;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FLinearColor> Colors = {
        FLinearColor::White, FLinearColor(.35f,.65f,1.f), FLinearColor(1.f,.4f,.3f), FLinearColor(.5f,1.f,.4f)};
};

/** One replicated value keeps definition, tint and size consistent on observers. */
USTRUCT(BlueprintType)
struct FPlankTownHeadpieceState
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UPlankTownHeadpieceDefinition> Definition;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) int32 ColorIndex = 0;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="0.8", ClampMax="1.2")) float Size = 1.f;
};

UCLASS(Blueprintable)
class LYRAGAME_API APlankTownHeadpiecePickup : public AActor
{
    GENERATED_BODY()
public:
    APlankTownHeadpiecePickup();
    UPROPERTY(EditAnywhere, BlueprintReadOnly, ReplicatedUsing=OnRep_State) FPlankTownHeadpieceState State;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<UBoxComponent> Collision;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<UStaticMeshComponent> DisplayMesh;
    bool bClaimed = false;
    void LaunchDrop(const FVector& Velocity);
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void BeginPlay() override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
private:
    UFUNCTION() void OnRep_State();
};

UCLASS(BlueprintType, meta=(BlueprintSpawnableComponent))
class LYRAGAME_API UPlankTownHeadpieceComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UPlankTownHeadpieceComponent();
    UPROPERTY(BlueprintReadOnly, ReplicatedUsing=OnRep_Equipped) FPlankTownHeadpieceState Equipped;
    UPROPERTY(BlueprintReadOnly, Transient) TObjectPtr<UStaticMeshComponent> WornMesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float PickupDistance = 220.f;
    UFUNCTION(BlueprintPure) APlankTownHeadpiecePickup* FindPickup() const;
    UFUNCTION(Server, Reliable, BlueprintCallable) void ServerPickup(APlankTownHeadpiecePickup* Pickup);
    UFUNCTION(Server, Reliable, BlueprintCallable) void DropHeadpiece();
    UFUNCTION(Server, Reliable, BlueprintCallable) void CustomizeHeadpiece(int32 ColorIndex, float Size);
    UFUNCTION(BlueprintCallable) void CycleColor();
    UFUNCTION(BlueprintCallable) void IncreaseSize();
    UFUNCTION(BlueprintCallable) void DecreaseSize();
    void HandleDeath();
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
private:
    bool CanUse() const;
    bool CanReach(const APlankTownHeadpiecePickup* Pickup) const;
    APlankTownHeadpiecePickup* SpawnDropped(const FPlankTownHeadpieceState& State, const AActor* IgnoredActor = nullptr);
    void RefreshAttachment();
    UFUNCTION() void OnRep_Equipped();
    TWeakObjectPtr<USkeletalMeshComponent> AttachedMesh;
};
