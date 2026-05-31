-- Schema definitions for the AI Supply Chain Digital Twin

CREATE TABLE IF NOT EXISTS simulation_runs (
    run_id TEXT PRIMARY KEY,
    scenario_type TEXT NOT NULL, -- 'baseline', 'disrupted', 'mitigated'
    start_time TEXT NOT NULL,
    duration_days INTEGER NOT NULL,
    demand_mean REAL,
    demand_std REAL
);

CREATE TABLE IF NOT EXISTS nodes (
    run_id TEXT,
    node_id TEXT,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- 'Supplier', 'Factory', 'Warehouse', 'Customer'
    lat REAL,
    lon REAL,
    capacity REAL,
    PRIMARY KEY (run_id, node_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inventory_log (
    run_id TEXT,
    timestamp REAL NOT NULL, -- simulation time in days
    node_id TEXT NOT NULL,
    product_type TEXT NOT NULL, -- 'raw_material', 'finished_good'
    quantity REAL NOT NULL,
    holding_cost REAL NOT NULL,
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS orders (
    run_id TEXT,
    order_id TEXT,
    customer_id TEXT NOT NULL,
    warehouse_id TEXT NOT NULL,
    product_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    ordered_time REAL NOT NULL,
    fulfilled_time REAL,
    status TEXT NOT NULL, -- 'Pending', 'Fulfilled', 'Stockout'
    price_per_unit REAL NOT NULL,
    PRIMARY KEY (run_id, order_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS shipments (
    run_id TEXT,
    shipment_id TEXT,
    source_id TEXT NOT NULL,
    dest_id TEXT NOT NULL,
    product_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    status TEXT NOT NULL, -- 'In_Transit', 'Delivered', 'Delayed'
    dispatch_time REAL NOT NULL,
    estimated_delivery REAL NOT NULL,
    actual_delivery REAL,
    transport_cost REAL NOT NULL,
    mode TEXT NOT NULL, -- 'Standard', 'Expedited'
    disruption_cause TEXT,
    PRIMARY KEY (run_id, shipment_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS disruptions (
    run_id TEXT,
    disruption_id TEXT,
    type TEXT NOT NULL, -- 'port_closure', 'supplier_failure', 'truck_breakdown', 'demand_surge'
    target TEXT NOT NULL, -- target node or route
    start_time REAL NOT NULL,
    end_time REAL,
    description TEXT,
    PRIMARY KEY (run_id, disruption_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_decisions (
    run_id TEXT,
    timestamp REAL NOT NULL,
    disruption_id TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    explanation TEXT NOT NULL,
    cost_benefit_estimate REAL,
    applied INTEGER NOT NULL, -- 0 or 1
    PRIMARY KEY (run_id, timestamp, disruption_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
);
