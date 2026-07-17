from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_catalog",
    ROOT / "scripts" / "validate_catalog.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("validator module is unavailable")
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class CatalogTest(unittest.TestCase):
    def test_every_scenario_matches_its_expected_result(self) -> None:
        scenarios = validator.load_scenarios()
        observed = {
            scenario.scenario_id: validator.validate_scenario(scenario)
            for scenario in scenarios
        }

        self.assertGreaterEqual(len(observed), 14)
        self.assertEqual(observed["syntax-error"], "parse-error")
        self.assertEqual(observed["missing-kind"], "contract-error")
        self.assertEqual(observed["helm-chart"], "valid")
        self.assertEqual(observed["kustomize-dev"], "valid")

    def test_repository_connection_values_are_stable(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Jungle-303-04/yaml-demo", readme)
        self.assertIn("manifests/overlays/dev", readme)
        self.assertIn("charts/demo-app", readme)


if __name__ == "__main__":
    unittest.main()
