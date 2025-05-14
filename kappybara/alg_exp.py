from typing import Self
from collections import deque
import math

from kappybara.pattern import Component


class AlgExp:
    """
    Algebraic expressions as specified by the Kappa language.
    """

    def __init__(self, type, **attrs):
        self.type = type
        self.attrs = attrs

    def evaluate(self, system: "System" = None):
        try:
            return self._evaluate(system)
        except KeyError as e:
            raise ValueError(f"Undefined variable in expression: {e}")

    def _evaluate(self, system: "System"):
        if self.type == "literal":
            return self.attrs["value"]

        elif self.type == "variable":
            name = self.attrs["name"]

            if system is None:
                raise ValueError(
                    f"{self} requires a System to evaluate, due to referenced variable '{name}'."
                )

            return system.variables[name].evaluate(system)

        elif self.type == "binary_op":
            left_val = self.attrs["left"].evaluate(system)
            right_val = self.attrs["right"].evaluate(system)
            op = self.attrs["operator"]
            if op == "+":
                return left_val + right_val
            elif op == "-":
                return left_val - right_val
            elif op == "*":
                return left_val * right_val
            elif op == "/":
                return left_val / right_val
            elif op == "^":
                return left_val**right_val
            elif op == "mod":
                return left_val % right_val
            else:
                raise ValueError(f"Unknown binary operator: {op}")

        elif self.type == "unary_op":
            child_val = self.attrs["child"].evaluate(system)
            op = self.attrs["operator"]
            if op == "[log]":
                return math.log(child_val)
            elif op == "[exp]":
                return math.exp(child_val)
            elif op == "[sin]":
                return math.sin(child_val)
            elif op == "[cos]":
                return math.cos(child_val)
            elif op == "[tan]":
                return math.tan(child_val)
            elif op == "[sqrt]":
                return math.sqrt(child_val)
            else:
                raise ValueError(f"Unknown unary operator: {op}")

        elif self.type == "list_op":
            children_vals = [child.evaluate(system) for child in self.attrs["children"]]
            op = self.attrs["operator"]
            if op == "[max]":
                return max(children_vals)
            elif op == "[min]":
                return min(children_vals)
            else:
                raise ValueError(f"Unknown list operator: {op}")

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

        elif self.type == "comparison":
            left_val = self.attrs["left"].evaluate(system)
            right_val = self.attrs["right"].evaluate(system)
            op = self.attrs["operator"]
            if op == "=":
                return left_val == right_val
            elif op == "<":
                return left_val < right_val
            elif op == ">":
                return left_val > right_val
            else:
                raise ValueError(f"Unknown comparison operator: {op}")

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

        elif self.type == "boolean_literal":
            return self.attrs["value"]

        elif self.type == "reserved_variable":
            value = self.attrs["value"]
            if value.type == "component_pattern":
                component: Component = value.attrs["value"]
                if system is None:
                    raise ValueError(
                        f"{self} requires a System to evaluate, due to referenced pattern {component}."
                    )

                return len(system.mixture._embeddings[component])
            else:
                raise NotImplementedError(
                    f"Reserved variable {value.type} not implemented yet."
                )

        else:
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
