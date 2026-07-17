from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def render(*command: str) -> list[dict[str, Any]]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return [document for document in yaml.safe_load_all(completed.stdout) if isinstance(document, dict)]


def find_resource(
    documents: list[dict[str, Any]],
    kind: str,
    name: str,
) -> dict[str, Any]:
    return next(
        document
        for document in documents
        if document.get("kind") == kind and document.get("metadata", {}).get("name") == name
    )


class RenderTest(unittest.TestCase):
    def test_crd_precedes_its_custom_resource(self) -> None:
        documents = list(
            yaml.safe_load_all(
                (ROOT / "manifests/extensions/widget-crd.yaml").read_text(encoding="utf-8")
            )
        )

        self.assertEqual([document["kind"] for document in documents], ["CustomResourceDefinition", "Widget"])
        self.assertEqual(documents[0]["spec"]["group"], documents[1]["apiVersion"].split("/", 1)[0])

    def test_kustomize_component_changes_the_rendered_deployment(self) -> None:
        documents = render("kubectl", "kustomize", "manifests/overlays/diagnostics")
        deployment = find_resource(documents, "Deployment", "diagnostics-demo-api")
        generated = find_resource(documents, "ConfigMap", "diagnostics-demo-diagnostics")

        self.assertEqual(generated["data"]["LOG_LEVEL"], "debug")
        self.assertEqual(
            deployment["spec"]["template"]["metadata"]["annotations"]["demo.opsia.dev/diagnostics"],
            "enabled",
        )
        references = deployment["spec"]["template"]["spec"]["containers"][0]["envFrom"]
        self.assertIn({"configMapRef": {"name": "diagnostics-demo-diagnostics"}}, references)

    def test_helm_values_override_changes_rendered_fields(self) -> None:
        default = render("helm", "template", "yaml-demo", "charts/demo-app")
        staging = render(
            "helm",
            "template",
            "yaml-demo-staging",
            "charts/demo-app",
            "--values",
            "charts/demo-app/values-staging.yaml",
        )
        default_deployment = find_resource(default, "Deployment", "yaml-demo-demo-app")
        staging_deployment = find_resource(staging, "Deployment", "yaml-demo-staging-demo-app")
        staging_service = find_resource(staging, "Service", "yaml-demo-staging-demo-app")

        self.assertEqual(default_deployment["spec"]["replicas"], 2)
        self.assertEqual(staging_deployment["spec"]["replicas"], 4)
        self.assertTrue(
            staging_deployment["spec"]["template"]["spec"]["containers"][0]["image"].endswith(
                ":1.27.5-alpine"
            )
        )
        self.assertEqual(staging_service["spec"]["ports"][0]["port"], 8080)


if __name__ == "__main__":
    unittest.main()
