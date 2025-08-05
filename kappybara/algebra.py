import math
import operator
from collections import deque
from typing import Self, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from kappybara.pattern import Component
    from kappybara.system import System


string_to_operator = {
    # Unary
    "[log]": math.log,
    "[exp]": math.exp,
    "[sin]": math.sin,
    "[cos]": math.cos,
    "[tan]": math.tan,
    "[sqrt]": math.sqrt,
    # Binary
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "^": operator.pow,
    "mod": operator.mod,
    # Comparisons
    "=": operator.eq,
    "<": operator.lt,
    ">": operator.gt,
    # List
    "[max]": max,
    "[min]": min,
}


def parse_operator(kappa_operator: str) -> Callable:
    """Takes a Kappa string operator and returns a Python operator."""
    try:
        return string_to_operator[kappa_operator]
    except KeyError:
        raise ValueError(f"Unknown operator: {kappa_operator}")


class AlgExp:
    """Algebraic expressions as specified by the Kappa language."""

    def __init__(self, type, **attrs):
        self.type = type
        self.attrs = attrs

    @property
    def kappa_str(self) -> str:
        if self.type in ("literal", "boolean_literal"):
            return str(self.evaluate())
        elif self.type in ("variable", "defined_constant"):
            return self.attrs["name"]
        elif self.type in ("binary_op", "comparison"):
            return f"({self.attrs['left'].kappa_str}) {self.attrs['operator']} ({self.attrs['right'].kappa_str})"
        elif self.type == "unary_op":
            return f"{self.attrs['operator']} ({self.attrs['child'].kappa_str})"
        elif self.type == "list_op":
            return f"{self.attrs["operator"]} ({", ".join(child.kappa_str for child in self.attrs['children'])})"
        elif self.type == "parentheses":
            return self.attrs["child"].kappa_str
        # TODO: ternary_op
        elif self.type in ("logical_or", "logical_and"):
            op = {"logical_or": "||", "logical_and": "&&"}
            return f"({self.attrs['left'].kappa_str}) {op[self.type]} ({self.attrs['right'].kappa_str})"
        elif self.type == "logical_not":
            return f"[not] ({self.attrs['child'].kappa_str})"
        elif self.type == "reserved_variable":
            return self.attrs["value"].kappa_str
        elif self.type == "component_pattern":
            return f"|{self.attrs['value'].kappa_str}|"
        raise ValueError(f"Unsupported node type: {self.type}")

    def evaluate(self, system: Optional["System"] = None) -> int | float:
        try:
            return self._evaluate(system)
        except KeyError as e:
            raise ValueError(f"Undefined variable in expression: {e}")

    def _evaluate(self, system: "System") -> int | float:
        if self.type in ("literal", "boolean_literal"):
            return self.attrs["value"]

        elif self.type == "variable":
            name = self.attrs["name"]
            if system is None:
                raise ValueError(
                    f"{self} requires a System to evaluate, due to referenced variable '{name}'."
                )
            return system[name]

        elif self.type in ("binary_op", "comparison"):
            left_val = self.attrs["left"].evaluate(system)
            right_val = self.attrs["right"].evaluate(system)
            return parse_operator(self.attrs["operator"])(left_val, right_val)

        elif self.type == "unary_op":
            child_val = self.attrs["child"].evaluate(system)
            return parse_operator(self.attrs["operator"])(child_val)

        elif self.type == "list_op":
            children_vals = [child.evaluate(system) for child in self.attrs["children"]]
            return parse_operator(self.attrs["operator"])(children_vals)

        elif self.type == "defined_constant":
            const = self.attrs["name"]
            if const == "[pi]":
                return math.pi
            else:
                raise ValueError(f"Unknown constant: {const}")

        elif self.type == "parentheses":
            return self.attrs["child"].evaluate(system)

        elif self.type == "ternary":
            cond_val = self.attrs["condition"].evaluate(system)
            return (
                self.attrs["true_expr"].evaluate(system)
                if cond_val
                else self.attrs["false_expr"].evaluate(system)
            )

        elif self.type == "logical_or":
            left_val = self.attrs["left"].evaluate(system)
            right_val = self.attrs["right"].evaluate(system)
            return left_val or right_val

        elif self.type == "logical_and":
            left_val = self.attrs["left"].evaluate(system)
            right_val = self.attrs["right"].evaluate(system)
            return left_val and right_val

        elif self.type == "logical_not":
            child_val = self.attrs["child"].evaluate(system)
            return not child_val

        elif self.type == "reserved_variable":
            value = self.attrs["value"]
            if value.type == "component_pattern":
                component: Component = value.attrs["value"]
                if system is None:
                    raise ValueError(
                        f"{self} requires a System to evaluate, due to referenced pattern {component}."
                    )
                return system.count_observable(component)
            else:
                raise NotImplementedError(
                    f"Reserved variable {value.type} not implemented yet."
                )

        raise ValueError(f"Unsupported node type: {self.type}")

    def filter(self, type_str: str) -> list[Self]:
        """
        Returns all nodes in the expression tree whose type matches the provided string.

        NOTE: This doesn't catch stuff that's indirectly nested in named variables.
              If you are trying to search through the entire expression tree, including
              following AlgExp's with type "variable" to their referred contents, this
              won't do what you might expect.
        """
        result = []
        stack = deque([self])  # DFS from the root

        while stack:
            node = stack.pop()
            if node.type == type_str:
                result.append(node)

            # Add child nodes to the stack
            if hasattr(node, "attrs"):
                for attr_value in node.attrs.values():
                    if isinstance(attr_value, AlgExp):
                        stack.append(attr_value)
                    elif isinstance(attr_value, (list, tuple)):
                        stack.extend(v for v in attr_value if isinstance(v, AlgExp))

        return result
