# # Run FEWS visualiser
# This scipt bulk analyses FEWS configs using the FEWS visualiser tool.

import pandas as pd
from pathlib import Path
import numpy as np
import subprocess

def main():
    root_dir = Path("P:/PR/5473.10/Toeleveringen")
    df = pd.read_excel(root_dir / "overzicht.xlsx")
    df_filtered = df[['Waterschap','Config WIS','Config BOS']]
    for _, row in df_filtered.iterrows():
        name = row['Waterschap'] 
        wis  = row['Config WIS'] 
        bos = row['Config BOS']
        if isinstance(wis, str):
            subprocess.run(["pixi","run", "analyse_config", str(root_dir/str(wis)), f"db\\{name}_wis.db3"], check=True)
        if isinstance(bos, str):
            subprocess.run(["pixi", "run","analyse_config", str(root_dir/str(bos)), f"db\\{name}_bos.db3"], check=True)

if __name__ == "__main__":
    main()
