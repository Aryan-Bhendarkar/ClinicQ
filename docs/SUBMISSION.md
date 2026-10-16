# Submission evidence (module by module)

Repository: https://github.com/Aryan-Bhendarkar/ClinicQ
Region: `ap-south-1`. All screenshots are in [docs/screenshots/](screenshots/).

| Module | What it shows | Evidence |
|---|---|---|
| M1 Application | React UI + FastAPI + PostgreSQL via Compose, 12 endpoints, 2 Alembic migrations | `01-app-running.png` |
| M2 Testing | 15 pytest tests, in-memory SQLite test DB, `pytest.ini` + `conftest.py` | `m2-01-pytest-passing.png` |
| M3 Git | 18+ commits with descriptive messages, `.gitignore` for env, caches, venv, node_modules, tfstate | `m3-01-commit-history.png` |
| M4 Docker | Multi-stage frontend, non-root users (uid 10001 and 101), 3-service Compose | `01-app-running.png`, `backend/Dockerfile`, `frontend/Dockerfile` |
| M5 CI/CD | pytest, frontend build, image build, SHA-tagged push to GHCR | `m5-01-github-actions-run-success.png`, `m5-02-ghcr-package-sha-tags.png` |
| M6 Security | Trivy scans both images, fails on HIGH/CRITICAL | `m6-01-trivy-backend-scan.png` |
| M7 Terraform | VPC (2 public + 2 private subnets, NAT), EKS, node group, EBS CSI, metrics-server | `m7-01` to `m7-05` |
| M8 Kubernetes + Helm | Helm release, 2+ replicas, ClusterIP Services, Ingress, HPA | `m8-01` to `m8-06` |
| M9 Observability | `/metrics`, Prometheus target UP, Grafana dashboard with live panels | `m9-01` to `m9-03` |
| M10 Docs | README, this file, presentation script | `README.md`, `docs/PRESENTATION.md` |

## M6 - Trivy explanation

Trivy scanned both container images, covering OS packages and Python or Node dependencies, for HIGH and
CRITICAL vulnerabilities that have a fix available. My first local scan of the backend image found three HIGH
CVEs in `starlette` (for example CVE-2025-62727, a denial of service through Range header merging), pulled in
by an older FastAPI pin. The frontend image had two more in Alpine's `zlib` and `nghttp2`. I fixed them by
upgrading FastAPI, Starlette and the Prometheus instrumentator, and by running `apk upgrade` in the runtime
image. The rescan reported zero findings, which is what the pipeline's backend scan shows. The scan step uses
`--exit-code 1`, so any new HIGH or CRITICAL finding fails the build before anything is pushed.

## Problems hit while deploying, and how they were fixed

These are worth explaining in the presentation: each one is a real troubleshooting case.

| Symptom | Root cause | Fix |
|---|---|---|
| Node group stuck `CREATING`, add-ons `DEGRADED` | AWS Free Tier plan rejects `t3.medium` (`AsgInstanceLaunchFailures`) | Use `m7i-flex.large`, which is free-tier eligible |
| Nodes could not become Ready | Networking add-ons were created after the node group | `before_compute = true` for `vpc-cni` and `kube-proxy` |
| Postgres pod `Pending`, PVC unbound | EKS has no default StorageClass for the CSI driver | `k8s/storageclass.yaml` (default `gp3`, `ebs.csi.aws.com`) |
| HPA showed `<unknown>` | Control plane could not reach metrics-server on port 10251 | Security group rule in Terraform |
| Ingress had no address | AWS refused load balancer creation on this account | Reached the Ingress with `kubectl port-forward` |
| `terraform apply` failed with expired token | Short-lived exported credentials | `credential_process` profile that refreshes automatically |
| Trivy action failed to install | Pinned action tag could not fetch its Trivy binary | Run Trivy from its container image |

## Deployment note (be upfront about this)

The pipeline builds, tests, scans and pushes the images on every push to `main`. The `deploy` job only runs
when a `KUBE_CONFIG_DATA` secret is configured; it was not, so the job completes without deploying. The cluster
was deployed with `helm upgrade --install` from my laptop using the SHA-tagged images the pipeline pushed.

## How to reproduce

```powershell
# 1. Local
docker compose up --build            # http://localhost:3000
cd backend; pytest -v

# 2. AWS (sign in with `aws login`; add a profile that refreshes credentials)
#    ~/.aws/config:  [profile tf]
#                    credential_process = aws configure export-credentials --profile default --format process
#                    region = ap-south-1
$env:AWS_PROFILE = "tf"
cd terraform; terraform init; terraform plan -out tfplan; terraform apply tfplan
aws eks update-kubeconfig --region ap-south-1 --name clinicq-eks

# 3. Cluster add-ons and app
kubectl apply -f k8s/namespace.yaml -f k8s/storageclass.yaml
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring --create-namespace -f monitoring/prometheus-values.yaml
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace -f monitoring/ingress-nginx-values.yaml
kubectl apply -f monitoring/dashboards/clinicq-dashboard.yaml
helm upgrade --install clinicq ./helm/clinicq -n clinicq -f helm/clinicq/values-prod.yaml `
  --set backend.image=ghcr.io/<user>/clinicq-backend --set frontend.image=ghcr.io/<user>/clinicq-frontend `
  --set backend.tag=<commit-sha> --set frontend.tag=<commit-sha> --set postgres.password=<generated-secret> --wait

# 4. Reach it (this account cannot create load balancers)
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80     # app
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090   # Prometheus
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3001:80 # Grafana: admin / admin-change-me

# 5. Tear down (run from the terraform folder)
helm uninstall clinicq -n clinicq; helm uninstall kube-prometheus-stack -n monitoring; helm uninstall ingress-nginx -n ingress-nginx
kubectl delete namespace clinicq clinicq-lab monitoring ingress-nginx
terraform destroy
```

## Troubleshooting lab (live demo)

```powershell
kubectl apply -f troubleshooting/broken-image.yaml     # ImagePullBackOff: describe pod -> fix the tag
kubectl apply -f troubleshooting/broken-service.yaml   # no endpoints: selector does not match pod labels
kubectl apply -f troubleshooting/broken-probe.yaml     # pod never Ready: wrong readiness path
kubectl delete namespace clinicq-lab
```
Each file's header comment contains the exact investigation commands and the fix.
