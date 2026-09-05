import HolonomyMemory.Equivalences

namespace HolonomyMemory

def PredictiveSetoid
    (T : RouteTransportCore) (i : T.Interface) :
    Setoid (T.History i) where
  r := FuturePredictiveEquiv T
  iseqv := ⟨futurePredictiveEquiv_refl T, futurePredictiveEquiv_symm T, futurePredictiveEquiv_trans T⟩

def CurrentSetoid
    (T : RouteTransportCore) (i : T.Interface) :
    Setoid (T.History i) where
  r := CurrentEventEquiv T
  iseqv := ⟨currentEventEquiv_refl T, currentEventEquiv_symm T, currentEventEquiv_trans T⟩

abbrev PredictiveQuotient
    (T : RouteTransportCore) (i : T.Interface) :=
  Quotient (PredictiveSetoid T i)

abbrev CurrentQuotient
    (T : RouteTransportCore) (i : T.Interface) :=
  Quotient (CurrentSetoid T i)

theorem futurePredictiveEquiv_push
    (T : RouteTransportCore)
    {i j : T.Interface}
    (γ : T.Continuation i j)
    {h h' : T.History i}
    (hEq : FuturePredictiveEquiv T h h') :
    FuturePredictiveEquiv T (T.push h γ) (T.push h' γ) := by
  intro k δ e
  simpa [T.push_compose h γ δ, T.push_compose h' γ δ]
    using hEq (T.compose γ δ) e

def predictiveTransport
    (T : RouteTransportCore)
    {i j : T.Interface}
    (γ : T.Continuation i j) :
    PredictiveQuotient T i → PredictiveQuotient T j :=
  Quotient.lift
    (fun h => Quotient.mk (PredictiveSetoid T j) (T.push h γ))
    (fun _ _ hEq => Quotient.sound (futurePredictiveEquiv_push T γ hEq))

@[simp] theorem predictiveTransport_mk
    (T : RouteTransportCore)
    {i j : T.Interface}
    (γ : T.Continuation i j)
    (h : T.History i) :
    predictiveTransport T γ (Quotient.mk (PredictiveSetoid T i) h) =
      Quotient.mk (PredictiveSetoid T j) (T.push h γ) := by
  rfl

def predictiveToCurrent
    (T : RouteTransportCore)
    {i : T.Interface} :
    PredictiveQuotient T i → CurrentQuotient T i :=
  Quotient.lift
    (fun h => Quotient.mk (CurrentSetoid T i) h)
    (fun _ _ hEq =>
      Quotient.sound (futurePredictiveEquiv_implies_currentEventEquiv T hEq))

@[simp] theorem predictiveToCurrent_mk
    (T : RouteTransportCore)
    {i : T.Interface}
    (h : T.History i) :
    predictiveToCurrent T (Quotient.mk (PredictiveSetoid T i) h) =
      Quotient.mk (CurrentSetoid T i) h := by
  rfl

def currentTransport
    (T : RouteTransportCore)
    {i j : T.Interface}
    (γ : T.Continuation i j) :
    CurrentCompatible T γ →
    CurrentQuotient T i → CurrentQuotient T j :=
  fun hCompat =>
  Quotient.lift
    (fun h => Quotient.mk (CurrentSetoid T j) (T.push h γ))
    (fun _ _ hEq => Quotient.sound (currentEventEquiv_push T γ hCompat hEq))

@[simp] theorem currentTransport_mk
    (T : RouteTransportCore)
    {i j : T.Interface}
    (γ : T.Continuation i j)
    (hCompat : CurrentCompatible T γ)
    (h : T.History i) :
    currentTransport T γ hCompat (Quotient.mk (CurrentSetoid T i) h) =
      Quotient.mk (CurrentSetoid T j) (T.push h γ) := by
  rfl

theorem predictiveToCurrent_commutes_with_transport
    (T : RouteTransportCore)
    {i j : T.Interface}
    (γ : T.Continuation i j)
    (hCompat : CurrentCompatible T γ)
    (q : PredictiveQuotient T i) :
    currentTransport T γ hCompat (predictiveToCurrent T q) =
      predictiveToCurrent T (predictiveTransport T γ q) := by
  induction q using Quotient.ind
  simp

end HolonomyMemory
