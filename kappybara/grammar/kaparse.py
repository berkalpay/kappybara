from pathlib import Path
from lark import Lark, ParseTree


class KappaParser:
    """
    Don't instantiate this class, use `kappa_parser`, which
    is provided by the top level of the `grammar` module
    """

    def __init__(self) -> None:
        lark_file_path = str(Path(__file__).parent / "kappa.lark")

        self._parser = Lark.open(
            lark_file_path,
            rel_to=__file__,
            #  parser='lalr',
            parser="earley",
            # Using the basic lexer isn't required, and isn't usually recommended.
            lexer="dynamic",
            #  lexer='basic',
            start="kappa_input",
            # Disabling propagate_positions and placeholders slightly improves speed
            propagate_positions=False,
            maybe_placeholders=False,
        )

    def parse_file(self, filepath: str) -> ParseTree:
        with open(filepath, "r") as file:
            return self._parser.parse(file.read())

    def parse(self, kappa_string: str) -> ParseTree:
        return self._parser.parse(kappa_string)


kappa_parser = KappaParser()


# TODO: get pytest to pick up on inline test functions like this and run them
# Need to create a .pytest file in the root dir and add some setting there
def test_parse_file():
    kappa_file_path = str(Path(__file__).parent / "wnt_v8.ka")

    kappa_parser.parse_file(kappa_file_path)
    n_rules_expected = 121
    n_agents_expected = 10


def test_parse():
    test_kappa = """
    A(s[.]), S(a[.]) -> A(s[1]), S(a[1])    @	1
    """

    test_kappa = """
    A(s[.])
    """

    ka = kappa_parser.parse(test_kappa)
    print(ka)
