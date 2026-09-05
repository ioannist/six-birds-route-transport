import HolonomyMemory.Transport

namespace HolonomyMemory

structure PredictiveWitness
    (T : RouteTransportCore) (i : T.Interface) where
  h : T.History i
  h' : T.History i
  sameCurrent : CurrentEventEquiv T h h'
  notSameFuture : ¬ FuturePredictiveEquiv T h h'

def StrictRefinement
    (T : RouteTransportCore) (i : T.Interface) : Prop :=
  ∃ q q' : PredictiveQuotient T i,
    q ≠ q' ∧ predictiveToCurrent T q = predictiveToCurrent T q'

theorem PredictiveWitness.distinct_predictive_classes_same_current_class
    (T : RouteTransportCore) {i : T.Interface}
    (w : PredictiveWitness T i) :
    let q : PredictiveQuotient T i := Quotient.mk (PredictiveSetoid T i) w.h
    let q' : PredictiveQuotient T i := Quotient.mk (PredictiveSetoid T i) w.h'
    q ≠ q' ∧ predictiveToCurrent T q = predictiveToCurrent T q' := by
  dsimp
  refine ⟨?_, ?_⟩
  · intro hEq
    apply w.notSameFuture
    exact Quotient.exact hEq
  · apply Quotient.sound
    exact w.sameCurrent

theorem PredictiveWitness.induces_strictRefinement
    (T : RouteTransportCore) {i : T.Interface}
    (w : PredictiveWitness T i) :
    StrictRefinement T i := by
  refine ⟨Quotient.mk (PredictiveSetoid T i) w.h, Quotient.mk (PredictiveSetoid T i) w.h', ?_, ?_⟩
  · intro hEq
    apply w.notSameFuture
    exact Quotient.exact hEq
  · apply Quotient.sound
    exact w.sameCurrent

theorem strictRefinement_implies_predictiveWitness
    (T : RouteTransportCore) {i : T.Interface}
    (hStrict : StrictRefinement T i) :
    Nonempty (PredictiveWitness T i) := by
  rcases hStrict with ⟨q, q', hNe, hSameCurrent⟩
  refine Quotient.inductionOn₂ q q' ?_ hSameCurrent hNe
  intro h h' hSameCurrent hNe
  have hCurrent :
      CurrentEventEquiv T h h' := by
    exact Quotient.exact (by simpa using hSameCurrent)
  have hNotFuture :
      ¬ FuturePredictiveEquiv T h h' := by
    intro hFuture
    apply hNe
    exact Quotient.sound hFuture
  exact ⟨⟨h, h', hCurrent, hNotFuture⟩⟩

theorem strictRefinement_iff_nonempty_predictiveWitness
    (T : RouteTransportCore) (i : T.Interface) :
    StrictRefinement T i ↔ Nonempty (PredictiveWitness T i) := by
  constructor
  · exact strictRefinement_implies_predictiveWitness T
  · intro hWitness
    rcases hWitness with ⟨w⟩
    exact w.induces_strictRefinement T

end HolonomyMemory
