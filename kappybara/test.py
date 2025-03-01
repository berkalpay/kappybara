import random

from physics import AgentType, Molecule
from chemistry import Mixture, System
from rules import BasicBindingRule

random.seed(42)


# %sig: A@100(p[a1.P$m a2.P$m a3.P$m], l[r.A$w], r[l.A]), P@100(a1[p.A], a2[p.A], a3[p.A], d[d.P$m])
agent_types = [AgentType("A", ["p", "l", "r"]), AgentType("P", ["a1", "a2", "a3", "d"])]
rules = [
    BasicBindingRule(("A", "A"), ("l", "r"), True, 1),
    BasicBindingRule(("A", "A"), ("l", "r"), False, 1),
    BasicBindingRule(("P", "P"), ("d", "d"), True, 1),
    BasicBindingRule(("P", "P"), ("d", "d"), False, 1),
    BasicBindingRule(("P", "A"), ("a1", "p"), True, 1),
    BasicBindingRule(("P", "A"), ("a1", "p"), False, 1),
    BasicBindingRule(("P", "A"), ("a2", "p"), True, 1),
    BasicBindingRule(("P", "A"), ("a2", "p"), False, 1),
    BasicBindingRule(("P", "A"), ("a3", "p"), True, 1),
    BasicBindingRule(("P", "A"), ("a3", "p"), False, 1),
]

A0 = P0 = 10**4
mixture = Mixture(
    set(
        [Molecule.create([agent_types[0]]) for _ in range(A0)]
        + [Molecule.create([agent_types[1]]) for _ in range(P0)]
    )
)
system = System(mixture, rules)

for i in range(10**5):
    if not i % 10**3:
        molecule_sizes = [len(molecule) for molecule in system.mixture]
        print(max(molecule_sizes))
    system.update()
