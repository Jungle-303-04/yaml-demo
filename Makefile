.PHONY: test validate render

validate:
	python3 scripts/validate_catalog.py

render:
	kubectl kustomize manifests/base >/dev/null
	kubectl kustomize manifests/overlays/dev >/dev/null
	kubectl kustomize manifests/overlays/staging >/dev/null
	kubectl kustomize manifests/overlays/diagnostics >/dev/null
	helm lint charts/demo-app
	helm lint charts/demo-app --values charts/demo-app/values-staging.yaml
	helm template yaml-demo charts/demo-app >/dev/null
	helm template yaml-demo-staging charts/demo-app --values charts/demo-app/values-staging.yaml >/dev/null

test: validate render
	python3 -m unittest discover -s tests -v
