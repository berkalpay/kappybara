from dataclasses import dataclass
from math import prod
from abc import ABC, abstractmethod
from typing import Optional
import random

import kappybara.site_states as states
from kappybara.pattern import Pattern, Component, Agent, Site
from kappybara.mixture import Mixture, MixtureUpdate
from kappybara.utils import rejection_sample


class Rule(ABC):
    def reactivity(self, system: "System") -> float:
        return self.n_embeddings(system.mixture) * self.rate(system)

    @abstractmethod
    def rate(self, system: "System") -> float:
        """
        The stochastic rate of the rule.
        """
        pass

    @abstractmethod
    def n_embeddings(self, mixture: Mixture) -> int:
        pass

    @abstractmethod
    def select(self, mixture: Mixture) -> Optional[MixtureUpdate]:
        """
        DO NOT modify anything in `mixture` directly here except for changing
        internal sites of agents (which should be added to the `agents_changed` field
        of the returned `MixtureUpdate`). Anything else will cause undefined behavior.
        Instead, create a `MixtureUpdate` and use its helper functions to indicate
        what connectivity changes or agent additions/removals *should* occur in the
        mixture by the application of your rule.

        The return type is an `Optional` because we want to allow the rule to return
        a null event, which we represent with `None`
        """
        pass


@dataclass
class KappaRule(Rule):
    left: Pattern
    right: Pattern
    stochastic_rate: float

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
        return self.stochastic_rate

    def n_embeddings(self, mixture: Mixture) -> int:
        return prod(
            len(mixture.fetch_embeddings(component))
            for component in self.left.components
        )

    def select(self, mixture: Mixture) -> Optional[MixtureUpdate]:
        """
        This function is not quite pure since internal states of agents in the
        mixture can be changed by this method. Everything else however (edge/bond
        insertions/removals, agent insertions/removals) is just recorded in the
        returned `MixtureUpdate` without actually occurring in the mixture. I would
        rather this function just not touch the actual mixture at all, but would have
        to rework the `MixtureUpdate` class to be able to accomodate specific internal
        state changes.
        """
        # A map from the agents in the left hand side of a rule
        # to chosen instances of agents in the mixture.
        selection_map: dict[Agent, Pattern] = {}

        for component in self.left.components:
            choices = mixture.fetch_embeddings(component)
            assert (
                len(choices) > 0
            ), f"A rule with no valid embeddings was selected: {self}"
            component_selection = random.choice(mixture.fetch_embeddings(component))

            for agent in component_selection:
                if component_selection[agent] in selection_map.values():
                    # This means two selected components have intersecting
                    # sets of mixture agents, so this is an invalid match.
                    return None
                else:
                    selection_map[agent] = component_selection[agent]

        return self._produce_update(selection_map, mixture)

    def _produce_update(
        self, selection_map: dict[Agent, Pattern], mixture: Mixture
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
        )  # The new/modified agents used to make the appropriate edges.
        update = MixtureUpdate()

        # Manage agents
        for i in range(len(self)):
            l_agent = self.left.agents[i]
            r_agent = self.right.agents[i]
            agent: Optional[Agent] = selection[i]

            match l_agent, r_agent:
                case None, Agent():
                    new_selection[i] = update.create_agent(r_agent, mixture)
                case Agent(), None:
                    update.remove_agent(agent)
                case Agent(), Agent() if l_agent.type != r_agent.type:
                    update.remove_agent(agent)
                    new_selection[i] = update.create_agent(r_agent, mixture)
                case Agent(), Agent() if l_agent.type == r_agent.type:
                    for r_site in r_agent.sites.values():
                        if isinstance(r_site.state, states.Internal):
                            agent.sites[r_site.label].state = r_site.state
                            if r_site.state != l_agent.sites[r_site.label].state:
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
            for r_site in r_agent.sites.values():
                site: Site = agent.sites[r_site.label]
                match r_site.partner:
                    case Site() as r_partner:
                        partner_idx = self.right.agents.index(r_partner.agent)
                        partner: Site = new_selection[partner_idx].sites[
                            r_partner.label
                        ]
                        update.connect_sites(site, partner)
                    case states.Empty():
                        update.disconnect_site(site)
                    case x if not isinstance(x, states.Undetermined):
                        raise TypeError(
                            f"Link states of type {type(x)} are unsupported for right-hand rule patterns."
                        )

        return update


@dataclass
class KappaRuleUnimolecular(KappaRule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.component_weights: dict[Component, int] = {}

    def n_embeddings(self, mixture: Mixture) -> int:
        """
        TODO: if a component gets removed from the mixture, its entry
        in `self.component_weights` will remain unless we remake it from
        scratch like we do here. So for an incremental version the logic
        would have to be more complicated or we'd have to rethink things a bit.
        """
        count = 0

        # Reset the index from scratch. Removes some tricky considerations from now,
        # but obviously not desirable performance wise. Doesn't matter as long as we're
        # recomputing every weight anyways below, though.
        self.component_weights = {}

        for component in mixture.components:
            weight = prod(
                len(mixture.fetch_embeddings_in_component(match_component, component))
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
        components_ordered = list(self.component_weights.keys())
        weights = [self.component_weights[c] for c in components_ordered]

        selected_component = random.choices(components_ordered, weights)[0]

        selection_map: dict[Agent, Pattern] = {}

        for component in self.left.components:
            choices = mixture.fetch_embeddings_in_component(
                component, selected_component
            )
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

        # TODO: Remove this sanity check
        # Assert that all agents are in the same mixture Component
        component = mixture.component_index[next(iter(selection_map.values()))]
        for agent in selection_map.values():
            assert component == mixture.component_index[agent]

        return self._produce_update(selection_map, mixture)


@dataclass
class KappaRuleBimolecular(KappaRule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.component_weights: dict[Component, int] = {}

        assert (
            len(self.left.components) == 2
        ), "Bimolecular rules patterns must consist of exactly 2 components."

    def n_embeddings(self, mixture: Mixture) -> int:
        res = 0
        self.component_weights = (
            {}
        )  # Again, we're just doing this from scratch from now

        for component in mixture.components:
            match1: Component = self.left.components[0]
            match2: Component = self.left.components[1]

            # Number of times the first component in the left Pattern of this rule
            # embeds into `component`
            n_match1 = len(mixture.fetch_embeddings_in_component(match1, component))

            # Number of times the second component in the left Pattern of this rule
            # embeds anywhere *outside of* `component`
            n_match2 = len(mixture.fetch_embeddings(match2)) - len(
                mixture.fetch_embeddings_in_component(match2, component)
            )

            weight = n_match1 * n_match2

            self.component_weights[component] = weight
            res += weight

        return res

    def select(self, mixture: Mixture) -> Optional[MixtureUpdate]:
        """
        NOTE: `self.n_embeddings` must be called before this method so that the
        `component_weights` cache is up-to-date.
        """
        components_ordered = list(self.component_weights.keys())
        weights = [self.component_weights[c] for c in components_ordered]

        selected_component = random.choices(components_ordered, weights)[0]

        match1 = random.choice(
            mixture.fetch_embeddings_in_component(
                self.left.components[0], selected_component
            )
        )

        # Sample from all embeddings of the second component in `self.left` in `mixture`,
        # excluding the embeddings found in the same component as `match1`
        match2 = rejection_sample(
            mixture.fetch_embeddings(self.left.components[1]),
            mixture.fetch_embeddings_in_component(
                self.left.components[1], selected_component
            ),
        )

        # TODO: Assert that the two chosen components are not in the same
        # connected component as a sanity check

        selection_map: dict[Agent, Pattern] = match1 | match2

        return self._produce_update(selection_map, mixture)
