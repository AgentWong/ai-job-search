<!-- CUSTOMIZE: Replace this entire file with your own complete work history. -->
<!-- This fictional CV demonstrates the format expected by the resume tailoring workflow. -->
<!-- TIP: The more detailed your CV, the better the AI can tailor resumes to specific postings. -->
<!-- A real CV should be 200+ lines. Include everything -- the AI will select what's relevant. -->

# Alex Johnson

**Location:** Portland, Oregon (Remote)
**Email:** alex.johnson@example.com
**Phone:** (555) 867-5309
**LinkedIn:** linkedin.com/in/alexjohnson-devops
**GitHub:** github.com/alexjohnson-devops

---

## Professional Summary

Cloud Infrastructure Engineer with 5 years of experience building and maintaining AWS environments using Terraform and Ansible. Focused on automation, reliability, and cost optimization for mid-size SaaS companies. Coming from the Ops side -- started in IT support and progressively moved into infrastructure automation and DevOps.

### Key Areas of Expertise

- **Cloud Infrastructure:** AWS (EC2, VPC, ECS, S3, RDS, Lambda, CloudFront, Route 53, IAM, CloudWatch, Transit Gateway, KMS), Azure (basic VPN Gateway, Entra ID)
- **Infrastructure as Code:** Terraform (modules, state management, workspaces), Ansible (roles, playbooks, Molecule testing), CloudFormation
- **CI/CD & Automation:** GitHub Actions, Jenkins, GitLab CI, blue-green deployments, container image pipelines
- **Monitoring & Observability:** Datadog, CloudWatch, PagerDuty, Grafana, centralized logging
- **Scripting:** Bash, Python (Boto3, automation), PowerShell (Windows administration)

---

## Technical Skills

**Cloud Platforms:** AWS (EC2, S3, RDS, Lambda, ECS, CloudFront, Route 53, IAM, VPC, CloudWatch, Transit Gateway, KMS, Secrets Manager, GuardDuty, Security Hub), Azure (VPN Gateway, Entra ID, basic networking)
**Infrastructure as Code:** Terraform, Ansible, CloudFormation, Packer
**CI/CD:** GitHub Actions, Jenkins, GitLab CI
**Containers:** Docker, ECS, basic Kubernetes (EKS)
**Monitoring:** Datadog, CloudWatch, PagerDuty, Grafana
**Scripting:** Bash, Python (Boto3, automation/scripting), PowerShell
**Operating Systems:** RHEL, Ubuntu, Amazon Linux 2, Amazon Linux 2023, Windows Server
**Networking:** VPC design, Transit Gateway, Route 53, ALB/NLB, Security Groups, Site-to-Site VPN
**Security:** IAM policies, Secrets Manager, GuardDuty, Security Hub, CIS benchmarks, SSL/TLS certificate management
**Version Control:** Git, GitHub, GitLab

---

## Certifications

| Certification | Issuing Organization | Date |
|--------------|---------------------|------|
| AWS Solutions Architect - Associate (SAA-C03) | Amazon Web Services | 2024 |
| Red Hat Certified System Administrator (RHCSA) | Red Hat | 2023 |
| CompTIA Security+ | CompTIA | 2022 |

---

## Professional Experience

### Cloud Infrastructure Engineer
**Nimbus Technologies** | Remote | Mar 2023 - Present

- **AWS Environment Management:** Managed production AWS environment spanning 3 accounts with 200+ EC2 instances, 40 RDS databases, and 15 ECS services serving a SaaS platform with 10,000+ customers.

- **Terraform Module Library:** Built reusable Terraform modules for standardized VPC, ECS, and RDS deployments, reducing new environment provisioning from 2 days to 45 minutes. Modules included configurable security groups, subnet layouts, and tagging standards. Managed Terraform state in S3 with DynamoDB locking.

- **Ansible Patch Management:** Implemented Ansible playbooks for RHEL patching across 200 servers, achieving 99.8% patch compliance within SLA. Created rolling patch strategy that maintained service availability by patching servers in batches with health checks between rounds.

- **Blue-Green Deployment Pipeline:** Designed and deployed blue-green deployment pipeline using GitHub Actions and ECS, reducing deployment failures by 70%. Pipeline included automated smoke tests, canary health checks, and one-click rollback capability.

- **Cost Optimization:** Reduced monthly AWS spend by $18,000 (22%) through Reserved Instance planning, S3 lifecycle policies, right-sizing recommendations using CloudWatch metrics, and identifying unused EBS volumes and Elastic IPs. Created weekly cost reports using Python/Boto3.

- **Monitoring & Alerting:** Configured Datadog monitoring with custom dashboards and alerting for all production services. Set up PagerDuty integration with escalation policies. Created runbooks for common alert scenarios to reduce mean time to resolution.

- **DNS & Multi-Region:** Managed DNS infrastructure in Route 53 with automated failover for multi-region deployments. Configured health checks and weighted routing policies for gradual traffic migration during region failovers.

- **On-Call:** Participated in on-call rotation (1 week per month) with average response time under 10 minutes. Maintained incident response runbooks and conducted post-incident reviews.

- **Security Hardening:** Implemented AWS Security Hub and GuardDuty across all accounts. Created IAM policies following least-privilege principles. Configured Secrets Manager rotation for database credentials and API keys.

### Systems Administrator / Junior DevOps
**Stratus Digital** | Remote | Jun 2021 - Feb 2023

- **Linux Administration:** Administered 50+ Linux servers (RHEL 8, Ubuntu 20.04) across AWS and on-premises VMware environment. Managed user accounts, SSH keys, and sudo configurations through Ansible.

- **Cloud Migration:** Migrated 12 on-premises applications to AWS EC2 and RDS with zero unplanned downtime. Created migration runbooks, performed data replication validation, and coordinated cutover windows with application teams.

- **Terraform Infrastructure:** Wrote Terraform configurations for AWS VPC, Security Groups, EC2 auto-scaling groups, and RDS instances. Introduced Terraform to the team and established code review practices for infrastructure changes.

- **Ansible Roles:** Created Ansible roles for server hardening (CIS Level 1 benchmarks), user management, application deployment, and SSL certificate installation. Tested roles locally using Ansible Molecule with Docker containers before deploying to cloud.

- **CI/CD Pipelines:** Built Jenkins CI/CD pipelines for 8 application teams, standardizing build and deployment processes. Configured webhook triggers, artifact management, and deployment approval gates.

- **Centralized Logging:** Implemented centralized logging with CloudWatch Logs and created operational dashboards for application health monitoring. Configured log retention policies and metric filters for error rate alerting.

- **Self-Service Provisioning:** Reduced server provisioning time from 2 weeks (manual ticketing) to 30 minutes through self-service Terraform workflows with pre-approved configurations. Created documentation and trained developers on the new process.

- **Automation Scripts:** Wrote Python scripts for automated AWS resource tagging and cost allocation reporting. Created Bash scripts for log rotation, backup verification, and disk space monitoring.

- **VMware Administration:** Managed on-premises VMware vSphere environment including ESXi hosts, vCenter, and VM lifecycle. Performed VM migrations during hardware refresh cycles.

### IT Support Specialist
**Cascade Networks** | Portland, OR | Aug 2019 - May 2021

- **Tier 2 Support:** Provided Tier 2 support for 500-user environment including Windows Server 2016/2019, Active Directory, Group Policy, and VMware vSphere 6.7. Handled escalated tickets from Tier 1 team.

- **Office 365 Administration:** Managed Office 365 tenant including Exchange Online, SharePoint, OneDrive, and Azure AD (now Entra ID). Configured conditional access policies and MFA enforcement.

- **PowerShell Automation:** Automated repetitive support tasks with PowerShell scripts including bulk user provisioning, mailbox permission management, and Active Directory cleanup. Reduced ticket resolution time by 35%.

- **Documentation:** Maintained documentation for 200+ IT procedures in Confluence. Created onboarding guides for new team members and knowledge base articles for common issues.

- **Certification & Career Transition:** Earned AWS Solutions Architect Associate certification while in this role. Built personal AWS lab environment to practice Terraform and Ansible. Transitioned focus from desktop support to cloud infrastructure, which led to the Junior DevOps role at Stratus Digital.

- **Network Support:** Assisted with basic network troubleshooting including VLAN configuration, firewall rule requests, and VPN connectivity issues. Configured DHCP reservations and DNS records for new services.

---

## Technical Projects

**Terraform AWS Landing Zone** - Built multi-account AWS organization with Control Tower, SSO, and standardized networking using Terraform modules. Deployed across 5 accounts (dev, staging, prod, shared-services, security). Implemented Service Control Policies (SCPs) to enforce guardrails across the organization. Created reusable VPC module with public/private/database subnet tiers and consistent CIDR allocation.

**Ansible Configuration Management Library** - Developed role-based Ansible playbook library for RHEL server hardening (CIS Level 1 benchmarks), application deployment, SSL certificate rotation, and user management. Manages 200+ servers. Implemented Molecule testing with Docker containers for local validation before production deployment. Created collection packaging for distribution across teams.

**Cost Optimization Dashboard** - Created Python-based AWS cost analysis tool using Boto3 that generates weekly reports with recommendations for Reserved Instances, unused resources, and right-sizing opportunities. Integrated with Slack for automated weekly cost summaries to engineering leadership. Saved $18K/month in the first quarter after deployment.

**Packer AMI Pipeline** - Built GitHub Actions pipeline for automated AMI creation using Packer and Ansible. Created base images for Amazon Linux 2, RHEL 8, and Ubuntu 22.04 with standard security hardening, monitoring agents, and company-standard tooling pre-installed. Monthly automated builds with Trivy vulnerability scanning.

**Container Migration POC** - Led proof-of-concept migration of a monolithic Python application to ECS Fargate. Created Dockerfile, ECS task definitions, ALB target group configuration, and GitHub Actions deployment pipeline. Demonstrated 40% cost reduction versus EC2-based deployment for variable-traffic workloads.

---

## Education

Associate of Applied Science in Information Technology
Portland Community College | Portland, OR | 2019

---

## Salary Information

- **Minimum Acceptable:** $80,000 USD
- **Target Range:** $90,000 - $120,000 USD
- **Notes:** Positions above $140,000 may carry senior-level expectations that exceed current experience level
