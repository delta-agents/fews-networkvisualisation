# FEWSVisualiser: Insights for optimized Delft-FEWS configurations

A differerent approach to the analysis and visualisation of Delft-FEWS configuration

## Data model

![Config Vis Datamodel](https://github.com/delta-agents/fews-networkvisualisation/blob/main/ConfigVisDatamodel.png?raw=true)

## Development

To manage the environment we use Pixi.

<details>
<summary>windows</summary>

```powershell
iwr -useb https://pixi.sh/install.ps1 | iex
```

</details>

<details>
<summary>Linux/Mac</summary>

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

</details>

### installing

With the `Pixi` command in powershell install the python environment:

```bash
 cd ../python_package_template
 pixi install
```

The `pixi.lock` file loads the correct packages and downloads to the `.pixi` file, you can use this environment in developing and resting.

#### How to run when developing?

```bash
pixi install
```

```bash
pixi run analyse_config {path_to_config} {path_to_db}
# e.g: 
pixi run analyse_config  "..\FEWS Digiflow\Config" "db\digiflow.db3"
```
