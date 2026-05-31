import streamlit as st
import simpy
import time
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

from digital_twin.database import DatabaseManager
from digital_twin.simulation import SupplyChainSimulation
from digital_twin.kpis import KPICalculator

# Set page config
st.set_page_config(
    page_title="AI Supply Chain Digital Twin",
    page_icon="⛓️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium CSS
st.markdown("""
<style>
    /* Sleek gradient background for metrics */
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }
    .main-header {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(135deg, #1f4068, #162447);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .kpi-card {
        padding: 15px;
        border-radius: 8px;
        background-color: #f8f9fa;
        border-left: 5px solid #1f4068;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }
    .ai-card {
        padding: 20px;
        border-radius: 10px;
        background-color: #eef2f7;
        border-left: 5px solid #00b4d8;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 15px;
    }
    .ai-applied {
        color: #2a9d8f;
        font-weight: bold;
    }
    .ai-not-applied {
        color: #e76f51;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize DB Manager
db = DatabaseManager()

# Header Title
st.markdown("""
<div class="main-header">
    <h1>⛓️ AI Supply Chain Digital Twin Dashboard</h1>
    <p>Discrete-Event Logistics Simulation, AI-Powered Disruption Mitigations & Real-time KPI Comparison</p>
</div>
""", unsafe_allow_html=True)

# Helper function to run the simulation
def run_simulation(duration_days, demand_mean, demand_std, disruptions, mitigation_enabled, run_id, scenario_type, use_ortools=False):
    env = simpy.Environment()
    config = {
        "demand_mean": demand_mean,
        "demand_std": demand_std,
        "disruptions": disruptions,
        "mitigation_enabled": mitigation_enabled,
        "use_ortools": use_ortools
    }
    # Instantiate and run
    sim = SupplyChainSimulation(run_id, scenario_type, db, env, duration_days, config)
    env.run(until=duration_days)
    return sim

# Sidebar controls
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3061/3061341.png", width=80)
st.sidebar.header("🕹️ Simulation Settings")

duration = st.sidebar.slider("Simulation Duration (Days)", min_value=30, max_value=90, value=60, step=5)

st.sidebar.subheader("📈 Customer Demand Parameters")
demand_mean = st.sidebar.slider("Base Daily Demand (Units)", min_value=2.0, max_value=10.0, value=5.0, step=0.5)
demand_std = st.sidebar.slider("Demand Std Dev", min_value=0.5, max_value=3.0, value=1.5, step=0.1)

st.sidebar.subheader("⚠️ Disruption Injectors")
inject_port = st.sidebar.toggle("Inject Port Closure", value=True)
port_day = st.sidebar.slider("Port Closure Start Day", min_value=5, max_value=duration-10, value=15) if inject_port else None

inject_supplier = st.sidebar.toggle("Inject Supplier B Failure", value=True)
supplier_day = st.sidebar.slider("Supplier Failure Start Day", min_value=5, max_value=duration-10, value=30) if inject_supplier else None

inject_truck = st.sidebar.toggle("Inject Highway Storm (Truck Breakdown)", value=True)
truck_day = st.sidebar.slider("Highway Storm Start Day", min_value=5, max_value=duration-10, value=10) if inject_truck else None

inject_surge = st.sidebar.toggle("Inject Demand Surge (3x Spike)", value=True)
surge_day = st.sidebar.slider("Demand Surge Start Day", min_value=5, max_value=duration-10, value=20) if inject_surge else None

# Pack disruption configuration
disruptions_config = {
    "port_closure": port_day,
    "supplier_failure": supplier_day,
    "truck_breakdown": truck_day,
    "demand_surge": surge_day
}

# Run execution
if st.sidebar.button("🚀 Run Digital Twin Simulation", use_container_width=True):
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Run IDs
    baseline_run_id = f"Run_{timestamp_str}_Baseline"
    disrupted_run_id = f"Run_{timestamp_str}_Disrupted"
    mitigated_run_id = f"Run_{timestamp_str}_Mitigated"
    optimized_run_id = f"Run_{timestamp_str}_Optimized"
    
    with st.spinner("Running simulation scenarios..."):
        # 1. Baseline Run: No disruptions, mitigation disabled
        empty_disruptions = {k: None for k in disruptions_config}
        run_simulation(duration, demand_mean, demand_std, empty_disruptions, False, baseline_run_id, "baseline")
        
        # 2. Disrupted Run: Disruptions active, mitigation disabled (no action taken)
        run_simulation(duration, demand_mean, demand_std, disruptions_config, False, disrupted_run_id, "disrupted")
        
        # 3. AI-Mitigated Run: Disruptions active, mitigation enabled (AI overrides actions)
        run_simulation(duration, demand_mean, demand_std, disruptions_config, True, mitigated_run_id, "mitigated")
        
        # 4. OR-Tools Optimised Run: Disruptions active, optimization enabled
        run_simulation(duration, demand_mean, demand_std, disruptions_config, False, optimized_run_id, "optimized", use_ortools=True)
        
        # Cache active runs in Streamlit state
        st.session_state["baseline_run_id"] = baseline_run_id
        st.session_state["disrupted_run_id"] = disrupted_run_id
        st.session_state["mitigated_run_id"] = mitigated_run_id
        st.session_state["optimized_run_id"] = optimized_run_id
        st.session_state["simulation_executed"] = True
        
    st.success("Simulation finished successfully! View results in tabs below.")

# Check if simulation was run, if not load last run or show warning
if "simulation_executed" not in st.session_state:
    # Try to load existing runs from DB
    runs_df = db.get_runs()
    if not runs_df.empty:
        # Find the latest set of runs (grouped by timestamp prefix)
        runs_df['timestamp_group'] = runs_df['run_id'].apply(lambda x: x.split('_')[1] + '_' + x.split('_')[2] if len(x.split('_')) > 2 else x)
        latest_group = runs_df['timestamp_group'].iloc[0]
        
        st.session_state["baseline_run_id"] = f"Run_{latest_group}_Baseline"
        st.session_state["disrupted_run_id"] = f"Run_{latest_group}_Disrupted"
        st.session_state["mitigated_run_id"] = f"Run_{latest_group}_Mitigated"
        st.session_state["optimized_run_id"] = f"Run_{latest_group}_Optimized"
        st.session_state["simulation_executed"] = True
    else:
        st.info("👋 Welcome! Use the sidebar settings to configure and click **Run Digital Twin Simulation** to begin.")
        st.stop()

# Retrieve run IDs
baseline_id = st.session_state["baseline_run_id"]
disrupted_id = st.session_state["disrupted_run_id"]
mitigated_id = st.session_state["mitigated_run_id"]
optimized_id = st.session_state["optimized_run_id"]

# Compute KPIs for all scenarios
kpi_calc = KPICalculator(db)
kpis_baseline = kpi_calc.calculate_kpis(baseline_id)
kpis_disrupted = kpi_calc.calculate_kpis(disrupted_id)
kpis_mitigated = kpi_calc.calculate_kpis(mitigated_id)
kpis_optimized = kpi_calc.calculate_kpis(optimized_id)

# Main tabs layout
tab_map, tab_kpis, tab_inventory, tab_ai, tab_comparison = st.tabs([
    "🗺️ Network Topology Map",
    "📊 Operational KPIs",
    "📈 Inventory Trends",
    "🤖 AI Control Room",
    "⚖️ Scenario Comparison"
])

# -----------------
# TAB 1: Map
# -----------------
with tab_map:
    st.subheader("Geospatial Supply Chain Network Topology")
    
    # Load nodes
    nodes_df = db.get_nodes(mitigated_id)
    
    if not nodes_df.empty:
        # Define routes (edges)
        routes = [
            ("Hamburg_Hub", "Cork_Factory", "Hamburg Hub -> Cork Factory (Rail/Sea)"),
            ("Rotterdam_Port", "Cork_Factory", "Rotterdam Port -> Cork Factory (Maritime)"),
            ("Cork_Factory", "Dublin_DC", "Cork Factory -> Dublin DC Lane"),
            ("Cork_Factory", "Galway_DC", "Cork Factory -> Galway DC Lane"),
            ("Dublin_DC", "Retailer_Dublin_1", "Dublin DC -> Dublin Retailer East"),
            ("Dublin_DC", "Retailer_Dublin_2", "Dublin DC -> Dundalk Retailer North"),
            ("Galway_DC", "Retailer_Galway", "Galway DC -> Galway Retailer West"),
            ("Galway_DC", "Retailer_Cork", "Galway DC -> Limerick Retailer South"),
        ]
        
        fig = go.Figure()
        
        # Plot Routes (Lines)
        for src, dest, name in routes:
            src_row = nodes_df[nodes_df['node_id'] == src].iloc[0]
            dest_row = nodes_df[nodes_df['node_id'] == dest].iloc[0]
            
            # Determine color of route based on active disruptions in Disrupted run
            color = "rgba(46, 196, 182, 0.7)" # teal green standard
            
            # Highlight disrupted routes in red
            dis_df = db.get_disruptions(disrupted_id)
            is_disrupted = False
            
            if not dis_df.empty:
                for _, row in dis_df.iterrows():
                    dtype = row['type']
                    if dtype == "port_closure" and src == "Rotterdam_Port":
                        is_disrupted = True
                    elif dtype == "supplier_failure" and src == "Rotterdam_Port":
                        is_disrupted = True
                    elif dtype == "truck_breakdown" and src == "Cork_Factory":
                        is_disrupted = True
                        
            if is_disrupted:
                color = "rgba(231, 111, 81, 0.95)" # orange/red
                name += " [⚠️ DISRUPTED]"
                
            fig.add_trace(go.Scattermapbox(
                mode="lines",
                lon=[src_row['lon'], dest_row['lon']],
                lat=[src_row['lat'], dest_row['lat']],
                line=dict(width=3, color=color),
                name=name,
                hoverinfo="text",
                text=name
            ))
            
        # Plot Nodes
        # Define colors per type
        color_map = {
            "Supplier": "#457b9d",
            "Factory": "#e63946",
            "Warehouse": "#f4a261",
            "Customer": "#2a9d8f"
        }
        
        nodes_df['color'] = nodes_df['type'].map(color_map)
        
        fig.add_trace(go.Scattermapbox(
            lat=nodes_df['lat'],
            lon=nodes_df['lon'],
            mode='markers+text',
            marker=dict(
                size=16,
                color=nodes_df['color'],
                opacity=0.9
            ),
            text=nodes_df['name'],
            textposition="top right",
            hoverinfo='text',
            hovertext=nodes_df['name'] + " (" + nodes_df['type'] + ")",
            name="Network Nodes"
        ))
        
        # Set layout
        fig.update_layout(
            mapbox_style="open-street-map",
            mapbox=dict(
                center=dict(lat=53.0, lon=-7.5),
                zoom=6.5
            ),
            margin=dict(l=0, r=0, t=0, b=0),
            height=600,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("No node data found.")
        
    st.markdown("""
    ### 📌 Network Guide
    * **Hamburg Logistics Hub (Reliable)**: High unit cost ($20), fast and reliable overland rail/express lead times. Bypasses maritime ports.
    * **Rotterdam Port (Low-Cost)**: Cheap ($15), but prone to worker strikes and maritime congestion (Port Closures).
    * **Cork Manufacturing Facility**: Daily production capacity of 20 units. Converts Raw Material into Finished Goods.
    * **Distribution Centres (Dublin / Galway)**: Holds finished goods to fulfill local retail customer demands.
    * **Customers**: Irish regional retail nodes generating daily orders.
    """)

# -----------------
# TAB 2: KPIs
# -----------------
with tab_kpis:
    st.subheader("Key Performance Indicators Comparison")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.metric(
            label="Service Level (Baseline)", 
            value=f"{kpis_baseline['service_level']:.1f}%",
            delta=None
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="kpi-card" style="border-left-color: #e76f51;">', unsafe_allow_html=True)
        delta_sl_dis = kpis_disrupted['service_level'] - kpis_baseline['service_level']
        st.metric(
            label="Service Level (Disrupted - No Mitigation)", 
            value=f"{kpis_disrupted['service_level']:.1f}%",
            delta=f"{delta_sl_dis:.1f}%"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col3:
        st.markdown('<div class="kpi-card" style="border-left-color: #2a9d8f;">', unsafe_allow_html=True)
        delta_sl_mit = kpis_mitigated['service_level'] - kpis_disrupted['service_level']
        st.metric(
            label="Service Level (Heuristic AI)", 
            value=f"{kpis_mitigated['service_level']:.1f}%",
            delta=f"+{delta_sl_mit:.1f}% Recovery" if delta_sl_mit > 0 else f"{delta_sl_mit:.1f}%"
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="kpi-card" style="border-left-color: #0077b6;">', unsafe_allow_html=True)
        delta_sl_opt = kpis_optimized['service_level'] - kpis_disrupted['service_level']
        st.metric(
            label="Service Level (OR-Tools Optimised)", 
            value=f"{kpis_optimized['service_level']:.1f}%",
            delta=f"+{delta_sl_opt:.1f}% Recovery" if delta_sl_opt > 0 else f"{delta_sl_opt:.1f}%"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Cost KPIs row
    col1_c, col2_c, col3_c, col4_c = st.columns(4)
    with col1_c:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.metric(label="Total Cost (Baseline)", value=f"${kpis_baseline['total_cost']:,.2f}")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2_c:
        st.markdown('<div class="kpi-card" style="border-left-color: #e76f51;">', unsafe_allow_html=True)
        delta_cost_dis = kpis_disrupted['total_cost'] - kpis_baseline['total_cost']
        st.metric(
            label="Total Cost (Disrupted - No Mitigation)", 
            value=f"${kpis_disrupted['total_cost']:,.2f}",
            delta=f"+${delta_cost_dis:,.2f} Penalty"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col3_c:
        st.markdown('<div class="kpi-card" style="border-left-color: #2a9d8f;">', unsafe_allow_html=True)
        delta_cost_mit = kpis_mitigated['total_cost'] - kpis_disrupted['total_cost']
        savings = -delta_cost_mit
        st.metric(
            label="Total Cost (Heuristic AI)", 
            value=f"${kpis_mitigated['total_cost']:,.2f}",
            delta=f"-${savings:,.2f} Saved by AI" if savings > 0 else f"+${delta_cost_mit:,.2f}"
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with col4_c:
        st.markdown('<div class="kpi-card" style="border-left-color: #0077b6;">', unsafe_allow_html=True)
        delta_cost_opt = kpis_optimized['total_cost'] - kpis_disrupted['total_cost']
        savings_opt = -delta_cost_opt
        st.metric(
            label="Total Cost (OR-Tools)", 
            value=f"${kpis_optimized['total_cost']:,.2f}",
            delta=f"-${savings_opt:,.2f} Saved" if savings_opt > 0 else f"+${delta_cost_opt:,.2f}"
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # Cost Breakdowns Plotly Chart
    st.subheader("Cost Structure Analysis")
    
    categories = ["Inventory Holding Cost", "Transportation Cost", "Stockout Cost"]
    
    costs_baseline = [kpis_baseline['inventory_cost'], kpis_baseline['transportation_cost'], kpis_baseline['stockout_cost']]
    costs_disrupted = [kpis_disrupted['inventory_cost'], kpis_disrupted['transportation_cost'], kpis_disrupted['stockout_cost']]
    costs_mitigated = [kpis_mitigated['inventory_cost'], kpis_mitigated['transportation_cost'], kpis_mitigated['stockout_cost']]
    costs_optimized = [kpis_optimized['inventory_cost'], kpis_optimized['transportation_cost'], kpis_optimized['stockout_cost']]
    
    fig_costs = go.Figure(data=[
        go.Bar(name='Baseline', x=categories, y=costs_baseline, marker_color='#457b9d'),
        go.Bar(name='Disrupted (No Mitigation)', x=categories, y=costs_disrupted, marker_color='#e63946'),
        go.Bar(name='Heuristic AI-Mitigated', x=categories, y=costs_mitigated, marker_color='#2a9d8f'),
        go.Bar(name='OR-Tools Optimised', x=categories, y=costs_optimized, marker_color='#0077b6')
    ])
    fig_costs.update_layout(
        barmode='group',
        yaxis_title='Cost ($)',
        legend_title='Scenarios',
        hovermode="x unified",
        template="plotly_white"
    )
    st.plotly_chart(fig_costs, use_container_width=True)

# -----------------
# TAB 3: Inventory
# -----------------
with tab_inventory:
    st.subheader("Inventory Stock Levels Tracking")
    
    # Scenario picker for inventory curves
    scenario_inv = st.selectbox("Select Scenario to view stock details:", ["Baseline", "Disrupted (No Mitigation)", "AI-Mitigated", "OR-Tools Optimised"])
    
    if scenario_inv == "Baseline":
        active_id = baseline_id
    elif scenario_inv == "Disrupted (No Mitigation)":
        active_id = disrupted_id
    elif scenario_inv == "AI-Mitigated":
        active_id = mitigated_id
    else:
        active_id = optimized_id
        
    inv_df = db.get_inventory_logs(active_id)
    
    if not inv_df.empty:
        # Separate products
        fig_inv = go.Figure()
        
        # Factory RM
        fact_rm = inv_df[inv_df['node_id'] == 'Cork_Factory']
        fig_inv.add_trace(go.Scatter(
            x=fact_rm['timestamp'], y=fact_rm['quantity'],
            mode='lines', name='Cork Factory RM (Raw Steel)',
            line=dict(color='#e63946', width=2.5)
        ))
        
        # Factory FG
        # Note: Factory logs RM and FG separately
        fact_fg = inv_df[(inv_df['node_id'] == 'Cork_Factory') & (inv_df['product_type'] == 'finished_good')]
        fig_inv.add_trace(go.Scatter(
            x=fact_fg['timestamp'], y=fact_fg['quantity'],
            mode='lines', name='Cork Factory FG (Finished Units)',
            line=dict(color='#457b9d', width=2.5, dash='dash')
        ))
        
        # Warehouse North (Dublin DC)
        wn = inv_df[inv_df['node_id'] == 'Dublin_DC']
        fig_inv.add_trace(go.Scatter(
            x=wn['timestamp'], y=wn['quantity'],
            mode='lines', name='Dublin DC (East Hub)',
            line=dict(color='#f4a261', width=2)
        ))
        
        # Warehouse South (Galway DC)
        ws = inv_df[inv_df['node_id'] == 'Galway_DC']
        fig_inv.add_trace(go.Scatter(
            x=ws['timestamp'], y=ws['quantity'],
            mode='lines', name='Galway DC (West Hub)',
            line=dict(color='#2a9d8f', width=2)
        ))
        
        fig_inv.update_layout(
            xaxis_title='Simulation Time (Days)',
            yaxis_title='Stock On-Hand (Units)',
            template='plotly_white',
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_inv, use_container_width=True)
    else:
        st.warning("No inventory records found.")

# -----------------
# TAB 4: AI Control Room
# -----------------
with tab_ai:
    st.subheader("AI Decision Logs & Recommendations Feed")
    
    # Load disruptions and recommendations
    disruptions_df = db.get_disruptions(mitigated_id)
    decisions_df = db.get_ai_decisions(mitigated_id)
    decisions_disrupted_df = db.get_ai_decisions(disrupted_id)
    
    if not disruptions_df.empty:
        for idx, row in disruptions_df.iterrows():
            d_id = row['disruption_id']
            d_type = row['type']
            target_node = row['target']
            start_t = row['start_time']
            end_t = row['end_time']
            desc = row['description']
            
            # Find AI decisions
            ai_row_mitigated = decisions_df[decisions_df['disruption_id'] == d_id]
            
            st.markdown(f'<div class="ai-card">', unsafe_allow_html=True)
            col_l, col_r = st.columns([3, 1])
            
            with col_l:
                st.markdown(f"### ⚠️ {d_type.upper().replace('_', ' ')}: Day {start_t:.1f}")
                st.markdown(f"**Target Area:** `{target_node}`")
                st.markdown(f"**Disruption Event Description:** *{desc}*")
            with col_r:
                st.markdown(f"**Mitigated Status:**")
                st.markdown('<span class="ai-applied">🚀 MITIGATION APPLIED</span>', unsafe_allow_html=True)
                
            if not ai_row_mitigated.empty:
                ai_rec = ai_row_mitigated.iloc[0]['recommendation']
                ai_exp = ai_row_mitigated.iloc[0]['explanation']
                ai_cb = ai_row_mitigated.iloc[0]['cost_benefit_estimate']
                
                with st.expander("🔍 View AI Impact & Trade-Off Assessment Report", expanded=True):
                    st.markdown(f"#### Recommended Action: **{ai_rec}**")
                    st.markdown(ai_exp)
                    if ai_cb > 0:
                        st.success(f"💰 **Estimated Mitigation Net Value (Avoided Stockout Cost - Premium Cost):** ${ai_cb:,.2f}")
            else:
                st.info("No AI assessment logged.")
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No disruptions occurred in this simulation run. Enable them in the sidebar configuration.")

# -----------------
# TAB 5: Scenario Comparison
# -----------------
with tab_comparison:
    st.subheader("Digital Twin Scenario Comparison Ledger")
    
    # Build a comparative table
    comparison_data = {
        "Metric": [
            "Service Level (%)", 
            "Fill Rate (%)", 
            "Stockout Order Rate (%)",
            "Inventory Holding Cost ($)", 
            "Transportation Cost ($)", 
            "Stockout Penalties ($)", 
            "Total Operating Cost ($)"
        ],
        "Baseline (Normal)": [
            f"{kpis_baseline['service_level']:.2f}%",
            f"{kpis_baseline['fill_rate']:.2f}%",
            f"{kpis_baseline['stockout_rate']:.2f}%",
            f"${kpis_baseline['inventory_cost']:,.2f}",
            f"${kpis_baseline['transportation_cost']:,.2f}",
            f"${kpis_baseline['stockout_cost']:,.2f}",
            f"${kpis_baseline['total_cost']:,.2f}"
        ],
        "Disrupted (Unmitigated)": [
            f"{kpis_disrupted['service_level']:.2f}%",
            f"{kpis_disrupted['fill_rate']:.2f}%",
            f"{kpis_disrupted['stockout_rate']:.2f}%",
            f"${kpis_disrupted['inventory_cost']:,.2f}",
            f"${kpis_disrupted['transportation_cost']:,.2f}",
            f"${kpis_disrupted['stockout_cost']:,.2f}",
            f"${kpis_disrupted['total_cost']:,.2f}"
        ],
        "Heuristic AI-Mitigated": [
            f"{kpis_mitigated['service_level']:.2f}%",
            f"{kpis_mitigated['fill_rate']:.2f}%",
            f"{kpis_mitigated['stockout_rate']:.2f}%",
            f"${kpis_mitigated['inventory_cost']:,.2f}",
            f"${kpis_mitigated['transportation_cost']:,.2f}",
            f"${kpis_mitigated['stockout_cost']:,.2f}",
            f"${kpis_mitigated['total_cost']:,.2f}"
        ],
        "OR-Tools Optimised": [
            f"{kpis_optimized['service_level']:.2f}%",
            f"{kpis_optimized['fill_rate']:.2f}%",
            f"{kpis_optimized['stockout_rate']:.2f}%",
            f"${kpis_optimized['inventory_cost']:,.2f}",
            f"${kpis_optimized['transportation_cost']:,.2f}",
            f"${kpis_optimized['stockout_cost']:,.2f}",
            f"${kpis_optimized['total_cost']:,.2f}"
        ]
    }
    
    df_compare = pd.DataFrame(comparison_data)
    st.table(df_compare)
    
    # Financial metrics highlight
    cost_diff = kpis_disrupted['total_cost'] - kpis_mitigated['total_cost']
    cost_diff_opt = kpis_disrupted['total_cost'] - kpis_optimized['total_cost']
    service_diff = kpis_mitigated['service_level'] - kpis_disrupted['service_level']
    service_diff_opt = kpis_optimized['service_level'] - kpis_disrupted['service_level']
    
    st.markdown(f"""
    ### 🧠 Operational Performance Analysis
    * **Heuristic AI Engine Performance:**
      * **Loss Mitigation Net Value:** Reduced total operational losses by **${cost_diff:,.2f}** compared to running the supply chain without mitigations.
      * **Customer Service Level Recovery:** Service level recovered by **+{service_diff:.2f}%** back towards the normal baseline.
    * **OR-Tools Mathematical Optimisation Engine Performance:**
      * **Loss Mitigation Net Value:** Reduced total operational losses by **${cost_diff_opt:,.2f}** (yielding optimal cost routing and sourcing allocation).
      * **Customer Service Level Recovery:** Service level recovered by **+{service_diff_opt:.2f}%** back towards the baseline.
    * **Supply Chain Resiliency Analysis:**
      * Mathematical optimization (OR-Tools) dynamically and globally allocates raw materials and routes distribution daily. By solving a Mixed-Integer Linear Program, it yields a lower cost solution than standard heuristic rules, especially during combined supplier failures and demand surges.
    """)
