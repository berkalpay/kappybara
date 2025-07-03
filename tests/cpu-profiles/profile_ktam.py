from kappybara.mixture import Mixture
from kappybara.system import System
import kappybara.kappa as kappa

if __name__ == "__main__":
    init_patterns = [("A(l[.], r[.], u[.], d[.])", 200)]
    rules = [
        "A(l[.]), A(r[.]) <-> A(l[1]), A(r[1]) @ 50.0, 1.0",
        "A(u[.]), A(d[.]) <-> A(u[1]), A(d[1]) @ 50.0, 1.0",
    ]

    mixture = Mixture()
    for pair in init_patterns:
        pattern_str, count = pair
        pattern = kappa.pattern(pattern_str)

        for _ in range(count):
            mixture.instantiate(pattern)
    rules = [rule for rule_str in rules for rule in kappa.rules(rule_str)]
    system = System(mixture, rules)

    for _ in range(5000):
        system.update()
