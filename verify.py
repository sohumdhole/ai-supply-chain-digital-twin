import simpy
from digital_twin.database import DatabaseManager
from digital_twin.simulation import SupplyChainSimulation
from digital_twin.kpis import KPICalculator

def main():
    print("Initializing Database Manager...")
    db = DatabaseManager()
    db.clear_all()
    
    run_id = "Verification_Test_Run"
    scenario_type = "optimized"
    duration_days = 30
    
    config = {
        "demand_mean": 5.0,
        "demand_std": 1.5,
        "mitigation_enabled": False,
        "use_ortools": True,
        "disruptions": {
            "port_closure": 10,
            "supplier_failure": 20,
            "truck_breakdown": 5,
            "demand_surge": 15
        }
    }
    
    print(f"Creating SimPy environment and launching run: {run_id} ({scenario_type})...")
    env = simpy.Environment()
    sim = SupplyChainSimulation(run_id, scenario_type, db, env, duration_days, config)
    
    print("Running simulation...")
    env.run(until=duration_days)
    print("Simulation finished.")
    
    print("Calculating KPIs...")
    kpi_calc = KPICalculator(db)
    kpis = kpi_calc.calculate_kpis(run_id)
    
    print("\n--- KPI RESULTS ---")
    print(f"Service Level: {kpis['service_level']:.2f}%")
    print(f"Fill Rate:     {kpis['fill_rate']:.2f}%")
    print(f"Inventory Cost:   ${kpis['inventory_cost']:.2f}")
    print(f"Transportation Cost: ${kpis['transportation_cost']:.2f}")
    print(f"Stockout Cost:    ${kpis['stockout_cost']:.2f}")
    print(f"Total Cost:       ${kpis['total_cost']:.2f}")
    print("-------------------")
    
    print("Checking database entries...")
    runs = db.get_runs()
    nodes = db.get_nodes(run_id)
    inventory = db.get_inventory_logs(run_id)
    orders = db.get_orders(run_id)
    shipments = db.get_shipments(run_id)
    disruptions = db.get_disruptions(run_id)
    
    print(f"Runs Logged: {len(runs)}")
    print(f"Nodes Logged: {len(nodes)}")
    print(f"Inventory Records Logged: {len(inventory)}")
    print(f"Orders Logged: {len(orders)}")
    print(f"Shipments Logged: {len(shipments)}")
    print(f"Disruptions Logged: {len(disruptions)}")
    
    if len(inventory) > 0 and len(orders) > 0 and len(shipments) > 0:
        print("\n[SUCCESS] Verification Successful: All components logging correctly to database!")
    else:
        print("\n[FAILED] Verification Failed: Missing logged data in some tables.")

if __name__ == "__main__":
    main()
