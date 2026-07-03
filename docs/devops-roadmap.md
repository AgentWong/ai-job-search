# DevOps Roadmap

Source: https://roadmap.sh/devops  
Data source: https://github.com/kamranahmedse/developer-roadmap

## Legend

- **RECOMMENDED** — Personal Recommendation / Opinion (author's suggested pick)
- ALTERNATIVE — Valid option, not the primary recommendation
- ANYTIME — Order not strict; learn whenever relevant

---

## Learning Path (Recommended Order)

### 1. Learn a Programming Language

| Tool | Status |
|------|--------|
| Python | RECOMMENDED |
| Go | RECOMMENDED |
| Ruby | ALTERNATIVE |
| Rust | ALTERNATIVE |
| JavaScript / Node.js | ALTERNATIVE |

---

### 2. Operating System

**Linux**

| Tool | Status |
|------|--------|
| Ubuntu / Debian | RECOMMENDED |
| RHEL / Derivatives | RECOMMENDED |
| SUSE Linux | ALTERNATIVE |

**Unix / BSD**

| Tool | Status |
|------|--------|
| FreeBSD | RECOMMENDED |
| OpenBSD | ALTERNATIVE |
| NetBSD | ALTERNATIVE |

**Other**

| Tool | Status |
|------|--------|
| Windows | ALTERNATIVE |

---

### 3. Terminal Knowledge

| Tool | Status |
|------|--------|
| Bash | RECOMMENDED |
| Vim / Nano / Emacs | RECOMMENDED |
| Process Monitoring | RECOMMENDED |
| Performance Monitoring | RECOMMENDED |
| Networking Tools | RECOMMENDED |
| Text Manipulation | RECOMMENDED |
| PowerShell | ALTERNATIVE |

---

### 4. Version Control Systems

| Tool | Status |
|------|--------|
| Git | RECOMMENDED |

---

### 5. VCS Hosting

| Tool | Status |
|------|--------|
| GitHub | RECOMMENDED |
| GitLab | ALTERNATIVE |
| Bitbucket | ALTERNATIVE |

---

### 6. Containers

| Tool | Status |
|------|--------|
| Docker | RECOMMENDED |
| LXC | ALTERNATIVE |

---

### 7. Web Servers, Proxies, and Networking Setup

**Web Servers**

| Tool | Status |
|------|--------|
| Nginx | RECOMMENDED |
| Caddy | ALTERNATIVE |
| Apache | ALTERNATIVE |
| Tomcat | ALTERNATIVE |
| IIS | ALTERNATIVE |

**Proxies and Load Balancing**

| Tool | Status |
|------|--------|
| Forward Proxy | RECOMMENDED |
| Reverse Proxy | RECOMMENDED |
| Caching Server | RECOMMENDED |
| Load Balancer | RECOMMENDED |
| Firewall | RECOMMENDED |

---

### 8. Networking and Protocols

| Topic | Status |
|-------|--------|
| DNS | RECOMMENDED |
| HTTP | RECOMMENDED |
| HTTPS | RECOMMENDED |
| SSL / TLS | RECOMMENDED |
| SSH | RECOMMENDED |
| FTP / SFTP | ANYTIME |
| OSI Model | ANYTIME |

**Email Protocols** (all ANYTIME — learn as needed)

- SMTP
- IMAP
- POP3S
- SPF
- DMARC
- Domain Keys
- White / Grey Listing

---

### 9. Cloud Providers

| Provider | Status |
|----------|--------|
| AWS | RECOMMENDED |
| Azure | RECOMMENDED |
| Google Cloud | RECOMMENDED |
| Digital Ocean | ALTERNATIVE |
| Alibaba Cloud | ALTERNATIVE |
| Hetzner | ALTERNATIVE |
| Heroku | ALTERNATIVE |
| Contabo | ALTERNATIVE |

---

### 10. Serverless

| Tool | Status |
|------|--------|
| AWS Lambda | RECOMMENDED |
| Cloudflare | RECOMMENDED |
| Azure Functions | ALTERNATIVE |
| GCP Functions | ALTERNATIVE |
| Vercel | ALTERNATIVE |
| Netlify | ALTERNATIVE |

---

### 11. Logs Management

| Tool | Status |
|------|--------|
| Loki | RECOMMENDED |
| Elastic Stack (ELK) | RECOMMENDED |
| Graylog | ALTERNATIVE |
| Splunk | ALTERNATIVE |
| Papertrail | ALTERNATIVE |

---

### 12. Provisioning (Infrastructure as Code)

| Tool | Status |
|------|--------|
| Terraform | RECOMMENDED |
| AWS CDK | ALTERNATIVE |
| CloudFormation | ALTERNATIVE |
| Pulumi | ALTERNATIVE |

---

### 13. Configuration Management

| Tool | Status |
|------|--------|
| Ansible | RECOMMENDED |
| Chef | ALTERNATIVE |
| Puppet | ALTERNATIVE |

---

### 14. CI / CD Tools

| Tool | Status |
|------|--------|
| GitLab CI | RECOMMENDED |
| GitHub Actions | RECOMMENDED |
| Circle CI | RECOMMENDED |
| Jenkins | ALTERNATIVE |
| TeamCity | ALTERNATIVE |
| Travis CI | ALTERNATIVE |
| Drone | ALTERNATIVE |

---

### 15. Secret Management

| Tool | Status |
|------|--------|
| Vault (HashiCorp) | RECOMMENDED |
| Sealed Secrets | ALTERNATIVE |
| SOPs | ALTERNATIVE |
| Cloud Specific Tools | ALTERNATIVE |

---

### 16. Infrastructure Monitoring

| Tool | Status |
|------|--------|
| Prometheus | RECOMMENDED |
| Grafana | RECOMMENDED |
| Datadog | RECOMMENDED |
| Zabbix | ALTERNATIVE |

---

### 17. Artifact Management

| Tool | Status |
|------|--------|
| Artifactory | RECOMMENDED |
| Nexus | ALTERNATIVE |
| Cloud Smith | ALTERNATIVE |

---

### 18. GitOps

| Tool | Status |
|------|--------|
| ArgoCD | RECOMMENDED |
| FluxCD | ALTERNATIVE |

---

### 19. Container Orchestration

| Tool | Status |
|------|--------|
| Kubernetes | RECOMMENDED |
| GKE / EKS / AKS (Managed Kubernetes) | ALTERNATIVE |
| AWS ECS / Fargate | ALTERNATIVE |
| Docker Swarm | ALTERNATIVE |

---

### 20. Application Monitoring

> No single recommended pick — choose based on your stack.

| Tool | Status |
|------|--------|
| OpenTelemetry | ALTERNATIVE |
| Jaeger | ALTERNATIVE |
| New Relic | ALTERNATIVE |
| Datadog | ALTERNATIVE |
| Prometheus | ALTERNATIVE |

---

### 21. Service Mesh

| Tool | Status |
|------|--------|
| Istio | RECOMMENDED |
| Consul | RECOMMENDED |
| Linkerd | ALTERNATIVE |
| Envoy | ALTERNATIVE |

---

### 22. Cloud Design Patterns

> Conceptual topics — no tool recommendations, learn as needed.

- Availability
- Data Management
- Design and Implementation
- Management and Monitoring

---

## Market Validation Assessment

> Analysis based on 92 job postings collected Jan–Mar 2026 (DevOps Engineer, SRE, Platform Engineer, Cloud Engineer roles).

### Recommendations That Are Well-Validated

These RECOMMENDED picks are strongly confirmed by job posting frequency:

| Roadmap Item | Posting Frequency | Notes |
|---|---|---|
| AWS | 89% | Dominant provider by far |
| Terraform | 86% | Undisputed IaC standard |
| Kubernetes | 72% | Non-negotiable in most roles |
| Python | 65% | Most-demanded language |
| Docker | 55% | Foundational prereq |
| Bash | 48% | Core scripting skill |
| Azure | 42% | Correctly recommended alongside AWS |
| Ansible | 40% | Still the config mgmt leader |
| GitHub / GitHub Actions | 38% / 33% | Leading VCS host and CI/CD platform |
| Datadog | 24% | Market-leading observability tool |
| Prometheus + Grafana | 16% each | Widely used together |
| GCP | 30% | Correctly recommended; multi-cloud is real |

---

### Recommendations That Are Inaccurate or Overstated

**CircleCI (RECOMMENDED) vs. Jenkins (ALTERNATIVE)**
- Jenkins: 28% | CircleCI: 2%
- Jenkins still significantly outperforms CircleCI in actual demand despite being "legacy." CircleCI appears to be declining. Jenkins should be at minimum co-recommended.

**Loki (RECOMMENDED) is overstated**
- Loki: 1% | ELK/Elasticsearch: 5%
- Marking Loki as RECOMMENDED alongside ELK overstates its market presence. It is a niche tool. Datadog is the correct primary pick for monitoring.

**Service Mesh (Istio/Consul RECOMMENDED) is overstated**
- Istio: 2% | Consul: 1% | Linkerd/Envoy: ~0%
- Service mesh is a real technology but far from expected knowledge in most DevOps roles. These are niche and should be ALTERNATIVE or ANYTIME.

**Vault (RECOMMENDED) vs. Cloud-Native Secret Management (ALTERNATIVE)**
- HashiCorp Vault: ~1% explicit mention
- In AWS-heavy environments, AWS Secrets Manager / Parameter Store are the actual day-to-day tools. The roadmap has this backwards — cloud-native secret management deserves co-recommended status.

**Artifactory (RECOMMENDED) is unsupported**
- Artifactory: 1% | Nexus: 3%
- Neither tool appears frequently enough to justify RECOMMENDED. Artifact management is a background concern in most postings and not a meaningful differentiator.

**CloudFormation (ALTERNATIVE) is undersold**
- CloudFormation: 35% — higher than many RECOMMENDED tools
- AWS shops use both CF and Terraform. Marking CloudFormation as merely ALTERNATIVE undersells it for anyone targeting AWS-focused roles.

---

### Gaps in the Roadmap

**Helm is missing entirely**
- Helm: 11% of postings — more common than ArgoCD (9%), CircleCI (2%), or any service mesh tool
- It is standard practice alongside Kubernetes and should be added under Container Orchestration.

**No AWS service-level guidance**
- The roadmap lists "AWS" as a single line item, but postings frequently call out specific services. Prioritized by frequency:

| AWS Service | Posting Frequency |
|---|---|
| IAM | 30% |
| VPC | 21% |
| S3 | 18% |
| EC2 | 17% |
| CloudWatch | 16% |
| EKS | 27% |
| RDS | 12% |

Stopping at "learn AWS" is too coarse. IAM, VPC, EC2/EKS, S3, and CloudWatch are practical starting points.

**CloudWatch is missing from Logs/Monitoring sections**
- CloudWatch: 16% — more common than Prometheus or Grafana in these postings
- As an AWS-native tool it is ubiquitous in AWS shops but absent from the roadmap.

---

### Overall Verdict

The roadmap's core recommendations are largely sound. The top-tier picks — Terraform, Kubernetes, AWS, Python, Docker, Ansible, GitHub Actions, Prometheus/Grafana/Datadog — are all well-validated by market data.

The main weaknesses are:
1. **CircleCI over-ranked, Jenkins under-ranked** — the clearest factual error
2. **Loki over-ranked, CloudWatch missing** — AWS context is underweighted throughout
3. **Service mesh overstated** as expected knowledge for most roles
4. **Helm missing** despite strong market presence alongside Kubernetes
5. **No AWS service-level guidance** — too coarse for practical learning prioritization
6. **CloudFormation deserves more than ALTERNATIVE** given 35% market penetration
