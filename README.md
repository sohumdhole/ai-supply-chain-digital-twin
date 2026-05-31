# AI Supply Chain Digital Twin

A realistic digital twin simulation of a supply chain network (Suppliers, Factories, Warehouses, Customers) featuring discrete-event logistics modeling (SimPy), dynamic disruption injection, SQLite event logging, and an AI Decision Engine providing operational recommendations during disruptions.

---

## 🌟 Key Features

1. **Discrete-Event Simulation (SimPy)**: Models material flows, daily production constraints at factories, $(s, S)$ inventory control policies, transit delays, and customer demand distributions.
2. **Interactive Controls**: Customize simulation parameters, demand volatility, and schedule specific disruptions (Port Closures, Supplier failures, Storms, and Demand Surges) at designated simulation days.
3. **Database Ledgers (SQLite)**: Automatically persists simulation runs, inventory tracking, shipments, customer orders, disruptions, and AI actions to database tables.
4. **AI Decision Engine**: Employs cognitive reasoning (Time-to-Survive vs. Time-to-Recovery) to assess disruption impact, evaluate cost-benefit trade-offs of alternative strategies (dual sourcing vs. expediting), and automatically apply mitigation actions.
5. **Interactive Dashboard (Streamlit)**:
   * **Network Map**: Visualization of geographic nodes (Suppliers, Factories, Warehouses, Customers) with colored indicator lines showing active bottlenecks or disruptions.
   * **KPI Analytics**: Multi-scenario comparison of Service Level, Fill Rate, and Costs between Baseline (Normal), Disrupted (No Mitigation), and AI-Mitigated runs.
   * **Inventory Curves**: Multi-series line charts of daily stock-on-hand levels.
   * **AI Control Room**: Explanatory cards showing the AI's impact assessment and recommended mitigation actions.

---

## 📂 Project Structure

```
supply_chain_digital_twin/
├── README.md                  # Comprehensive description, setup, & usage
├── requirements.txt           # Python dependency file
├── schema.sql                 # SQL schema definitions for SQLite
├── app.py                     # Streamlit multi-tab dashboard entry point
├── deployment_guide.md        # Guide on how to run, scale, and host
├── architecture.md            # System architecture details and diagrams
├── verify.py                  # Verification script to test environment, database, and optimization
├── Dockerfile                 # Docker configuration for containerized deployment
├── .dockerignore              # Excluded file paths for Docker builds
└── digital_twin/              # Main library directory
    ├── __init__.py
    ├── database.py            # SQLite helper classes for logging/retrieval
    ├── simulation.py          # SimPy core environment, nodes, transport, and disruptions
    ├── ai_engine.py           # Heuristic/analytical rule engine for mitigation
    ├── kpis.py                # Performance metric calculations & aggregations
    └── optimisation.py        # OR-Tools Mixed-Integer Linear Programming optimizer
```

---

## 🚀 Quick Start

1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the Streamlit Dashboard:
   ```bash
   streamlit run app.py
   ```

---

## 📊 Logistics KPIs Tracked

* **Service Level (%)**: Percentage of customer orders fulfilled instantly.
* **Fill Rate (%)**: Total product quantity successfully fulfilled divided by total units ordered.
* **Inventory Cost ($)**: Cumulative daily holding costs (Raw Materials: $0.50/unit/day, Factory Finished Goods: $1.00/unit/day, Warehouse Finished Goods: $1.50/unit/day).
* **Transportation Cost ($)**: Total costs of standard transit, expedited carrier premiums, and towing fees from highway breakdowns.
* **Stockout Penalty ($)**: Evaluated at $10.00 per unfulfilled customer demand unit, representing lost goodwill and contribution margin.
* **Total Operating Cost ($)**: Inventory Holding Cost + Transportation Cost + Stockout Penalties.
