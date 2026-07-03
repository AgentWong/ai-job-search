# Alex Johnson
DevOps Engineer | Portland, Oregon, United States

## Contact
- **Email:** alex.johnson@example.com
- **LinkedIn:** www.linkedin.com/in/alexjohnson-devops
- **Portfolio:** www.alexjohnson.example.com

## Professional Summary

DevOps Engineer with 7+ years in IT, including 3.5 years automating AWS infrastructure at Nimbus Technologies and 1.5 years of Windows and VMware systems administration before that. I focus on eliminating manual work through infrastructure automation: turning multi-week manual efforts into repeatable, version-controlled pipelines you can run with a single click.

Most of my work is Terraform and Ansible on AWS. I cut Splunk HA cluster deployments from 153 hours to under 5, built CI/CD pipelines that deploy full environments in roughly 45 minutes, and resolved a multi-week AWS-to-Azure VPN deadlock in two days by capturing both ends in Terraform.

I also integrate AI tooling (GitHub Copilot, Claude) into infrastructure workflows to speed up the write-test-fix loop on Ansible roles and Terraform modules.

## Top Skills
- Terraform
- Ansible
- AWS
- Kubernetes
- CI/CD Pipelines
- GitLab CI / GitHub Actions
- Python
- PowerShell
- Linux Administration
- Infrastructure Automation

## Certifications
- AWS Certified Solutions Architect – Associate
- Red Hat Certified Specialist in Containers (EX188)
- Red Hat Certified Engineer (RHCE EX294, Ansible)
- VMware Certified Professional - Data Center Virtualization 2021
- Offensive Security Certified Professional (OSCP)
- MCSE: Core Infrastructure

## Experience

### Nimbus Technologies
**DevOps Engineer** | May 2022 - January 2026 (3 years 9 months)

- Cut Splunk HA cluster deployments from 153 hours of manual work to under 5 hours per environment by replacing fragile shell-script bootstraps with reusable Terraform and Ansible. Made it possible for junior engineers to run deployments that previously required senior staff.
- Built GitLab CI/CD pipelines that deploy full environments on a single button push: Active Directory domains, PKI, firewalls, and clustered applications (Elasticsearch, Splunk, GitLab) in roughly 45 minutes.
- AWS-to-Azure VPN had been stuck for three weeks. Captured both tunnel endpoints in Terraform, turned on tunnel logging to surface the encryption mismatch, and had it running in two days.
- Fixed a broken AWS-to-Azure log pipeline that dropped everything except timestamp and message body. Built a Lambda transform that prefixes each record with account, log group, and stream name so engineers could filter by source.
- Set up Ansible Molecule with Docker containers so engineers could test infrastructure code locally instead of waiting on EC2 instances. Caught configuration errors before anything touched a cloud account.
- Integrated GitHub Copilot Agent Mode with the Molecule test harness so the AI runs tests, reads failures, and fixes issues on its own loop. Significantly cut debug time on complex Ansible roles.
- Re-architected a Golang drift detection tool: replaced 103 separate AWS API enumerators with a single AWS Config query, and added a Terraform plan integration so the tool detects real configuration drift instead of just unmanaged resources.
- Built a hardened container image pipeline with Trivy vulnerability scanning and STIG compliance checks. Runs on both GitHub Actions and an airgapped GitLab.

### Meridian Federal Systems
**VMware Systems Administrator - a federal systems integrator** | April 2021 - April 2022 (1 year 1 month) | a federal systems integrator

- Diagnosed VDI recompose operations taking 3-5 hours, traced to the View Agent defaulting to a slow activation path. A registry fix cut recompose time to 30 minutes per pool (97% reduction).
- Resolved a 4-month outage where VDI pools could not be managed or recomposed. Traced the failure to a database ID mismatch on the View Connection Server and corrected it, restoring full pool management.
- Hyperconverged infrastructure upgrades had been stalled for a month across 6 production enclaves despite vendor support. Identified a certificate trust issue from a recent CA rotation plus missing host file entries. Completed 5 of 6 enclaves in one week.
- Wrote PowerShell scripts to orchestrate Windows patching across 6 production environments in a single day, sequencing primary VMs before secondaries.
- Deployed centralized monitoring (vRealize Operations + Log Insight) into environments that previously had no shared visibility, so engineers stopped logging into individual systems to chase logs.
- Wrote a PowerShell script that resets a stale C2PC database after every VDI pool recompose, deployed across 6 production enclaves to eliminate recurring post-recompose failures.

### Summit Talent Group
**Systems Administrator - a federal systems integrator** | October 2020 - April 2021 (7 months) | a federal systems integrator

- Applied WSUS metadata cleanup and Microsoft-recommended optimizations across 7 air-gapped production environments. Cut monthly patch export/import from 100+ hours to 8 hours and fixed chronic delta import failures.
- Wrote PowerShell scripts to automate Exchange DAG maintenance mode, including service health checks before major Cumulative Update upgrades. Prevents email loss by gracefully failing over nodes prior to patching.

### Cascade Networks
**PC Technician - a public-sector client** | April 2019 - September 2020 (1 year 6 months) | Honolulu, Hawaii

- Wrote multi-threaded PowerShell tools to scan 600+ computers in parallel for SCCM client health, BitLocker encryption status, patch compliance, and Group Policy freshness. Health audits that previously took days completed in hours.
- Built a WPF diagnostic GUI in PowerShell showing real-time status across 50+ system properties. Used parallel CIM queries (DCOM, since PowerShell Remoting was disabled), making it 3-5x faster than the legacy VBScript tool it replaced.
- Wrote a BITS-based deployment script for 20-30GB CAD software (AutoCAD, Revit) to remote workers during COVID. Transfers ran asynchronously in the background and survived VPN disconnections, so users did not need to bring laptops on-site.
- Diagnosed an enterprise-wide incident where SCCM clients were uninstalling themselves across hundreds of machines. Traced the cause to a recently enabled add-on, restoring patch delivery capability.

### Coastal IT Support
**Help Desk Technician** | February 2018 - February 2019 (1 year 1 month) | Honolulu, HI

- Deployed Auvik network monitoring across MSP client environments and discovered undocumented infrastructure still running factory-default credentials. Built baseline inventories for environments that had none.
- Set up an MDT/WDS imaging server with PXE boot automation. New computers went from bare metal to fully configured with standard software in 30 minutes instead of 3+ hours of hands-on work.
- Wrote remote agent installation scripts using Webroot shell execution and domain-joined psexec, eliminating site visits to deploy management software.
- Configured SPF, DKIM, and DMARC records to fix email deliverability for clients whose mail kept getting flagged as spam.

### Riverside Community College
**PC Technician I** | September 2017 - November 2017 (3 months) | United States

- Imaged and deployed faculty workstations, kept supported software current, and troubleshot connectivity, OS, and software issues from helpdesk tickets.

## Projects

### Apache Kafka Cluster with Observability Stack (April 2026)

- Built an automated deployment for a full Kafka messaging environment in containers: coordination cluster, message brokers, a monitoring stack (Prometheus + Grafana), and a Python load generator. Whole stack tested locally without touching a cloud account.
- End-to-end encryption across the cluster with a built-in certificate authority that issues per-node keys, all distributed by Ansible. Five Grafana dashboards deployed by configuration so they appear automatically rather than being clicked into a UI.
- Developed with GitHub Copilot Agent Mode in a self-driving test loop. The AI runs tests, reads failures, and fixes the playbooks on its own until everything passes.

### driftctl Fork: Terraform Drift Detection in Go (April 2026)

- Forked an open-source AWS drift detection tool and reworked it in Go to fix three real limitations: it didn't actually detect drift (only listed orphan resources), it hit AWS rate limits on large accounts, and it had no awareness of resources managed by CloudFormation.
- Replaced 103 separate AWS API calls with a single AWS Config query, cutting maintenance from a per-service enumerator down to one SQL-style query and eliminating the rate-limit risk.
- Added a real Terraform plan integration so the tool now compares live AWS state against what Terraform thinks should exist. That's actual attribute-level drift detection, not just unmanaged-vs-managed.

### Elastic Cloud on Kubernetes on AWS EKS (February 2026)

- Built a full Kubernetes-hosted Elasticsearch stack on AWS EKS, deployed entirely through Terraform and GitOps (ArgoCD). Runs on Spot instances for 60-80% compute savings.
- Single sign-on through Keycloak so engineers log into Elasticsearch, Kibana, and ArgoCD with one identity. Solved an EKS networking quirk by splitting public and internal sign-on calls down different paths.
- Service mesh (Istio + Kiali) for traffic observability and default-deny network policies so traffic between services has to be explicitly allowed.

### AI Job Search Automation with Orchestrator-Agent Pattern (February 2026)

- Built an AI-assisted job search tool using Claude. An orchestrator coordinates isolated AI subagents so each one starts with clean context instead of drowning in accumulated job description text. The AI equivalent of breaking a long script into focused functions.
- Searches Greenhouse, Lever, Ashby, Workday, and Hiring Cafe. A scoring framework ranks postings 0-10 and filters out the disqualifying ones before they ever hit my queue.
- Generates tailored resumes and cover letters from a single source CV, with strict rules that prevent the AI from inventing experience that isn't actually there.

### Multi-Distribution Container Build Pipeline (February 2026)

- GitHub Actions pipeline that builds 20 container images in parallel across 4 Linux distributions (Alpine, Red Hat UBI9, Ubuntu, Amazon Linux) and 5 DevOps tools.
- Every build is scanned for known vulnerabilities and produces a software bill of materials, so you can trace what's actually inside each image.
- All images run as non-root by default. Local builds work on Apple Silicon (ARM64) so the develop-test-scan loop doesn't depend on CI.

### AWS Cloud Resume Challenge (March 2022)

- Static resume site on AWS: S3 for hosting, CloudFront for HTTPS, and Route 53 for DNS. Visitor counter built with API Gateway, Lambda (Python), and DynamoDB, using atomic database updates so the count stays accurate even with concurrent visitors.
- GitHub Actions pipeline pushes content changes and refreshes the cache on every push to main. Migrated from long-lived AWS keys to GitHub's OIDC federation in 2025, so no AWS credentials are stored in GitHub.
- Whole infrastructure migrated from CloudFormation to Terraform in 2025 without downtime by importing existing resources into Terraform state.

## Education

**Riverside Community College**
- Associate of Science (AS) in Information Technology | January 2015 - December 2017

## Honors & Awards
- Microsoft Certification Official Transcript
- Red Hat Transcript
