import HolonomyMemory.Interfaces

namespace HolonomyMemory

/-- Two histories are currently equivalent when they agree on all present events. -/
def CurrentEventEquiv
    (T : RouteTransportCore) {i : T.Interface}
    (h h' : T.History i) : Prop :=
  ∀ e : T.Event i, T.observe h e = T.observe h' e

theorem currentEventEquiv_refl
    (T : RouteTransportCore) {i : T.Interface}
    (h : T.History i) :
    CurrentEventEquiv T h h := by
  intro e
  rfl

theorem currentEventEquiv_symm
    (T : RouteTransportCore) {i : T.Interface}
    {h h' : T.History i}
    (hEq : CurrentEventEquiv T h h') :
    CurrentEventEquiv T h' h := by
  intro e
  exact Eq.symm (hEq e)

theorem currentEventEquiv_trans
    (T : RouteTransportCore) {i : T.Interface}
    {h h' h'' : T.History i}
    (hEq₁ : CurrentEventEquiv T h h')
    (hEq₂ : CurrentEventEquiv T h' h'') :
    CurrentEventEquiv T h h'' := by
  intro e
  exact Eq.trans (hEq₁ e) (hEq₂ e)

/-- Two histories are future-predictively equivalent when they agree after every
admissible continuation on every later event. -/
def FuturePredictiveEquiv
    (T : RouteTransportCore) {i : T.Interface}
    (h h' : T.History i) : Prop :=
  ∀ {j : T.Interface} (γ : T.Continuation i j) (e : T.Event j),
    T.observe (T.push h γ) e = T.observe (T.push h' γ) e

theorem futurePredictiveEquiv_refl
    (T : RouteTransportCore) {i : T.Interface}
    (h : T.History i) :
    FuturePredictiveEquiv T h h := by
  intro j γ e
  rfl

theorem futurePredictiveEquiv_symm
    (T : RouteTransportCore) {i : T.Interface}
    {h h' : T.History i}
    (hEq : FuturePredictiveEquiv T h h') :
    FuturePredictiveEquiv T h' h := by
  intro j γ e
  exact Eq.symm (hEq γ e)

theorem futurePredictiveEquiv_trans
    (T : RouteTransportCore) {i : T.Interface}
    {h h' h'' : T.History i}
    (hEq₁ : FuturePredictiveEquiv T h h')
    (hEq₂ : FuturePredictiveEquiv T h' h'') :
    FuturePredictiveEquiv T h h'' := by
  intro j γ e
  exact Eq.trans (hEq₁ γ e) (hEq₂ γ e)

theorem futurePredictiveEquiv_implies_currentEventEquiv
    (T : RouteTransportCore) {i : T.Interface}
    {h h' : T.History i}
    (hEq : FuturePredictiveEquiv T h h') :
    CurrentEventEquiv T h h' := by
  intro e
  simpa [FuturePredictiveEquiv, CurrentEventEquiv, T.push_id h, T.push_id h']
    using hEq (j := i) (γ := T.idCont) e

/-- Current observations need not be closed under all future experiments. -/
def CurrentCompatible
    (T : RouteTransportCore) {i j : T.Interface}
    (γ : T.Continuation i j) : Prop :=
  ∀ {h h' : T.History i}, CurrentEventEquiv T h h' →
    CurrentEventEquiv T (T.push h γ) (T.push h' γ)

theorem currentEventEquiv_push
    (T : RouteTransportCore)
    {i j : T.Interface}
    (γ : T.Continuation i j)
    (hCompat : CurrentCompatible T γ)
    {h h' : T.History i}
    (hEq : CurrentEventEquiv T h h') :
    CurrentEventEquiv T (T.push h γ) (T.push h' γ) := by
  exact hCompat hEq

/-- A global current-compatibility assumption would rule out predictive residue. -/
theorem currentEventEquiv_implies_future_of_all_compatible
    (T : RouteTransportCore)
    (hAll : ∀ {i j : T.Interface} (γ : T.Continuation i j), CurrentCompatible T γ)
    {i : T.Interface} {h h' : T.History i}
    (hEq : CurrentEventEquiv T h h') : FuturePredictiveEquiv T h h' := by
  intro j γ e
  exact hAll γ hEq e

end HolonomyMemory
