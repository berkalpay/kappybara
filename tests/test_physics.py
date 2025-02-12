import pytest

from kappybara.physics import AgentType, Molecule
from kappybara.chemistry import Mixture

agent_types = {
    "A": AgentType("A", ["p", "l", "r"]),
    "P": AgentType("P", ["a1", "a2", "a3", "d"]),
}


def test_binding():
    molecule1 = Molecule.create([agent_types["A"]])
    molecule2 = Molecule.create([agent_types["P"]])
    Mixture(set([molecule1, molecule2]))
    agent1 = molecule1.agents[0]
    agent2 = molecule2.agents[0]
    assert not agent1.same_molecule(agent2)
    agent1.interface["p"].bind(agent2.interface["a1"])
    assert agent1.same_molecule(agent2)
