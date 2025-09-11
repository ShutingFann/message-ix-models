import os
import pandas as pd
import message_ix # type: ignore
import ixmp # type: ignore
import logging
import sys

mp = ixmp.Platform("ixmp_dev", jvmargs = ["-Xmx16G"])
from pathlib import Path
from message_ix_models.util import package_data_path

def get_logger(name: str):
    # Set the logging level to INFO (will show INFO and above messages)
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)

    # Define the format of log messages:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(name)s %(asctime)s %(levelname)s %(message)s")

    # Apply the format to the handler
    handler.setFormatter(formatter)

    # Add the handler to the logger
    log.addHandler(handler)

    return log

log = get_logger(__name__)

par_list = [
    "inv_cost",
    # "bound_new_capacity_lo",
]

# All power generation technologies
# check here
# https://github.com/iiasa/message-ix-models/blob/main/message_ix_models/data/technology.yaml
tech_list = [
    "coal_ppl", "coal_ppl_u", "coal_adv", "coal_adv_ccs",
    "igcc", "igcc_ccs",
    "foil_ppl", "loil_ppl", "loil_cc",
    "gas_ppl", "gas_ct", "gas_cc", "gas_cc_ccs",
    "bio_ppl", "bio_istig", "bio_istig_ccs",
    "geo_ppl",
    "solar_res1", "solar_res2", "solar_res3", "solar_res4",
    "solar_res5", "solar_res6", "solar_res7", "solar_res8",
    "solar_res_RT1", "solar_res_RT2", "solar_res_RT3", "solar_res_RT4",
    "solar_res_RT5", "solar_res_RT6", "solar_res_RT7", "solar_res_RT8",
    "csp_sm1_res1", "csp_sm1_res2", "csp_sm1_res3", "csp_sm1_res4",
    "csp_sm1_res5", "csp_sm1_res6", "csp_sm1_res7",
    "wind_res1", "wind_res2", "wind_res3", "wind_res4",
    "wind_ref1", "wind_ref2", "wind_ref3", "wind_ref4", "wind_ref5",
    "nuc_lc", "nuc_hc", "nuc_fbr"
]

# Specify scenario
wacc_scenario, ssp = "Low_ICF_His", "SSP2"
model_ori = "SSP_SSP2_v5.3.1" # latest version "SSP_SSP2_v6.1"
scen_ori = "baseline_1000f" # latest version "SSP2 - Low Emissions"
model_tgt = "MESSAGEix-GLOBIOM 2.0-M-R12 Investment"
# scen_tgt = "baseline_ssp6.1_low_base"
scen_tgt = f"{wacc_scenario}_{ssp}"

# Load scenario
base = message_ix.Scenario(mp, model=model_ori, scenario=scen_ori)
log.info("Scenario loaded.")

# Check the inv_cost of power technologies
inv_cost = base.par('inv_cost', filters={'technology': tech_list})
folder_path = package_data_path("investment")
inv_cost.to_csv(os.path.join(str(folder_path), "inv_cost_ori.csv"), index=False)

# Function that generate new inv_cost # Dummy
def gene_coc(
    ssp: str = "SSP2",
    wacc_scenario: str = "Baseline",
    baseline_year: int = 2020,
    A_default: float = 0.10,
    wacc_csv_path: str = "message-ix-models/message_ix_models/project/investment/Predicted_WACC_All_SSPs_8_mean.csv",
    inv_cost_filename: str = "inv_cost_ori.csv",
    out_filename: str = "inv_cost.csv",
    category_map_override: dict | None = None,
) -> None:
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
        if category_map_override:
            for prefix, cat in category_map_override.items():
                if tech.startswith(prefix):
                    return cat
        return tech

    # 1. Load original investment cost data
    folder_path = package_data_path("investment")
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

# Function that implements new CoC (read inv_cost)
def imple_coc(scen):
    scen.check_out()

    # Create data file list
    folder_path = package_data_path("investment")
    data_files = [f for f in os.listdir(folder_path) if f.endswith(".csv")]

    # Load data files
    dic_data = {}
    for file in data_files:
        file_path = os.path.join(folder_path, file)
        key_name = file.replace(".csv", "")  # Remove .csv extension
        df = pd.read_csv(file_path)
        dic_data[key_name] = df

    # Add par
    for i in par_list:
        # Find all keys in dic_data that exactly matching the parameter name
        matching_keys = [k for k in dic_data.keys() if k == i]
        if matching_keys:
            # Combine all matching DataFrames
            combined_df = pd.concat(
                [dic_data[k] for k in matching_keys], ignore_index=True
            )
            scen.add_par(i, combined_df)
            log.info(f"Parameter {i} from {matching_keys} added.")
        else:
            log.info("No new parameters found.")
            pass
    scen.commit("New CoC implemented.")

# Clone scenario
scen = base.clone(model_tgt, scen_tgt, keep_solution=False)
scen.set_as_default()
log.info("Scenario cloned.")

# Generate new parameters
gene_coc(ssp=ssp, wacc_scenario=wacc_scenario)

# Apply scenario settings
imple_coc(scen)
log.info("Scenario settings added.")

# Specify cplex solver options
message_ix.models.DEFAULT_CPLEX_OPTIONS = {
    "advind": 0,
    "lpmethod": 4,
    "threads": 4,
    "epopt": 1e-6,
    "scaind": -1,
    # "predual": 1,
    "barcrossalg": 0,
}

# Specify solver
solver = "MESSAGE"  # after having some solved runs, try using solver = "MESSAGE-MACRO"

# Solve scenario
scen.solve(solver)

# Close the connection to the database
log.info("Closing connection to the database.")
mp.close_db()
