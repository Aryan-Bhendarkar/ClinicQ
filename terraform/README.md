# Terraform - AWS VPC + EKS

Creates, in `ap-south-1`:

- VPC `10.20.0.0/16` with 2 public and 2 private subnets across 2 AZs, an internet gateway and one NAT gateway
- EKS cluster (Kubernetes 1.31) with a managed node group of 2 x `m7i-flex.large`
- EKS add-ons: `vpc-cni` and `kube-proxy` (installed before the nodes), `coredns`,
  `aws-ebs-csi-driver` (with an IRSA role) and `metrics-server`
- A security-group rule so the control plane can reach metrics-server on port 10251

## Use

```powershell
$env:AWS_PROFILE = "tf"        # profile with credential_process, see docs/SUBMISSION.md
terraform init
terraform plan -out tfplan
terraform apply tfplan         # about 15 minutes
aws eks update-kubeconfig --region ap-south-1 --name clinicq-eks
```

Copy `terraform.tfvars.example` to `terraform.tfvars` to override defaults. No credentials belong in this folder.

## Notes

- Accounts on the AWS Free Tier plan can only launch free-tier-eligible instance types, so the default is
  `m7i-flex.large` and not `t3.medium`.
- State is local (git-ignored). For a team, use an S3 backend with DynamoDB locking.
- Destroy from **this folder**, after removing the Helm releases and namespaces so the EBS volume is released:

```powershell
terraform destroy
```
