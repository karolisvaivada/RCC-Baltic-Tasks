import json
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import requests
from lxml import etree
import matplotlib.pyplot as plt


def request_data(
    report_id: str,
    start_date: str,
    end_date: str,
    value_name: str,
) -> pd.DataFrame:
    """
    Request a report from the Baltic Transparency Dashboard API
    and return an expanded time-series DataFrame.

    Parameters
    ----------
    report_id : str
        Report identifier.
    start_date : str
        ISO timestamp in UTC.
    end_date : str
        ISO timestamp in UTC.
    value_name : str
        Name of the value column.

    Returns
    -------
    pd.DataFrame
        Time-series DataFrame with UTC timestamps.
    """
    url = "https://api-baltic.transparency-dashboard.eu/api/v1/export"

    params = {
        "id": report_id,
        "start_date": start_date,
        "end_date": end_date,
        "output_time_zone": "UTC",
        "output_format": "json",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    frames = []

    for ts in payload["data"]["timeseries"]:
        start = pd.to_datetime(ts["from"], utc=True)
        end = pd.to_datetime(ts["to"], utc=True)
        values = ts["values"]

        freq = (end - start) / len(values)
        timestamps = pd.date_range(start=start, periods=len(values), freq=freq)

        frames.append(
            pd.DataFrame(
                {
                    "timestamp": timestamps,
                    value_name: values,
                }
            )
        )

    df = pd.concat(frames, ignore_index=True)
    return df.sort_values("timestamp").reset_index(drop=True)


def afrr_assessment_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute metrics describing aFRR activation versus system imbalance.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing `imbalance` and `afrr_activation`.

    Returns
    -------
    pd.DataFrame
        Metrics table.
    """
    d = df.copy()
    d["abs_imbalance"] = d["imbalance"].abs()

    total_abs_imb = d["abs_imbalance"].sum()
    total_afrr = d["afrr_activation"].sum()

    active_mask = d["afrr_activation"] > 0

    metrics = {
        "total_abs_imbalance_MWh": total_abs_imb,
        "total_afrr_activation_MWh": total_afrr,
        "coverage_ratio_total": (
            total_afrr / total_abs_imb if total_abs_imb else np.nan
        ),
        "activation_frequency": active_mask.mean(),
        "corr(|imbalance|, afrr)": d["abs_imbalance"].corr(
            d["afrr_activation"]
        ),
        "active_period_coverage": (
            d.loc[active_mask, "afrr_activation"].sum()
            / d.loc[active_mask, "abs_imbalance"].sum()
            if d.loc[active_mask, "abs_imbalance"].sum()
            else np.nan
        ),
        "peak_abs_imbalance_MWh": d["abs_imbalance"].max(),
        "peak_afrr_activation_MWh": d["afrr_activation"].max(),
    }

    return pd.DataFrame(
        {"metric": metrics.keys(), "value": metrics.values()}
    )



def plot_abs_imbalance_vs_afrr(
    df,
    title="Absolute Imbalance vs aFRR Activation",
    save_path=None
):
    """
    Wide, static Matplotlib plot (GitHub-safe).
    Shows only once in Jupyter.
    """

    ts_col = "timestamp"
    afrr_col = next((c for c in df.columns if "afrr" in c.lower()), None)
    imb_col = next((c for c in df.columns if "imb" in c.lower()), None)

    abs_imbalance = np.abs(df[imb_col])

    fig, ax1 = plt.subplots(figsize=(18, 6))  

    ax1.plot(
        df[ts_col],
        abs_imbalance,
        color="royalblue",
        linewidth=1.8,
        label="Absolute Imbalance (MW)"
    )
    ax1.set_xlabel("Time (UTC)")
    ax1.set_ylabel("Absolute Imbalance (MW)", color="royalblue")
    ax1.tick_params(axis='y', labelcolor="royalblue")


    ax2 = ax1.twinx()
    ax2.plot(
        df[ts_col],
        df[afrr_col],
        color="crimson",
        linestyle="--",
        linewidth=1.6,
        label="aFRR Activation (MW)"
    )
    ax2.set_ylabel("aFRR Activation (MW)", color="crimson")
    ax2.tick_params(axis='y', labelcolor="crimson")

    fig.suptitle(title, fontsize=14, fontweight="bold")
    fig.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150)

    plt.show()          
    plt.close(fig) 


def load_xml_tree(xml_path: str) -> etree._ElementTree:
    """
    Load an XML file into an lxml tree.

    Parameters
    ----------
    xml_path : str
        Path to XML file.

    Returns
    -------
    etree._ElementTree
        Parsed XML tree.
    """
    parser = etree.XMLParser(recover=True)
    return etree.parse(xml_path, parser)


def get_generating_units_q1(tree: etree._ElementTree) -> pd.DataFrame:
    """
    Extract generating units and maximum operating power.

    Parameters
    ----------
    tree : etree._ElementTree
        CIM XML tree.

    Returns
    -------
    pd.DataFrame
        Generating units table.
    """
    ns = {
        "cim": "http://iec.ch/TC57/CIM100#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    }

    rows = []

    for unit in tree.xpath("//cim:GeneratingUnit", namespaces=ns):
        name = unit.xpath(
            "cim:IdentifiedObject.name/text()", namespaces=ns
        )
        max_p = unit.xpath(
            "cim:GeneratingUnit.maxOperatingP/text()", namespaces=ns
        )

        rows.append(
            {
                "GeneratingUnit": name[0] if name else None,
                "MaxOperatingP_MW": float(max_p[0]) if max_p else None,
            }
        )

    return pd.DataFrame(rows)


def get_generator_regulation_q2(
    tree: etree._ElementTree,
    generator_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve voltage regulation details for a synchronous generator.
    """
    ns = {
        "cim": "http://iec.ch/TC57/CIM100#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    }

    machines = tree.xpath(
        f"//cim:SynchronousMachine[cim:IdentifiedObject.name='{generator_name}']",
        namespaces=ns,
    )

    if not machines:
        return None

    sm = machines[0]

    voltage_reg = sm.xpath(
        "cim:SynchronousMachine.voltageRegulationRange/text()",
        namespaces=ns,
    )

    regulating_control = sm.xpath(
        "cim:RegulatingCondEq.RegulatingControl/@rdf:resource",
        namespaces=ns,
    )

    sm_type = sm.xpath(
        "cim:SynchronousMachine.type/@rdf:resource",
        namespaces=ns,
    )

    return {
        "Generator": generator_name,
        "VoltageRegulationRange": float(voltage_reg[0]) if voltage_reg else None,
        "RegulatingControlRef": regulating_control[0] if regulating_control else None,
        "MachineType": sm_type[0] if sm_type else None,
    }


def get_transformer_windings_q3(
    tree: etree._ElementTree,
    transformer_id: str,
) -> List[Dict[str, Any]]:
    """
    Extract transformer winding information.
    """
    ns = {
        "cim": "http://iec.ch/TC57/CIM100#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    }

    results = []

    for end in tree.xpath("//cim:PowerTransformerEnd", namespaces=ns):
        pt_ref = end.xpath(
            "cim:PowerTransformerEnd.PowerTransformer/@rdf:resource",
            namespaces=ns,
        )

        if not pt_ref or pt_ref[0] != f"#{transformer_id}":
            continue

        end_number = end.xpath(
            "cim:PowerTransformerEnd.endNumber/text()",
            namespaces=ns,
        )

        base_voltage_ref = end.xpath(
            "cim:TransformerEnd.BaseVoltage/@rdf:resource",
            namespaces=ns,
        )

        nominal_voltage = None

        if base_voltage_ref:
            bv = tree.xpath(
                f"//cim:BaseVoltage[@rdf:ID='{base_voltage_ref[0].replace('#', '')}']"
                "/cim:BaseVoltage.nominalVoltage/text()",
                namespaces=ns,
            )
            if bv:
                nominal_voltage = float(bv[0])

        results.append(
            {
                "EndNumber": int(end_number[0]) if end_number else None,
                "NominalVoltage_kV": nominal_voltage,
            }
        )

    return results


def get_line_limits_q4(
    tree: etree._ElementTree,
    line_id: str,
) -> List[Dict[str, Any]]:
    """
    Extract operational limits for a given AC line.
    """
    ns = {
        "cim": "http://iec.ch/TC57/CIM100#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    }

    limits = []

    terminals = tree.xpath(
        "//cim:Terminal"
        "[cim:Terminal.ConductingEquipment/@rdf:resource="
        f"'#{line_id}']",
        namespaces=ns,
    )

    for terminal in terminals:
        term_id = terminal.get(
            "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}ID"
        )

        limit_sets = tree.xpath(
            "//cim:OperationalLimitSet"
            "[cim:OperationalLimitSet.Terminal/@rdf:resource="
            f"'#{term_id}']",
            namespaces=ns,
        )

        for ls in limit_sets:
            limit_refs = ls.xpath(
                "cim:OperationalLimitSet.OperationalLimit/@rdf:resource",
                namespaces=ns,
            )

            for ref in limit_refs:
                lim_id = ref.replace("#", "")
                lim = tree.xpath(
                    f"//cim:OperationalLimit[@rdf:ID='{lim_id}']",
                    namespaces=ns,
                )

                if not lim:
                    continue

                lim = lim[0]

                value = lim.xpath(
                    "cim:OperationalLimit.value/text()",
                    namespaces=ns,
                )

                limit_type_ref = lim.xpath(
                    "cim:OperationalLimit.OperationalLimitType/@rdf:resource",
                    namespaces=ns,
                )

                limit_kind = None

                if limit_type_ref:
                    lt_id = limit_type_ref[0].replace("#", "")
                    kind = tree.xpath(
                        f"//cim:OperationalLimitType[@rdf:ID='{lt_id}']"
                        "/cim:OperationalLimitType.kind/text()",
                        namespaces=ns,
                    )
                    if kind:
                        limit_kind = kind[0]

                limits.append(
                    {
                        "LimitKind": limit_kind,
                        "Value": float(value[0]) if value else None,
                    }
                )

    return limits


def find_limit_elements(tree: etree._ElementTree) -> List[str]:
    """
    Find unique element names containing the word 'Limit'.
    """
    elements = tree.xpath("//*[contains(local-name(), 'Limit')]")

    names = {
        el.tag.split("}")[-1]
        for el in elements
    }

    return sorted(names)


def get_slack_generator_q5(tree: etree._ElementTree) -> str:
    """
    Identify slack generator based on referencePriority.
    """
    ns = {
        "cim": "http://iec.ch/TC57/CIM100#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    }

    ref_attrs = tree.xpath(
        "//cim:SynchronousMachine.referencePriority",
        namespaces=ns,
    )

    if not ref_attrs:
        return (
            "No SynchronousMachine.referencePriority attribute "
            "defined in this EQ profile."
        )

    for machine in tree.xpath(
        "//cim:SynchronousMachine",
        namespaces=ns,
    ):
        priority = machine.xpath(
            "cim:SynchronousMachine.referencePriority/text()",
            namespaces=ns,
        )

        if priority and priority[0] == "1":
            name = machine.xpath(
                "cim:IdentifiedObject.name/text()",
                namespaces=ns,
            )
            return (
                f"Slack generator: {name[0]}"
                if name
                else "Slack generator found but name missing."
            )

    return (
        "referencePriority exists, but no generator is set "
        "as slack (priority = 1)."
    )


def check_model_issues_q6(
    tree: etree._ElementTree,
) -> List[Dict[str, str]]:
    """
    Perform structural validation checks on model.
    """
    ns = {
        "cim": "http://iec.ch/TC57/CIM100#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    }

    issues: List[Dict[str, str]] = []

    for machine in tree.xpath("//cim:SynchronousMachine", namespaces=ns):
        name = machine.xpath(
            "cim:IdentifiedObject.name/text()",
            namespaces=ns,
        )
        name = name[0] if name else "UNKNOWN"

        rc = machine.xpath(
            "cim:RegulatingCondEq.RegulatingControl/@rdf:resource",
            namespaces=ns,
        )

        if not rc:
            issues.append(
                {
                    "Type": "Logical",
                    "Issue": "Generator without regulating control",
                    "Object": name,
                }
            )

        vr = machine.xpath(
            "cim:SynchronousMachine.voltageRegulationRange/text()",
            namespaces=ns,
        )

        if vr and float(vr[0]) == 0:
            issues.append(
                {
                    "Type": "Parameter",
                    "Issue": "Generator has zero voltage regulation range",
                    "Object": name,
                }
            )

        gu = machine.xpath(
            "cim:RotatingMachine.GeneratingUnit/@rdf:resource",
            namespaces=ns,
        )

        if not gu:
            issues.append(
                {
                    "Type": "Logical",
                    "Issue": "Generator without GeneratingUnit link",
                    "Object": name,
                }
            )

    for transformer in tree.xpath(
        "//cim:PowerTransformer",
        namespaces=ns,
    ):
        t_id = transformer.get(
            "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}ID"
        )

        ends = tree.xpath(
            "//cim:PowerTransformerEnd"
            "[cim:PowerTransformerEnd.PowerTransformer/@rdf:resource="
            f"'#{t_id}']",
            namespaces=ns,
        )

        if len(ends) < 2:
            issues.append(
                {
                    "Type": "Logical",
                    "Issue": "Transformer with less than two windings",
                    "Object": t_id,
                }
            )

        for end in ends:
            bv = end.xpath(
                "cim:TransformerEnd.BaseVoltage/@rdf:resource",
                namespaces=ns,
            )

            if not bv:
                issues.append(
                    {
                        "Type": "Power-system",
                        "Issue": "Transformer winding without BaseVoltage",
                        "Object": t_id,
                    }
                )

    for line in tree.xpath("//cim:ACLineSegment", namespaces=ns):
        line_id = line.get(
            "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}ID"
        )

        terminals = tree.xpath(
            "//cim:Terminal"
            "[cim:Terminal.ConductingEquipment/@rdf:resource="
            f"'#{line_id}']",
            namespaces=ns,
        )

        if not terminals:
            issues.append(
                {
                    "Type": "Logical",
                    "Issue": "Line without terminals",
                    "Object": line_id,
                }
            )

    for terminal in tree.xpath("//cim:Terminal", namespaces=ns):
        term_id = terminal.get(
            "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}ID"
        )

        node = terminal.xpath(
            "cim:Terminal.TopologicalNode/@rdf:resource",
            namespaces=ns,
        )

        if not node:
            issues.append(
                {
                    "Type": "Logical",
                    "Issue": "Terminal without TopologicalNode",
                    "Object": term_id,
                }
            )

    for limit_set in tree.xpath(
        "//cim:OperationalLimitSet",
        namespaces=ns,
    ):
        ls_id = limit_set.get(
            "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}ID"
        )

        limits = limit_set.xpath(
            "cim:OperationalLimitSet.OperationalLimit",
            namespaces=ns,
        )

        if not limits:
            issues.append(
                {
                    "Type": "Logical",
                    "Issue": "OperationalLimitSet without limits",
                    "Object": ls_id,
                }
            )

    return issues