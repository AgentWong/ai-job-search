# Technical Requirements

This document defines the technical skill requirements and alignment criteria for evaluating job positions. Subagents should reference this when assessing technical fit.

---

## Core Technical Competencies

Based on the candidate's background, the following technical areas represent strong alignment:

### Primary Strengths (High Confidence)

| Technology | Experience Level | Evidence |
|------------|-----------------|----------|
| **Terraform** | Advanced | Enterprise deployments, multi-cloud, Terragrunt |
| **Ansible** | Advanced | RHCE certified, Molecule testing, enterprise roles |
| **AWS** | Advanced | AWS-SAA certified, extensive service usage |
| **GitLab CI/CD** | Advanced | Complex pipelines, Terraform/Ansible orchestration |
| **GitHub Actions** | Intermediate | CI pipelines, OIDC integration |
| **Docker** | Intermediate | Container testing, Molecule integration |
| **Kubernetes/EKS** | Beginner | Basic EKS deployment exposure, limited direct hands-on |

### Secondary Strengths (Good Confidence)

| Technology | Experience Level | Evidence |
|------------|-----------------|----------|
| **Azure** | Intermediate | VPN Gateway, cross-cloud connectivity |
| **PowerShell** | Advanced | DSC, automation, multi-threading |
| **Python** | Intermediate | Scripting, MCP server development |
| **Windows Server** | Advanced | AD, GPO, Exchange, PKI |
| **VMware** | Intermediate | vSphere, vSAN, vRealize suite |
| **Linux** | Intermediate | RHCE, systemd, bash scripting |

---

## Technical Alignment Scoring

### Strong Alignment (+2 points each)

Positions mentioning these technologies explicitly align well:

- **Terraform** - Primary IaC tool experience
- **Ansible** - Primary configuration management experience
- **AWS** - Primary cloud platform experience

### Moderate Alignment (+1 point each)

- **GitLab CI** - Extensive pipeline experience
- **GitHub Actions** - Growing experience
- **Docker/Containers** - Solid foundation

### Neutral Alignment (0 points)

- **Kubernetes/EKS** - Beginner experience, basic exposure
- **Azure** - Secondary experience, acceptable in multi-cloud
- **CloudFormation** - Limited but transferable from Terraform
- **Pulumi** - No experience but IaC concepts transfer

### Negative Alignment (-1 to -2 points)

- **GCP-exclusive** - No experience, would require significant ramp-up
- **Azure-primary** - Limited experience, not ideal as primary
- **Bare-metal focus** - Outside current expertise

---

## Technical Red Flags

### Automatic Disqualification

Positions with these as **primary** requirements should be rejected:

| Requirement | Reason |
|-------------|--------|
| **KVM/QEMU/Hypervisor management** | Bare-metal focus, not cloud |
| **GPU passthrough/RDMA** | Specialized hardware, not cloud automation |
| **Python development/frameworks** | Software development, not infrastructure |
| **Django/Flask/FastAPI** | Web development frameworks |
| **Microservices development** | Application development focus |
| **API development** | Backend development focus |
| **GCP as only cloud** | No experience with GCP |

### Concerning Requirements

Positions with these should be scored lower but not automatically rejected:

| Requirement | Impact | Notes |
|-------------|--------|-------|
| **Heavy Kubernetes development** | -1 point | Operations OK, development concerning |
| **Go programming required** | -1 point | Limited experience |
| **Java/Node.js required** | -2 points | Outside infrastructure focus |
| **Rotating on-call** | -1 point | Standard on-call with sustainable rotation |
| **24/7 on-call** | Disqualifying | No rotation, always available, or <15min response |

---

## Programming Boundaries

### Acceptable Programming

These programming-related requirements are within scope:

```
✅ "Python scripting for automation"
✅ "Bash/shell scripting"
✅ "PowerShell automation"
✅ "Writing Ansible playbooks"
✅ "Terraform module development"
✅ "CI/CD pipeline scripting"
✅ "Infrastructure automation scripts"
✅ "Basic Python for tooling"
```

### Unacceptable Programming

These indicate software development focus, not infrastructure:

```
❌ "Python development experience"
❌ "Advanced Python programming"
❌ "Python frameworks (Django, Flask)"
❌ "Object-oriented programming"
❌ "Software design patterns"
❌ "Microservices architecture"
❌ "API development"
❌ "Backend development"
❌ "Full-stack development"
```

---

## Cloud Platform Evaluation

### AWS Services (Strong Experience)

| Service Category | Specific Services |
|------------------|-------------------|
| **Compute** | EC2, ASG, ELB/ALB |
| **Storage** | S3, EBS |
| **Networking** | VPC, Transit Gateway, Route 53 |
| **Security** | IAM, KMS, Security Groups |
| **Containers** | EKS, ECR |
| **Database** | RDS, DynamoDB |
| **Monitoring** | CloudWatch |
| **Automation** | SSM, Lambda |
| **Data** | Kinesis Firehose |

### Azure Services (Limited Experience)

| Service | Experience Level |
|---------|-----------------|
| VPN Gateway | Production experience |
| Site-to-Site VPN | Production experience |
| Entra ID | Basic familiarity |
| Virtual Networks | Basic familiarity |

### GCP Services (No Experience)

No hands-on experience with Google Cloud Platform. Positions requiring GCP as primary cloud should be rejected.

---

## Certification Alignment

Current certifications that demonstrate qualification:

| Certification | Relevance |
|---------------|-----------|
| **AWS Solutions Architect Associate** | Validates AWS cloud architecture knowledge |
| **RHCE (Ansible)** | Validates advanced Ansible skills |
| **RHCS Containers** | Validates container knowledge |
| **VCP-DCV** | Validates VMware expertise |
| **OSCP** | Demonstrates security awareness |
| **MCSE Core Infrastructure** | Validates Windows infrastructure skills |

---

## Technical Fit Assessment Template

For each position, evaluate:

```markdown
## Technical Alignment Assessment

### IaC Tools Match
- [ ] Terraform mentioned: __ (Yes/No/Preferred)
- [ ] Ansible mentioned: __ (Yes/No/Preferred)
- [ ] Other IaC: __

### Cloud Platform Match
- [ ] AWS focus: __ (Primary/Secondary/None)
- [ ] Azure focus: __ (Primary/Secondary/None)
- [ ] GCP focus: __ (Primary/Secondary/None) - DISQUALIFY if primary

### Programming Requirements
- [ ] Scripting only: __ (Yes/No)
- [ ] Development focus: __ (Yes/No) - DISQUALIFY if Yes

### Container/K8s Requirements
- [ ] Container operations: __ (Yes/No)
- [ ] K8s development: __ (Yes/No) - Concerning if Yes

### Technical Score Adjustments
- Terraform: +2 / Ansible: +2 / AWS-primary: +2
- Azure-primary: -1 / GCP-any: DISQUALIFY
- Heavy programming: DISQUALIFY
```

---

## Related Documents

- [CV Full](../config/cv_full.md) - Complete technical background
- [Scoring Framework](./scoring_framework.md) - How technical alignment affects score (includes disqualification criteria)
