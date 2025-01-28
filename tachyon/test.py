from physics import AgentType, Molecule
from chemistry import Rule, Mixture, System


# %sig: A@100(p[a1.P$m a2.P$m a3.P$m], l[r.A$w], r[l.A]), P@100(a1[p.A], a2[p.A], a3[p.A], d[d.P$m])
agent_types = [AgentType("A", ["p", "l", "r"]), AgentType("P", ["a1", "a2", "a3", "d"])]
rules = [Rule(("A", "A"), ("l", "r"), 1)]

A0 = P0 = 2
mixture = Mixture(
    [Molecule.create([agent_types[0]]) for _ in range(A0)]
    + [Molecule.create([agent_types[1]]) for _ in range(P0)]
)
system = System(mixture, rules)

while True:
    print([len(molecule) for molecule in system.mixture])
    system.update()
