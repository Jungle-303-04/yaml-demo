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

        self.assertEqual(len(observed), 17)
        self.assertEqual(observed["syntax-error"], "parse-error")
        self.assertEqual(observed["missing-kind"], "contract-error")
        self.assertEqual(observed["helm-chart"], "valid")
        self.assertEqual(observed["helm-values-override"], "valid")
        self.assertEqual(observed["kustomize-dev"], "valid")
        self.assertEqual(observed["kustomize-component-generator-patch"], "valid")
        self.assertEqual(observed["crd-and-custom-resource"], "valid")

    def test_helm_override_is_catalogued_without_changing_the_default_chart(self) -> None:
        scenarios = {scenario.scenario_id: scenario for scenario in validator.load_scenarios()}

        default = scenarios["helm-chart"]
        override = scenarios["helm-values-override"]
        self.assertIsNone(default.values_path)
        self.assertEqual(override.path, default.path)
        self.assertEqual(override.values_path, ROOT / "charts/demo-app/values-staging.yaml")

    def test_kustomize_references_remain_inside_the_repository(self) -> None:
        overlay = ROOT / "manifests/overlays/diagnostics"

        validator.validate_kustomize(overlay)

    def test_repository_connection_values_are_stable(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Jungle-303-04/yaml-demo", readme)
        self.assertIn("manifests/base/workloads.yaml", readme)
        self.assertIn("manifests/overlays/dev", readme)
        self.assertIn("manifests/overlays/diagnostics", readme)
        self.assertIn("charts/demo-app", readme)
        self.assertIn("charts/demo-app/values-staging.yaml", readme)
        self.assertIn("kubectl --context demo-server apply -k manifests/overlays/dev", readme)

    def test_gitops_and_overlay_target_demo_server(self) -> None:
        argo = (ROOT / "gitops/argo/application.yaml").read_text(encoding="utf-8")
        flux = (ROOT / "gitops/flux/kustomization.yaml").read_text(encoding="utf-8")
        overlay = (ROOT / "manifests/overlays/dev/kustomization.yaml").read_text(
            encoding="utf-8",
        )

        self.assertIn("opsia.dev/target-cluster: demo-server", argo)
        self.assertIn("opsia.dev/target-cluster: demo-server", flux)
        self.assertIn("opsia.dev/cluster-role: demo-server", overlay)
        self.assertNotIn("cluster-1", argo + flux + overlay)
        self.assertNotIn("cluster-2", argo + flux + overlay)

    def test_read_only_nginx_has_bounded_runtime_storage(self) -> None:
        workload = (ROOT / "manifests/base/workloads.yaml").read_text(encoding="utf-8")

        self.assertIn("readOnlyRootFilesystem: true", workload)
        self.assertIn("mountPath: /tmp", workload)
        self.assertIn("medium: Memory", workload)
        self.assertIn("sizeLimit: 32Mi", workload)


if __name__ == "__main__":
    unittest.main()
