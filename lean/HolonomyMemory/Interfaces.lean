import HolonomyMemory.Basic

universe u v w x y

namespace HolonomyMemory

/-- Minimal typed core for the first abstract theorem spine. -/
structure RouteTransportCore where
  Interface : Type u
  History : Interface → Type v
  Continuation : Interface → Interface → Type w
  Event : Interface → Type x
  Observation : Type y
  idCont : {i : Interface} → Continuation i i
  compose :
    {i j k : Interface} →
      Continuation i j →
      Continuation j k →
      Continuation i k
  push : {i j : Interface} → History i → Continuation i j → History j
  observe : {i : Interface} → History i → Event i → Observation
  push_id : ∀ {i : Interface} (h : History i), push h idCont = h
  push_compose :
    ∀ {i j k : Interface}
      (h : History i)
      (γ : Continuation i j)
      (δ : Continuation j k),
      push (push h γ) δ = push h (compose γ δ)

end HolonomyMemory
