class AIDecisionEngine:
    def __init__(self, simulation_instance):
        self.sim = simulation_instance

    def evaluate_and_mitigate(self, disruption_id, disruption_type, target, timestamp):
        """Assesses disruption impact, evaluates mitigation options, and triggers actions if mitigation is enabled."""
        
        recommendation = ""
        explanation = ""
        cost_benefit_estimate = 0.0
        actions_to_apply = {}
        
        # Calculate key heuristics
        factory_rm_stock = self.sim.factory_rm.level
        factory_fg_stock = self.sim.factory_fg.level
        wn_stock = self.sim.warehouse_inventories["Dublin_DC"].level
        ws_stock = self.sim.warehouse_inventories["Galway_DC"].level
        
        # Daily demand estimate
        avg_demand_per_warehouse = self.sim.demand_mean * 2.0  # 2 customers per warehouse
        total_daily_demand = avg_demand_per_warehouse * 2.0
        
        if disruption_type == "port_closure":
            # Impact Assessment: Port Closure blocks Rotterdam Port shipments
            # Time-to-Survive (TTS) for raw material at factory:
            # Factory consumes up to 20 units/day
            tts_rm = factory_rm_stock / 20.0
            ttr = 10.0 # Port closure lasts 10 days
            
            explanation += f"### Impact Assessment:\n"
            explanation += f"* **Disruption**: Port Closure affecting shipping lanes from {target}.\n"
            explanation += f"* **Time-to-Recovery (TTR)**: 10.0 days.\n"
            explanation += f"* **Factory Raw Material Stock**: {factory_rm_stock:.1f} units.\n"
            explanation += f"* **Time-to-Survive (TTS)**: {tts_rm:.1f} days of manufacturing operations.\n"
            
            if tts_rm < ttr:
                explanation += f"* **Risk Warning**: Stockout imminent! Factory will run out of raw materials in {tts_rm:.1f} days, halting production for {ttr - tts_rm:.1f} days.\n\n"
            else:
                explanation += f"* **Risk Warning**: Factory has sufficient raw material to weather the closure without production halts.\n\n"
                
            explanation += "### Mitigation Evaluation:\n"
            # Option 1: Do Nothing
            lost_prod_days = max(0.0, ttr - tts_rm)
            lost_production_units = lost_prod_days * 20.0
            penalty_cost = lost_production_units * 30.0 # $30 selling price per unit
            explanation += f"1. **Option A: No Action (Maintain current path)**\n"
            explanation += f"   * Keep ordering from Rotterdam Port. Deliveries delayed by 10 days.\n"
            explanation += f"   * Projected factory shutdown: {lost_prod_days:.1f} days.\n"
            explanation += f"   * Projected revenue loss: ${penalty_cost:,.2f}.\n"
            
            # Option 2: Dual Source to Hamburg Logistics Hub
            supplier_premium = (self.sim.nodes["Hamburg_Hub"]["cost_per_unit"] - self.sim.nodes["Rotterdam_Port"]["cost_per_unit"])
            extra_material_cost = 60.0 * supplier_premium # Assume ordering 60 units
            explanation += f"2. **Option B: Switch Sourcing to Hamburg Logistics Hub**\n"
            explanation += f"   * Redirect raw material ordering to Hamburg Hub (Reliable rail/road line).\n"
            explanation += f"   * Unit price increase: +${supplier_premium:.2f}/unit (Total extra: ${extra_material_cost:,.2f}).\n"
            explanation += f"   * Lead time: 3.0 days (bypasses Rotterdam maritime strike completely).\n"
            explanation += f"   * Avoids factory shutdown: Yes.\n\n"
            
            if tts_rm < ttr:
                recommendation = "Switch raw material ordering to Hamburg Logistics Hub immediately"
                explanation += "### Recommendation:\n"
                explanation += "**Option B is recommended**. Sourcing from Hamburg Hub prevents a factory stockout and shutdown, saving significant revenue despite the higher unit purchase price."
                cost_benefit_estimate = penalty_cost - extra_material_cost
                actions_to_apply = {
                    "active_supplier": "Hamburg_Hub"
                }
            else:
                recommendation = "Maintain Rotterdam Port with standard orders; monitor safety stocks"
                explanation += "### Recommendation:\n"
                explanation += "**Option A is recommended**. Factory inventory is currently high enough to buffer the 10-day port closure. Sourcing switch is unnecessary."
                cost_benefit_estimate = 0.0

        elif disruption_type == "supplier_failure":
            # Rotterdam Port has worker strike (15 days delay on all shipments)
            tts_rm = factory_rm_stock / 20.0
            ttr = 10.0 # Disruption duration is 10 days, but lead times are pushed out by 15 days
            
            explanation += f"### Impact Assessment:\n"
            explanation += f"* **Disruption**: worker strike at {target}.\n"
            explanation += f"* **Supplier Lead Time Penalty**: +15.0 days lead time for orders from Rotterdam Port.\n"
            explanation += f"* **Factory Raw Material Stock**: {factory_rm_stock:.1f} units.\n"
            explanation += f"* **Time-to-Survive (TTS)**: {tts_rm:.1f} days.\n\n"
            
            explanation += "### Mitigation Evaluation:\n"
            # Option 1: Do Nothing
            lost_prod_days = max(0.0, 15.0 - tts_rm)
            lost_production_units = lost_prod_days * 20.0
            penalty_cost = lost_production_units * 30.0
            explanation += f"1. **Option A: No Action**\n"
            explanation += f"   * Wait for Rotterdam Port to recover. Lead time remains elevated.\n"
            explanation += f"   * Projected factory shutdown: {lost_prod_days:.1f} days.\n"
            explanation += f"   * Projected revenue loss: ${penalty_cost:,.2f}.\n"
            
            # Option 2: Sourcing to Hamburg Logistics Hub
            supplier_premium = (self.sim.nodes["Hamburg_Hub"]["cost_per_unit"] - self.sim.nodes["Rotterdam_Port"]["cost_per_unit"])
            extra_material_cost = 80.0 * supplier_premium
            explanation += f"2. **Option B: Switch Sourcing to Hamburg Logistics Hub (Reliable)**\n"
            explanation += f"   * Route all new orders to Hamburg Hub.\n"
            explanation += f"   * Lead time: 3.0 days (no delays).\n"
            explanation += f"   * Avoids factory shutdown: Yes.\n"
            explanation += f"   * Extra cost: ${extra_material_cost:,.2f}.\n\n"
            
            recommendation = "Switch raw material ordering to Hamburg Logistics Hub"
            explanation += "### Recommendation:\n"
            explanation += "**Option B is recommended**. Sourcing from Hamburg Logistics Hub is critical to maintain production continuity at Cork. Doing nothing will cause severe raw material stockouts."
            cost_benefit_estimate = penalty_cost - extra_material_cost
            actions_to_apply = {
                "active_supplier": "Hamburg_Hub"
            }

        elif disruption_type == "truck_breakdown":
            # Active winter storm in Ireland - high frequency of transit breakdowns
            avg_stock = (wn_stock + ws_stock) / 2.0
            tts_fg = avg_stock / avg_demand_per_warehouse if avg_demand_per_warehouse > 0 else 99
            
            explanation += f"### Impact Assessment:\n"
            explanation += f"* **Disruption**: Severe winter storm across {target}.\n"
            explanation += f"* **Impact**: 35% chance of breakdown per shipment, adding 3 days delay and $300 recovery fee.\n"
            explanation += f"* **Warehouse Inventory Level (Avg)**: {avg_stock:.1f} units.\n"
            explanation += f"* **Time-to-Survive (TTS)**: {tts_fg:.1f} days of customer demand.\n\n"
            
            explanation += "### Mitigation Evaluation:\n"
            # Option 1: Do Nothing
            explanation += f"1. **Option A: No Action**\n"
            explanation += f"   * Risk high failure rates and vehicle damage on regional highways.\n"
            explanation += f"   * Estimated towing/delay penalty: ~$900.00.\n"
            
            # Option 2: Expedite with priority carriers (e.g. winter-equipped express transport)
            explanation += f"2. **Option B: Expedite shipments and use winter-priority carriers**\n"
            explanation += f"   * Route through premium carriers with guaranteed delivery and winter safety protocols.\n"
            explanation += f"   * Eliminates breakdown risk and halves standard lead time to 1.0 day.\n"
            explanation += f"   * Extra transport premium: ~$250.00.\n\n"
            
            recommendation = "Expedite Cork Factory to Irish Distribution Centres lanes"
            explanation += "### Recommendation:\n"
            explanation += "**Option B is recommended**. Transitioning to winter-priority expedited carriers guarantees supply to regional distribution hubs, bypassing delays and avoiding costly breakdown recovery fees."
            cost_benefit_estimate = 650.0 # Estimate savings
            actions_to_apply = {
                "shipping_modes": {"Hamburg_Hub": "Standard", "Rotterdam_Port": "Standard", "Cork_Factory": "Expedited"}
            }

        elif disruption_type == "demand_surge":
            # Demand Surge: 3x demand for 10 days
            avg_stock = (wn_stock + ws_stock) / 2.0
            surged_demand = avg_demand_per_warehouse * 3.0
            tts_fg = avg_stock / surged_demand if surged_demand > 0 else 99
            
            explanation += f"### Impact Assessment:\n"
            explanation += f"* **Disruption**: 3x Demand Surge at {target}.\n"
            explanation += f"* **Surge Daily Demand**: {surged_demand:.1f} units/day per warehouse (Standard: {avg_demand_per_warehouse:.1f}).\n"
            explanation += f"* **Warehouse Inventory Level (Avg)**: {avg_stock:.1f} units.\n"
            explanation += f"* **Time-to-Survive (TTS)**: {tts_fg:.1f} days (Down from {avg_stock / avg_demand_per_warehouse:.1f} days).\n\n"
            
            explanation += "### Mitigation Evaluation:\n"
            # Option 1: Do Nothing
            explanation += f"1. **Option A: Keep standard (s, S) policy (s=30, S=80)**\n"
            explanation += f"   * Stockout occurs within 2 days. Standard lead times cause replenishment delay.\n"
            explanation += f"   * Estimated stockout penalty: ~$1,000.00.\n"
            
            # Option 2: Pre-emptively raise s and S and expedite transport
            explanation += f"2. **Option B: Adjust inventory parameters & expedite shipping**\n"
            explanation += f"   * Raise reorder points dynamically to 60 units (S=150) to absorb the demand wave.\n"
            explanation += f"   * Set shipping mode from Cork Factory to Expedited to reduce lead time to 1 day.\n"
            explanation += f"   * Extra holding & shipping costs: ~$300.00.\n\n"
            
            recommendation = "Increase warehouse safety stock levels and expedite replenishment"
            explanation += "### Recommendation:\n"
            explanation += "**Option B is recommended**. Increasing safety stock thresholds and expediting factory shipments allows the distribution nodes to absorb the surge without running out of stock."
            cost_benefit_estimate = 700.0
            actions_to_apply = {
                "warehouse_reorder_points": {"Dublin_DC": 60, "Galway_DC": 60},
                "warehouse_order_up_tos": {"Dublin_DC": 150, "Galway_DC": 150},
                "shipping_modes": {"Hamburg_Hub": "Standard", "Rotterdam_Port": "Standard", "Cork_Factory": "Expedited"}
            }

        # Apply actions if mitigation is enabled
        applied = 0
        if self.sim.mitigation_enabled and actions_to_apply:
            applied = 1
            if "active_supplier" in actions_to_apply:
                self.sim.active_supplier = actions_to_apply["active_supplier"]
            if "shipping_modes" in actions_to_apply:
                self.sim.shipping_modes = actions_to_apply["shipping_modes"]
            if "warehouse_reorder_points" in actions_to_apply:
                self.sim.warehouse_reorder_points = actions_to_apply["warehouse_reorder_points"]
            if "warehouse_order_up_tos" in actions_to_apply:
                self.sim.warehouse_order_up_tos = actions_to_apply["warehouse_order_up_tos"]
                
        # Log to database
        self.sim.db.log_ai_decision(
            run_id=self.sim.run_id,
            timestamp=timestamp,
            disruption_id=disruption_id,
            recommendation=recommendation,
            explanation=explanation,
            cost_benefit_estimate=cost_benefit_estimate,
            applied=applied
        )
