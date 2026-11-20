"""Regression checks for handler dependency injection."""
import ast
from pathlib import Path
import unittest


class HandlerDependencyTests(unittest.TestCase):
    def test_handlers_do_not_reference_uninjected_store(self):
        source = Path(__file__).parents[1] / "bot" / "handlers.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))

        failures = []
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            arguments = {
                argument.arg
                for argument in (
                    node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                )
            }
            if "store" in arguments:
                continue
            if any(
                isinstance(child, ast.Name)
                and child.id == "store"
                and isinstance(child.ctx, ast.Load)
                for child in ast.walk(node)
            ):
                failures.append(node.name)

        self.assertEqual(
            failures,
            [],
            "Handlers reference the MongoDB store without receiving it: "
            + ", ".join(failures),
        )


if __name__ == "__main__":
    unittest.main()
