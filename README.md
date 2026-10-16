# ClinicQ - Clinic Appointment Booking

DevOps Final Capstone by **Aryan Bhendarkar**.

ClinicQ is a front-desk console for a medical clinic. Staff book appointments for patients with a doctor, see the
schedule, mark visits completed or cancelled, and the system refuses to double-book a doctor's time slot.

The application is intentionally small. The focus is the delivery path: a commit on a laptop becomes a tested,
scanned, versioned container image, deployed by ArgoCD (GitOps) to a Kubernetes cluster that Terraform built on AWS, and
watched with Prometheus and Grafana.

| Deliverable | Location |
|---|---|
| Presentation video (MP4) | [demo/ClinicQ-Presentation.mp4](demo/) |
| Slide deck (PPT and PDF) | [demo/ClinicQ-DevOps-Capstone.pptx](demo/ClinicQ-DevOps-Capstone.pptx), [PDF](demo/ClinicQ-DevOps-Capstone.pdf) |
| Evidence, problems solved, reproduction steps | [docs/SUBMISSION.md](docs/SUBMISSION.md) |
| Screenshots | [docs/screenshots/](docs/screenshots/) |

![ClinicQ UI](docs/screenshots/01-app-running.png)

## Contents

1. [Architecture](#architecture)
2. [Tech stack](#tech-stack)
3. [Repository layout](#repository-layout)
4. [Run locally](#run-locally)
5. [REST API](#rest-api)
6. [Testing](#testing)
7. [Docker](#docker)
8. [CI/CD pipeline](#cicd-pipeline)
9. [Security scanning](#security-scanning)
10. [Terraform (AWS)](#terraform-aws)
11. [Kubernetes and Helm](#kubernetes-and-helm)
12. [GitOps with ArgoCD](#gitops-with-argocd)
13. [Observability](#observability)
14. [Troubleshooting lab](#troubleshooting-lab)
15. [Design decisions](#design-decisions)
16. [Known limitations](#known-limitations)
17. [Evidence](#evidence)

## Architecture

```text
Developer -> GitHub -> GitHub Actions
                         |- pytest (quality gate)
                         |- frontend build
                         |- Docker build (backend + frontend)
                         |- Trivy scan (fails on HIGH/CRITICAL)
                         |- push to GHCR, tagged with the commit SHA
                         '- commit the new image tag to helm/clinicq/values-prod.yaml
                                        |
                         ArgoCD watches the repo and syncs the cluster (GitOps)
                                        |
Terraform -> AWS VPC (2 public + 2 private subnets, NAT) -> EKS (managed node group)
                                        |
        Ingress (nginx) --/-->  frontend (React + Nginx)  x2
                        --/api-> backend  (FastAPI)       x2..6 (HPA) --> PostgreSQL (StatefulSet + EBS volume)
                                        |
                     Prometheus (ServiceMonitor scrapes /metrics) -> Grafana dashboard
```

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, responsive CSS, served by unprivileged Nginx |
| Backend | FastAPI, SQLAlchemy 2, Alembic, Pydantic, prometheus-fastapi-instrumentator |
| Database | PostgreSQL 16 |
| Tests | Pytest, FastAPI TestClient, in-memory SQLite |
| Containers | Docker multi-stage builds, non-root users, Docker Compose |
| CI/CD | GitHub Actions, GitHub Container Registry (GHCR) |
| Security | Trivy image scanning |
| Infrastructure as code | Terraform (VPC, EKS, add-ons) |
| Orchestration | Kubernetes 1.31 on Amazon EKS, Helm, Ingress NGINX, HPA |
| GitOps | ArgoCD, automated sync with prune and self-heal |
| Observability | kube-prometheus-stack (Prometheus, Grafana), ServiceMonitor |

## Repository layout

```text
backend/            FastAPI app, Alembic migrations, pytest tests, Dockerfile
frontend/           React app, nginx template, multi-stage Dockerfile
docker-compose.yml  full local stack (postgres + backend + frontend)
terraform/          AWS VPC + EKS + add-ons (see terraform/README.md)
helm/clinicq/       Helm chart: deployments, services, ingress, HPA, postgres, migration job, ServiceMonitor
argocd/             ArgoCD Application that deploys the chart from this repository
k8s/                namespace and default StorageClass manifests
monitoring/         Prometheus/Grafana/ingress-nginx values and the Grafana dashboard
troubleshooting/    three deliberately broken manifests for the live demo
scripts/            load-test.sh
.github/workflows/  CI/CD pipeline
demo/               slide deck (PPT and PDF)
docs/               submission evidence and screenshots
```

## Run locally

Requirements: Docker Desktop.

```bash
docker compose up --build
# UI        http://localhost:3000
# API docs  http://localhost:8000/docs
# metrics   http://localhost:8000/metrics
docker compose down -v      # stop and delete the database volume
```

Compose starts PostgreSQL, waits for it to be healthy, runs the Alembic migrations on backend start, then starts the
frontend. The backend can also be run without Docker:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg://clinicq:clinicq@localhost:5432/clinicq'
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## REST API

| Method | Path | Purpose |
|---|---|---|
| GET | `/`, `/health`, `/ready`, `/metrics` | info, liveness, readiness (checks the database), Prometheus metrics |
| GET / POST | `/api/doctors` | list / add doctors |
| DELETE | `/api/doctors/{id}` | remove a doctor (409 if they have appointments) |
| GET | `/api/appointments?status=&doctor_id=` | list, filterable |
| POST | `/api/appointments` | book (409 if the slot is taken, 422 for an unknown doctor) |
| GET / PUT / DELETE | `/api/appointments/{id}` | read, update (reschedule, change status), delete |
| GET | `/api/appointments/stats` | counts for the dashboard cards |

Custom Prometheus counters: `clinicq_appointments_booked_total` and `clinicq_appointments_cancelled_total`, in
addition to the request count and latency metrics from the FastAPI instrumentator.

Database schema, managed by Alembic (`backend/alembic/versions/`): `doctors` and `appointments` (foreign key to
doctors, indexes on doctor, time and status), plus a second migration that seeds four doctors.

## Testing

```bash
cd backend && pytest -v
```

15 tests cover health, readiness, metrics, doctors and every appointment endpoint including the double-booking
guard. Tests use an in-memory SQLite database through a FastAPI dependency override (`tests/conftest.py`), never the
real database. They run before any image is built, so a failing test stops the pipeline.

## Docker

- `backend/Dockerfile`: `python:3.12-slim`, non-root user (uid 10001), health check, runs migrations then Uvicorn.
- `frontend/Dockerfile`: multi-stage. Node builds the React app, then `nginx-unprivileged` serves it as uid 101 on
  port 8080. Nginx proxies `/api` to the backend through a `BACKEND_URL` environment variable, so the same image
  works in Compose and Kubernetes.
- `docker-compose.yml`: postgres with a health check, backend, frontend.

## CI/CD pipeline

`.github/workflows/ci-cd.yml` runs on every push to `main` (and on pull requests):

1. **test**: install dependencies, `pytest -v`, then build the React frontend.
2. **build-scan-push** (needs test): build both images, scan both with Trivy, log in to GHCR, push.
   Images are tagged with the **commit SHA**, never `latest`. The push steps come after the scan steps, so nothing
   that fails a scan is published.
3. **update-gitops** (needs build-scan-push): writes the new commit SHA into the image tags of
   `helm/clinicq/values-prod.yaml` and commits it. ArgoCD sees that commit and rolls the cluster forward, so the
   pipeline needs no cluster credentials. The job uses the built-in `GITHUB_TOKEN`; no repository secrets are required.

## Security scanning

Trivy scans both images for HIGH and CRITICAL vulnerabilities that have a fix, with `--exit-code 1`, so the build
fails on any finding. The first scan of this project found three HIGH CVEs in `starlette` (pulled in by an old
FastAPI pin) and two in Alpine `zlib` and `nghttp2`. They were fixed by upgrading FastAPI, Starlette and the
instrumentator and running `apk upgrade` in the runtime image. Both scans in the pipeline now report zero findings.
No credentials are committed; `.gitignore` excludes env files, caches, virtual environments, `node_modules` and
Terraform state and plans.

## Terraform (AWS)

`terraform/` creates, in `ap-south-1`:

- a VPC `10.20.0.0/16` with 2 public and 2 private subnets across 2 availability zones, an internet gateway and a NAT gateway
- an EKS cluster (Kubernetes 1.31) with a managed node group of 2 x `m7i-flex.large`
- EKS add-ons: `vpc-cni` and `kube-proxy` (installed before the nodes), `coredns`, `aws-ebs-csi-driver` with an IRSA
  role, and `metrics-server`
- a security group rule so the control plane can reach metrics-server on port 10251

```bash
cd terraform
terraform init
terraform plan -out tfplan        # 60 resources to add
terraform apply tfplan            # about 15 minutes
aws eks update-kubeconfig --region ap-south-1 --name clinicq-eks
terraform destroy                 # when finished, to stop AWS charges
```

Copy `terraform.tfvars.example` to `terraform.tfvars` to override defaults. See [terraform/README.md](terraform/README.md).

## Kubernetes and Helm

The chart in `helm/clinicq/` contains:

| Resource | Purpose |
|---|---|
| Deployments (backend, frontend) | 2 replicas each, probes, resource requests and limits, non-root security contexts |
| ClusterIP Services | stable networking for backend (8000), frontend (80) and PostgreSQL (5432) |
| StatefulSet + PVC | PostgreSQL on an EBS gp3 volume |
| Job (Helm hook) | runs `alembic upgrade head` after install and upgrade, so replicas never race to migrate |
| Ingress | `/api` goes to the backend, `/` to the frontend |
| HorizontalPodAutoscaler | backend scales between 2 and 6 pods at 50% CPU |
| ServiceMonitor | tells Prometheus to scrape the backend `/metrics` |
| Secret | database password, supplied at deploy time |

Cluster setup and deploy:

```bash
kubectl apply -f k8s/namespace.yaml -f k8s/storageclass.yaml     # gp3 default class for the Postgres volume
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring --create-namespace -f monitoring/prometheus-values.yaml
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace -f monitoring/ingress-nginx-values.yaml
kubectl apply -f monitoring/dashboards/clinicq-dashboard.yaml
# the database password is created in the cluster, never committed
kubectl create namespace clinicq
kubectl create secret generic clinicq-db -n clinicq --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 12)"
# deploy the app through ArgoCD (see the next section)
kubectl apply -f argocd/application.yaml
```

Check it:

```bash
kubectl get pods,svc,ingress,hpa -n clinicq
kubectl get application -n argocd
```

`values-dev.yaml` targets a local cluster (Docker Desktop, kind, minikube) with local images.

## GitOps with ArgoCD

ArgoCD runs in the `argocd` namespace and owns the application. `argocd/application.yaml` points it at this
repository: path `helm/clinicq`, values file `values-prod.yaml`, destination namespace `clinicq`, with automated sync,
**prune** (resources removed from Git are removed from the cluster) and **self-heal** (manual drift is reverted).

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
# the UI is only reached through a local tunnel, so serve it over plain HTTP (no certificate warning)
kubectl patch configmap argocd-cmd-params-cm -n argocd --type merge -p '{"data":{"server.insecure":"true"}}'
kubectl rollout restart deploy/argocd-server -n argocd
# this account cannot create load balancers, so treat an Ingress as healthy once it exists
kubectl patch configmap argocd-cm -n argocd --type merge --patch-file argocd/ingress-health.yaml
kubectl port-forward -n argocd svc/argocd-server 8081:80          # http://localhost:8081, user admin
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

The flow for every change:

1. Push code to `main`.
2. GitHub Actions tests, builds, scans and pushes the images tagged with the commit SHA.
3. The `update-gitops` job commits the new SHA into `helm/clinicq/values-prod.yaml`.
4. ArgoCD detects the new commit, renders the chart and rolls the Deployments forward; the Application shows
   `Synced` and `Healthy`.

The database password is the one thing that stays out of Git: the chart reads it from the `clinicq-db` Secret
(`postgres.existingSecret`), which is created with `kubectl`.

## Observability

- The backend exposes Prometheus metrics at `/metrics`: request count, request latency histograms by endpoint, plus
  the booking and cancellation counters.
- `kube-prometheus-stack` provides Prometheus and Grafana. The chart's ServiceMonitor makes Prometheus scrape both
  backend pods; the Prometheus Targets page shows them `UP`.
- `monitoring/dashboards/clinicq-dashboard.yaml` is a ConfigMap the Grafana sidecar imports automatically: request rate by
  endpoint, p95 latency, 5xx error rate, appointments booked and cancelled, backend pod count and CPU.

Reach the services (this AWS account could not create load balancers, so use port-forwards):

```bash
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80            # app: http://localhost:8080
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090     # Prometheus
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3001:80          # Grafana: admin / admin-change-me
bash scripts/load-test.sh http://localhost:8080 120 20                                # generate traffic for the panels
```

## Troubleshooting lab

Three deliberately broken manifests in `troubleshooting/`, each with the diagnosis commands and the fix in its header:

| File | Symptom | Root cause |
|---|---|---|
| `broken-image.yaml` | `ImagePullBackOff` | the image tag does not exist |
| `broken-service.yaml` | Service has no endpoints | selector does not match the pod labels |
| `broken-probe.yaml` | pod never becomes Ready | readiness probe path returns 404 |

[docs/SUBMISSION.md](docs/SUBMISSION.md) also lists the real problems hit while deploying to EKS and their fixes
(Free Tier instance types, add-on ordering, the default StorageClass, metrics-server networking, expiring credentials).

## Design decisions

- **Migrations run as a Helm hook Job**, not in every pod, so several replicas never race to migrate the schema.
  Compose, with one backend, runs them on container start.
- **Readiness vs liveness**: `/health` only proves the process is alive; `/ready` also queries the database, so a pod
  without database access leaves the Service instead of being restarted.
- **Images are tagged with the commit SHA**, so every running pod traces back to a commit.
- **Nothing is pushed unless tests and Trivy pass.**
- **PostgreSQL runs in the cluster** (StatefulSet + EBS volume) to keep the capstone self-contained. In production I
  would use Amazon RDS for backups, patching and Multi-AZ failover.
- **GitOps**: the cluster changes only through a Git commit, so every deployment is reviewable, auditable and
  revertible, and CI needs no cluster credentials.
- **Secrets**: the database password is a Kubernetes Secret created with `kubectl` and referenced by the chart
  through `postgres.existingSecret`. No credentials are in Git.

## Known limitations

- The AWS account used (Free Tier plan) cannot create load balancers, so the Ingress is reached with
  `kubectl port-forward` instead of a public address. The routing rules are unchanged.

## Evidence

| | |
|---|---|
| ![CI run](docs/screenshots/m5-01-github-actions-run-success.png) | ![GHCR](docs/screenshots/m5-02-ghcr-package-sha-tags.png) |
| GitHub Actions: test, build, Trivy scan, push | GHCR images tagged with the commit SHA |
| ![Trivy](docs/screenshots/m6-01-trivy-backend-scan.png) | ![EKS](docs/screenshots/m7-04-aws-eks-cluster.png) |
| Trivy scan: zero findings | EKS cluster in ap-south-1 |
| ![App via ingress](docs/screenshots/m8-06-app-via-ingress.png) | ![ArgoCD](docs/screenshots/m8-08-argocd-clinicq-synced.png) |
| App served through the Ingress | ArgoCD: Healthy and Synced; last sync is the pipeline's tag commit |
| ![Prometheus](docs/screenshots/m9-02-prometheus-targets.png) | ![Grafana](docs/screenshots/m9-03-grafana-dashboard.png) |
| Prometheus: backend targets UP | Grafana dashboard with live metrics |

All screenshots are in [docs/screenshots/](docs/screenshots/).
