<!-- CUSTOMIZE: Replace this entire file with your own complete work history. -->
<!-- This fictional CV demonstrates the format expected by the resume tailoring workflow. -->
<!-- TIP: The more detailed your CV, the better the AI can tailor resumes to specific postings. -->
<!-- A real CV should be 200+ lines. Include everything -- the AI will select what's relevant. -->

# Alex Johnson - Full Curriculum Vitae

**Location:** Portland, OR
**Email:** alex.johnson@example.com

---

## Professional Summary

DevOps Engineer with **7+ years in IT**, coming from the Ops side. I focus on eliminating manual work through infrastructure automation - turning multi-week manual efforts into repeatable, version-controlled pipelines you can run with a single click.

Most of my recent work has been Terraform and Ansible on AWS. I've built everything from multi-cloud VPN connectivity (AWS-to-Azure, dual tunnels with BGP) to fully automated Splunk HA cluster deployments that cut provisioning from 153 hours to under 5. I write CI/CD pipelines in GitLab CI and GitHub Actions, build hardened container images, and use Ansible Molecule for testing infrastructure code locally before it touches a cloud account.

A recurring pattern across my career: when something stalls, I'm usually the one who walks the line and finds the slowest node. A 3-week site-to-site VPN deadlock resolved in 2 days. A 4-month VDI pool management outage traced to a database ID mismatch. 153-hour Splunk deployments cut to under 5. A VxRail upgrade frozen across 6 enclaves unblocked in a week. SCCM clients silently uninstalling fleet-wide, traced to a recently enabled add-on. An Adobe Flash killswitch found proactively before it took out admin portals across all production environments. Whether the bottleneck is a misconfigured cipher, a stale GPO, an undocumented end-of-life mechanism, or just toil that nobody thought to question, the muscle is the same: trace the stall to its source, fix it, and where possible turn the fix into automation so the next person doesn't rediscover it.

I also integrate AI tooling (GitHub Copilot, Claude) into infrastructure workflows - not as a gimmick, but to speed up the write-test-fix loop on Ansible roles and Terraform modules.

### Key Areas of Expertise

- **Incident Diagnosis & Bottleneck Removal:** Root-cause analysis on stalled deployments, failed upgrades, and chronic operational toil; turning one-off fixes into reusable automation so the same problem doesn't return
- **Cloud Infrastructure:** AWS (EC2, VPC, EKS, Transit Gateway, IAM, S3, RDS, KMS), Azure (VPN Gateway, Entra ID), multi-cloud connectivity
- **Infrastructure as Code:** Terraform, Terragrunt, Ansible (roles, collections, Molecule testing), Packer AMI/container builds
- **CI/CD & Automation:** GitLab CI, GitHub Actions, container image pipelines with Trivy scanning, automated deployment orchestration
- **Monitoring & Observability:** Splunk HA clusters, Elasticsearch, Prometheus, Grafana, vRealize Operations
- **Scripting:** Python, PowerShell, Bash, Golang (practical modifications to existing tools)
- **AI-Augmented Workflows:** Claude Code, GitHub Copilot, MCP integrations (Firecrawl, Chrome DevTools), orchestrator-agent patterns for token-aware automation

---

## Professional Experience

### DevOps Engineer
**Nimbus Technologies** | Remote | May 2022 – Jan 2026

*All infrastructure was built within greenfield cloud environments being prepared for FedRAMP authorization and ATO, deployed in AWS GovCloud (US) regions to meet federal data residency and compliance requirements. STIG hardening was the default baseline, CIS Level 2 benchmarks where STIGs weren't available, FIPS-validated endpoints and encryption configurations throughout. Any compliance violations discovered post-deployment were escalated to me for corrective action. Nimbus Technologies is a cybersecurity and compliance services firm; my role was building the infrastructure to meet these requirements, not performing the audits or assessments themselves.*

- **Infrastructure Automation & Deployment:** Splunk HA Cluster deployments required 153 hours of manual work per environment, repetitive, error-prone, and blocking project deadlines. Only Senior engineers had enough context to deploy them successfully. Built Terraform configs for cloud resource provisioning (EC2, Kinesis Firehose, ALB, Security Groups, SQS) and Ansible roles for configuration management, cutting Splunk deployments to under 5 hours through standardized playbooks. The Ansible roles abstract away 80-90% of the configuration complexity, similar to how Helm charts wrap raw Kubernetes manifests: you still need foundational Ansible knowledge (where variables go, how to read playbooks, how roles and collections work), but the roles limit what you need to touch and expose the rest as adjustable values. The practical result was that Junior engineers could deploy a functional Splunk cluster without needing to understand every config decision under the hood. It's not a true zero-touch push-button automation that removes the need to learn the tool, but it made cluster deployments accessible to people who previously couldn't attempt them. SQS queues are a standard part of the log ingestion pipeline for AWS services that cannot write directly to CloudWatch (ALB access logs being a primary example). S3 bucket notifications trigger SQS, and Splunk's S3 input polls the queue to ingest those logs. Kinesis Firehose handles the real-time streaming path; SQS handles the S3-notification-based path for services where that's the only option.

- **Ansible Molecule Container-Based Testing:** Set up Ansible Molecule with Docker containers for local role and collection testing, replacing slow cloud-based validation cycles where you'd wait for EC2 instances just to test a config change. Configured multi-node test scenarios simulating production topologies (Elasticsearch clusters, Kibana, Fleet Server) with systemd support and custom networking. Catches configuration errors locally before anything touches a cloud account.

- **AI-Assisted Development with Continuous Feedback Loop:** Integrated GitHub Copilot Agent Mode with Molecule testing so the AI could run tests, read failures, and fix issues on its own in a loop. Created instruction files defining test commands, error patterns, and fix strategies so the AI handles the tedious Run → Analyze → Fix → Repeat cycle, which cut debugging time on complex Ansible roles significantly.

- **AWS CloudWatch → Azure Sentinel Log Ingestion Pipeline:** A client operating an AWS/Azure hybrid environment needed all AWS service logs (Lambda, RDS, etc.) centralized in Azure Sentinel as their SIEM. The native Microsoft AWS S3 CloudWatch connector only populates two fields in the AWSCloudWatch table: timestamp and message, with no log group name, log stream name, or account ID. With hundreds of log groups across services, there was no scalable way to distinguish a Lambda log from an RDS log without reading individual message bodies, making alerting and KQL queries impractical. Built a Terraform-provisioned pipeline: CloudWatch Subscription Filters → Kinesis Data Firehose → S3 → SQS → Sentinel. A Lambda transform function prefixed each log message with three metadata fields (AWS Account ID, Log Group Name, Log Stream Name) as a comma-delimited header before the original message body, embedding the context that Kinesis strips during transit. On the Azure side, extended the Log Analytics table schema with custom columns for those fields, then configured a DCR ingestion-time KQL transformation to parse the comma-delimited prefix out of the raw message field and populate the new columns at write time. The result was a queryable pipeline where engineers could filter by log source (e.g., all Lambda logs across all accounts) without inspecting message contents.

- **Multi-Cloud Architecture:** Built Terraform configs for HA Site-to-Site VPN between AWS Transit Gateway and Azure VPN Gateway with dual tunnels and BGP routing.
  - **Implementation:** A colleague had spent 3 weeks unable to get the VPN communicating. ClickOps made it nearly impossible to tear down and rebuild cleanly, and reviewing the configuration required opening both the AWS and Azure portals side by side. Capturing the full setup in Terraform meant we could reset to a known-good state instantly and review both ends of the tunnel in a single diff. What had been stuck for weeks was resolved in 2 days.
  - **Troubleshooting:** Enabled VPN logging on both the AWS and Azure resources by changing a few lines of Terraform, which surfaced IKE negotiation errors in the tunnel logs. Formed a hypothesis that neither AWS nor Azure had been explicitly told which encryption protocols to use, causing them to negotiate with incompatible defaults. Consulted an LLM to generate aligned Diffie-Hellman Group 24 cipher configurations for both ends, applied them via Terraform, and confirmed the fix. The root cause and resolution were documented so the next engineer wouldn't need to rediscover it.

- **CI/CD Pipeline Development:** Built GitLab CI/CD pipelines that orchestrate Terraform + Ansible workflows. Push a button and within an hour you have Active Directory domains, PKI services, Palo Alto NGFW, and clustered applications (Gitlab/Elasticsearch) fully deployed. More complex applications like Splunk deploy in approximately 2 hours due to multi-node cluster coordination.

- **Configuration Management Migration:** Inherited an environment where all EC2 provisioning was done through ad-hoc User Data scripts (fire-and-forget, no visibility into failures, no idempotency, no coordination between dependent systems). The Splunk cluster setup alone involved 9+ Python scripts and a custom module with hard-coded hostname logic that couldn't scale beyond the original node count. Windows Domain Controllers were configured via PowerShell/DSC scripts that hit the User Data size limit. Rather than using the correct workaround (store the script in S3 and download it at runtime), the previous engineers had modified AWS-controlled cloud-init files inside the Windows AMI itself to add GZIP decompression support, allowing oversized scripts to be crammed directly into User Data. This was a time bomb: when AWS updated their Windows AMI (likely adding code-signing to their PowerShell scripts), the modifications broke. Replica DC setup was a 45-minute sleep followed by a domain join attempt, which was just a race condition pretending to be orchestration. Ansible Tower itself was bootstrapped through shell scripts wrapping its own setup tooling, stitched together with jq for inventory configuration.  Migrated this entire surface area to native Ansible roles: idempotent, version-controlled, and with real-time stdout feedback so failures surface immediately and in context rather than requiring engineers to SSH into individual nodes and dig through cloud-init logs. The improvement was most significant for clustered applications, where the original scripts had no mechanism to coordinate across nodes at all.

- **Cost Optimization:** Set up AWS cost controls in Terraform: Cost Allocation Tags with enforced SCP and Tag policies, Instance Scheduler to shut down resources off-hours, and cloud-nuke via GitHub Actions OIDC to wipe sandbox environments on schedule which were not explicitly excluded. Made it obvious who's spending what.

- **Jira SLA Metrics Reporting Tool (Python, AI-Assisted):** Manager needed a way to pull SLA violation and compliance data out of client Jira deployments. No clear spec on presentation, so I figured out the audience (non-technical IT managers) and chose a single HTML report as output since it's easy to open anywhere without extra dependencies. Used GitHub Copilot to write a ~1,300-line single-file Python script that queries Jira's REST API for SLA breaches, MTTR/MTTA by priority, ticket activity trends, and closure quality metrics. Kept it as one file deliberately so Tier 1-2 support engineers can copy/paste it into client environments without dealing with pip packages or project structure. Supports AWS Secrets Manager for credentials in production, with env var fallback for dev. Tested locally using Ansible Molecule to spin up a Jira instance in Docker containers rather than developing against production. Had to do some manual setup (trial license, SLA configurations, mock projects), but it gave the AI a real Jira API to test against instead of guessing from documentation, and kept the blast radius at zero.

- **Process Automation:** Wrote Selenium (Python) scripts to automate browser-based configurations for systems with no API. When there's no API, you either click through a web UI manually or you script a browser to do it for you.

- **Packer AMI Templating with Jinja2:** Built an Ansible Jinja2 templating tool that generates valid Packer HCL templates for multiple Linux distributions (AL2, AL2023, Ubuntu 20.04/22.04, RHEL8/9) and AMI purposes (base-os, docker, eks). Shared build steps (cloud-init wait, package updates, Python/Ansible install, LVM compliance volumes, STIG hardening via Ansible Lockdown roles, FIPS mode enablement where supported) live in one place; distro-specific variations are handled by the template. FIPS configuration extended beyond the OS to enterprise application endpoints (e.g., ensuring AWS API calls used FIPS-validated endpoints). GitHub Actions CI pipeline runs monthly sandbox builds with automated validation.

- **Cross-Platform Container Image Build Pipeline:** Built a container build pipeline using go-task, building hardened images from IronBank ubi9-minimal base with Trivy scanning and OpenSCAP RHEL9 STIG checks. Runs on both GitHub Actions (external, with build validation and badges) and airgapped GitLab with ECR push for internal deployments. Makefile handles local builds for bootstrapping Docker executor images.

- **RegScale GRC Platform Infrastructure Deployment:** Deployed the RegScale GRC application on AWS via Terraform, building an EKS cluster with AWS-managed node groups for multi-environment workloads (dev/prod/default namespaces), IRSA roles for granular service account permissions (VPC-CNI, AWS Load Balancer Controller, External DNS). Backend was multi-AZ RDS SQL Server (Express for dev, Standard Edition for prod) with KMS encryption and automated backups, plus multi-AZ EFS for persistent storage. Networking was VPC with multi-tier subnets (public/private/database/intra), least-privilege security groups, and AWS Load Balancer Controller via Helm for ingress.

### VMware Systems Administrator
**Meridian Federal Systems** | Hawaii | April 2021 – April 2022
*a federal systems integrator (Government Client)*

- **VMware Horizon VDI Performance Optimization:** Diagnosed VDI recompose operations taking 3-5 hours due to Horizon View Agent defaulting to KMS activation instead of AD-based activation. Implemented registry fix reducing recompose time to 30 minutes per pool (97% reduction), dramatically cutting maintenance windows and increasing VDI availability.

- **VDI Infrastructure Recovery:** Resolved critical issue where VDI pools could not be managed or recomposed for 4 months. Diagnosed SQL database deployment group ID mismatch with ADAM database values on View Connection Server and corrected, restoring full pool management capability across production environment.

- **C2PC Legacy Software VDI Integration:** Integrated C2PC (military Command and Control software by Northrop Grumman) with Horizon View VDI infrastructure it was never designed for. C2PC's SQL Server instances are hostname-based, causing the application to spam critical alerts and become unresponsive after VDI pool recompose operations changed clone hostnames. Wrote a PowerShell script to connect to SQL Server, drop the stale database, create a new database, and run the vendor's table-recreation script; registered it as a Horizon View post-synchronization script so it ran automatically after every pool publish. Successfully tested in lab and deployed across all 6 production enclaves, resolving recurring C2PC failures after pool recompose.

- **VxRail Upgrade Troubleshooting & PKI Certificate Remediation:** When VxRail upgrades stalled for one month across 6 production enclaves despite vendor support, volunteered to investigate. Identified two configuration issues: new SubCA certificate not added to VxRail Manager trust store after CA rotation, and missing /etc/hosts entries for ESXi hosts. Located documentation on vendor portal that team members couldn't access. Successfully upgraded 5 of 6 production enclaves within one week after diagnosis. Also diagnosed a separate incident where serious problems in new systems were caused by incorrectly issued Subordinate CA (PKI/SSL) certificates; worked with government SME to reissue correctly configured certificates and reinstall them across all affected infrastructure components (vCenter, VxRail) to prevent service impacts.

- **Log4J Vulnerability Remediation:** Assessed and executed patching procedures for vROPs, Horizon View, and vCenter to address Log4J vulnerability across production environments. Resolved legacy View Security Server blocking issue requiring Flash-based pairing password reset; adapted unsupported PowerCLI script as workaround. Trained team on VMware stack patching procedures.

- **Unified Access Gateway HA Architecture:** Researched and proposed 2x VCS (View Connection Server) + 4x UAG architecture replacing the original 4x VCS setup. Configured load-balanced UAG appliances so VDI sessions stay active during Connection Server restarts, so users stop getting kicked during monthly patching.

- **Domain Controller Outage Diagnosis and Recovery:** Domain controllers in a production enclave dropped to Public network profiles after NLA misclassified their NICs, causing domain authentication failures across VMs and VDI pools. After a reboot to fix the NLA issue, logins stopped working entirely. Event Log analysis showed SYSVOL replication had been silently failing because the C: drive on replica domain controller was full, no SYSVOL replication meant domain auth was broken. Cleared C:\Windows\Temp by mapping C$ from the healthy primary domain controller, rebooted replica domain controller, and restored full domain authentication.

- **Infrastructure Monitoring Stack:** Production environments had no centralized visibility; troubleshooting meant logging into individual systems to check logs. Deployed vRealize Operations Manager with vCenter SSO integration and DISA Compliance Pack for STIG monitoring. Integrated vRealize Log Insight with Content Packs for AD, Exchange, SQL, Windows, Horizon View, and Linux, all funneled through vROPS so you have one place to look.

- **Internal Documentation Platform (DokuWiki):** There was no internal documentation across production enclaves. Confluence was available but leadership wanted an air-gap-friendly alternative they directly controlled. Deployed DokuWiki on a Synology NAS with plugins for backup, syntax highlighting, discussions, and tagging. Set up namespace hierarchy covering infrastructure domains and operational areas. Ended up being the primary author, writing runbooks for vROPs/vLOG SSO, VxRail troubleshooting, C2PC administration, and Horizon View administration.

- **Windows Failover Clustering:** Monthly patching took file servers offline, disrupting user access across production enclaves. Set up native clustered VMDK on vSAN with Windows Failover Clustering and anti-affinity rules to keep file servers on separate hosts, giving users zero-downtime file access during patching. Wrote and tested a PowerShell script to automate cluster creation and configuration.

- **PowerShell DSC Patch Orchestration:** Wrote PowerShell DSC configurations for orchestrated patching across 6 production enclaves (separate Windows domain environments). Primary VMs in each role get patched first, secondaries wait until primary completes. DSC Pull Server with a config data file to toggle orchestration on/off. Enabled fully patching all 6 enclaves in a single day.

- **PowerShell DSC Software Inventory via vRealize Log Insight:** Wrote a custom PowerShell DSC class-based resource that reads the uninstall registry hive to determine installed software names and versions, then writes custom Events for vRealize Log Insight to consume. Provided automated inventory of all software and versions across 100+ VMs per enclave without requiring agents or third-party tools.

- **Office 2019 Air-Gapped Distribution:** Air-gapped downstream servers had no path to Microsoft's update infrastructure, leaving Office 2019 unpatched across the fleet, a compliance gap surfaced during reaccreditation. Wrote two PowerShell scripts to close this: the first pulled the latest Office 2019 installer files from Microsoft's CDN via the Office Deployment Tool onto an internet-connected WSUS server; the second synced only changed files to air-gapped downstream servers using SHA hash comparison to skip unchanged files and avoid redundant transfers. Deployed to four production environments, where the scripts ran as the ongoing patch delivery mechanism for Office.

- **Adobe Flash Killswitch: Proactive Discovery and Fleet-Wide Remediation:** Production Horizon View admin portals were going to become inaccessible on January 12, 2021 due to a time-based killswitch built into Adobe Flash: an obscure end-of-life mechanism most teams weren't aware of. Discovered the issue proactively by manually advancing the system date on a management VM to February 2021 and confirming the Horizon portal became unreachable. Found and documented an `mms.cfg` allowlist configuration that bypasses the killswitch. Led the contractor team in deploying the fix across all production enclaves before the cutoff date, preventing a maintenance window that would have blindsided operations.

- **SubCA Certificate / NDES Misconfiguration Root Cause Analysis:** NDES web server configuration was failing with generic 500 errors across three new production enclaves despite identical configurations, months of work had stalled with no progress. Volunteered to investigate and traced the 500 errors to DNS resolution failures, which exposed a deeper structural issue, the Subordinate CA certificate had incorrect CRL/AIA distribution point URLs, causing all enclave assets to reference an airgapped legacy enclave domain controller (which it could not physically communicate with due to being on airgapped networks) for Certificate Revocation checks, a single point of failure that crossed environment boundaries. Worked with the architect and team lead to reissue the SubCA certificates with correct CRL/AIA locations. This unblocked NDES deployment and eliminated the cross-environment CRL dependency.

- **Certificate Trust List Sync for Air-Gapped Networks:** Air-gapped downstream WSUS servers had no mechanism to receive updated Windows Certificate Trust Lists, a gap surfaced as a reaccreditation finding. Wrote two PowerShell scripts: the first used `certutil -SyncWithWU` on the internet-connected WSUS to pull the latest CTL; the second downloaded it to air-gapped downstream servers. Added a custom GPO to redirect the domain CTL URL to the local WSUS path so endpoints pulled from the internal source. Deployed across all production enclaves and closed the reaccreditation finding.

- **Windows 10 WSUS GPO Regression After 1909 Upgrade:** All Windows 10 VMs across all production MOC enclaves stopped receiving WSUS-targeted patches after being upgraded past Windows 10 1909, they were silently ignoring existing Windows Update GPOs, meaning none of them were patching automatically. A secondary issue was that Dual-Scan behavior was causing the VMs to attempt outbound connections to Microsoft's public Windows Update servers, generating unnecessary firewall noise in an air-gapped environment. Researched Microsoft's whitepaper on GPO changes introduced in 1909+, identified the new required policy settings, tested in lab, and documented the changes for the team to apply across all production MOC enclaves. Also added settings to disable Dual-Scan, eliminating the firewall traffic.

- **DISM Air-Gapped OS Repair Procedure:** DOD air-gapped environments had no documented method to repair Windows component store corruption short of rebuilding the VM, the standard DISM repair source is Windows Update, which isn't reachable. Researched and validated an alternative: using the WinSxS folder from a healthy VM running the same OS version at equal or higher patch level as an offline repair source. Tested the method in lab and documented it as a viable repair option for engineers facing component store corruption in air-gapped environments.

- **vRealize Log Insight Appliance Recovery from Filesystem Corruption:** A production vRealize Log Insight appliance became unbootable with no obvious cause. Analyzed journalctl boot logs, identified inode corruption on the core data volume (`/dev/mapper/data-core`), and ran fsck to repair it. Appliance recovered and booted successfully without data loss or a rebuild.

- **PowerShell Pester Infrastructure Health Test Suite:** No standardized validation existed for verifying the health of critical environment infrastructure before and after patching cycles. Wrote a PowerShell Pester test suite covering Active Directory, Exchange DAG, File Server Failover Cluster, Horizon View, Admin Server, and C2PCGW. Tests gave engineers an automated health baseline instead of manual spot-checking. Formally handed off the suite during offboarding to four personnel alongside the DSC orchestration scripts, vROPs/vLOG configurations, and WSUS tooling.

### Systems Administrator
**Summit Talent Group** | Hawaii | October 2020 – April 2021
*a federal systems integrator (Government Client)*

- **WSUS Performance Optimization:** Applied WSUS metadata cleanup and Microsoft-recommended optimizations across 7 production enclaves, getting 20-30x improvement in patch deployment speed. Fixed chronic delta import failures on air-gapped networks that previously required importing a full OVF of the upstream WSUS server. Monthly patch export/import went from 100+ hours to 8 hours.

- **WSUS Infrastructure & Storage:** Diagnosed and corrected VMFS deployment issues where thin-provisioned disks consumed maximum allocated space due to improper datastore initialization. Used vmkfstools to zero datastores and reclaim disk space, recovering 200-300GB. Converted thick-provisioned WSUS servers to thin-provisioned via vMotion to resolve storage constraints. Reconfigured lab WSUS to pull patches from DISA WSUS servers over SSL, replacing unsecured connections to Microsoft update servers.

- **Exchange DAG Maintenance Automation:** Wrote PowerShell scripts to start and stop DAG (Database Availability Group) maintenance mode for Microsoft Exchange mailbox servers, including checks to ensure all relevant services were properly started and stopped prior to major Cumulative Update upgrades. Prevents email loss by gracefully failing over nodes prior to patching.

### PC Technician
**Cascade Networks** | Hawaii | April 2019 – September 2020
*a public-sector client IT*

- **Enterprise System Health Monitoring:** Wrote multi-threaded PowerShell tools using runspaces to scan 600+ computers in parallel, checking SCCM client health (installation, registry, WMI namespace), Bitlocker encryption status with AD recovery key validation, Avamar backup agent, Windows Update compliance via registry UBR version tracking, Group Policy freshness (stale registry.pol blocks SCCM updates), TPM/Secure Boot, and Bomgar agent components. System health checks went from days to hours. Built during COVID downtime when ticket volume was minimal.

- **WPF Diagnostic Dashboard:** Reverse-engineered an existing VBScript diagnostic tool (basically end-of-life language) that was natively single-threaded and painfully slow. Rebuilt the whole thing in PowerShell as a WPF GUI, using runspace pools for parallel CIM queries with DCOM protocol (since PowerShell Remoting wasn't enabled), making it about 3-5x faster. Shows real-time status of 50+ system properties: SCCM health, Bitlocker status, McAfee HBSS components (Engine version, DAT version/date, EPO server, HIPS, DLP), Windows services, VPN detection, and network config.

- **BITS-Based Software Deployment:** Needed to deploy 20-30GB CAD software (AutoCAD, Revit) to remote workers over VPN during COVID. Noticed SCCM uses BITS for fault-tolerant transfers, so I wrote a PowerShell script that does the same thing, asynchronous low-priority background transfers that survive VPN disconnections and resume automatically. Users didn't need to bring laptops on-site; installations completed fully remotely via Bomgar while they worked normally. My peers were doing File Explorer copies that failed after 10+ hours when users disconnected.

- **SCCM Enterprise Incident Investigation:** Assisted SCCM Administrators in diagnosing an enterprise-wide issue where SCCM clients were uninstalling themselves across hundreds of machines, causing operational impacts (inability to deliver OS patches and software). Traced Event Logs to identify that a recently enabled SCCM add-on was the root cause, enabling the team to resolve the issue and restore patch delivery capability.

- **Microsoft Office Mass Activation Failure:** Diagnosed and resolved a work-stopping incident where hundreds of users had Microsoft Office deactivated and unable to open. Root cause analysis identified a misconfigured Group Policy Object (missing DNS suffix SearchList entry) as the culprit. Provided the Tier 3 Active Directory management team with the specific GPO configuration changes needed to resolve the issue enterprise-wide.

- **Remote SCCM Patch Orchestration:** Wrote a PowerShell tool that uses WMI remote registry to write SCCM reboot notification registry values and restart ccmexec on target computers, triggering Software Center restart prompts without mandatory enforcement. Users restart at their convenience, no phone calls or office visits. I resolved patching tickets entirely remotely while peers were asking users to drive to the office.

- **Bitlocker Compliance Auditing:** Built automated Bitlocker compliance reporting that queries AD computer objects for msFVE-RecoveryInformation to find systems missing AD-stored recovery keys. Domain-wide scanner compares on-device recovery passwords with AD records to catch sync failures that need re-escrow.

- **System Remediation Tooling:** Wrote PowerShell tools for common break/fix scenarios: Windows Update Agent reset (stop BITS/WUA services, clear SoftwareDistribution folder, re-register 30+ DLLs per Microsoft docs) and WMI repository repair (adapted Microsoft's script to filter autorecover/deleteinstance/deleteclass MOF files that broke on Windows 10+). Fixed machines remotely instead of reimaging.

### Helpdesk Technician
**Coastal IT Support** | Hawaii | February 2018 – February 2019

- **Network Discovery & Asset Documentation (Auvik):** Deployed Auvik network monitoring across MSP client environments, discovered undocumented switches, firewalls, and servers still running factory-default credentials. Configured WinRM, SNMP, and SSH integration for device profiling. Documented all network assets, changed default credentials on discovered iDRAC/iLO and SonicWall devices, and built baseline inventories for environments that had none.

- **OS Deployment Automation (MDT/WDS):** Technicians were spending hours babysitting individual Windows 10 installs. Set up MDT/WDS imaging server with VLAN isolation for PXE boot automation. New computers go from bare metal to fully imaged with standard software (RMM, Webroot, Office) in 30 minutes instead of 3+ hours of hands-on work.

- **Out-of-Band Server Management:** Configured iDRAC/iLO access for client servers to enable remote power operations after power outages. Documented credentials and created procedures for other technicians, eliminating site visits previously required to physically power on servers when UPS-protected network equipment recovered but servers remained offline.

- **Remote Endpoint Remediation:** Figured out how to install RMM agents remotely using Webroot shell command execution and domain-joined psexec for computers that Auvik discovered but had no management software. No more client site visits or asking users to bring laptops in just to install an agent.

- **Azure Recovery Services Deployment:** Set up Azure Recovery Services for a non-profit client who had Azure credits sitting unused, gave them free direct-to-cloud offsite backups instead of relying solely on on-premises backup infrastructure.

- **Active Directory Lifecycle Automation:** Set up PowerShell + Task Scheduler to automatically prune stale AD computer and user accounts. Keeps the directory clean without someone manually auditing it.

- **Tableau Service Startup Automation:** Resolved recurring issue where Tableau Server services failed to start automatically after monthly patching-related server restarts. Worked with Tableau vendor support to identify required startup command sequence, then implemented PowerShell + Task Scheduler automation to run the commands before and after patching. Tableau support noted the issue for future software improvement.

- **SQL Server Backup Automation:** Configured SQL Server Agent to automate cleanup of SQL Server backups, preventing storage exhaustion from accumulated backup files.

- **Client Communication Automation:** Utilized Microsoft Flows (Power Automate) to automate regular email notices to clients, reducing manual follow-up overhead.

- **Email Deliverability Configuration:** Client emails kept getting flagged as spam. Set up SPF/DKIM/DMARC records in their DNS to fix email authentication.

---

## Technical Projects

### Apache Kafka Cluster with Observability Stack (April 2026)

- Ansible collection that deploys an 11-node environment across Rocky Linux 9 Molecule containers: Root CA, 3-node ZooKeeper ensemble, 3 Kafka brokers, Kafka UI, dedicated Prometheus/Grafana monitoring node, Nginx reverse proxy, and a Python traffic generator. Full stack tested entirely in containers.
- TLS end-to-end across the cluster: Root CA role generates per-node PKCS12 keystores and JKS truststores distributed via Ansible. ZooKeeper quorum runs on the TLS port (2281), Kafka inter-broker replication uses the SSL listener (9093), and Nginx terminates HTTPS with a CA-signed cert. JMX Exporter agents are loaded at JVM startup on all Kafka and ZooKeeper nodes; `kafka_exporter` adds consumer-group lag and offset metrics.
- Five Grafana dashboards deployed via file-provisioned JSON (no manual import): custom dashboards for broker throughput/partition health, consumer lag by group and topic, and ZooKeeper latency/connection counts; plus the community Node Exporter Full and kafka_exporter dashboards. Four Prometheus alert rules cover broker and ZooKeeper availability and under-replicated partitions.
- Nginx reverse proxy with HTTPS and HTTP→HTTPS redirect, basic auth on all routes, Kafka UI served at root `/` and Grafana at `/grafana/`. Handles the Grafana sub-path asset loading requirement (`serve_from_sub_path`) and React SPA routing correctly without manual workarounds.
- Python traffic generator using `kafka-python` produces to 5 topics with 3 consumer groups at deliberately different polling delays (1s / 8s / 15s) to create realistic, measurable consumer lag profiles. Dashboards show meaningful data immediately after `molecule converge` completes.
- Developed with GitHub Copilot Agent Mode using Molecule as the test harness. The agent's autonomous Run → Analyze → Fix loop iterates through converge/verify cycles without human intervention. An entire multi-service debugging session counts as one premium request regardless of iteration count.

### driftctl Fork: Terraform Drift Detection Tool (Golang) (April 2026)

- Forked [snyk/driftctl](https://github.com/snyk/driftctl) and re-architected it in Go to fix three fundamental limitations: no actual drift detection (it only compared state vs. live resources, never ran `terraform plan`), 103 separate AWS API enumerators that hit rate limits and required constant maintenance, and no CloudFormation awareness causing most resources to show as "Unmanaged" in mixed IaC environments.
- Replaced all 103 per-service API enumerators with a single AWS Config Advanced Query API call covering 132 resource type mappings. Eliminates rate-limiting risk and reduces the maintenance surface from 103 enumerator files to one SQL-style query. The tool runs with standard `ReadOnlyAccess` IAM permissions; inventory mode can be narrowed to just 5 IAM actions.
- Integrated HashiCorp's `terraform-exec` Go library to run `terraform init` + `terraform plan` against discovered root modules with parallel execution. This enables true attribute-level drift detection (e.g., a security group rule changed outside Terraform) rather than just identifying unmanaged resources.
- Built categorization logic that queries the CloudFormation API (`ListStacks` + `ListStackResources`) to classify CloudFormation-managed resources separately from genuinely unmanaged ones. Also filters default AWS resources (default event buses, SSO reserved roles, default KMS aliases) and service-linked roles to reduce false positives to a meaningful signal.
- Used Claude Code + Github Copilot for navigating the unfamiliar Go codebase and iterating on API integration, demonstrating practical AI-assisted development on a real open-source project rather than greenfield code.

### Elastic Cloud on Kubernetes on AWS EKS (February 2026)

- Deployed EKS v1.33 cluster via Terragrunt with SPOT instances (m5.xlarge family) across 2 AZs for 60-80% compute savings. IRSA roles for AWS Load Balancer Controller, External DNS, and EBS CSI Driver so there are zero static AWS credentials on the cluster.
- ArgoCD manages the entire stack through an App of Apps pattern with 14 child Applications across 7 sync waves. Kustomize base/overlay structure handles differences between local Rancher Desktop K3s and AWS EKS without duplicating manifests. Automated self-heal and prune keep the cluster in sync with Git.
- Full Elastic stack (Elasticsearch 8.17.4, Kibana, Fleet Server, Elastic Agent) deployed as ECK Operator custom resources. 3-node Elasticsearch cluster on encrypted gp3 EBS volumes. Elastic Agent runs as a DaemonSet collecting system and Kubernetes metrics from every node.
- Keycloak OIDC SSO across Elasticsearch, Kibana, ArgoCD, and Kiali. Solved an EKS hairpin NAT issue by splitting OIDC front-channel calls (public ALB URL) from back-channel token/JWKS calls (internal K8s DNS). Realm bootstrap and Elasticsearch role mappings handled by ArgoCD PostSync Jobs.
- Istio service mesh in sidecar mode on the Elastic namespace for L7 traffic observability through Kiali and Prometheus. 15 NetworkPolicies across 3 namespaces implementing default-deny-ingress with selective allow rules.
- AWS ALB with ACM wildcard TLS termination and CIDR-restricted access. External DNS auto-creates Route53 records from Ingress annotations. cert-manager with a self-signed CA issues internal TLS certs for all internal-only components.

### AI Job Search Automation with Orchestrator-Agent Pattern (February 2026)

- Built an AI-assisted job search system using GitHub Copilot prompt files with Claude models. Uses an orchestrator + agent pattern where orchestrators coordinate isolated subagents so each one gets clean context instead of drowning in accumulated job description tokens.
- Searches multiple platforms (Greenhouse, Lever, Ashby, Workday, Hiring Cafe) using Firecrawl MCP for scraping and Chrome DevTools MCP for browser automation. Scoring framework ranks positions 0-10 with boosters, penalties, and disqualifiers.
- Resume tailoring pipeline uses Claude Code slash commands to extract keywords from job postings, match against a full CV, and generate DOCX resumes and cover letters via Python docx library. Only uses skills actually listed in the CV, no fabrication.
- Config is modular: YAML for inclusions/exclusions, markdown for scoring rules, CSV for company monitoring targets. Easy to swap out for different roles or tech stacks.

### Multi-Distribution Container Build Pipeline (February 2026)

- CI/CD pipeline that builds 20 container images across 4 Linux distros (Alpine, UBI9, Ubuntu, Amazon Linux 2023) and 5 DevOps tools (Ansible, Terraform, Packer, Python, Golang) using GitHub Actions matrix strategy for parallel builds.
- Trivy scanning for CVEs, secrets, and misconfigs on every build. Generates SPDX SBOMs for supply chain visibility.
- All images run as non-root with distro-specific optimizations. Shared requirements files so you're not duplicating package lists across 20 Dockerfiles.
- Makefile handles local builds on Apple Silicon (ARM64), so you can build, test, scan, and shell into containers without waiting for CI.


### AWS Cloud Resume Challenge (March 2022)

- Built a static resume site on AWS: S3 for hosting, CloudFront for HTTPS delivery with a managed cache policy, ACM for TLS, and Route53 for DNS. Root domain redirects to www via S3 website redirect.
- Visitor counter built with API Gateway, Lambda (Python), and DynamoDB. Lambda uses an atomic DynamoDB UpdateItem so the count is accurate even with concurrent hits. API Gateway has rate limiting configured to avoid surprise costs.
- GitHub Actions CI/CD pipeline syncs the repo to S3 and invalidates the CloudFront cache on every push to main. Originally used IAM access keys; later migrated to GitHub OIDC so no long-lived credentials are stored in GitHub secrets.
- Infrastructure migrated from AWS SAM/CloudFormation to Terraform in 2025. Existing S3, CloudFront, ACM, and Route53 resources were imported into state. The SAM counter stack was replaced with new Terraform-managed resources and the old CloudFormation stacks deleted. State stored in S3 with native locking.

---

## Skills

### Cloud Platforms & Infrastructure

- **AWS Core Services:** EC2, S3, VPC, DynamoDB, RDS, Route 53, IAM, SSM, EKS, KMS, ASG, ELB, Kinesis Firehose, SQS, Transit Gateway, CloudFormation, Lambda, CloudWatch
- **Azure Services:** VPN Gateway, Site-to-Site VPN, Entra ID, Virtual Networks, Resource Manager, Azure Monitor, Azure Policy, Azure Arc
- **Multi-Cloud Integration:** Cross-cloud connectivity (AWS-to-Azure VPN), hybrid architecture

### Infrastructure as Code & Automation

- **IaC Tools:** Terraform, Terragrunt, AWS CloudFormation, Packer for image automation
- **Configuration Management:** Ansible playbooks, roles, and collections for enterprise deployments
- **Infrastructure Testing:** Ansible Molecule for container-based testing, Powershell Pester testing framework
- **Automation Frameworks:** PowerShell DSC, Selenium for web automation, Python scripting

### Container Technologies & DevOps

- **Container Orchestration:** Docker, Kubernetes, AWS EKS, IRSA roles for service accounts, External DNS, AWS Load Balancer Controller, Helm package management
- **EKS Components:** VPC-CNI networking, CoreDNS, kube-proxy, OIDC provider integration, multi-namespace isolation, EKS add-ons management
- **Persistent Storage:** EFS integration with Kubernetes, multi-AZ mount targets, CSI drivers, StatefulSets
- **CI/CD Platforms:** GitLab CI, GitHub Actions, Git workflows, ArgoCD for GitOps
- **Monitoring & Observability:** Splunk HA Cluster implementation, Elasticsearch, Prometheus (alerting rules, JMX Exporter, kafka_exporter), Grafana (dashboard-as-code via JSON file provisioning), CloudWatch, RDS Performance Insights

### Windows Infrastructure

- **Core Services:** Active Directory, GPO, DNS, PKI, PowerShell, Exchange DAG, WSUS, MDT/WDS, BITS
- **High Availability:** Windows Failover Clustering, File Server Clusters
- **Server Management:** WinRM, SNMP, iDRAC/iLO

### VMware Technologies

- **Platform:** vCenter, vSphere, VxRail, vSAN, Nutanix
- **VDI:** Horizon View, Unified Access Gateway (UAG), App Volumes
- **Monitoring:** vRealize Operations Manager, vRealize Log Insight
- **Automation:** PowerCLI

### Linux Infrastructure

- **Core Skills:** Bash, Cron, LVM, Systemd
- **Distributions:** RHEL, Rocky Linux, Amazon Linux, Ubuntu
- **Web/Proxy:** Nginx (reverse proxy, SSL termination, sub-path routing, HTTP→HTTPS redirect)

### Email Security

- **Protocols:** SPF, DKIM, DMARC

### AI-Assisted Development

- **AI Tools:** Claude Code CLI, GitHub Copilot
- **Model Context Protocol (MCP):** Firecrawl MCP for web scraping, Chrome DevTools MCP for browser automation
- **Patterns:** Orchestrator-agent pattern for breaking up token-heavy workloads, each subagent gets clean context instead of accumulating noise
- **Practical Usage:** AI pair programming for Terraform and Ansible, writing structured AI instructions for consistent and parseable output, building repeatable AI workflows with the same rigor as infrastructure code (version-controlled configs, modular design, testable components)

---

## Education

**Associate of Applied Science in Information Technology**  
Riverside Community College | December 2017

---

## Certifications

| Certification | Issuing Organization | Date |
|--------------|---------------------|------|
| Certified Kubernetes Application Developer (CKAD) | The Linux Foundation | June 2026 |
| AWS Solutions Architect Associate (AWS-SAA) | Amazon Web Services | January 2025 |
| Red Hat Certified Specialist: Containers (RHCS) - EX188 | Red Hat | September 2024 |
| Red Hat Certified Engineer (RHCE) - EX294 Ansible | Red Hat | February 2022 |
| VMware Certified Professional – Data Center Virtualization (VCP-DCV) | VMware | March 2021 |
| Offensive Security Certified Professional (OSCP) | Offensive Security | May 2020 |
| Microsoft Certified Solutions Expert – Core Infrastructure (MCSE) | Microsoft | May 2019 |

---

## Salary Information

- **Minimum Acceptable:** $80,000 USD
- **Target Range:** $100,000 - $130,000 USD
- **Notes:** Positions above $150,000 may carry senior-level expectations that exceed current experience level
