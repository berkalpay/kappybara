from pathlib import Path
from lark import Lark, ParseTree


class KappaParser:
    """Don't instantiate: use `kappa_parser`"""

    def __init__(self) -> None:
        self._parser = Lark.open(
            str(Path(__file__).parent / "kappa.lark"),
            rel_to=__file__,
            parser="earley",
            # The basic lexer isn't required and isn't usually recommended
            lexer="dynamic",
            start="kappa_input",
            # Disabling these slightly improves speed
            propagate_positions=False,
            maybe_placeholders=False,
        )

    def parse(self, text: str) -> ParseTree:
        return self._parser.parse(text)

    def parse_file(self, filepath: str) -> ParseTree:
        with open(filepath, "r") as file:
            return self._parser.parse(file.read())


kappa_parser = KappaParser()
