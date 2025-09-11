import ixmp
import message_ix
import pandas as pd
import logging
import sys
from pathlib import Path
import pandas as pd
sys.path.append(str(Path.cwd().parent.parent))

from tool.util import get_logger

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

# Load platform
mp = ixmp.Platform("local", jvmargs = ["-Xmx16G"])

# Specify model and scenario
model_ori = "SSP2_v6.1_local"
scenario_ori = "baseline_DEFAULT"

# model_ori = "Westeros Electrified"
# scenario_ori = "baseline_test"

# Create new scenario
scen_load = message_ix.Scenario(mp, model_ori, scenario_ori, version="new")
log.info("New scen created.")

# Specify the dir
repo_dir = Path.cwd().resolve()
repo_dir
data_dir = repo_dir / "data" / "20250801local_db"
xlsx_file = data_dir / "ssp2_v6_baseline_default.xlsx"
# xlsx_file = data_dir / "test_westeros.xlsx"

# Load excel file
log.info("Loading excel ...")
scen_load.read_excel(
    xlsx_file,
    add_units=True,
    init_items=True,
    commit_steps=True,
)
log.info("Loaded.")

# Specify name for output gdx
case = scen_load.model + "_" + scen_load.scenario
print("CASE:",case)


# Solve scenario
message_ix.models.DEFAULT_CPLEX_OPTIONS = {
    "advind": 0,
    "lpmethod": 4,
    "threads": 4,
    "epopt": 1e-6,
    "scaind": -1,
    # "predual": 1, 
    "barcrossalg": 0,
}

scen_load.solve(case = case)

# Load base scenario
log.info("Loading scenario from local db ...")
base = message_ix.Scenario(mp, model_ori, scenario_ori)
log.info("Loaded.")
base.set_as_default()

# check = base.var("EMISS")
check = base.par("input")
print(check.head())

check = base.var("ACT")
print(check.head())

# Something might be useful

# from message_ix.testing import make_westeros
# scen = make_westeros(mp)
# scen.to_excel("test_westeros.xlsx")


mp = ixmp.Platform("ixmp_dev", jvmargs = ["-Xmx16G"])

model_ori = "SSP_SSP1_v5.3.1" # latest version "SSP_SSP2_v6.1"
scen_ori = "baseline_1000f" # latest version "SSP2 - Low Emissions"

# Load scenario
base = message_ix.Scenario(mp, model=model_ori, scenario=scen_ori)
log.info("Scenario loaded.")

scen = base.clone(model_ori, scen_ori, keep_solution=False)
scen.to_excel("SSP_SSP1_v5.3.1_baseline_1000f.xlsx")

