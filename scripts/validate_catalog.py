from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog.toml"


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    path: Path
    mode: str
    expected: str
    values_path: Path | None = None


def resolve_repository_path(base: Path, relative: str, source: Path) -> Path:
    target = (base / relative).resolve()
    if target != ROOT and ROOT not in target.parents:
        raise ContractError(f"{source}: path escapes the repository: {relative}")
    if not target.exists():
        raise ContractError(f"{source}: missing path {relative}")
    return target


def load_scenarios() -> list[Scenario]:
    payload = tomllib.loads(CATALOG.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise ContractError("catalog version must equal 1")
    scenarios: list[Scenario] = []
    seen: set[str] = set()
    for item in payload.get("scenario", []):
        scenario_id = str(item.get("id", "")).strip()
        relative = str(item.get("path", "")).strip()
        mode = str(item.get("mode", "")).strip()
        expected = str(item.get("expected", "")).strip()
        values = str(item.get("values", "")).strip()
        if not scenario_id or scenario_id in seen:
            raise ContractError("scenario ids must be non-empty and unique")
        if mode not in {"raw-yaml", "kustomize", "helm"}:
            raise ContractError(f"unsupported scenario mode: {mode}")
        if expected not in {"valid", "parse-error", "contract-error"}:
            raise ContractError(f"unsupported expectation: {expected}")
        path = resolve_repository_path(ROOT, relative, CATALOG)
        values_path = resolve_repository_path(ROOT, values, CATALOG) if values else None
        if values_path is not None and mode != "helm":
            raise ContractError(f"{scenario_id}: values is only supported for helm scenarios")
        seen.add(scenario_id)
        scenarios.append(Scenario(scenario_id, path, mode, expected, values_path))
    if not scenarios:
        raise ContractError("catalog must contain at least one scenario")
    return scenarios


def validate_raw_yaml(path: Path) -> None:
    documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    if not documents:
        raise ContractError(f"{path}: no YAML documents")
    for index, document in enumerate(documents, start=1):
        if not isinstance(document, dict):
            raise ContractError(f"{path}#{index}: document must be an object")
        for key in ("apiVersion", "kind", "metadata"):
            if key not in document:
                raise ContractError(f"{path}#{index}: missing {key}")
        metadata = document["metadata"]
        if not isinstance(metadata, dict) or not str(metadata.get("name", "")).strip():
            raise ContractError(f"{path}#{index}: missing metadata.name")


def find_kustomization(path: Path) -> Path:
    config_path = next(
        (candidate for candidate in (path / "kustomization.yaml", path / "kustomization.yml") if candidate.exists()),
        None,
    )
    if config_path is None:
        raise ContractError(f"{path}: missing kustomization file")
    return config_path


def validate_kustomization_file(config_path: Path, visited: set[Path]) -> None:
    if config_path in visited:
        raise ContractError(f"{config_path}: cyclic kustomization reference")
    visited.add(config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("kind") not in {"Kustomization", "Component"}:
        raise ContractError(f"{config_path}: kind must be Kustomization or Component")
    resources = config.get("resources")
    if config.get("kind") == "Kustomization" and (not isinstance(resources, list) or not resources):
        raise ContractError(f"{config_path}: resources must be non-empty")
    for key in ("resources", "components"):
        references = config.get(key, [])
        if not isinstance(references, list):
            raise ContractError(f"{config_path}: {key} must be a list")
        for reference in references:
            if not isinstance(reference, str) or not reference.strip():
                raise ContractError(f"{config_path}: invalid {key} reference")
            target = resolve_repository_path(config_path.parent, reference, config_path)
            if target.is_dir():
                validate_kustomization_file(find_kustomization(target), visited)

    patches = config.get("patches", [])
    if not isinstance(patches, list):
        raise ContractError(f"{config_path}: patches must be a list")
    for patch in patches:
        relative = patch if isinstance(patch, str) else patch.get("path") if isinstance(patch, dict) else None
        if relative is not None:
            resolve_repository_path(config_path.parent, str(relative), config_path)
    visited.remove(config_path)


def validate_kustomize(path: Path) -> None:
    config_path = find_kustomization(path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("kind") != "Kustomization":
        raise ContractError(f"{config_path}: entrypoint kind must be Kustomization")
    validate_kustomization_file(config_path, set())


def validate_helm(path: Path, values_path: Path | None = None) -> None:
    chart_path = path / "Chart.yaml"
    chart = yaml.safe_load(chart_path.read_text(encoding="utf-8")) if chart_path.exists() else None
    if not isinstance(chart, dict) or chart.get("apiVersion") != "v2":
        raise ContractError(f"{path}: Chart.yaml apiVersion must equal v2")
    for key in ("name", "version"):
        if not str(chart.get(key, "")).strip():
            raise ContractError(f"{chart_path}: missing {key}")
    templates = path / "templates"
    if not templates.is_dir() or not any(templates.glob("*.yaml")):
        raise ContractError(f"{path}: chart templates are missing")
    if values_path is not None:
        values = yaml.safe_load(values_path.read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise ContractError(f"{values_path}: Helm values must be an object")


def validate_scenario(scenario: Scenario) -> str:
    try:
        if scenario.mode == "helm":
            validate_helm(scenario.path, scenario.values_path)
        else:
            validator = {
                "raw-yaml": validate_raw_yaml,
                "kustomize": validate_kustomize,
            }[scenario.mode]
            validator(scenario.path)
    except yaml.YAMLError:
        actual = "parse-error"
    except ContractError:
        actual = "contract-error"
    else:
        actual = "valid"
    if actual != scenario.expected:
        raise AssertionError(
            f"{scenario.scenario_id}: expected {scenario.expected}, observed {actual}"
        )
    return actual


def main() -> int:
    scenarios = load_scenarios()
    for scenario in scenarios:
        actual = validate_scenario(scenario)
        print(f"[완료] {scenario.scenario_id}: {actual}")
    print(f"[완료] catalog: {len(scenarios)} scenarios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
