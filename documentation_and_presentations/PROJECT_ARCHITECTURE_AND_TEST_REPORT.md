# CTG-CPM: Self-Healing Networks via Counterfactual Telemetry
## System Architecture & Complete Application Test Report

**Project Title:** CTG-CPM: Autonomous Predictive Maintenance & Self-Healing Networks via Counterfactual Telemetry Generation & Game-Theoretic Multi-Agent AI  
**Version:** 2.0 (Honest Dynamic & Model Provenance Release)  
**Date:** August 2026  
**Repository Path:** `d:\Predictive Maintenance Project 3`

---

## 1. Executive Summary

CTG-CPM is an enterprise-grade predictive maintenance decision architecture designed for 5G optical backhaul networks and host computing infrastructure. The system combines:
- **Real-Time Telemetry Streaming**: Apache Kafka bus integration (`localhost:9092`) with live `psutil` host hardware sampling and synthetic 5G optical fiber fault generation.
- **Graph Neural Network (GNN) Cascade Analysis**: PyTorch Graph Convolutional Network (GCN) and GraphSAGE models for topological node risk score estimation.
- **Counterfactual Telemetry Generation**: Generative time-series modeling via Diffusion (`diffusion_ts_model.pt`) and labeled physics-based heuristic fallbacks to simulate "what-if" intervention scenarios.
- **Dynamic Game-Theoretic Decision Engine**: Multi-agent task allocation via Vickrey-Clarke-Groves (VCG) auctions, exact Shapley value feature attribution for root-cause isolation, and Subgame Perfect Equilibrium (SPE) backward induction for optimal cost-risk trade-off.
- **Interactive UI & LLM Diagnostics**: Flask web interface (`app.py`, `templates/index.html`) integrated with Google Gemini LLM diagnostic generation and fallback diagnostic templates.

---

## 2. System Architecture & Component Breakdown

```
 +-----------------------------------------------------------------------------------+
 |                             LAYER 1: DATA INGESTION                               |
 |   [Laptop Host Telemetry (psutil)]     [Synthetic 5G Optical Fiber Generator]     |
 |                                  \     /                                          |
 |                           [Apache Kafka Producer]                                 |
 +-----------------------------------------------------------------------------------+
                                       |
                                       v
 +-----------------------------------------------------------------------------------+
 |                         LAYER 2: NEURAL MODELING & CF                             |
 |       [GNN Topology Model (GCN/GraphSAGE)] --> Cascade Risk Assessment            |
 |       [Counterfactual Generator (Diffusion TS Model)] --> Projected Trajectories  |
 +-----------------------------------------------------------------------------------+
                                       |
                                       v
 +-----------------------------------------------------------------------------------+
 |                   LAYER 3: GAME-THEORETIC MULTI-AGENT ENGINE                      |
 |       [VCG Auction Allocator]      [Shapley Root Cause Attributor]                |
 |       [Bargaining Game Tree (SPE via Backward Induction)]                         |
 |       [Multi-Agent Remediator] --> Emits Structured Remediation Recommendations    |
 +-----------------------------------------------------------------------------------+
                                       |
                                       v
 +-----------------------------------------------------------------------------------+
 |                    LAYER 4: DIAGNOSTICS & DASHBOARD INTERFACE                     |
 |       [LLM Diagnostician (Google Gemini API / Heuristic Fallback Engine)]         |
 |       [Flask Web Dashboard (http://127.0.0.1:5000) & Interactive CLI (main.py)]   |
 +-----------------------------------------------------------------------------------+
```

### Key Python Module Descriptions

| File / Module | Responsibility & Architecture Role |
| :--- | :--- |
| **`telemetry_collector.py`** | Ingests live host hardware metrics (`psutil`: CPU, RAM, Disk I/O, Top Processes, dynamic Z-score) and generates synthetic 5G optical fiber telemetry (OSNR, laser bias current, temperature). |
| **`kafka_telemetry_streaming.py`** | Connects to Apache Kafka (`localhost:9092`). Reports `connected` when broker is live and gracefully falls back to `unavailable` when no broker is running without throwing exceptions. |
| **`gnn_topology_model.py`** | Implements PyTorch Graph Convolutional Networks (GCN) & GraphSAGE (`gnn_model.pt`) for network topology graph node risk evaluation. |
| **`diffusion_ts_model.py`** | PyTorch conditional 1D convolutional diffusion neural network for time-series counterfactual trajectory generation. |
| **`counterfactual_engine.py`** | Orchestrates counterfactual projections. Employs `DiffusionTSModel` primary generator with tagged heuristic fallbacks (`projected_health_score`, `generator`). |
| **`game_engine.py`** | Core dynamic game theory suite: VCG auction task allocator, Shapley value root-cause attributor, and Nash/SPE bargaining solver using backward induction. |
| **`agentic_remediator.py`** | Multi-agent orchestrator (`MultiAgentRemediator`). Coordinates VCG task allocation, Shapley attribution, SPE bargaining, and counterfactual analysis to generate structured recommendations. |
| **`llm_diagnostician.py`** | Leverages Google Gemini LLM (`google-generativeai`) to produce human-readable diagnostic summaries and step-by-step remediation plans, supported by a deterministic fallback generator. |
| **`app.py`** | Flask web app server exposing REST APIs (`/api/telemetry`, `/api/run_pipeline`, `/api/game_tree`, `/api/toggle_anomaly`) and serving the interactive dashboard (`templates/index.html`). |
| **`main.py`** | Interactive CLI demonstrator offering live laptop host monitoring, synthetic 5G backhaul fault simulation, and game tree solving. |
| **`train_and_evaluate.py`** | Training script for GNN and Diffusion models; generates synthetic dataset and saves trained PyTorch state dicts (`gnn_model.pt`, `diffusion_ts_model.pt`). |
| **`test_prototype.py`** | Automated unit and integration test suite asserting mathematical models, auction allocators, counterfactual engines, and fallback behavior. |

---

## 3. Mathematical & Algorithmic Foundations

### 3.1 Vickrey-Clarke-Groves (VCG) Task Auction
Agents bid on diagnostic sub-tasks ($T_k$) based on current telemetry dynamic urgency:
$$\text{Social Welfare Maximization}: \quad a^* = \arg\max_{a} \sum_{i} v_i(a_i)$$
Payments incentivizing truthful bidding:
$$p_i = \max_{a' \setminus i} \sum_{j \neq i} v_j(a'_j) - \sum_{j \neq i} v_j(a^*_j)$$

### 3.2 Shapley Value Feature Attribution
Calculates exact marginal contribution of telemetry features $i \in N$ to system anomaly score:
$$\phi_i(v) = \sum_{S \subseteq N \setminus \{i\}} \frac{|S|!(|N| - |S| - 1)!}{|N|!} \big( v(S \cup \{i\}) - v(S) \big)$$

### 3.3 Subgame Perfect Equilibrium (SPE) Bargaining
Solves the extensive form bargaining game between Network Maintenance Provider ($P_1$) and Resource Operator ($P_2$) via Backward Induction:
$$u_1(a^*) = S - u_2(a^*), \quad u_2(a^*) = \delta \cdot \text{Reserve Payoff}$$

---

## 4. Verification & Test Execution Results

### 4.1 Python Compilation Check
All 15 Python codebase files passed syntax validation:
- `app.py`: **OK**
- `main.py`: **OK**
- `gnn_topology_model.py`: **OK**
- `counterfactual_engine.py`: **OK**
- `kafka_telemetry_streaming.py`: **OK**
- `telemetry_collector.py`: **OK**
- `agentic_remediator.py`: **OK**
- `llm_diagnostician.py`: **OK**
- `test_prototype.py`: **OK**
- `train_and_evaluate.py`: **OK**
- `dataset_generator.py`: **OK**
- `game_engine.py`: **OK**
- `create_ppt.py`: **OK**
- `generate_review2_ppt.py`: **OK**
- `convert_guide_to_pdf.py`: **OK**

### 4.2 Automated Unit & Integration Suite (`test_prototype.py`)
- **Backward Induction SPE Default**: Passed (`payoffs = (13.0, 0.0)`).
- **Dynamic Telemetry Game Tree**: Passed (valid parameters derived from OSNR & temperature).
- **VCG Auction Allocation**: Passed (optimal social allocation assigned).
- **Dynamic Shapley Attribution**: Passed (feature contributions sum to exactly 100.0%).
- **Laptop Telemetry Collector**: Passed (live `psutil` sampling verified).
- **Counterfactual Generator**: Passed (scenarios tagged with honest provenance & projection notes).
- **Multi-Agent Remediator Pipeline**: Passed (in-process decision compute latency < 10ms; honest `recommendation_only` status).
- **Kafka Streaming Integration**: Passed (graceful status handling when broker offline).

---

## 5. Consolidated Project Documentation & Presentations

All project documentation, slide presentations, and technical PDF guides have been consolidated into the unified directory:
`documentation_and_presentations/`

Consolidated Files:
1. `COMPREHENSIVE_SYSTEM_GUIDE.md`: Full technical guide & viva preparation manual.
2. `COMPREHENSIVE_SYSTEM_GUIDE.pdf`: Compiled PDF version of master guide.
3. `CTG-CPM- Self-Healing Networks via Counterfactual Telemetry (1).pptx`: Main project presentation.
4. `CTG-CPM_Implementation_Plan.pptx`: Project architecture & implementation plan slides.
5. `CTG-CPM_Review2_Presentation.pptx`: Review 2 presentation slide deck.
6. `PROJECT_ARCHITECTURE_AND_TEST_REPORT.md`: This comprehensive architecture and test report.
