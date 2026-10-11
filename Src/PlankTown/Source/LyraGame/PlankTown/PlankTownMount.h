#pragma once

#include "Animation/AnimInstance.h"
#include "Components/ActorComponent.h"
#include "GameFramework/Character.h"
#include "InputActionValue.h"
#include "PlankTownMount.generated.h"

class ACRTraversalCharacter;
class UAnimSequence;

/** Replicated quadruped. The rider retains possession, inventory and Lyra abilities. */
UCLASS(Blueprintable)
class LYRAGAME_API APlankTownMount : public ACharacter
{
    GENERATED_BODY()
public:
    APlankTownMount();
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Mount") FText DisplayName;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Mount") float WalkSpeed = 240.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Mount") float RunSpeed = 520.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Mount") FName SeatSocket = TEXT("RiderSocket");
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Mount") float RiderHeightOffset = 35.f;
    UPROPERTY(BlueprintReadOnly, Replicated, Category="Mount") TObjectPtr<ACRTraversalCharacter> Rider;
    void SetRideInput(const FVector2D& Input, float Yaw, bool bSprint);
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
private:
    FVector2D RideInput = FVector2D::ZeroVector;
    float RideYaw = 0.f;
    bool bRunRequested = false;
    double LastInputTime = -1.0;
};

UCLASS(Transient, Blueprintable)
class LYRAGAME_API UPlankTownMountAnimInstance : public UAnimInstance
{
    GENERATED_BODY()
public:
    UPROPERTY(BlueprintReadOnly, Transient, Category="Mount") float Speed = 0.f;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Mount") float AirWeight = 0.f;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Mount") float RisingWeight = 0.f;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Mount") float LandingWeight = 0.f;
    virtual void NativeUpdateAnimation(float DeltaSeconds) override;
private:
    bool bWasFalling = false;
    float LandingTimeRemaining = 0.f;
};

UCLASS(BlueprintType, meta=(BlueprintSpawnableComponent))
class LYRAGAME_API UPlankTownRiderComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UPlankTownRiderComponent();
    UPROPERTY(BlueprintReadOnly, ReplicatedUsing=OnRep_MountedMount, Category="Mount") TObjectPtr<APlankTownMount> MountedMount;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Mount") float MountDistance = 250.f;
    UPROPERTY(BlueprintReadOnly, Replicated, Category="Mount") FString LastInteractionResult;
    UFUNCTION(BlueprintPure, Category="Mount") bool IsMounted() const { return MountedMount != nullptr; }
    UFUNCTION(BlueprintPure, Category="Mount") APlankTownMount* FindMount() const;
    UFUNCTION(BlueprintCallable, Category="Mount") void Interact();
    UFUNCTION(Server, Reliable, BlueprintCallable, Category="Mount") void ServerMount(APlankTownMount* Mount);
    UFUNCTION(Server, Reliable, BlueprintCallable, Category="Mount") void ServerDismount();
    UFUNCTION(Server, Reliable, BlueprintCallable, Category="Mount") void ServerJump();
    UFUNCTION(Server, Unreliable, BlueprintCallable, Category="Mount") void ServerRideInput(FVector2D Input, float Yaw, bool bSprint);
    void InputMove(const FInputActionValue& Value);
    void InputMoveReleased(const FInputActionValue& Value);
    void InputSprint(const FInputActionValue& Value);
    void InputSprintReleased(const FInputActionValue& Value);
    void InputJump(const FInputActionValue& Value);
    void HandleDeath();
    void MountRemoved();
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
private:
    bool CanMount(const APlankTownMount* Mount) const;
    bool FindDismountLocation(FVector& Location) const;
    void Dismount(bool bForce);
    UFUNCTION() void OnRep_MountedMount();
    void ApplyMountedState();
    void UpdateRidingRetarget();
    TWeakObjectPtr<APlankTownMount> AppliedMount;
    bool bAppliedMounted = false;
    FVector2D LocalInput = FVector2D::ZeroVector;
    bool bLocalSprint = false;
    float SendInputIn = 0.f;
};
