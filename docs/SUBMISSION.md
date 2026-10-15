# Submission runbook and evidence checklist

Deadline: 16 Oct 2026, 11:59 PM. Late penalty: 5 points per 24 hours.
Capture each screenshot below into `docs/screenshots/` and attach them to the Google Form.

## 0. One-time setup

1. Create a **public** GitHub repo (e.g. `clinicq-devops-capstone`) and push this project (see the commit plan in section 1).
2. Repo Settings -> Actions -> General -> Workflow permissions: **Read and write**.
3. After the first successful run, GHCR packages are private by default. Either make both packages public
   (Package settings -> Change visibility) or create an image pull secret and set `imagePullSecrets` in the chart.
4. Authenticate AWS: `aws login` (or `aws configure`). Never commit keys.

## 1. Git (M3, needs 10+ meaningful commits)

Suggested commit sequence (one commit per step):

```text
feat(backend): add FastAPI app with doctors and appointments models
feat(backend): add appointment CRUD, stats and double-booking guard
feat(db): add Alembic migrations with seed doctors
test(backend): add pytest suite with in-memory test database
feat(frontend): add React booking console
build(docker): add multi-stage non-root Dockerfiles and compose stack
ci: add GitHub Actions pipeline with pytest, Trivy and GHCR push
build(infra): add Terraform for AWS VPC and EKS
feat(helm): add ClinicQ Helm chart with ingress, HPA and migration job
feat(monitoring): add Prometheus values and Grafana dashboard
docs: add troubleshooting labs, README and submission runbook
```

Evidence: screenshot of the GitHub commit history.

## 2. Local run (M1, M2, M4)

| Evidence | Command |
|---|---|
| pytest passing | `cd backend && pytest -v` |
| Compose running | `docker compose up --build` |
| App in browser | http://localhost:3000 (a screenshot is already in `docs/screenshots/01-app-running.png`) |
| Swagger | http://localhost:8000/docs |
| Non-root proof | `docker compose exec backend id -u` -> 10001, `docker compose exec frontend id -u` -> 101 |
| DB table (demo) | `docker compose exec postgres psql -U clinicq -d clinicq -c "select * from appointments;"` |

## 3. CI/CD, Trivy, GHCR (M5, M6)

Push to `main`. Evidence:
- Green Actions run URL (jobs: test, build-scan-push; deploy is skipped until the cluster exists).
- Screenshot of a Trivy step's output.
- GHCR packages page showing `clinicq-backend` and `clinicq-frontend` with SHA tags.

**Trivy explanation to submit (edit to match your final run):**
> Trivy scanned both container images (OS packages and Python/Node dependencies) for HIGH and CRITICAL
> vulnerabilities with fixes available. On my first scan it found three HIGH CVEs in the backend's `starlette`
> package (for example CVE-2025-62727, a denial of service through Range header merging) pulled in by an older
> FastAPI pin, and two in the frontend's Alpine `zlib` and `nghttp2` libraries. I fixed them by upgrading FastAPI,
> Starlette and the instrumentator, and by running `apk upgrade` in the runtime image; the rescan reported zero
> findings, and the pipeline is set to fail (`exit-code: 1`) if any reappear.

## 4. Terraform (M7)

```bash
cd terraform
terraform init
terraform plan -out tfplan          # screenshot the plan summary
terraform apply tfplan              # ~15 minutes
```
Evidence: plan output, AWS Console screenshots of the VPC (2 public subnets) and the EKS cluster in `ap-south-1`.
At the end: `terraform destroy` and screenshot the "Destroy complete" line. **Do this the same day** - EKS, NAT
gateway and 3 x t3.medium cost roughly $0.25-0.30/hour.

Already verified locally: `terraform init` and `terraform validate` succeed.

## 5. Kubernetes + Helm + Ingress + HPA (M8)

```bash
aws eks update-kubeconfig --region ap-south-1 --name clinicq-eks
kubectl apply -f k8s/namespace.yaml
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace -f monitoring/ingress-nginx-values.yaml
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring --create-namespace -f monitoring/prometheus-values.yaml
kubectl apply -f monitoring/dashboards/clinicq-dashboard.yaml
```

Get the cluster credentials into GitHub so the pipeline can deploy:
```bash
# base64 of a kubeconfig -> repo secret KUBE_CONFIG_DATA ; also add secret DB_PASSWORD
aws eks update-kubeconfig --region ap-south-1 --name clinicq-eks --kubeconfig ./kc.yaml
base64 -w0 kc.yaml            # paste into GitHub secret, then delete kc.yaml
```
Note: that kubeconfig uses `aws eks get-token`, which needs AWS credentials on the runner. Simplest options:
(a) run the first `helm upgrade --install` yourself from your laptop (command in README) and use the pipeline
deploy for the live demo only if you add AWS credentials as secrets, or (b) skip pipeline deploy and demo
`helm upgrade` manually. The rubric requires the pipeline to build/scan/push; deploy-by-pipeline is a bonus.

Evidence:
```bash
kubectl get pods -n clinicq        # all Running, 2 backend + 2 frontend + postgres
kubectl get svc -n clinicq
helm list -n clinicq
kubectl get ingress -n clinicq     # open the ADDRESS in a browser -> screenshot
kubectl get hpa -n clinicq
```
HPA demo: `scripts/load-test.sh http://<ingress-address> 180 30` while running `kubectl get hpa -n clinicq -w`.

## 6. Observability (M9)

```bash
kubectl port-forward -n clinicq svc/clinicq-backend 8000:8000     # then: curl localhost:8000/metrics
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090   # Status -> Targets: clinicq UP
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3001:80   # admin / admin-change-me
```
Open the "ClinicQ - Application Overview" dashboard, run the load test, screenshot populated panels.

## 7. Troubleshooting demo (live)

```bash
kubectl apply -f troubleshooting/broken-image.yaml     # ImagePullBackOff -> kubectl describe pod -> fix tag
kubectl apply -f troubleshooting/broken-service.yaml   # no endpoints -> label mismatch -> patch selector
kubectl apply -f troubleshooting/broken-probe.yaml     # never Ready -> bad probe path
kubectl delete ns clinicq-lab                          # cleanup
```
Each file has the diagnosis and the fix in its header comment.

## 8. Live demo script (3 minutes)

1. Edit a UI string in `frontend/src/main.jsx`, commit, push.
2. Show the Actions run: test -> build -> Trivy -> push.
3. Show the new SHA tag in GHCR; `helm upgrade --install ... --set backend.tag=<sha>`; `kubectl rollout status`.
4. Refresh the app via the Ingress address.
5. Show Grafana, then break a Service and fix it.
