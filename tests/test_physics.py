import pytest

from kappybara.physics import AgentType, Molecule, Mixture

agent_types = {
    "A": AgentType("A", ["p", "l", "r"]),
    "P": AgentType("P", ["a1", "a2", "a3", "d"]),
}


def test_binding():
    molecule1 = agent_types["A"].molecule()
    molecule2 = agent_types["P"].molecule()
    Mixture(set([molecule1, molecule2]))
    agent1 = molecule1.agents[0]
    agent2 = molecule2.agents[0]
    assert not agent1.same_molecule(agent2)
    agent1.interface["p"].bind(agent2.interface["a1"])
    assert agent1.same_molecule(agent2)


@pytest.mark.parametrize(
    "molecule",
    [
        Molecule(
            [
                ("A", {"l": 1, "p": None, "r": None}),
                ("A", {"l": None, "p": None, "r": 1}),
            ]
        ),
        Molecule.from_kappa("A(l[1] p[.] r[.]), A(l[.] p[.] r[1])"),
    ],
)
def test_molecule_init(molecule):
    assert len(molecule) == 2
    assert molecule.agents[0].interface["l"].partner.agent.type == "A"
    assert molecule.agents[1].interface["r"].partner.agent.type == "A"
    assert not molecule.agents[0].interface["r"].bound
