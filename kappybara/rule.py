import random
from dataclasses import dataclass
from math import prod
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

from kappybara.pattern import Pattern, Component, Agent, Site
from kappybara.mixture import Mixture, MixtureUpdate
from kappybara.alg_exp import AlgExp
from kappybara.utils import rejection_sample

if TYPE_CHECKING:
    from kappybara.system import System


# Useful constants
AVOGADRO = 6.02214e23
DIFFUSION_RATE = 1e9
KDS = {"weak": 1e-6, "moderate": 1e-7, "strong": 1e-8}
VOLUMES = {"fibro": 2.25e-12, "yeast": 4.2e-14}
ROOM_TEMPERATURE = 273.15 + 25


def kinetic_to_stochastic_on_rate(
    k_on: float = DIFFUSION_RATE, volume: float = 1, order: int = 2
) -> float:
    return k_on / (AVOGADRO * volume ** (order - 1))


class Rule(ABC):
    def reactivity(self, system: "System") -> float:
        return self.n_embeddings(system.mixture) * self.rate(system)

    @abstractmethod
    def rate(self, system: "System") -> float:
        """The stochastic rate of the rule."""
        pass

    @abstractmethod
    def n_embeddings(self, mixture: Mixture) -> int:
        pass

    @abstractmethod
    def select(self, mixture: Mixture) -> Optional[MixtureUpdate]:
        """
        Don't modify anything in `mixture` directly here except for changing
        internal sites of agents (which should be added to the `agents_changed` field
        of the returned `MixtureUpdate`). A null event is represented by returning None.
        """
        pass


@dataclass
class KappaRule(Rule):
    left: Pattern
    right: Pattern
    stochastic_rate: AlgExp

    def __post_init__(self):
        l = len(self.left.agents)
        r = len(self.right.agents)
        assert (
            l == r
        ), f"The left-hand side of this rule has {l} slots, but the right-hand side has {r}."

    def __len__(self):
        return len(self.left.agents)

    def __iter__(self):
        yield from zip(self.left.agents, self.right.agents)

    def rate(self, system: "System") -> float:
        return self.stochastic_rate.evaluate(system)

    def n_embeddings(self, mixture: Mixture) -> int:
        return prod(
            len(mixture.embeddings(component)) for component in self.left.components
        )

    def select(self, mixture: Mixture) -> Optional[MixtureUpdate]:
        """
        NOTE: Can change the internal states of agents in the mixture but
        records everything else in the `MixtureUpdate`.
        TODO: Rework `MixtureUpdate` to accomodate the internal state changes.
        """
        # Maps agents on the left hand side of a rule to agents in the mixture
        rule_embedding: dict[Agent, Agent] = {}

        for component in self.left.components:
            component_embeddings = mixture.embeddings(component)
            assert (
                len(component_embeddings) > 0
            ), f"A rule with no valid embeddings was selected: {self}"
            component_embedding = random.choice(component_embeddings)

            for rule_agent in component_embedding:
                mixture_agent = component_embedding[rule_agent]
                if mixture_agent in rule_embedding.values():
                    return None  # Invalid match: two selected components intersect
                else:
                    rule_embedding[rule_agent] = mixture_agent

        return self._produce_update(rule_embedding, mixture)

    def _produce_update(
        self, selection_map: dict[Agent, Agent], mixture: Mixture
    ) -> MixtureUpdate:
        """
        Takes the agents that have been chosen to be transformed by this rule,
        and specifies an update to the mixture without actually applying it.

        TODO: check for different agents in the left-hand rule pattern mapping
        to the same agent in the mixture (illegal).
        """

        selection = [
            None if agent is None else selection_map[agent]
            for agent in self.left.agents
        ]  # Select agents in the mixture matching the rule, in order
        new_selection: list[Optional[Agent]] = [None] * len(
            selection
        )  # The new/modified agents used to make the appropriate edges
        update = MixtureUpdate()

        # Manage agents
        for i in range(len(self)):
            l_agent = self.left.agents[i]
            r_agent = self.right.agents[i]
            agent: Optional[Agent] = selection[i]

            match l_agent, r_agent:
                case None, Agent():
                    new_selection[i] = update.create_agent(r_agent)
                case Agent(), None:
                    update.remove_agent(agent)
                case Agent(), Agent() if l_agent.type != r_agent.type:
                    update.remove_agent(agent)
                    new_selection[i] = update.create_agent(r_agent)
                case Agent(), Agent() if l_agent.type == r_agent.type:
                    for r_site in r_agent:
                        if r_site.stated:
                            agent[r_site.label].state = r_site.state
                            if r_site.state != l_agent[r_site.label].state:
                                update.register_changed_agent(agent)
                    new_selection[i] = agent
                case _:
                    pass

        # Manage explicitly referenced edges
        # TODO: Maybe could have patterns collect a list of their explicitly mentioned
        # edges at initialization. Efficiency of this step is probably not important though.
        for i, r_agent in enumerate(self.right.agents):
            if r_agent is None:
                continue
            agent = new_selection[i]
            for r_site in r_agent:
                site = agent[r_site.label]
                match r_site.partner:
                    case Site() as r_partner:
                        partner_idx = self.right.agents.index(r_partner.agent)
                        partner = new_selection[partner_idx][r_partner.label]
                        update.connect_sites(site, partner)
                    case ".":
                        update.disconnect_site(site)
                    case x if x != "?":
                        raise TypeError(
                            f"Site partners of type {x} are unsupported for right-hand rule patterns."
                        )

        return update


@dataclass
class KappaRuleUnimolecular(KappaRule):
    def __post_init__(self):
        super().__post_init__()
        self.component_weights: dict[Component, int] = {}

    def n_embeddings(self, mixture: Mixture) -> int:
        count = 0
        # TODO: incrementally update counts (also accounting for component removal)
        self.component_weights = {}
        for component in mixture.components:
            weight = prod(
                len(mixture.embeddings_in_component(match_component, component))
                for match_component in self.left.components
            )
            self.component_weights[component] = weight
            count += weight
        return count

    def select(self, mixture: Mixture) -> Optional[MixtureUpdate]:
        """
        NOTE: `self.n_embeddings` must be called before this method so that the
        `component_weights` cache is up-to-date.
        """
        components_ordered = list(self.component_weights)
        weights = [self.component_weights[c] for c in components_ordered]
        selected_component = random.choices(components_ordered, weights)[0]

        selection_map: dict[Agent, Agent] = {}
        for component in self.left.components:
            choices = mixture.embeddings_in_component(component, selected_component)
            assert (
                len(choices) > 0
            ), f"A rule with no valid embeddings was selected: {self}"
            component_selection = random.choice(choices)

            for agent in component_selection:
                if component_selection[agent] in selection_map.values():
                    # This means two selected components have intersecting
                    # sets of mixture agents, so this is an invalid match/null event.
                    return None
                else:
                    selection_map[agent] = component_selection[agent]

        return self._produce_update(selection_map, mixture)


@dataclass
class KappaRuleBimolecular(KappaRule):
    def __post_init__(self):
        super().__post_init__()
        self.component_weights: dict[Component, int] = {}
        assert (
            len(self.left.components) == 2
        ), "Bimolecular rule patterns must consist of exactly 2 components."

    def n_embeddings(self, mixture: Mixture) -> int:
        count = 0
        self.component_weights = {}  # TODO: incrementally update

        for component in mixture.components:
            n_match1 = len(
                mixture.embeddings_in_component(self.left.components[0], component)
            )
            n_match2 = len(mixture.embeddings(self.left.components[1])) - len(
                mixture.embeddings_in_component(self.left.components[1], component)
            )  # Embed this part of the rule outside the component

            weight = n_match1 * n_match2
            self.component_weights[component] = weight
            count += weight

        return count

    def select(self, mixture: Mixture) -> Optional[MixtureUpdate]:
        """
        NOTE: `self.n_embeddings` must be called before this method so that the
        `component_weights` cache is up-to-date.
        """
        components_ordered = list(self.component_weights.keys())
        weights = [self.component_weights[c] for c in components_ordered]
        selected_component = random.choices(components_ordered, weights)[0]

        match1 = random.choice(
            mixture.embeddings_in_component(self.left.components[0], selected_component)
        )
        match2 = rejection_sample(
            mixture.embeddings(self.left.components[1]),
            mixture.embeddings_in_component(
                self.left.components[1], selected_component
            ),
        )  # Embed this part of the rule outside the component

        return self._produce_update(match1 | match2, mixture)
