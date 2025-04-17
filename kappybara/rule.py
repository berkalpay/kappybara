from dataclasses import dataclass
from math import prod
from abc import ABC, abstractmethod
from typing import Optional, Iterable
import random

from kappybara.site_states import *
from kappybara.chemistry import Rule
from kappybara.pattern import (
    Pattern,
    ComponentPattern,
    Component,
    AgentPattern,
    Agent,
    SitePattern,
    Site,
)
from kappybara.mixture import Mixture, MixtureUpdate
from kappybara.rate import *


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
    stochastic_rate: Rate

    def __init__(self, left: Pattern, right: Pattern, stochastic_rate: Rate, *args, **kwargs):
        super().__init__(*args, **kwargs)

        l = len(left.agents)
        r = len(right.agents)
        assert (
            l == r
        ), f"The left-hand side of this rule has {l} slots, but the right-hand side has {r}."

        self.left = left
        self.right = right

        self.stochastic_rate = stochastic_rate

    def rate(self, system: "System") -> float:
        match self.stochastic_rate:
            case float():
                return self.stochastic_rate
            case RateFunction():
                raise NotImplementedError

    def n_embeddings(self, mixture: Mixture) -> int:
        return self.n_embeddings_default(mixture)

    def n_embeddings_default(self, mixture: Mixture) -> int:
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
        selection_map: dict[AgentPattern, Pattern] = {}

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
        self, selection_map: dict[AgentPattern, Pattern], mixture: Mixture
    ) -> MixtureUpdate:
        """
        Takes the agents that have been chosen to be transformed by this rule, and produces
        a `MixtureUpdate` which specifies what changes to the mixture should take place (without actually applying those changes).

        TODO: This is another place where the code is maybe too messy
        """

        # TODO: check for illegal collisions (i.e. different agents in the left-hand rule pattern
        # map to the same agent in the mixture). This can only happen when there's more than one
        # component in `self.left`.

        selection = self.convert_selection_map(selection_map)

        # References to the new or modified mixture agents which we
        # use to create the appropriate edges.
        new_selection = [None] * len(selection)

        update = MixtureUpdate()

        # Manage agents
        for i, l_agent in enumerate(self.left.agents):
            r_agent = self.right.agents[i]
            agent: Optional[Agent] = selection[i]

            match l_agent, r_agent:
                case None, AgentPattern():
                    # Create the new Agent
                    new_agent = update.create_agent(r_agent)
                    new_selection[i] = new_agent
                case AgentPattern(), None:
                    update.remove_agent(agent)
                    new_selection[i] = None  # Redundant but just for clarity
                case AgentPattern(), AgentPattern() if l_agent.type != r_agent.type:
                    update.remove_agent(agent)

                    new_agent = update.create_agent(r_agent, mixture)
                    new_selection[i] = new_agent
                case AgentPattern(), AgentPattern() if l_agent.type == r_agent.type:
                    for r_site in r_agent.sites.values():
                        if isinstance(r_site.internal_state, InternalState):
                            agent.sites[r_site.label].internal_state = (
                                r_site.internal_state
                            )

                            if (
                                r_site.internal_state
                                != l_agent.sites[r_site.label].internal_state
                            ):
                                update.agents_changed.add(agent)

                    new_selection[i] = agent
                case _:
                    pass

        # Manage explicitly referenced edges
        # TODO: Maybe could have patterns collect a list of their explicitly mentioned
        # edges at initialization. Efficiency of this step is probably not important though.
        for i, r_agent in enumerate(self.right.agents):
            agent: Optional[Agent] = new_selection[i]

            if r_agent is None:
                continue

            for r_site in r_agent.sites.values():
                site: Site = agent.sites[r_site.label]

                match r_site.link_state:
                    case SitePattern() as r_partner:
                        partner_idx = self.right.agents.index(r_partner.agent)
                        partner: Site = new_selection[partner_idx].sites[
                            r_partner.label
                        ]
                        update.connect_sites(site, partner)
                    case EmptyState():
                        update.disconnect_site(site)
                    case x if not isinstance(x, UndeterminedState):
                        raise TypeError(
                            f"Link states of type {type(x)} are unsupported for right-hand rule patterns."
                        )

        return update

    def convert_selection_map(
        self, selection_map: dict[AgentPattern, Pattern]
    ) -> list[Optional[Agent]]:
        # Convert from a dictionary representation of a selection, to an
        # array of just the selected agents, where the i'th `AgentPattern` in
        # self.left.agents corresponds to the i'th `Agent` (which exists in the mixture)
        # in the returned array.
        selection = []

        for agent in self.left.agents:
            if agent is None:
                selection.append(None)
            else:
                selection.append(selection_map[agent])

        return selection

    def stochastic_rate(self, system) -> float:
        match rate_value:
            case float() as x:
                return x
            case RateFunction() as rate_function:
                raise NotImplementedError


@dataclass
class KappaRuleUnimolecular(KappaRule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.component_weights: dict[Component, int] = {}

    def n_embeddings(self, mixture: Mixture) -> int:
        return self.n_embeddings_unimolecular(mixture)

    def n_embeddings_unimolecular(self, mixture: Mixture) -> int:
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

        selection_map: dict[AgentPattern, Pattern] = {}

        for component_pattern in self.left.components:
            choices = mixture.fetch_embeddings_in_component(
                component_pattern, selected_component
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
            match1: ComponentPattern = self.left.components[0]
            match2: ComponentPattern = self.left.components[1]

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

        selection_map: dict[AgentPattern, Pattern] = match1 | match2

        return self._produce_update(selection_map, mixture)


def rejection_sample(population: Iterable, exclude: Iterable, max_attempts=100):
    pop_ordered = list(population)
    exclude_set = set(id(x) for x in exclude)

    n = len(pop_ordered)
    if n == 0:
        raise ValueError("Sequence is empty")

    # Phase 1: Fast rejection sampling (O(1) average case for small exclusion sets)
    for _ in range(max_attempts):
        idx = random.randrange(n)
        if id(pop_ordered[idx]) not in exclude_set:
            return pop_ordered[idx]

    # Phase 2: Fallback to O(n) scan only if necessary (rare for small exclusion sets)
    valid_indices = [i for i, elem in enumerate(pop_ordered) if elem not in exclude_set]
    if not valid_indices:
        raise ValueError("No valid elements to choose from")
    return pop_ordered[random.choice(valid_indices)]
