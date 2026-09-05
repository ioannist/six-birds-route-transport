import HolonomyMemory.Transport

namespace HolonomyMemory

/-- A future observable bundles a target interface, an admissible continuation,
and an event to be observed after pushing forward. -/
structure FutureObservable
    (T : RouteTransportCore) (i : T.Interface) where
  target : T.Interface
  continuation : T.Continuation i target
  event : T.Event target

/-- Evaluate a bundled future observable on a history at the source interface. -/
def evalFutureObservable
    (T : RouteTransportCore) {i : T.Interface} :
    FutureObservable T i → T.History i → T.Observation
  | ⟨_, γ, e⟩, h => T.observe (T.push h γ) e

/-- A state abstraction is future-sufficient when every bundled future observable
factors through the state value. -/
def FutureSufficient
    (T : RouteTransportCore) {i : T.Interface}
    {S : Type} (state : T.History i → S) : Prop :=
  ∀ obs : FutureObservable T i,
    ∃ f : S → T.Observation,
      ∀ h : T.History i,
        f (state h) = evalFutureObservable T obs h

theorem predictiveQuotient_futureSufficient
    (T : RouteTransportCore) (i : T.Interface) :
    FutureSufficient T (fun h : T.History i => (Quotient.mk (PredictiveSetoid T i) h : PredictiveQuotient T i)) := by
  intro obs
  cases obs with
  | mk j γ e =>
      refine ⟨Quotient.lift (fun qh : T.History i => T.observe (T.push qh γ) e) ?_, ?_⟩
      · intro h h' hEq
        exact hEq γ e
      · intro h
        rfl

theorem futureSufficient_stateEq_implies_futurePredictiveEquiv
    (T : RouteTransportCore) {i : T.Interface}
    {S : Type} {state : T.History i → S}
    (hSuf : FutureSufficient T state)
    {h h' : T.History i}
    (hEq : state h = state h') :
    FuturePredictiveEquiv T h h' := by
  intro j γ e
  let obs : FutureObservable T i := ⟨j, γ, e⟩
  rcases hSuf obs with ⟨f, hf⟩
  calc
    T.observe (T.push h γ) e = f (state h) := by
      simpa [obs, evalFutureObservable] using (hf h).symm
    _ = f (state h') := by rw [hEq]
    _ = T.observe (T.push h' γ) e := by
      simpa [obs, evalFutureObservable] using (hf h')

/-- The reachable image of a state abstraction, packaged as actual attained
state values. -/
def ReachableState
    (T : RouteTransportCore) {i : T.Interface}
    {S : Type} (state : T.History i → S) :=
  { s : S // ∃ h : T.History i, state h = s }

noncomputable def reachableStateRepresentative
    (T : RouteTransportCore) {i : T.Interface}
    {S : Type} {state : T.History i → S}
    (x : ReachableState T state) : T.History i :=
  Classical.choose x.property

theorem reachableStateRepresentative_state_eq
    (T : RouteTransportCore) {i : T.Interface}
    {S : Type} {state : T.History i → S}
    (x : ReachableState T state) :
    state (reachableStateRepresentative T x) = x.1 :=
  Classical.choose_spec x.property

noncomputable def reachableStateToPredictiveQuotient
    (T : RouteTransportCore) {i : T.Interface}
    {S : Type} {state : T.History i → S}
    (hSuf : FutureSufficient T state) :
    ReachableState T state → PredictiveQuotient T i :=
  let _ := hSuf
  fun x => Quotient.mk (PredictiveSetoid T i) (reachableStateRepresentative T x)

theorem reachableStateToPredictiveQuotient_commutes
    (T : RouteTransportCore) {i : T.Interface}
    {S : Type} {state : T.History i → S}
    (hSuf : FutureSufficient T state)
    (h : T.History i) :
    reachableStateToPredictiveQuotient T hSuf ⟨state h, ⟨h, rfl⟩⟩ =
      (Quotient.mk (PredictiveSetoid T i) h : PredictiveQuotient T i) := by
  apply Quotient.sound
  apply futureSufficient_stateEq_implies_futurePredictiveEquiv T hSuf
  simpa [reachableStateRepresentative, ReachableState] using
    (reachableStateRepresentative_state_eq T (x := ⟨state h, ⟨h, rfl⟩⟩))

theorem futureSufficient_factorsThroughPredictiveQuotient_onReachable
    (T : RouteTransportCore) {i : T.Interface}
    {S : Type} {state : T.History i → S}
    (hSuf : FutureSufficient T state) :
    ∃ f : ReachableState T state → PredictiveQuotient T i,
      ∀ h : T.History i,
        f ⟨state h, ⟨h, rfl⟩⟩ = (Quotient.mk (PredictiveSetoid T i) h : PredictiveQuotient T i) := by
  refine ⟨reachableStateToPredictiveQuotient T hSuf, ?_⟩
  intro h
  exact reachableStateToPredictiveQuotient_commutes T hSuf h

theorem futureSufficient_factorization_unique_onReachable
    (T : RouteTransportCore) {i : T.Interface}
    {S : Type} {state : T.History i → S}
    {f g : ReachableState T state → PredictiveQuotient T i}
    (hf : ∀ h : T.History i,
      f ⟨state h, ⟨h, rfl⟩⟩ = (Quotient.mk (PredictiveSetoid T i) h : PredictiveQuotient T i))
    (hg : ∀ h : T.History i,
      g ⟨state h, ⟨h, rfl⟩⟩ = (Quotient.mk (PredictiveSetoid T i) h : PredictiveQuotient T i)) :
    f = g := by
  funext x
  let h := reachableStateRepresentative T x
  have hx : x = ⟨state h, ⟨h, rfl⟩⟩ := by
    apply Subtype.ext
    exact (reachableStateRepresentative_state_eq T x).symm
  rw [hx]
  rw [hf h, hg h]

theorem reachableStateToPredictiveQuotient_unique
    (T : RouteTransportCore) {i : T.Interface}
    {S : Type} {state : T.History i → S}
    (hSuf : FutureSufficient T state)
    {f : ReachableState T state → PredictiveQuotient T i}
    (hf : ∀ h : T.History i,
      f ⟨state h, ⟨h, rfl⟩⟩ = (Quotient.mk (PredictiveSetoid T i) h : PredictiveQuotient T i)) :
    f = reachableStateToPredictiveQuotient T hSuf := by
  apply futureSufficient_factorization_unique_onReachable T hf
  intro h
  exact reachableStateToPredictiveQuotient_commutes T hSuf h

end HolonomyMemory
