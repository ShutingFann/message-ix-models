import os
import pandas as pd
from message_ix_models.util import package_data_path

wacc_scenario, ssp = "Baseline", "SSP2"
ssp = "SSP2"
wacc_scenario = "Baseline"
baseline_year = 2020
A_default = 0.10
wacc_csv_path = "message-ix-models/message_ix_models/project/investment/Predicted_WACC_All_SSPs_8_mean.csv"
inv_cost_filename = "inv_cost_ori.csv"
out_filename = "inv_cost.csv"

"""
Generate investment cost file (inv_cost.csv) with CoC decomposition.
"""

def map_category(tech: str) -> str:
    """Map technology name to category."""
    if tech.startswith("solar_") or tech.startswith("csp_"):
        return "solar"
    elif tech.startswith("wind_"):
        return "wind"
    elif tech.startswith("bio_"):
        return "bio"
    elif tech.startswith("hydro_"):
        return "hydro"
    # if category_map_override:
    #     for prefix, cat in category_map_override.items():
    #         if tech.startswith(prefix):
    #             return cat
    return tech

# 1. Load original investment cost data
folder_path = package_data_path("investment")
folder_path
inv_cost_ori = pd.read_csv(os.path.join(folder_path, inv_cost_filename))
inv_cost = inv_cost_ori[inv_cost_ori["year_vtg"] >= baseline_year].copy()

# 2. Load and filter WACC data
wacc = pd.read_csv(wacc_csv_path)
wacc = wacc[
    (wacc["Scenario"] == wacc_scenario) &
    (wacc["SSP"] == ssp)
].copy()
wacc = wacc.rename(columns={
    "Region": "node_loc",
    "Year": "year_vtg",
    "Tech": "category",
    "WACC": "A"
})

# 3. Map technology to category and merge
inv_cost = inv_cost.rename(columns={"technology": "technology_ori"})
inv_cost["category"] = inv_cost["technology_ori"].apply(map_category)
inv_cost = inv_cost.merge(
    wacc[["node_loc", "year_vtg", "category", "A"]],
    on=["node_loc", "year_vtg", "category"],
    how="left"
)

# 4. Fill missing WACC and compute CoC/non-CoC
inv_cost["A"] = inv_cost["A"].fillna(A_default)
inv_cost["coc_base"] = inv_cost["value"] * inv_cost["A"]
inv_cost["non_coc_base"] = inv_cost["value"] - inv_cost["coc_base"]

# 5. Restore original technology column
inv_cost["technology"] = inv_cost["technology_ori"]
inv_cost = inv_cost.drop(columns=["technology_ori", "category"], errors="ignore")

# 6. Sort and compute growth
inv_cost = inv_cost.sort_values(["node_loc", "technology", "year_vtg"]).copy()
inv_cost["value_growth"] = (
    inv_cost
    .groupby(["node_loc", "technology"])["value"]
    .transform(lambda x: x.div(x.shift(1)))
    .fillna(1.0)
)
inv_cost["non_coc_base0"] = (
    inv_cost
    .groupby(["node_loc", "technology"])["non_coc_base"]
    .transform("first")
)
inv_cost["cum_growth"] = (
    inv_cost
    .groupby(["node_loc", "technology"])["value_growth"]
    .cumprod()
)

# 7. Recalculate non-CoC and total value
inv_cost["non_coc_new"] = inv_cost["non_coc_base0"] * inv_cost["cum_growth"]
inv_cost["value"] = inv_cost["non_coc_new"] / (1.0 - inv_cost["A"])
inv_cost["coc_base"] = inv_cost["value"] * inv_cost["A"]

# 8. Save final output
cols = [
    "node_loc", "technology", "year_vtg", "value",
    "unit", "coc_base", "non_coc_base"
]
out = inv_cost[cols]
out.to_csv(os.path.join(str(folder_path), out_filename), index=False)
os.path.join(str(folder_path), out_filename)