import random

from kappybara.physics import AgentType, mixture
from kappybara.chemistry import basic_binding_unbinding, KDS, System

random.seed(42)

# %sig: A@100(p[a1.P$m a2.P$m a3.P$m], l[r.A$w], r[l.A]), P@100(a1[p.A], a2[p.A], a3[p.A], d[d.P$m])
agent_types = [AgentType("A", ["p", "l", "r"]), AgentType("P", ["a1", "a2", "a3", "d"])]
rules = [
    *basic_binding_unbinding(("A", "A"), ("l", "r"), kd=KDS["weak"]),
    *basic_binding_unbinding(("P", "P"), ("d", "d"), kd=KDS["moderate"]),
    *basic_binding_unbinding(("P", "A"), ("a1", "p"), kd=KDS["moderate"]),
    *basic_binding_unbinding(("P", "A"), ("a2", "p"), kd=KDS["moderate"]),
    *basic_binding_unbinding(("P", "A"), ("a3", "p"), kd=KDS["moderate"]),
]

num_each = 10**4
system = System(mixture, rules)
for _ in range(num_each):
    system.mixture.add(agent_types[0].molecule())

for i in range(10**5):
    if not i % 10**3:
        molecule_sizes = [len(molecule) for molecule in system.mixture]
        print(max(molecule_sizes))
    system.update()
