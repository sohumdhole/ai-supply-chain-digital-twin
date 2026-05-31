import pandas as pd

class KPICalculator:
    def __init__(self, db_manager):
        self.db = db_manager

    def calculate_kpis(self, run_id):
        """Retrieves data for a run and calculates all required logistics KPIs."""
        
        # Load tables
        df_orders = self.db.get_orders(run_id)
        df_inventory = self.db.get_inventory_logs(run_id)
        df_shipments = self.db.get_shipments(run_id)
        
        # Default empty KPIs structure
        kpis = {
            "service_level": 100.0,
            "fill_rate": 100.0,
            "inventory_cost": 0.0,
            "transportation_cost": 0.0,
            "stockout_cost": 0.0,
            "total_cost": 0.0,
            "stockout_rate": 0.0,
            "total_orders": 0,
            "fulfilled_orders": 0,
            "stockout_orders": 0,
            "total_quantity_ordered": 0.0,
            "total_quantity_fulfilled": 0.0,
            "total_quantity_stockout": 0.0
        }
        
        # Calculate Orders KPIs
        if not df_orders.empty:
            total_orders = len(df_orders)
            fulfilled_orders = len(df_orders[df_orders['status'] == 'Fulfilled'])
            stockout_orders = len(df_orders[df_orders['status'] == 'Stockout'])
            
            qty_fulfilled = df_orders[df_orders['status'] == 'Fulfilled']['quantity'].sum()
            qty_stockout = df_orders[df_orders['status'] == 'Stockout']['quantity'].sum()
            qty_ordered = qty_fulfilled + qty_stockout
            
            kpis["total_orders"] = total_orders
            kpis["fulfilled_orders"] = fulfilled_orders
            kpis["stockout_orders"] = stockout_orders
            kpis["total_quantity_ordered"] = qty_ordered
            kpis["total_quantity_fulfilled"] = qty_fulfilled
            kpis["total_quantity_stockout"] = qty_stockout
            
            if total_orders > 0:
                kpis["service_level"] = (fulfilled_orders / total_orders) * 100.0
                kpis["stockout_rate"] = (stockout_orders / total_orders) * 100.0
            
            if qty_ordered > 0:
                kpis["fill_rate"] = (qty_fulfilled / qty_ordered) * 100.0
                
            # Stockout penalty cost ($10 per unit missed)
            kpis["stockout_cost"] = float(qty_stockout * 10.0)

        # Calculate Inventory Holding Costs
        if not df_inventory.empty:
            # Inventory log is daily: sum of (quantity * holding_cost_rate)
            # holding_cost column stores the unit rate (e.g. 0.5 for RM, 1.0/1.5 for FG)
            kpis["inventory_cost"] = float((df_inventory['quantity'] * df_inventory['holding_cost']).sum())

        # Calculate Transportation Costs
        if not df_shipments.empty:
            # Sum of transport_cost for all logged shipments
            kpis["transportation_cost"] = float(df_shipments['transport_cost'].sum())
            
        # Total Operating Cost
        kpis["total_cost"] = kpis["inventory_cost"] + kpis["transportation_cost"] + kpis["stockout_cost"]
        
        return kpis
