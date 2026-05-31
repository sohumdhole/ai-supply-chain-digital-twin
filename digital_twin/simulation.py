import simpy
import random
import uuid
import numpy as np
from datetime import datetime
from .database import DatabaseManager
from .optimisation import SupplyChainOptimizer

class SupplyChainSimulation:
    def __init__(self, run_id, scenario_type, db_manager, env, duration_days=60, config=None):
        self.run_id = run_id
        self.scenario_type = scenario_type
        self.db = db_manager
        self.env = env
        self.duration_days = duration_days
        
        # Configurations
        self.config = config or {}
        self.demand_mean = self.config.get("demand_mean", 5.0)
        self.demand_std = self.config.get("demand_std", 1.5)
        self.mitigation_enabled = self.config.get("mitigation_enabled", False)
        
        # Disruption schedules (day to trigger, or None)
        self.disruption_days = self.config.get("disruptions", {
            "port_closure": None,
            "supplier_failure": None,
            "truck_breakdown": None,
            "demand_surge": None
        })
        
        # Network nodes configuration
        self.nodes = {
            "Hamburg_Hub": {"name": "Hamburg Logistics Hub", "type": "Supplier", "lat": 53.5, "lon": 10.0, "cost_per_unit": 20.0, "base_lead_time": 3.0},
            "Rotterdam_Port": {"name": "Rotterdam Port", "type": "Supplier", "lat": 51.9, "lon": 4.4, "cost_per_unit": 15.0, "base_lead_time": 6.0},
            "Cork_Factory": {"name": "Cork Manufacturing Facility", "type": "Factory", "lat": 51.9, "lon": -8.5, "capacity": 20.0},
            "Dublin_DC": {"name": "Dublin Distribution Centre", "type": "Warehouse", "lat": 53.3, "lon": -6.3, "holding_cost_rate": 1.5},
            "Galway_DC": {"name": "Galway Distribution Centre", "type": "Warehouse", "lat": 53.3, "lon": -9.0, "holding_cost_rate": 1.5},
            "Retailer_Dublin_1": {"name": "Dublin Retailer East", "type": "Customer", "lat": 53.4, "lon": -6.2, "warehouse": "Dublin_DC"},
            "Retailer_Dublin_2": {"name": "Dundalk Retailer North", "type": "Customer", "lat": 54.0, "lon": -6.4, "warehouse": "Dublin_DC"},
            "Retailer_Galway": {"name": "Galway Retailer West", "type": "Customer", "lat": 53.3, "lon": -9.1, "warehouse": "Galway_DC"},
            "Retailer_Cork": {"name": "Limerick Retailer South", "type": "Customer", "lat": 52.7, "lon": -8.6, "warehouse": "Galway_DC"},
        }
        
        # Save nodes in database
        self.db.log_run(self.run_id, self.scenario_type, self.duration_days, self.demand_mean, self.demand_std)
        db_nodes_list = []
        for nid, ninfo in self.nodes.items():
            db_nodes_list.append({
                "node_id": nid,
                "name": ninfo["name"],
                "type": ninfo["type"],
                "lat": ninfo["lat"],
                "lon": ninfo["lon"],
                "capacity": ninfo.get("capacity", None)
            })
        self.db.log_nodes(self.run_id, db_nodes_list)

        # SimPy Containers for Inventory
        # Factory
        self.factory_rm = simpy.Container(env, init=50, capacity=200) # Raw materials
        self.factory_fg = simpy.Container(env, init=40, capacity=200) # Finished goods
        
        # Warehouses
        self.warehouse_inventories = {
            "Dublin_DC": simpy.Container(env, init=40, capacity=150),
            "Galway_DC": simpy.Container(env, init=40, capacity=150)
        }
        
        # Track in-transit inventory to prevent double-ordering
        self.in_transit_rm = 0
        self.in_transit_fg = {
            "Dublin_DC": 0,
            "Galway_DC": 0
        }
        
        # Operational parameters (modifiable by AI Engine)
        self.use_ortools = self.config.get("use_ortools", False)
        if self.use_ortools:
            self.optimizer = SupplyChainOptimizer(self.nodes)
            
        self.active_supplier = "Rotterdam_Port"  # Start with cheaper supplier
        self.factory_reorder_point = 40
        self.factory_order_up_to = 100
        
        self.warehouse_reorder_points = {
            "Dublin_DC": 30,
            "Galway_DC": 30
        }
        self.warehouse_order_up_tos = {
            "Dublin_DC": 80,
            "Galway_DC": 80
        }
        
        # Transport settings
        self.shipping_modes = {
            "Hamburg_Hub": "Standard",
            "Rotterdam_Port": "Standard",
            "Cork_Factory": "Standard"
        }
        
        # Disruption states
        self.active_disruptions = set()
        self.disrupted_suppliers = set()
        self.closed_ports = set()
        self.broken_trucks = set()
        self.demand_surge_active = False
        
        # Backlog of warehouse orders at Factory (Factory -> Warehouse)
        self.factory_backlog = {
            "Dublin_DC": [],
            "Galway_DC": []
        }
        
        # Let's register simulation processes
        self.env.process(self.inventory_logging_loop())
        self.env.process(self.factory_production_loop())
        
        if self.use_ortools:
            self.env.process(self.daily_optimisation_loop())
        else:
            self.env.process(self.factory_replenishment_loop())
            for w_id in self.warehouse_inventories.keys():
                self.env.process(self.warehouse_replenishment_loop(w_id))
            
        for c_id, c_info in self.nodes.items():
            if c_info["type"] == "Customer":
                self.env.process(self.customer_demand_loop(c_id, c_info["warehouse"]))
                
        # Register disruptions
        self.env.process(self.disruption_scheduler())

    def inventory_logging_loop(self):
        """Logs inventories daily for chart plotting."""
        while True:
            # Factory RM holding cost = 0.5, FG holding cost = 1.0
            self.db.log_inventory(self.run_id, self.env.now, "Cork_Factory", "raw_material", self.factory_rm.level, 0.5)
            self.db.log_inventory(self.run_id, self.env.now, "Cork_Factory", "finished_good", self.factory_fg.level, 1.0)
            
            # Warehouses FG holding cost = 1.5
            for w_id, container in self.warehouse_inventories.items():
                self.db.log_inventory(self.run_id, self.env.now, w_id, "finished_good", container.level, 1.5)
                
            yield self.env.timeout(1.0) # check once a day

    def factory_production_loop(self):
        """Factory pulls raw materials and produces finished goods."""
        while True:
            capacity = self.nodes["Cork_Factory"]["capacity"]
            rm_available = self.factory_rm.level
            qty_to_produce = min(capacity, rm_available)
            
            if qty_to_produce > 0:
                # Consume RM
                yield self.factory_rm.get(qty_to_produce)
                # Production takes 1 day
                yield self.env.timeout(1.0)
                # Put in FG
                yield self.factory_fg.put(qty_to_produce)
                
                # Check factory backlog and fulfill
                self.fulfill_factory_backlog()
            else:
                yield self.env.timeout(1.0) # wait a day and check again

    def factory_replenishment_loop(self):
        """Periodic review of Raw Materials inventory at the Factory."""
        while True:
            current_inv = self.factory_rm.level
            # Check if inventory + in_transit is below reorder point
            if (current_inv + self.in_transit_rm) < self.factory_reorder_point:
                order_qty = self.factory_order_up_to - (current_inv + self.in_transit_rm)
                if order_qty > 0:
                    supplier_id = self.active_supplier
                    mode = self.shipping_modes[supplier_id]
                    self.env.process(self.shipment_process(
                        source_id=supplier_id,
                        dest_id="Cork_Factory",
                        product_type="raw_material",
                        qty=order_qty,
                        mode=mode
                    ))
            yield self.env.timeout(1.0) # Check daily

    def warehouse_replenishment_loop(self, warehouse_id):
        """Periodic review of Finished Goods inventory at the Warehouses."""
        while True:
            container = self.warehouse_inventories[warehouse_id]
            current_inv = container.level
            in_transit = self.in_transit_fg[warehouse_id]
            
            reorder_pt = self.warehouse_reorder_points[warehouse_id]
            order_up_to = self.warehouse_order_up_tos[warehouse_id]
            
            if (current_inv + in_transit) < reorder_pt:
                order_qty = order_up_to - (current_inv + in_transit)
                if order_qty > 0:
                    self.in_transit_fg[warehouse_id] += order_qty
                    self.factory_backlog[warehouse_id].append(order_qty)
                    self.fulfill_factory_backlog()
                    
            yield self.env.timeout(1.0)

    def fulfill_factory_backlog(self):
        """Checks if factory has FG to satisfy warehouse orders, then dispatches them."""
        for w_id, orders_list in self.factory_backlog.items():
            while orders_list and self.factory_fg.level > 0:
                order_qty = orders_list[0]
                qty_to_ship = min(order_qty, self.factory_fg.level)
                
                if qty_to_ship > 0:
                    self.factory_fg.get(qty_to_ship) # Sync SimPy container
                    orders_list[0] -= qty_to_ship
                    
                    # Dispatch shipment
                    self.env.process(self.shipment_process(
                        source_id="Cork_Factory",
                        dest_id=w_id,
                        product_type="finished_good",
                        qty=qty_to_ship,
                        mode=self.shipping_modes["Cork_Factory"]
                    ))
                    
                    if orders_list[0] <= 0:
                        orders_list.pop(0)

    def customer_demand_loop(self, customer_id, warehouse_id):
        """Generates random customer orders and processes fulfillment."""
        while True:
            # Customer demand occurs daily
            yield self.env.timeout(1.0)
            
            # Calculate demand
            mean = self.demand_mean
            std = self.demand_std
            if self.demand_surge_active:
                mean *= 3.0 # Surge multiplies demand mean by 3
                std *= 1.5
                
            qty = max(1.0, round(random.normalvariate(mean, std)))
            order_id = str(uuid.uuid4())[:8]
            ordered_time = self.env.now
            
            warehouse_container = self.warehouse_inventories[warehouse_id]
            
            # Check availability
            if warehouse_container.level >= qty:
                # Fulfill immediately
                yield warehouse_container.get(qty)
                self.db.log_order(
                    run_id=self.run_id,
                    order_id=order_id,
                    customer_id=customer_id,
                    warehouse_id=warehouse_id,
                    product_type="finished_good",
                    quantity=qty,
                    ordered_time=ordered_time,
                    fulfilled_time=ordered_time,
                    status="Fulfilled",
                    price_per_unit=30.0 # Customer pays $30 per finished good
                )
            else:
                # Partial fulfillment (lost sales for the deficit)
                qty_fulfilled = warehouse_container.level
                if qty_fulfilled > 0:
                    yield warehouse_container.get(qty_fulfilled)
                    # Log partial fulfillment as fulfilled order
                    self.db.log_order(
                        run_id=self.run_id,
                        order_id=order_id + "_part",
                        customer_id=customer_id,
                        warehouse_id=warehouse_id,
                        product_type="finished_good",
                        quantity=qty_fulfilled,
                        ordered_time=ordered_time,
                        fulfilled_time=ordered_time,
                        status="Fulfilled",
                        price_per_unit=30.0
                    )
                
                # Log stockout for the rest
                qty_stockout = qty - qty_fulfilled
                self.db.log_order(
                    run_id=self.run_id,
                    order_id=order_id + "_stockout",
                    customer_id=customer_id,
                    warehouse_id=warehouse_id,
                    product_type="finished_good",
                    quantity=qty_stockout,
                    ordered_time=ordered_time,
                    fulfilled_time=None,
                    status="Stockout",
                    price_per_unit=30.0
                )

    def shipment_process(self, source_id, dest_id, product_type, qty, mode="Standard"):
        """Models transit time, transportation delays, and costs."""
        shipment_id = str(uuid.uuid4())[:8]
        dispatch_time = self.env.now
        
        # Track in transit
        if product_type == "raw_material":
            self.in_transit_rm += qty
        else:
            # finished goods to warehouse
            pass # already added to self.in_transit_fg[dest_id] in replenishment review

        # Calculate base lead time and distance
        # Node coordinates
        s_coord = (self.nodes[source_id]["lat"], self.nodes[source_id]["lon"])
        d_coord = (self.nodes[dest_id]["lat"], self.nodes[dest_id]["lon"])
        distance = np.sqrt((s_coord[0] - d_coord[0])**2 + (s_coord[1] - d_coord[1])**2) * 100 # Rough km scaling
        
        # Base lead time
        if "Supplier" in source_id:
            base_lead = self.nodes[source_id]["base_lead_time"]
        else:
            base_lead = 2.0 # Factory to Warehouse is 2 days base
            
        # Expedited shipping cuts lead time in half, but costs more
        lead_time = base_lead / 2.0 if mode == "Expedited" else base_lead
        
        # Cost structure: unit cost + distance cost
        # Supplier units have a purchase price
        purch_cost = (self.nodes[source_id]["cost_per_unit"] * qty) if "Supplier" in source_id else 0.0
        
        # Distance cost
        rate_per_unit_km = 0.25 if mode == "Expedited" else 0.10
        trans_cost = rate_per_unit_km * qty * distance
        total_cost = purch_cost + trans_cost
        
        disruption_cause = None
        
        # Apply Port Closure disruption (Rotterdam_Port -> Cork_Factory goes through English Channel)
        if "port_closure" in self.active_disruptions and source_id == "Rotterdam_Port":
            lead_time += 10.0 # Port closure adds 10 days delay!
            disruption_cause = "Port Closure"
            
        # Apply Supplier Failure (Rotterdam_Port fails completely)
        if source_id in self.disrupted_suppliers:
            # Orders are heavily delayed (e.g. Supplier shuts down, adding 15 days)
            lead_time += 15.0
            disruption_cause = "Supplier Failure"
            
        # Simulate potential Truck Breakdown during transit (10% chance if not mitigated, or active disruption triggers it)
        is_broken = False
        if "truck_breakdown" in self.active_disruptions and random.random() < 0.35: # high chance during truck breakdown disruption
            is_broken = True
        elif random.random() < 0.02: # 2% baseline breakdown chance
            is_broken = True
            
        if is_broken:
            lead_time += 3.0 # Adds 3 days breakdown delay
            total_cost += 300.0 # Towing and replacement truck fee
            disruption_cause = "Truck Breakdown"
            
        estimated_delivery = dispatch_time + lead_time
        
        # Log shipment creation
        self.db.log_shipment(
            run_id=self.run_id,
            shipment_id=shipment_id,
            source_id=source_id,
            dest_id=dest_id,
            product_type=product_type,
            quantity=qty,
            status="In_Transit" if disruption_cause is None else "Delayed",
            dispatch_time=dispatch_time,
            estimated_delivery=estimated_delivery,
            actual_delivery=None,
            transport_cost=total_cost,
            mode=mode,
            disruption_cause=disruption_cause
        )
        
        # Perform transit wait
        yield self.env.timeout(lead_time)
        
        # Arrived!
        actual_delivery = self.env.now
        
        # Add to inventory
        if dest_id == "Cork_Factory":
            yield self.factory_rm.put(qty)
            self.in_transit_rm -= qty
        else:
            # Dest is Warehouse
            yield self.warehouse_inventories[dest_id].put(qty)
            self.in_transit_fg[dest_id] -= qty
            
        # Update shipment status in database
        self.db.log_shipment(
            run_id=self.run_id,
            shipment_id=shipment_id,
            source_id=source_id,
            dest_id=dest_id,
            product_type=product_type,
            quantity=qty,
            status="Delivered",
            dispatch_time=dispatch_time,
            estimated_delivery=estimated_delivery,
            actual_delivery=actual_delivery,
            transport_cost=total_cost,
            mode=mode,
            disruption_cause=disruption_cause
        )

    def disruption_scheduler(self):
        """Simulates disruptions and queries the AI Decision Engine if active."""
        from .ai_engine import AIDecisionEngine
        ai_engine = AIDecisionEngine(self)
        
        # Create triggers based on configuration
        for disruption_type, trigger_day in self.disruption_days.items():
            if trigger_day is not None:
                self.env.process(self.run_single_disruption(disruption_type, trigger_day, ai_engine))
                
        yield self.env.timeout(0)

    def run_single_disruption(self, disruption_type, trigger_day, ai_engine):
        """Triggers a specific disruption at the scheduled time, runs the AI engine, and resolves the disruption later."""
        # Wait until the trigger day
        yield self.env.timeout(trigger_day - self.env.now)
        
        disruption_id = str(uuid.uuid4())[:8]
        target = ""
        description = ""
        duration = 10.0 # Disruption duration (e.g. 10 days)
        
        if disruption_type == "port_closure":
            self.active_disruptions.add("port_closure")
            target = "Rotterdam Port (Rotterdam -> Cork Route)"
            description = "Major weather event causes cargo congestion and customs backlog at Rotterdam Port, adding 10 days of delay to maritime routes."
        elif disruption_type == "supplier_failure":
            self.disrupted_suppliers.add("Rotterdam_Port")
            target = "Rotterdam_Port"
            description = "Rotterdam Port experiences worker strike, shutting down logistics operations. Lead time on outstanding or new orders increases by 15 days."
        elif disruption_type == "truck_breakdown":
            self.active_disruptions.add("truck_breakdown")
            target = "Irish Highway Transport Lanes"
            description = "Severe winter storm in Ireland leads to a high frequency of truck breakdowns and traffic halts, adding 3 days delay and extra towing costs."
        elif disruption_type == "demand_surge":
            self.demand_surge_active = True
            target = "All Customer Nodes"
            description = "Viral marketing campaign causes an unexpected 3x surge in regional customer demands for 10 days."
            duration = 10.0
            
        # Log disruption start
        self.db.log_disruption(
            run_id=self.run_id,
            disruption_id=disruption_id,
            type_str=disruption_type,
            target=target,
            start_time=self.env.now,
            description=description
        )
        
        # Call AI Engine for recommendation
        ai_engine.evaluate_and_mitigate(disruption_id, disruption_type, target, self.env.now)
        
        # Wait for disruption to resolve
        yield self.env.timeout(duration)
        
        # Resolve disruption
        if disruption_type == "port_closure":
            self.active_disruptions.discard("port_closure")
        elif disruption_type == "supplier_failure":
            self.disrupted_suppliers.discard("Rotterdam_Port")
        elif disruption_type == "truck_breakdown":
            self.active_disruptions.discard("truck_breakdown")
        elif disruption_type == "demand_surge":
            self.demand_surge_active = False
            
        # Log disruption end
        self.db.log_disruption(
            run_id=self.run_id,
            disruption_id=disruption_id,
            type_str=disruption_type,
            target=target,
            start_time=trigger_day,
            end_time=self.env.now,
            description=description + " [RESOLVED]"
        )

    def daily_optimisation_loop(self):
        """Runs the Google OR-Tools optimization engine daily to make sourcing and dispatch decisions."""
        while True:
            # Run optimization solver
            decisions = self.optimizer.solve(
                factory_rm=self.factory_rm.level,
                factory_fg=self.factory_fg.level,
                in_transit_rm=self.in_transit_rm,
                warehouse_stocks={w_id: self.warehouse_inventories[w_id].level for w_id in self.warehouse_inventories},
                in_transit_fg={w_id: self.in_transit_fg[w_id] for w_id in self.in_transit_fg},
                active_disruptions=self.active_disruptions,
                disrupted_suppliers=self.disrupted_suppliers,
                demand_means=self.demand_mean,
                simulation_time=self.env.now
            )
            
            if decisions and decisions["solver_status"] in ["OPTIMAL", "FEASIBLE"]:
                # 1. Process Sourcing Decisions (Supplier -> Factory)
                for s in ["Hamburg_Hub", "Rotterdam_Port"]:
                    qty = decisions.get(f"{s}_qty", 0.0)
                    if qty > 0.01:
                        mode = decisions.get(f"{s}_mode", "Standard")
                        self.env.process(self.shipment_process(
                            source_id=s,
                            dest_id="Cork_Factory",
                            product_type="raw_material",
                            qty=qty,
                            mode=mode
                        ))
                
                # 2. Process Distribution Decisions (Factory -> Warehouses)
                for w in ["Dublin_DC", "Galway_DC"]:
                    qty = decisions.get(f"{w}_qty", 0.0)
                    if qty > 0.01:
                        mode = decisions.get(f"{w}_mode", "Standard")
                        # Consume Finished Goods from factory container and dispatch
                        qty_to_ship = min(qty, self.factory_fg.level)
                        if qty_to_ship > 0.01:
                            yield self.factory_fg.get(qty_to_ship)
                            self.in_transit_fg[w] += qty_to_ship
                            self.env.process(self.shipment_process(
                                source_id="Cork_Factory",
                                dest_id=w,
                                product_type="finished_good",
                                qty=qty_to_ship,
                                mode=mode
                            ))
                            
            yield self.env.timeout(1.0) # Check daily

