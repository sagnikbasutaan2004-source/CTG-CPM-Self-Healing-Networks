# CTG-CPM: Master Technical Guide & Viva Preparation Manual
**Self-Healing Networks & Host Predictive Maintenance via Counterfactual Telemetry**

---

## Table of Contents
1. [Executive Summary & Core Concept](#1-executive-summary--core-concept)
2. [Data Layer: What Data is Used & How It is Collected](#2-data-layer-what-data-is-used--how-it-is-collected)
3. [The 5-Layer System Architecture](#3-the-5-layer-system-architecture)
4. [Deep-Dive into Algorithms & Internal Mechanics](#4-deep-dive-into-algorithms--internal-mechanics)
   - [Algorithm 1: GraphSAGE Graph Neural Network (GNN)](#algorithm-1-graphsage-graph-neural-network-gnn)
   - [Algorithm 2: Time-Series Diffusion Model (Diffusion-TS)](#algorithm-2-time-series-diffusion-model-diffusion-ts)
   - [Algorithm 3: Shapley Value Root-Cause Attribution](#algorithm-3-shapley-value-root-cause-attribution)
   - [Algorithm 4: VCG Auction for Agent Task Allocation](#algorithm-4-vcg-auction-for-agent-task-allocation)
   - [Algorithm 5: Extensive-Form Game & Backward Induction (SPE)](#algorithm-5-extensive-form-game--backward-induction-spe)
   - [Algorithm 6: Nash Equilibrium Conflict Resolution](#algorithm-6-nash-equilibrium-conflict-resolution)
   - [Algorithm 7: LLM-Powered Diagnostics (Groq Engine)](#algorithm-7-llm-powered-diagnostics-groq-engine)
5. [End-to-End Execution Flow (Step-by-Step Scenario)](#5-end-to-end-execution-flow-step-by-step-scenario)
6. [Codebase Map & Module Reference](#6-codebase-map--module-reference)
7. [Viva & Review Q&A Cheatsheet (Top 15 Questions & Answers)](#7-viva--review-qa-cheatsheet-top-15-questions--answers)
8. [Individual Contributions Breakdown](#8-individual-contributions-breakdown)

---

## 1. Executive Summary & Core Concept

### What is CTG-CPM?
**CTG-CPM** stands for **Counterfactual Telemetry Generation for Closed-Loop Predictive Maintenance**.

In simple terms:
- Traditional AI systems act like **smoke alarms**: they tell you that a server or network device is about to crash in 2 hours, but they **don't know why** and **don't know how to fix it**.
- Human NOC (Network Operations Center) engineers then have to manually guess what is wrong and deploy fix scripts onto live network traffic. This is **slow**, **risky** (can cause cascading outages), and **expensive** (leads to unnecessary hardware replacements called "truck rolls").

**CTG-CPM solves this completely**:
1. It uses **Generative AI** to create **"What-If" future projections** (Counterfactual Telemetry) that are clearly labelled as model/heuristic projections — **not** applied to or verified on live infrastructure.
2. It uses **Multi-Agent AI** to evaluate fix strategies via projected scenarios before any live deployment decision.
3. It uses **Algorithmic Game Theory** to coordinate agents' task allocation and conflict resolution.
4. It uses **LLM AI (Groq LPU)** to explain the problem and suggested steps in simple language for human operators.

Result (honest scope): **Sub-millisecond in-process decision compute (excluding LLM round-trip and real device deployment)**, potential OPEX savings **if** fewer truck-rolls result (not claimed as measured), and **zero-risk remediation is NOT claimed** — no command is auto-deployed in the prototype.

---

## 2. Data Layer: What Data is Used & How It is Collected

The system works with two primary data environments:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           TELEMETRY INGESTION                           │
│                                                                         │
│  LIVE LAPTOP HOST (psutil)             SIMULATED 5G OPTICAL TRANSCEIVER │
│  • CPU Load (% per core)               • OSNR (Optical Signal-to-Noise) │
│  • CPU Frequency (MHz)                 • Laser Bias Current (mA)        │
│  • Memory Used & Available (MB)        • Operating Temperature (°C)     │
│  • Swap Usage (%)                      • Packet Loss Rate (%)           │
│  • Disk Read/Write Rates (KB/s)        • Throughput (Gbps)              │
│  • Battery & Thermal Levels            • Anomaly Flag Indicators        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1. Live Laptop Host Telemetry (`telemetry_collector.py`)
- **Library used**: `psutil` (Python Process and System Utilities).
- **Data points collected**:
  - `cpu_overall_percent`: Overall CPU utilization across all cores.
  - `cpu_per_core`: Array of individual CPU core loads.
  - `cpu_frequency_mhz`: Operating CPU clock speed.
  - `memory_percent` & `memory_used_mb`: RAM consumption.
  - `disk_read_kbps` & `disk_write_kbps`: I/O throughput.
  - `top_processes`: List of top CPU-consuming process names, PIDs, and usage %.

### 2. 5G Optical Backhaul Telemetry (Simulated)
- **Data points generated**:
  - `osnr_db`: Optical Signal-to-Noise Ratio (Normal: ~22.4 dB, Anomaly: < 18.0 dB).
  - `laser_bias_ma`: Current powering the optical laser (Normal: ~45 mA, Anomaly: > 65 mA).
  - `temperature_celsius`: Physical transceiver temp (Normal: ~52°C, Anomaly: > 75°C).
  - `packet_loss_percent`: Percentage of lost data packets (Normal: 0.01%, Anomaly: > 3.0%).

### 3. Streaming Transport (Real Kafka)
- **Streaming Telemetry Bus**: A REAL Apache Kafka broker (default `localhost:9092`). Producers/consumers connect to the actual broker. If no broker is reachable, the system **reports `kafka_status: unavailable`** and does **not** silently substitute an emulator. An explicit, clearly-labelled local JSON debug file can optionally capture events offline (`offline_debug`), and is never reported as a broker.
- **Time-Series Database (production)**: InfluxDB or Prometheus for metrics storage.
- **Graph Database (production)**: Neo4j for network topology graph storage.

---

## 3. The 5-Layer System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│ LAYER 5: EXECUTION LAYER                                                 │
│ • NETCONF/YANG API Gateway  • PowerShell Script Generator  • Rollback     │
├──────────────────────────────────────────────────────────────────────────┤
│ LAYER 4: AGENTIC GAME THEORY LAYER                                       │
│ • VCG Task Auction  • Shapley RCA  • Backward Induction SPE  • Nash Eq. │
├──────────────────────────────────────────────────────────────────────────┤
│ LAYER 3: GenAI COUNTERFACTUAL LAYER                                      │
│ • Time-Series Diffusion Model (Diffusion-TS)  • "What-If" Generator      │
├──────────────────────────────────────────────────────────────────────────┤
│ LAYER 2: TOPOLOGY GNN LAYER                                              │
│ • GraphSAGE GNN  • Anomaly Detector  • Cascade Risk Predictor            │
├──────────────────────────────────────────────────────────────────────────┤
│ LAYER 1: DATA INGESTION & STORAGE LAYER                                  │
│ • Apache Kafka  • gNMI / SNMP Collectors  • psutil  • InfluxDB / Neo4j   │
└──────────────────────────────────────────────────────────────────────────┘
```

### Layer-by-Layer Breakdown:

1. **Layer 1 (Data Layer)**: Continuously streams raw telemetry metrics from physical servers or optical transceivers into real-time storage.
2. **Layer 2 (Topology Layer)**: Uses a Graph Neural Network (GraphSAGE) to understand how devices are connected physically and detect when a metric strays outside safe thresholds.
3. **Layer 3 (GenAI Layer)**: When an anomaly occurs, Generative AI creates parallel "What-If" futures representing different possible fix actions.
4. **Layer 4 (Agentic Game Theory Layer)**: Multi-Agent AI coordinates using formal mathematical rules (VCG, Shapley, SPE, Nash) to select the optimal fix without agent conflicts.
5. **Layer 5 (Execution Layer)**: Converts the verified fix into executable commands (NETCONF XML for routers, PowerShell for Windows) and applies it safely.

---

## 4. Deep-Dive into Algorithms & Internal Mechanics

---

### Algorithm 1: Graph Neural Network (GNN) — GCN & GraphSAGE
- **Role**: Topology-Aware Anomaly Detection & Cascade Risk Prediction.
- **Why this over standard CNNs/MLPs?**
  - Computer networks and data center servers are **graphs** (nodes connected by links), not 2D grids (images). Standard CNNs assume grid structures and fail on graph data.
- **Two supported architectures (both PyTorch)**:
  1. **GCN** (Graph Convolutional Network): symmetric-normalized adjacency aggregation `H' = σ(D^-1/2 A D^-1/2 H W)`. This is the architecture of the currently-shipped `gnn_model.pt` weights.
  2. **GraphSAGE**: genuine neighborhood sampling/aggregation via learned aggregators (`h_v = σ(W·[h_v ‖ mean_{u∈N(v)} h_u])`).
  - The report produced by `predict_cascade_risk` honestly identifies which architecture was used (`model_kind`), so a GCN is never mislabelled as GraphSAGE.
- **How it works internally**:
  1. Each device in the network is a node $v$.
  2. The GNN gathers telemetry features from node $v$'s connected neighbors.
  3. It combines neighbor information with node $v$'s own state to form an updated representation $h_v^k$.
  4. If node $v$'s embedding strays beyond normal bounds, an anomaly is flagged, and the GNN predicts which downstream connected nodes are at risk of cascading failure.

---

### Algorithm 2: Time-Series Diffusion Model (Diffusion-TS) & Heuristic Fallback
- **Role**: Counterfactual Telemetry **Projection** ("What-If" Future Simulator).
- **Why diffusion over GANs?**
  - GANs suffer from **mode collapse** and are unstable to train on continuous time-series metrics.
  - Diffusion models work via **denoising score matching**: they learn to reverse a gradual noise process, producing stable, high-fidelity synthetic time-series data.
- **How it works internally**:
  1. **Forward Process (Adding Noise)**: Takes baseline telemetry $x_0$ and gradually adds Gaussian noise over $T$ steps until it becomes pure noise $x_T$.
  2. **Reverse Process (Denoising)**: The AI neural network learns to remove noise step-by-step:
     $$x_{t-1} = \frac{1}{\sqrt{\alpha_t}} \left( x_t - \frac{1-\alpha_t}{\sqrt{1-\bar{\alpha}_t}} \epsilon_\theta(x_t, t) \right)$$
  3. **Intervention Conditioning**: The denoising process is conditioned on candidate actions $c$ (e.g. *c = "Throttle CPU 15%"*). The model outputs a synthetic 20-step time-series showing how temperature, OSNR, and load are **projected** to behave into the future under action $c$.
- **Honest provenance**: When `diffusion_ts_model.pt` weights load successfully, the learned diffusion model is used as the primary generator and the scenario is tagged `generator: "diffusion"`. If weights are absent or inference fails, an explicitly-labelled heuristic state-space trajectory model is used and tagged `generator: "heuristic"`. **Every projected scenario is labelled a projection, not a live-verified outcome.** The Diffusion-TS model is trained on synthetic data that follows an exponential trajectory prior, so it reflects that prior — its `is_learned` flag must be interpreted accordingly.
- **Honest health score**: the per-scenario health score is an informational diagnostic of the projected final state, **not** a claim that the fix was applied and verified on the live system.

---

### Algorithm 3: Shapley Value Root-Cause Attribution
- **Role**: Fairly determines how much each metric contributed to an anomaly.
- **Why this over simple correlation/regression?**
  - Standard correlation confuses cause and effect (e.g. high fan speed correlates with high temp, but fan speed isn't the cause).
  - Shapley values come from **Cooperative Game Theory** (Nobel Prize winning concept by Lloyd Shapley). They evaluate every possible subset of features to measure a feature's true marginal contribution.
- **Formula**:
  $$\phi_i(v) = \sum_{S \subseteq N \setminus \{i\}} \frac{|S|!(|N|-|S|-1)!}{|N|!} \big[v(S \cup \{i\}) - v(S)\big]$$
- **Properties guaranteed**:
  - **Efficiency**: Sum of all feature contributions equals the total anomaly score.
  - **Symmetry**: Two features contributing equally get equal attribution.
  - **Null Player**: A feature that never impacts the outcome gets $0\%$ weight.

---

### Algorithm 4: VCG (Vickrey-Clarke-Groves) Auction for Task Allocation
- **Role**: Assigns tasks (Diagnostics, Bargaining, Execution) to the best AI agent.
- **Why this over simple heuristic assignment?**
  - In multi-agent systems, agents might "overstate" their suitability to get assigned tasks.
  - VCG is a second-price auction mechanism that guarantees **Dominant-Strategy Incentive Compatibility (DSIC)**: an agent's best strategy is ALWAYS to report its true capability.
- **Payment Formula**:
  $$\text{Payment}_i = \sum_{j \neq i} v_j(a_{-i}^*) - \sum_{j \neq i} v_j(a^*)$$
- **Example in CTG-CPM**:
  - Agent 1 bids 98 on Diagnostics $\rightarrow$ Assigned Diagnostics.
  - Agent 2 bids 95 on Bargaining $\rightarrow$ Assigned Bargaining.
  - Agent 3 bids 99 on Execution $\rightarrow$ Assigned Execution.

---

### Algorithm 5: Extensive-Form Game & Backward Induction (SPE)
- **Role**: Models resource bargaining between the system host (P2) and the remediation agent (P1).
- **Game Setup**:
  - **P2 (Hardware/System)** chooses Investment level:
    - *High Investment*: Surplus = 18, Cost to P2 = 2.
    - *Low Investment*: Surplus = 14, Cost to P2 = 1.
  - **P1 (Remediation Agent)** proposes Split:
    - *Fair*: Equal 50/50 split of surplus.
    - *Greedy*: P1 takes Surplus - 1, P2 gets 1.
  - **P2 (System Response)** responds:
    - *Accept*: Both get shares, P2 pays cost.
    - *Reject*: Surplus destroyed (0), P2 still pays cost.

- **Backward Induction Solution (Step-by-Step)**:
  1. **Terminal Nodes (P2 Response)**:
     - High & Fair: Accept gives $7$, Reject gives $-2 \rightarrow$ **Accept**
     - High & Greedy: Accept gives $-1$, Reject gives $-2 \rightarrow$ **Accept**
     - Low & Fair: Accept gives $6$, Reject gives $-1 \rightarrow$ **Accept**
     - Low & Greedy: Accept gives $0$, Reject gives $-1 \rightarrow$ **Accept**
  2. **P1 Proposal Choice**:
     - Under High Investment: Greedy gives P1 $17$, Fair gives $9 \rightarrow$ **Greedy**
     - Under Low Investment: Greedy gives P1 $13$, Fair gives $7 \rightarrow$ **Greedy**
  3. **P2 Initial Choice**:
     - High Investment leads to Greedy Accept $\rightarrow$ Net P2 Payoff: $-1$
     - Low Investment leads to Greedy Accept $\rightarrow$ Net P2 Payoff: $0$
     - P2 compares $0 > -1 \rightarrow$ **P2 chooses Low Investment**.

- **Subgame Perfect Equilibrium (SPE) Path**:
  $$\text{Path} = (\text{Low Investment}, \text{Greedy Proposal}, \text{Accept}) \implies \text{Payoff: } (u_1 = 13.0, u_2 = 0.0)$$

---

### Algorithm 6: Nash Equilibrium Conflict Resolution
- **Role**: Prevents two remediation agents from taking conflicting actions (e.g. Agent A trying to load-balance traffic to Node 2 while Agent B takes Node 2 offline for maintenance).
- **How it works**:
  - Formulates a $2 \times 2$ payoff matrix between Agent A and Agent B strategies.
  - Uses **Best-Response Analysis**: finds cell $(r, c)$ where Agent A's action is optimal given B's choice AND B's action is optimal given A's choice.
  - Result: Guaranteed pure-strategy Nash Equilibrium with zero strategy conflicts.

---

### Algorithm 7: LLM-Powered Diagnostics (Groq Engine)
- **Role**: Converts complex telemetry, game theory math, and counterfactual scores into clear, human-understandable JSON diagnostics.
- **LLM Used**: Groq Cloud API with `openai/gpt-oss-20b` model.
- **Why Groq?** Groq's LPU (Language Processing Unit) architecture can return LLM analysis quickly (typically under a second for small payloads). This latency applies to the LLM diagnostic step only, and is separate from (and additional to) the in-process decision-compute time. We do not claim a single sub-second end-to-end MTTR.
- **Structured JSON Schema Output**:
  ```json
  {
    "severity": "High",
    "problem_title": "CPU and Memory Saturation",
    "problem_description": "CPU utilization is at 92.5% with memory at 78.3%. This indicates thermal stress...",
    "root_cause": "High CPU workload (50% Shapley attribution) combined with memory pressure...",
    "risk_if_unresolved": "Thermal throttling and system crashes within 2-4 hours...",
    "remediation_steps": [
      {"step_number": 1, "action": "Identify High CPU Processes", "detail": "...", "expected_impact": "..."},
      {"step_number": 2, "action": "Apply CPU Throttling 85%", "detail": "...", "expected_impact": "..."},
      {"step_number": 3, "action": "Optimize Memory Cache", "detail": "...", "expected_impact": "..."}
    ],
    "expected_outcome": "System health score is projected to improve from 24.5 to 83.0/100 (projection, not live-verified).",
    "truck_roll_avoided": "potential (not measured)",
    "estimated_fix_time": "Decision compute only (excludes deployment)"
  }
  ```

---

## 5. End-to-End Execution Flow (Step-by-Step Scenario)

Here is what happens inside the system during a real incident:

```
[TELEMETRY STREAM] → [ANOMALY DETECTED] → [GENERATE WHAT-IF] → [GAME THEORY & LLM] → [AUTONOMOUS FIX]
```

### Incident Scenario: 5G Optical Fiber Transceiver Degradation

1. **Step 1: Detection (~1s)**
   - Telemetry collector reads OSNR = $16.87\text{ dB}$ (below the $18.0\text{ dB}$ threshold).
   - GraphSAGE GNN flags node `opt-transceiver-5g-01` as degraded and identifies 3 downstream nodes at cascade risk.

2. **Step 2: Generation (~2s)**
   - Time-Series Diffusion model synthesizes 4 parallel future streams:
     - *Scenario 1 (Status Quo)*: Health Score = 24.5 (Unstable, OSNR drops to 10 dB)
     - *Scenario 2 (Adjust Laser Bias)*: Health Score = 85.0 (Stabilized, OSNR > 20 dB)
     - *Scenario 3 (Throttle 15%)*: Health Score = 83.0 (Stabilized)
     - *Scenario 4 (Reroute)*: Health Score = 78.0 (Stabilized)

3. **Step 3: Simulation & Negotiation (~2s)**
   - VCG Auction assigns task roles to Agent 1 (Diagnostics), Agent 2 (Bargaining), Agent 3 (Execution).
    - Agent 1 computes Shapley attribution to weight each telemetry feature's contribution to the anomaly (values are computed per-run, not fixed).
   - Agent 2 solves Backward Induction SPE $\rightarrow$ selects `(Low Investment, Greedy, Accept)`.
   - Groq LLM generates structured problem summary and 3-step remediation instructions.
    - Agent 3 selects the highest-projected candidate via the counterfactual projection stream and generates a recommended remediation command (NOT auto-deployed).

4. **Step 4: Recommendation Generation (~compute under 10ms)**
   - System generates a NETCONF XML configuration **recommendation**:
     ```xml
     <interface name='opt-transceiver-5g-01'>
       <laser-bias>current-adjusted</laser-bias>
       <traffic-policy>load-balance-30</traffic-policy>
     </interface>
     ```
   - **In the prototype this is a recommendation only — it is NOT pushed to a device**; deployment is disabled unless a real transport is wired in (`deploy_commands=True`).
   - Status updated on Web Dashboard.
   - **Honest scope:** in-process decision compute is fast; end-to-end time including any real deployment is not claimed.

---

## 6. Codebase Map & Module Reference

```
d:\Predictive Maintenance Project 3\
├── game_engine.py           # Game Theory (SPE, VCG, Shapley, Nash)
├── telemetry_collector.py   # Live psutil host & 5G transceiver telemetry
├── counterfactual_engine.py # Diffusion "What-If" time-series generator
├── agentic_remediator.py    # 3-Agent self-healing orchestrator
├── llm_diagnostician.py     # Groq LLM diagnosis & JSON parser
├── app.py                   # Flask web server REST APIs
├── main.py                  # CLI controller & demo runner
├── test_prototype.py        # Automated unit & integration test suite
├── templates/
│   └── index.html           # Premium glassmorphism Web UI
├── .env.example             # API key config template
└── generate_review2_ppt.py  # PowerPoint generator script
```

---

## 7. Viva & Review Q&A Cheatsheet (Top 15 Questions & Answers)

### Q1: Why did you use Counterfactual Telemetry instead of standard predictive ML?
> **Answer**: Standard predictive ML only tells you *that* a failure will happen. It doesn't tell you *what will happen if you take action A vs action B*. Counterfactual telemetry generates hypothetical future time-series data under different candidate actions ("What-If" scenarios), enabling *prescriptive* self-healing before touching live infrastructure.

### Q2: How does your system reduce risk before remediation?
> **Answer**: Candidate fixes are evaluated against the GenAI counterfactual projection stream first, and the projected health score is used to *recommend* the safest option. However, in the current prototype **no command is auto-deployed** — the output is a recommendation, so we do **not** claim "zero-risk remediation" or that any fix was applied to a live device.

### Q3: Why is VCG Auction used for multi-agent task allocation?
> **Answer**: VCG (Vickrey-Clarke-Groves) is a mathematically proven auction mechanism that guarantees Dominant-Strategy Incentive Compatibility (DSIC). This means agents are incentivized to report their true capability scores, allowing a welfare-maximising task assignment. (Note: this is a theoretical guarantee of the mechanism; the prototype's agent capability "bids" are derived from telemetry plus a fixed capability matrix.)

### Q4: Explain the Subgame Perfect Equilibrium (SPE) outcome in your game tree.
> **Answer**: Using Backward Induction, Player 2 (System) prefers Accept at all final nodes. Player 1 (Remediation Agent) prefers Greedy proposals over Fair proposals. Backward induction shows that High Investment gives P2 a net payoff of $-1$, while Low Investment gives $0$. Since $0 > -1$, P2 chooses Low Investment, leading to the SPE equilibrium `(Low Investment, Greedy Proposal, Accept)` with final payoff $(13, 0)$.

### Q5: How do Shapley Values help in Root-Cause **Attribution** (RCA)?
> **Answer**: Shapley values come from cooperative game theory. Instead of simple correlation, Shapley values evaluate the marginal contribution of a metric across all possible combinations of telemetry features. This gives an axiomatic, fair weight (e.g. CPU 50%, Temp 30%) to each feature's contribution to the anomaly *score*. **Important caveat:** this is feature *attribution*, not validated *causal* root cause — we do not claim the top-attributed metric is definitely the physical cause without further validation.

### Q6: Why did you use a GNN instead of standard CNNs?
> **Answer**: Network topologies are non-Euclidean graphs (nodes connected by dynamic links). Standard CNNs require regular grid structures like images. Our GNN (GCN or GraphSAGE, reported honestly per run) aggregates node neighbor embeddings to capture topological connectivity and cascading failure propagation.

### Q7: Why use Diffusion Models for time-series generation instead of GANs?
> **Answer**: GANs suffer from mode collapse and training instability on time-series metrics. Time-Series Diffusion (Diffusion-TS) uses denoising score matching, which is stable, avoids mode collapse, and allows precise conditioning on intervention variables.

### Q8: Why did you choose Groq API over running a local LLM?
> **Answer**: We chose a hosted LLM API (Groq) primarily for convenience and fast inference for the diagnostic step. Local LLMs can be slower and heavier to run on consumer hardware. We do **not** claim a sub-second end-to-end MTTR; Groq reduces the LLM diagnostic latency only, which is additive to the in-process decision compute.

### Q9: What happens if the Groq LLM API fails or goes offline?
> **Answer**: The system has a built-in `_generate_fallback_diagnosis()` engine. If the LLM call fails, the system falls back to rule-based Shapley and game theory analysis rather than crashing.

### Q10: How could CTG-CPM reduce OPEX / truck-rolls?
> **Answer**: By recommending software and configuration fixes (e.g., laser bias adjustment or CPU throttling) that may extend equipment life and avoid unnecessary physical hardware replacements ("truck rolls"). **This is a stated potential benefit, not a measured outcome** — the prototype does not yet report measured OPEX savings or truck-roll avoidance rates.

### Q11: What is the difference between Live Host mode and 5G Network mode in your prototype?
> **Answer**: Live Host mode ingests real-time CPU, RAM, Disk I/O, and process telemetry from the user's laptop using `psutil`. 5G Network mode simulates an optical backhaul transceiver experiencing OSNR degradation. Both feed into the same multi-layer recommendation pipeline.

### Q12: How fast does your multi-agent decision pipeline execute?
> **Answer**: In our benchmark tests (`main.py` and `test_prototype.py`), the **in-process compute** of the multi-agent decision pipeline (VCG + Shapley + SPE + Nash + projection) runs very fast. The 5G mode, which loads and runs the real PyTorch GraphSAGE GNN and diffusion models, measures roughly **150–200 ms** on this machine; the laptop heuristic path (which skips the neural models) is far faster (around a fraction of a millisecond). Because LLM round-trip and real device deployment are excluded, this is **compute latency only** — we do **not** claim sub-second end-to-end MTTR.

### Q13: What script formats are generated for execution?
> **Answer**: For 5G telecom networks, it generates **NETCONF/YANG XML** configuration payloads. For host laptop systems, it generates **PowerShell commands** for process priority demotion and CPU frequency capping.

### Q14: How does Nash Equilibrium prevent agent conflicts?
> **Answer**: When two agents propose remediation strategies, we construct a 2-player normal-form payoff matrix. Using best-response analysis, we find the pure-strategy Nash Equilibrium where neither agent can improve by changing action, preventing conflicting actions (e.g., load-balancing to a node being taken offline).

### Q15: Is your codebase publicly accessible for verification?
> **Answer**: Yes! The complete codebase (15 files, 3,368+ lines of code, unit tests) is committed to GitHub at `https://github.com/sagnikbasutaan2004-source/CTG-CPM-Self-Healing-Networks`.

---

## 8. Individual Contributions Breakdown

| Team Member | Reg No | Contribution % | Key Deliverables & Responsibilities |
| :--- | :--- | :--- | :--- |
| **Sagnik Basu** | `23MID0042` | **33.3%** | • Overall System Architecture & 5-Layer Stack Design<br>• Game Theory Engine (`game_engine.py`: VCG, Shapley, SPE, Nash)<br>• Groq LLM Diagnostics Integration (`llm_diagnostician.py`) & JSON parsing<br>• GitHub Repo setup, Git security audit & automated unit testing (`test_prototype.py`) |
| **C Sriharsha** | `23MID0111` | **33.3%** | • Telemetry Collection Engine (`telemetry_collector.py`)<br>• Real-time `psutil` host metric ingestion (CPU, RAM, Disk, Processes)<br>• 5G Optical Transceiver anomaly generator<br>• CLI Orchestrator (`main.py`) & sub-second pipeline timing benchmarks |
| **Maitree Singh** | `23MID0076` | **33.3%** | • Generative Counterfactual Engine (`counterfactual_engine.py`) for "What-If" projections<br>• Multi-Agent Remediation Orchestrator (`agentic_remediator.py`) & projection-based recommendation<br>• HMW-Style Modern Glassmorphism Web App UI (`templates/index.html`)<br>• Flask Server REST API endpoints (`app.py`) |

---

*Document compiled for Review 2 & Viva Defense — CTG-CPM Self-Healing Networks Project.*
