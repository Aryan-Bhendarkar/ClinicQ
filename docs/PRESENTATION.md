# Presentation video script (about 8-10 minutes)

Record with OBS Studio or the Windows Game Bar (Win+G). Use a 1080p screen, increase terminal font size,
and speak over it. Keep the cluster running until the recording is finished.

## Before you hit record

- Docker Desktop running; `docker compose down -v` so you can show a clean start
- Cluster up, `$env:AWS_PROFILE = "tf"` set, and these port-forwards open in separate windows:
  Ingress `8080:80`, Prometheus `9090`, Grafana `3001:80` (service) 
- A browser tab each for: the GitHub repo, the Actions page, the GHCR package, the AWS EKS console
- Run the load loop once so Grafana shows data

## Script

| Time | Show | Say |
|---|---|---|
| 0:00 | README architecture diagram | "ClinicQ is a clinic appointment booking app. React frontend, FastAPI backend, PostgreSQL. I built the full path from a commit to a monitored Kubernetes cluster on AWS." |
| 0:45 | `docker compose up --build`, then http://localhost:3000. Book an appointment, try booking the same slot again | "One command starts three containers. A second booking for the same doctor and slot returns 409, so a doctor can't be double-booked." |
| 1:45 | http://localhost:8000/docs: create, read, update, delete one appointment | "Twelve REST endpoints. `/health` is liveness, `/ready` checks the database, `/metrics` is for Prometheus." |
| 2:30 | `psql` in the postgres container: `select * from appointments;` and `select * from alembic_version;` | "Schema is managed by Alembic migrations, and the data is really in Postgres." |
| 3:00 | `pytest -v` | "15 tests on an in-memory database. This is the first quality gate: if tests fail, nothing is built or pushed." |
| 3:30 | Make a small UI text change, `git commit`, `git push` | "Now the live demo. I change something small and push to main." |
| 4:00 | GitHub Actions run, expand the Trivy step | "Pipeline: pytest, frontend build, Docker build for both images, Trivy scan that fails on HIGH or CRITICAL, then push to GHCR tagged with the commit SHA." |
| 5:00 | GHCR package page | "Every image is tagged with the commit SHA, so any running pod traces back to a commit. Nothing is called `latest`." |
| 5:30 | Terraform files in the editor; EKS and VPC console pages | "Terraform builds the VPC with public and private subnets, a NAT gateway, and EKS with a managed node group, plus the EBS CSI driver and metrics-server add-ons." |
| 6:15 | `helm upgrade --install ... --set backend.tag=<new-sha>`, then `kubectl rollout status`, `kubectl get pods,svc,hpa -n clinicq`, `helm list -n clinicq` | "Helm deploys the new image. Two replicas each, ClusterIP services, an HPA on the backend, and a migration Job that runs as a Helm hook." |
| 7:15 | Browser at `localhost:8080` (through the Ingress), reload and show the change | "The Ingress sends `/api` to the backend and everything else to the frontend. This AWS account can't create load balancers, so I reach the Ingress through a port-forward." |
| 7:45 | Run the load loop; `kubectl get hpa -n clinicq -w` | "Under load the HPA scales the backend from 2 up to 6 pods." |
| 8:15 | Prometheus targets page, then Grafana dashboard | "Prometheus scrapes both backend pods through a ServiceMonitor. Grafana shows request rate, p95 latency, 5xx errors and bookings." |
| 9:00 | `kubectl apply -f troubleshooting/broken-service.yaml`, `get endpoints`, `get pods --show-labels`, fix with `kubectl patch` | "A Service with no endpoints means its selector doesn't match the pod labels. Here is how I diagnose and fix it." |
| 9:45 | Close | "Everything is in the repo, and the deployment problems I hit and fixed are documented in docs/SUBMISSION.md." |

## Questions to be ready for

- **Why a migration Job instead of migrating on container start?** With several replicas, every pod would race to migrate the same schema.
- **Why `/ready` and `/health` separately?** A pod that can't reach the database should leave the Service, not be restarted.
- **Why Postgres in the cluster?** Self-contained for the capstone. In production I'd use Amazon RDS for backups and failover.
- **What did Trivy find?** Three HIGH CVEs in Starlette and two in Alpine libraries; fixed by upgrading, then the scan came back clean.
- **Why is the deploy job skipped in the pipeline?** No cluster kubeconfig secret is configured, so I deployed with Helm from my laptop using the pipeline's images.
- **What would you improve?** RDS, a real load balancer and DNS, secrets in AWS Secrets Manager, and OIDC-based deploy credentials for GitHub Actions.
