import HolonomyMemory.Transport

namespace HolonomyMemory

abbrev Loop
    (T : RouteTransportCore) (i : T.Interface) :=
  T.Continuation i i

def predictiveLoopAction
    (T : RouteTransportCore) {i : T.Interface}
    (ℓ : Loop T i) :
    PredictiveQuotient T i → PredictiveQuotient T i :=
  predictiveTransport T ℓ

def currentLoopAction
    (T : RouteTransportCore) {i : T.Interface}
    (ℓ : Loop T i) :
    CurrentCompatible T ℓ →
    CurrentQuotient T i → CurrentQuotient T i :=
  currentTransport T ℓ

@[simp] theorem predictiveLoopAction_mk
    (T : RouteTransportCore) {i : T.Interface}
    (ℓ : Loop T i) (h : T.History i) :
    predictiveLoopAction T ℓ (Quotient.mk (PredictiveSetoid T i) h) =
      Quotient.mk (PredictiveSetoid T i) (T.push h ℓ) := by
  rfl

@[simp] theorem currentLoopAction_mk
    (T : RouteTransportCore) {i : T.Interface}
    (ℓ : Loop T i) (hCompat : CurrentCompatible T ℓ) (h : T.History i) :
    currentLoopAction T ℓ hCompat (Quotient.mk (CurrentSetoid T i) h) =
      Quotient.mk (CurrentSetoid T i) (T.push h ℓ) := by
  rfl

theorem predictiveToCurrent_commutes_with_loopAction
    (T : RouteTransportCore)
    {i : T.Interface}
    (ℓ : Loop T i)
    (hCompat : CurrentCompatible T ℓ)
    (q : PredictiveQuotient T i) :
    currentLoopAction T ℓ hCompat (predictiveToCurrent T q) =
      predictiveToCurrent T (predictiveLoopAction T ℓ q) := by
  exact predictiveToCurrent_commutes_with_transport T ℓ hCompat q

end HolonomyMemory
