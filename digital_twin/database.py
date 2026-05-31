import os
import sqlite3
import pandas as pd
from datetime import datetime

# Resolve relative paths dynamically
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "digital_twin.db")
DEFAULT_SCHEMA_PATH = os.path.join(PROJECT_ROOT, "schema.sql")

class DatabaseManager:
    def __init__(self, db_path=None):
        self.db_path = db_path if db_path is not None else DEFAULT_DB_PATH
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self.init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Executes the schema file to initialize tables if they don't exist."""
        schema_path = DEFAULT_SCHEMA_PATH
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Schema file not found at {schema_path}")
            
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        with self._get_connection() as conn:
            conn.executescript(schema_sql)
            conn.commit()

    def log_run(self, run_id, scenario_type, duration_days, demand_mean, demand_std):
        start_time = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO simulation_runs (run_id, scenario_type, start_time, duration_days, demand_mean, demand_std)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, scenario_type, start_time, duration_days, demand_mean, demand_std)
            )
            conn.commit()

    def log_nodes(self, run_id, nodes_list):
        """nodes_list is a list of dicts: [{'node_id': ..., 'name': ..., 'type': ..., 'lat': ..., 'lon': ..., 'capacity': ...}]"""
        with self._get_connection() as conn:
            for node in nodes_list:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO nodes (run_id, node_id, name, type, lat, lon, capacity)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, node['node_id'], node['name'], node['type'], node['lat'], node['lon'], node.get('capacity'))
                )
            conn.commit()

    def log_inventory(self, run_id, timestamp, node_id, product_type, quantity, holding_cost):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO inventory_log (run_id, timestamp, node_id, product_type, quantity, holding_cost)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, timestamp, node_id, product_type, quantity, holding_cost)
            )
            conn.commit()

    def log_order(self, run_id, order_id, customer_id, warehouse_id, product_type, quantity, ordered_time, fulfilled_time, status, price_per_unit):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO orders (run_id, order_id, customer_id, warehouse_id, product_type, quantity, ordered_time, fulfilled_time, status, price_per_unit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, order_id, customer_id, warehouse_id, product_type, quantity, ordered_time, fulfilled_time, status, price_per_unit)
            )
            conn.commit()

    def log_shipment(self, run_id, shipment_id, source_id, dest_id, product_type, quantity, status, dispatch_time, estimated_delivery, actual_delivery, transport_cost, mode, disruption_cause=None):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO shipments (run_id, shipment_id, source_id, dest_id, product_type, quantity, status, dispatch_time, estimated_delivery, actual_delivery, transport_cost, mode, disruption_cause)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, shipment_id, source_id, dest_id, product_type, quantity, status, dispatch_time, estimated_delivery, actual_delivery, transport_cost, mode, disruption_cause)
            )
            conn.commit()

    def log_disruption(self, run_id, disruption_id, type_str, target, start_time, end_time=None, description=""):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO disruptions (run_id, disruption_id, type, target, start_time, end_time, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, disruption_id, type_str, target, start_time, end_time, description)
            )
            conn.commit()

    def log_ai_decision(self, run_id, timestamp, disruption_id, recommendation, explanation, cost_benefit_estimate=0.0, applied=1):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ai_decisions (run_id, timestamp, disruption_id, recommendation, explanation, cost_benefit_estimate, applied)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, timestamp, disruption_id, recommendation, explanation, cost_benefit_estimate, applied)
            )
            conn.commit()

    # Query methods returning pandas dataframes
    def get_runs(self):
        with self._get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM simulation_runs ORDER BY start_time DESC", conn)

    def get_nodes(self, run_id):
        with self._get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM nodes WHERE run_id = ?", conn, params=(run_id,))

    def get_inventory_logs(self, run_id):
        with self._get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM inventory_log WHERE run_id = ? ORDER BY timestamp ASC", conn, params=(run_id,))

    def get_orders(self, run_id):
        with self._get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM orders WHERE run_id = ?", conn, params=(run_id,))

    def get_shipments(self, run_id):
        with self._get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM shipments WHERE run_id = ?", conn, params=(run_id,))

    def get_disruptions(self, run_id):
        with self._get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM disruptions WHERE run_id = ?", conn, params=(run_id,))

    def get_ai_decisions(self, run_id):
        with self._get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM ai_decisions WHERE run_id = ?", conn, params=(run_id,))

    def clear_run(self, run_id):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM simulation_runs WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM nodes WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM inventory_log WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM orders WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM shipments WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM disruptions WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM ai_decisions WHERE run_id = ?", (run_id,))
            conn.commit()
            
    def clear_all(self):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM simulation_runs")
            conn.execute("DELETE FROM nodes")
            conn.execute("DELETE FROM inventory_log")
            conn.execute("DELETE FROM orders")
            conn.execute("DELETE FROM shipments")
            conn.execute("DELETE FROM disruptions")
            conn.execute("DELETE FROM ai_decisions")
            conn.commit()
