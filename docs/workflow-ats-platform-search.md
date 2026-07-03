# ATS Platform Search Workflow

Searches multiple ATS platforms (Greenhouse, Lever, Ashby, etc.) for infrastructure roles using the Firecrawl MCP Server.

## Overview

The orchestrator builds a query matrix of **roles x job boards**, dispatches parallel Firecrawl search agents in batches, then aggregates and deduplicates results into the application queue.

## Flow Diagram

```mermaid
flowchart TD
    Start([/ats-platform-search]) --> LoadConfig

    subgraph init ["Phase 0: Configuration"]
        LoadConfig[Load config.yml<br>roles, job boards, search_config]
        LoadExcl[Load exclusions.yml<br>excluded companies]
        LoadConfig --> BuildQueue
        LoadExcl --> BuildQueue
    end

    BuildQueue[Build Query Matrix<br>role x job_board<br>primary tier first] --> PrimaryLoop

    subgraph primary ["Phase 1: Primary Tier"]
        PrimaryLoop[Split primary queries<br>into batches of 16]
        PrimaryLoop --> BatchDispatch1

        subgraph batch1 ["Batch N (up to 16 parallel agents)"]
            BatchDispatch1[/"Dispatch firecrawl-job-search agents"/]
            BatchDispatch1 --> Agent1_1["Agent: Search board<br>for role term"]
            BatchDispatch1 --> Agent1_2["Agent: Search board<br>for role term"]
            BatchDispatch1 --> Agent1_N["... up to 16"]
        end

        Agent1_1 --> Agg1[Aggregate results<br>track stats by role + board]
        Agent1_2 --> Agg1
        Agent1_N --> Agg1
        Agg1 --> TargetCheck1{target_positions<br>reached?}
        TargetCheck1 -->|No, more batches| PrimaryLoop
    end

    TargetCheck1 -->|No, primary exhausted| SecondaryLoop
    TargetCheck1 -->|Yes| Dedup

    subgraph secondary ["Phase 2: Secondary Tier (if needed)"]
        SecondaryLoop[Split secondary queries<br>into batches of 16]
        SecondaryLoop --> BatchDispatch2

        subgraph batch2 ["Batch N (up to 16 parallel agents)"]
            BatchDispatch2[/"Dispatch firecrawl-job-search agents"/]
            BatchDispatch2 --> Agent2_1["Agent: Search board<br>for role term"]
            BatchDispatch2 --> Agent2_2["Agent: Search board<br>for role term"]
            BatchDispatch2 --> Agent2_N["... up to 16"]
        end

        Agent2_1 --> Agg2[Aggregate results]
        Agent2_2 --> Agg2
        Agent2_N --> Agg2
        Agg2 --> TargetCheck2{target_positions<br>reached?}
        TargetCheck2 -->|No, more batches| SecondaryLoop
    end

    TargetCheck2 -->|Yes or exhausted| Dedup

    subgraph output ["Phase 3: Output"]
        Dedup[Read existing application_queue.csv<br>Deduplicate by company+title]
        Dedup --> WriteCSV[Append new positions<br>source_track = job_board]
        WriteCSV --> Report[Final Report<br>stats by role, by board<br>qualification rates]
    end

    Report --> End([Done])

    style init fill:#e8f4f8,stroke:#2196F3
    style primary fill:#e8f8e8,stroke:#4CAF50
    style secondary fill:#fff8e1,stroke:#FFC107
    style output fill:#f3e5f5,stroke:#9C27B0
```

## Firecrawl Job Search Agent Detail

Each dispatched agent executes in isolation with clean context:

```mermaid
flowchart TD
    Input([Receive: role_term,<br>job_board, time_filter]) --> Search

    Search["firecrawl_search()<br>quoted role term + site filter<br>+ exclusion keywords"] --> Parse

    Parse[Extract positions:<br>title, company, URL,<br>location, description] --> Filter

    subgraph filters ["Disqualification Pipeline (ordered)"]
        Filter --> F0{Company in<br>exclusions.yml?}
        F0 -->|Yes| Excluded
        F0 -->|No| F1{Title-level?<br>Senior/Lead/Staff/<br>Backend/Fullstack}
        F1 -->|Yes| Excluded
        F1 -->|No| F2{Location?<br>non-US, non-remote,<br>hybrid, on-site}
        F2 -->|Yes| Excluded
        F2 -->|No| F3{Company/Industry?<br>Crypto, AI startup,<br>MSP, consulting}
        F3 -->|Yes| Excluded
        F3 -->|No| F4{Technical?<br>GCP-only, heavy Python,<br>bare-metal}
        F4 -->|Yes| Excluded
        F4 -->|No| F5{Cultural?<br>24/7 on-call,<br>experience/education}
        F5 -->|Yes| Excluded
    end

    F5 -->|No| Score

    subgraph scoring ["Scoring (0-10 scale)"]
        Score[Base score: 5] --> Boost
        Boost["Apply boosters:<br>Terraform +2, Ansible +2<br>AWS-focused +2, K8s +1"] --> Penalize
        Penalize["Apply penalties:<br>per scoring_framework.md"] --> Cap
        Cap["Cap at 0-10"] --> Threshold{Score >= 4?}
    end

    Threshold -->|Yes| Qualified[Add to qualified_positions]
    Threshold -->|No| Excluded[Add to excluded_positions<br>with reason]

    Qualified --> Output
    Excluded --> Output
    Output(["Return JSON:<br>qualified + excluded<br>+ stats"])

    style filters fill:#fff3e0,stroke:#FF9800
    style scoring fill:#e8f5e9,stroke:#4CAF50
```

## Key Configuration

| Config File | Used For |
|---|---|
| `config/config.yml` | Job boards list, primary/secondary role terms, search_config (time_filter, search_limit) |
| `config/exclusions.yml` | Companies to skip before any scoring |
| `shared/scoring_framework.md` | Boosters, penalties, disqualifiers for scoring |
| `results/application_queue.csv` | Deduplication target + output destination |
