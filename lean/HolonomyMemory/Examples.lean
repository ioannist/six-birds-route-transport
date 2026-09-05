import HolonomyMemory.Asymmetry
import HolonomyMemory.Witnesses

namespace HolonomyMemory

/-- A two-interface, two-history model. `false` observes nothing; `true` reads the bit.
All Boolean maps are continuations, so identity and composition are available. -/
def bitCore : RouteTransportCore where
  Interface := Bool
  History := fun _ => Bool
  Continuation := fun _ _ => Bool → Bool
  Event := fun _ => Unit
  Observation := Bool
  idCont := id
  compose := fun f g => g ∘ f
  push := fun h f => f h
  observe := fun {i} h _ => i && h
  push_id := fun _ => rfl
  push_compose := fun _ _ _ => rfl

theorem bitCore_witness : Nonempty (PredictiveWitness bitCore false) := by
  refine ⟨⟨false, true, ?_, ?_⟩⟩
  · intro e
    rfl
  · intro hEq
    have h := hEq (j := true) id ()
    change false = true at h
    cases h

theorem bitCore_swap_compatible :
    CurrentCompatible bitCore (i := false) (j := false) Bool.not := by
  intro h h' _ e
  rfl

theorem bitCore_loop_asymmetry :
    LoopAsymmetry bitCore false Bool.not bitCore_swap_compatible := by
  constructor
  · intro q
    induction q using Quotient.ind with
    | _ h =>
      apply Quotient.sound
      intro e
      rfl
  · refine ⟨Quotient.mk (PredictiveSetoid bitCore false) false, ?_⟩
    intro hEq
    have h : FuturePredictiveEquiv bitCore (i := false) true false :=
      Quotient.exact hEq
    have hBad := h (j := true) id ()
    change true = false at hBad
    cases hBad

/-- Reading the bit cannot descend to the uninformative current quotient. -/
theorem bitCore_read_not_compatible :
    ¬ CurrentCompatible bitCore (i := false) (j := true) id := by
  intro hCompat
  have hSame : CurrentEventEquiv bitCore (i := false) false true := by
    intro e
    rfl
  have hBad := hCompat hSame ()
  change false = true at hBad
  cases hBad

end HolonomyMemory
