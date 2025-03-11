import random

from kappybara.physics import AgentType, mixture
from kappybara.chemistry import BasicBindingRule, System

random.seed(42)


# %sig: A@100(p[a1.P$m a2.P$m a3.P$m], l[r.A$w], r[l.A]), P@100(a1[p.A], a2[p.A], a3[p.A], d[d.P$m])
agent_types = [AgentType("A", ["p", "l", "r"]), AgentType("P", ["a1", "a2", "a3", "d"])]
rules = [
    BasicBindingRule(True, ("A", "A"), ("l", "r"), 1),
    BasicBindingRule(False, ("A", "A"), ("l", "r"), 1),
    BasicBindingRule(True, ("P", "P"), ("d", "d"), 1),
    BasicBindingRule(False, ("P", "P"), ("d", "d"), 1),
    BasicBindingRule(True, ("P", "A"), ("a1", "p"), 1),
    BasicBindingRule(False, ("P", "A"), ("a1", "p"), 1),
    BasicBindingRule(True, ("P", "A"), ("a2", "p"), 1),
    BasicBindingRule(False, ("P", "A"), ("a2", "p"), 1),
    BasicBindingRule(True, ("P", "A"), ("a3", "p"), 1),
    BasicBindingRule(False, ("P", "A"), ("a3", "p"), 1),
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
