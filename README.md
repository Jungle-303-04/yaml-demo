# yaml-demo

Opsia의 저장소 탐색, YAML 검증, Kustomize 렌더링, Helm 렌더링을 확인하는 공개 테스트 카탈로그다.

## 주요 기능

- Kubernetes workload, network, policy, autoscaling, batch, stateful YAML을 제공한다.
- 하나의 multi-document 파일에서 CRD와 Custom Resource의 탐색 순서를 검증한다.
- 같은 애플리케이션을 raw YAML, Kustomize, Helm 경로로 검증한다.
- Kustomize component, ConfigMap generator, patch와 Helm values override의 렌더 차이를 확인한다.
- Argo CD, Flux, Prometheus Operator CRD 예제를 포함한다.
- 구문 오류와 Kubernetes 필수 필드 오류를 분리해 실패 처리를 확인한다.
- `catalog.toml`을 단일 테스트 목록으로 사용한다.

## 설치 방법

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

## 사용법

```bash
python3 scripts/validate_catalog.py
python3 -m unittest discover -s tests -v
make render
```

Opsia 저장소 연결 화면에서는 다음 값을 사용한다.

```text
Repository: Jungle-303-04/yaml-demo
Branch: main
Raw YAML: manifests/base/workloads.yaml
Kustomize: manifests/overlays/dev
Kustomize component: manifests/overlays/diagnostics
Helm: charts/demo-app
Helm values: charts/demo-app/values-staging.yaml
```

`catalog.toml`의 `helm-values-override`는 같은 차트에 별도 values 파일을 적용해 diff를 확인한다. 모든 Kustomize 참조는 저장소 내부 경로만 사용하며 Helm 외부 의존성은 없다.

`invalid/` 아래 파일과 이 저장소의 다른 예제는 렌더·탐색 검증 전용이다. 실제 클러스터에 적용하지 않는다.

## demo-server 배포

실제 적용 대상은 `demo-server` 클러스터다. 유효한 dev overlay를 직접 적용하거나, 같은 클러스터에 설치된
Argo CD/Flux가 저장소를 동기화하도록 아래 진입점 중 하나를 사용한다.

```bash
kubectl --context demo-server apply -k manifests/overlays/dev
kubectl --context demo-server apply -f gitops/argo/application.yaml
kubectl --context demo-server apply -f gitops/flux/kustomization.yaml
```

Argo CD와 Flux 매니페스트의 in-cluster destination은 위 명령을 실행한 `demo-server` 자체를 뜻한다.
`invalid/` 경로는 오류 계약 검증 전용이므로 어떤 배포 경로에서도 적용하지 않는다.
