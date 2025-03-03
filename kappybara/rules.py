import random
from abc import ABC, abstractmethod
from typing import Optional

from kappybara.physics import Site
from kappybara.chemistry import Mixture


class Rule(ABC):
    def __init__(
        self, agent_types: tuple[str, str], site_labels: tuple[str, str], rate: float
    ):
        self.agent_types = agent_types  # TODO: unneeded?
        self.site_labels = site_labels
        self.rate = rate

    def reactivity(self, mixture: Mixture) -> float:
        return self.n_embeddings(mixture) * self.rate

    @abstractmethod
    def n_embeddings(self, mixture: Mixture) -> int:
        pass

    @abstractmethod
    def _select(self, mixture: Mixture) -> tuple[Site, Optional[Site]]:
        pass

    @abstractmethod
    def act(self, mixture: Mixture) -> None:
        pass


class BasicBindingRule(Rule):
    def __init__(self, bind: bool, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind = bind

    def n_embeddings(self, mixture: Mixture) -> int:
        if self.bind:
            # Note: counts illegal intra-agent bond opportunities
            site1_choices = mixture.free_sites[self.site_labels[0]]
            site2_choices = mixture.free_sites[self.site_labels[1]]
            return len(site1_choices) * len(site2_choices)
        else:
            return [
                site.partner.label == self.site_labels[1]
                for site in mixture.bound_sites.get(self.site_labels[0], [])
            ].count(True)

    def _select(self, mixture: Mixture) -> tuple[Site, Optional[Site]]:
        if self.bind:
            # Note: might be an illegal intra-agent bond
            site1 = random.choice(tuple(mixture.free_sites[self.site_labels[0]]))
            site2 = random.choice(tuple(mixture.free_sites[self.site_labels[1]]))
            return (site1, site2)
        else:
            site_choices = []
            for agent in mixture.agents_by_type[self.agent_types[0]]:
                site = agent.interface[self.site_labels[0]]
                if site.bound and site.partner.label == self.site_labels[1]:
                    site_choices.append(site)
            site_choice = random.choice(site_choices)
            return (site_choice, None)

    def act(self, mixture: Mixture) -> None:
        site1, site2 = self._select(mixture)
        if self.bind:
            site1.bind(site2)
        else:
            site1.unbind()
