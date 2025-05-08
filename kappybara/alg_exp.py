import math


class AlgExp:
    """
    Algebraic expressions as specified by the Kappa language.
    """

    def __init__(self, type, **attrs):
        self.type = type
        self.attrs = attrs

    def evaluate(self, mixture=None):
        if mixture is None:
            mixture = {}
        try:
            return self._evaluate(mixture)
        except KeyError as e:
            raise ValueError(f"Undefined variable in expression: {e}")

    def _evaluate(self, mixture):
        if self.type == "literal":
            return self.attrs["value"]

        elif self.type == "variable":
            return mixture.variables[self.attrs["name"]].evaluate(mixture)

        elif self.type == "binary_op":
            left_val = self.attrs["left"].evaluate(mixture)
            right_val = self.attrs["right"].evaluate(mixture)
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
            child_val = self.attrs["child"].evaluate(mixture)
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
            children_vals = [
                child.evaluate(mixture) for child in self.attrs["children"]
            ]
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
            return self.attrs["child"].evaluate(mixture)

        elif self.type == "ternary":
            cond_val = self.attrs["condition"].evaluate(mixture)
            return (
                self.attrs["true_expr"].evaluate(mixture)
                if cond_val
                else self.attrs["false_expr"].evaluate(mixture)
            )

        elif self.type == "comparison":
            left_val = self.attrs["left"].evaluate(mixture)
            right_val = self.attrs["right"].evaluate(mixture)
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
            left_val = self.attrs["left"].evaluate(mixture)
            right_val = self.attrs["right"].evaluate(mixture)
            return left_val or right_val

        elif self.type == "logical_and":
            left_val = self.attrs["left"].evaluate(mixture)
            right_val = self.attrs["right"].evaluate(mixture)
            return left_val and right_val

        elif self.type == "logical_not":
            child_val = self.attrs["child"].evaluate(mixture)
            return not child_val

        elif self.type == "boolean_literal":
            return self.attrs["value"]

        elif self.type == "reserved_variable":
            var = self.attrs["name"]
            if var == "inf":
                return math.inf
            else:
                raise NotImplementedError(
                    f"Reserved variable {var} not implemented yet."
                )

        else:
            raise ValueError(f"Unsupported node type: {self.type}")
