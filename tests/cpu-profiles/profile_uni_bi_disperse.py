from kappybara.mixture import Mixture
from kappybara.system import System
import kappybara.kappa as kappa

if __name__ == "__main__":
    init_patterns = [("A(a1[.], a2[.], a3[.])", 10000)]
    on = 1e-5
    off = 1e-1
    rules = [
        f"A(a1[.]), A(a2[.]) <-> A(a1[1]), A(a2[1]) @ {on} {{{on}}}, {off}",
        f"A(a2[.]), A(a3[.]) <-> A(a2[1]), A(a3[1]) @ {on} {{{on}}}, {off}",
        f"A(a1[.]), A(a3[.]) <-> A(a1[1]), A(a3[1]) @ {on} {{{on}}}, {off}",
    ]

    mixture = Mixture()
    for pair in init_patterns:
        pattern_str, count = pair
        pattern = kappa.pattern(pattern_str)

        for _ in range(count):
            mixture.instantiate(pattern)
    rules = [rule for rule_str in rules for rule in kappa.rules(rule_str)]
    system = System(mixture, rules)

    while system.time < 0.05:
        print(len(mixture.components))
        system.update()
