import os
import sys

# DLL loading patch for ortools on Windows (Python 3.8+ DLL security change)
if sys.platform == "win32":
    try:
        import ortools
        ortools_dir = os.path.dirname(ortools.__file__)
        libs_path = os.path.join(ortools_dir, ".libs")
        if os.path.exists(libs_path):
            os.add_dll_directory(libs_path)
    except Exception as e:
        pass

from ortools.linear_solver import pywraplp
import numpy as np

class SupplyChainOptimizer:
    def __init__(self, nodes_config):
        """
        nodes_config: Dictionary containing node metadata (locations, base costs, capacities)
        """
        self.nodes = nodes_config

    def solve(self, 
              factory_rm, 
              factory_fg, 
              in_transit_rm,
              warehouse_stocks, 
              in_transit_fg,
              active_disruptions,
              disrupted_suppliers,
              demand_means,
              simulation_time):
        """
        Solves the daily logistics network optimization problem for Ireland/Europe.
        Returns a dictionary of recommended decisions:
        {
            "Hamburg_Hub_qty": float,
            "Hamburg_Hub_mode": str ("Standard" or "Expedited"),
            "Rotterdam_Port_qty": float,
            "Rotterdam_Port_mode": str ("Standard" or "Expedited"),
            "Dublin_DC_qty": float,
            "Dublin_DC_mode": str,
            "Galway_DC_qty": float,
            "Galway_DC_mode": str,
            "solver_status": str,
            "objective_value": float
        }
        """
        solver = pywraplp.Solver.CreateSolver("SCIP")
        if not solver:
            return None

        # Setup parameters
        # Node coordinates
        fact_coord = (self.nodes["Cork_Factory"]["lat"], self.nodes["Cork_Factory"]["lon"])
        wn_coord = (self.nodes["Dublin_DC"]["lat"], self.nodes["Dublin_DC"]["lon"])
        ws_coord = (self.nodes["Galway_DC"]["lat"], self.nodes["Galway_DC"]["lon"])
        sa_coord = (self.nodes["Hamburg_Hub"]["lat"], self.nodes["Hamburg_Hub"]["lon"])
        sb_coord = (self.nodes["Rotterdam_Port"]["lat"], self.nodes["Rotterdam_Port"]["lon"])

        # Distance scaling helper (Rough km)
        def get_dist(c1, c2):
            return np.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2) * 100

        dist_sa_f = get_dist(sa_coord, fact_coord)
        dist_sb_f = get_dist(sb_coord, fact_coord)
        dist_f_wn = get_dist(fact_coord, wn_coord)
        dist_f_ws = get_dist(fact_coord, ws_coord)

        # Capacity parameters
        cap_sa = 80.0 # Hamburg capacity limit
        cap_sb = 80.0 # Rotterdam capacity limit
        if "Rotterdam_Port" in disrupted_suppliers:
            cap_sb = 0.0 # Failed supplier has 0 capacity

        # Sourcing purchase costs
        p_sa = self.nodes["Hamburg_Hub"]["cost_per_unit"]
        p_sb = self.nodes["Rotterdam_Port"]["cost_per_unit"]

        # Transportation rates
        rate_std = 0.10
        rate_exp = 0.25

        # Disruption cost modifiers
        # Port closure delays Rotterdam Port standard shipping by 10 days
        port_closure_penalty = 0.0
        if "port_closure" in active_disruptions:
            port_closure_penalty = 12.0 # Penalty per unit shipped standard

        # Highway storm adds 35% breakdown chance to factory shipments, adding $300 towing fee.
        storm_penalty = 0.0
        if "truck_breakdown" in active_disruptions:
            storm_penalty = 8.0 

        # Decision Variables
        # Sourcing quantities: (Supplier, ShippingMode)
        xa_std = solver.NumVar(0.0, cap_sa, "xa_std")
        xa_exp = solver.NumVar(0.0, cap_sa, "xa_exp")
        xb_std = solver.NumVar(0.0, cap_sb, "xb_std")
        xb_exp = solver.NumVar(0.0, cap_sb, "xb_exp")

        # Distribution quantities: (Warehouse, ShippingMode)
        fact_fg_cap = float(factory_fg)
        ywn_std = solver.NumVar(0.0, fact_fg_cap, "ywn_std")
        ywn_exp = solver.NumVar(0.0, fact_fg_cap, "ywn_exp")
        yws_std = solver.NumVar(0.0, fact_fg_cap, "yws_std")
        yws_exp = solver.NumVar(0.0, fact_fg_cap, "yws_exp")

        # Stockout penalty variables (slack variables)
        s_wn = solver.NumVar(0.0, solver.infinity(), "s_wn")
        s_ws = solver.NumVar(0.0, solver.infinity(), "s_ws")
        s_fact = solver.NumVar(0.0, solver.infinity(), "s_fact")

        # --- CONSTRAINTS ---

        # 1. Supplier Capacity limits
        solver.Add(xa_std + xa_exp <= cap_sa)
        solver.Add(xb_std + xb_exp <= cap_sb)

        # 2. Factory RM storage limits
        # Prevent ordering more raw materials than factory capacity allows
        # RM capacity = 200
        solver.Add(xa_std + xa_exp + xb_std + xb_exp <= 200.0 - factory_rm - in_transit_rm)

        # 3. Factory FG output limits
        # We cannot ship more FG than currently in factory inventory
        solver.Add(ywn_std + ywn_exp + yws_std + yws_exp <= factory_fg)

        # 4. Warehouse storage capacity limits
        # Warehouse capacity = 150
        solver.Add(ywn_std + ywn_exp <= 150.0 - warehouse_stocks["Dublin_DC"] - in_transit_fg["Dublin_DC"])
        solver.Add(yws_std + yws_exp <= 150.0 - warehouse_stocks["Galway_DC"] - in_transit_fg["Galway_DC"])

        # 5. Customer demand satisfaction & Stockout definitions
        # Projected demand over lead times:
        dem_wn = demand_means * 2.0 * 3.0 # expected demand over 3 days (Dublin region)
        dem_ws = demand_means * 2.0 * 3.0 # (Galway/Cork region)
        
        # If demand surge is active, demand is tripled
        if "demand_surge" in active_disruptions:
            dem_wn *= 3.0
            dem_ws *= 3.0

        # Stockout definition at Dublin DC:
        solver.Add(s_wn >= dem_wn - (warehouse_stocks["Dublin_DC"] + in_transit_fg["Dublin_DC"] + ywn_std + ywn_exp))

        # Stockout definition at Galway DC:
        solver.Add(s_ws >= dem_ws - (warehouse_stocks["Galway_DC"] + in_transit_fg["Galway_DC"] + yws_std + yws_exp))

        # Stockout definition at Factory (RM required to produce required warehouse shipments)
        # We model the maximum of (20.0, total_shipped_FG) linearly using two separate constraints:
        solver.Add(s_fact >= 20.0 - (factory_rm + in_transit_rm + xa_std + xa_exp + xb_std + xb_exp))
        solver.Add(s_fact >= (ywn_std + ywn_exp + yws_std + yws_exp) - (factory_rm + in_transit_rm + xa_std + xa_exp + xb_std + xb_exp))

        # --- OBJECTIVE FUNCTION ---
        # Sourcing purchase cost
        cost_purch = p_sa * (xa_std + xa_exp) + p_sb * (xb_std + xb_exp)

        # Sourcing transport cost (standard rates vs expedited rates, plus port closure penalty)
        cost_trans_rm = (
            (rate_std * dist_sa_f * xa_std) + (rate_exp * dist_sa_f * xa_exp) +
            ((rate_std * dist_sb_f + port_closure_penalty) * xb_std) + (rate_exp * dist_sb_f * xb_exp)
        )

        # Warehouse distribution transport cost (standard rates vs expedited, plus highway storm penalty)
        cost_trans_fg = (
            ((rate_std * dist_f_wn + storm_penalty) * ywn_std) + (rate_exp * dist_f_wn * ywn_exp) +
            ((rate_std * dist_f_ws + storm_penalty) * yws_std) + (rate_exp * dist_f_ws * yws_exp)
        )

        # Stockout penalty cost
        cost_stockout = 100.0 * (s_wn + s_ws) + 50.0 * s_fact

        # Solve objective
        solver.Minimize(cost_purch + cost_trans_rm + cost_trans_fg + cost_stockout)

        status = solver.Solve()

        # Extract optimal decisions
        decisions = {
            "Hamburg_Hub_qty": 0.0,
            "Hamburg_Hub_mode": "Standard",
            "Rotterdam_Port_qty": 0.0,
            "Rotterdam_Port_mode": "Standard",
            "Dublin_DC_qty": 0.0,
            "Dublin_DC_mode": "Standard",
            "Galway_DC_qty": 0.0,
            "Galway_DC_mode": "Standard",
            "solver_status": "FAILED",
            "objective_value": 0.0
        }

        if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
            decisions["objective_value"] = solver.Objective().Value()
            
            # Sourcing decisions
            qty_sa_std = xa_std.solution_value()
            qty_sa_exp = xa_exp.solution_value()
            if qty_sa_std + qty_sa_exp > 0.01:
                decisions["Hamburg_Hub_qty"] = float(qty_sa_std + qty_sa_exp)
                decisions["Hamburg_Hub_mode"] = "Expedited" if qty_sa_exp > qty_sa_std else "Standard"

            qty_sb_std = xb_std.solution_value()
            qty_sb_exp = xb_exp.solution_value()
            if qty_sb_std + qty_sb_exp > 0.01:
                decisions["Rotterdam_Port_qty"] = float(qty_sb_std + qty_sb_exp)
                decisions["Rotterdam_Port_mode"] = "Expedited" if qty_sb_exp > qty_sb_std else "Standard"

            # Distribution decisions
            qty_wn_std = ywn_std.solution_value()
            qty_wn_exp = ywn_exp.solution_value()
            if qty_wn_std + qty_wn_exp > 0.01:
                decisions["Dublin_DC_qty"] = float(qty_wn_std + qty_wn_exp)
                decisions["Dublin_DC_mode"] = "Expedited" if qty_wn_exp > qty_wn_std else "Standard"

            qty_ws_std = yws_std.solution_value()
            qty_ws_exp = yws_exp.solution_value()
            if qty_ws_std + qty_ws_exp > 0.01:
                decisions["Galway_DC_qty"] = float(qty_ws_std + qty_ws_exp)
                decisions["Galway_DC_mode"] = "Expedited" if qty_ws_exp > qty_ws_std else "Standard"

            decisions["solver_status"] = "OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE"
            
        return decisions
