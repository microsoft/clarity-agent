"""
Mermaid threat model diagram generator.

Takes structured component/flow/boundary data (as JSON) and produces
a standalone .mmd Mermaid file.

Usage (CLI)::

    python -m clarity_agent.protocol.diagram \\
        --input .clarity-protocol/system_design.json \\
        --threats .clarity-protocol/system_design.json \\
        --output-dir .clarity-protocol

Or import as a module::

    from clarity_agent.protocol.diagram import generate_mermaid
    mermaid_code = generate_mermaid(components, flows, threats)
"""

from __future__ import annotations

import argparse
import json

COMPONENT_ICONS = {
    "External Entity": "👤",
    "Process": "⚙️",
    "Data Store": "🗄️",
    "AI Model": "🤖",
    "Agent": "🔮",
}

COMPONENT_SHAPES = {
    "External Entity": ('["', '"]'),
    "Process": ('["', '"]'),
    "Data Store": ('[("', '")]'),
    "AI Model": ('{"', '"}'),
    "Agent": ('{{"', '"}}'),
}

ZONE_STYLES = {
    "Untrusted": {"fill": "#f8f9fa", "stroke": "#868e96", "label": "🌐 Untrusted"},
    "Low Trust": {"fill": "#fff3bf", "stroke": "#e67700", "label": "🔓 Low Trust"},
    "Trusted": {"fill": "#e7f5ff", "stroke": "#1971c2", "label": "🔒 Trusted"},
    "High Trust": {"fill": "#ffe3e3", "stroke": "#c92a2a", "label": "🔐 High Trust"},
}


def _sanitize_id(name: str) -> str:
    return name.lower().replace(" ", "_").replace("/", "_").replace("-", "_").replace(".", "_").replace("(", "").replace(")", "").replace(",", "").replace("'", "").replace('"', "")[:30]


def _zone_sort_key(zone_name: str) -> int:
    """Sort zones from least trusted to most trusted.

    Uses keyword matching so any LLM-generated zone name gets a
    reasonable position without needing an explicit registry.
    """
    low = zone_name.lower()
    if "untrust" in low or "extern" in low or "public" in low:
        return 0
    if "low" in low or "partial" in low or "client" in low or "user" in low:
        return 1
    if "high" in low or "secret" in low or "privileged" in low:
        return 3
    # Default: middle/trusted
    return 2


def _zone_style(zone_name: str) -> dict[str, str]:
    """Return fill/stroke/label for a zone, using keyword heuristics for unknowns."""
    if zone_name in ZONE_STYLES:
        return ZONE_STYLES[zone_name]
    # Infer style from keywords in the zone name
    low = zone_name.lower()
    if "untrust" in low or "extern" in low or "public" in low:
        return {"fill": "#f8f9fa", "stroke": "#868e96", "label": f"🌐 {zone_name}"}
    if "high" in low or "secret" in low or "privileged" in low:
        return {"fill": "#ffe3e3", "stroke": "#c92a2a", "label": f"🔐 {zone_name}"}
    if "low" in low or "partial" in low or "client" in low or "user" in low:
        return {"fill": "#fff3bf", "stroke": "#e67700", "label": f"🔓 {zone_name}"}
    return {"fill": "#e7f5ff", "stroke": "#1971c2", "label": f"🔒 {zone_name}"}


def generate_mermaid(
    components: list[dict],
    flows: list[dict],
    threats: list[dict] | None = None,
) -> str:
    """Generate standalone Mermaid flowchart code.

    Design principle: readable at a glance by someone with zero threat
    modeling experience. Edge labels show ONLY what data flows. Protocol,
    sensitivity, and threat IDs are kept out of edge labels — they belong
    in the architecture.md tables.

    Renders ALL trust zones found in the data (not just a hardcoded set),
    sorted from least trusted to most trusted using keyword heuristics.
    """
    lines = ["flowchart TB"]

    # Group by trust zone
    zone_groups: dict[str, list] = {}
    for comp in components:
        zone = comp.get("trust_zone", "Trusted")
        zone_groups.setdefault(zone, []).append(comp)

    # Render subgraphs — sorted by inferred trust level
    sorted_zones = sorted(zone_groups.keys(), key=_zone_sort_key)

    for zone_name in sorted_zones:
        zone_comps = zone_groups[zone_name]
        style = _zone_style(zone_name)
        zone_id = _sanitize_id(zone_name)

        lines.append(f'    subgraph {zone_id}["{style["label"]}"]')

        for comp in zone_comps:
            comp_id = _sanitize_id(comp["name"])
            icon = COMPONENT_ICONS.get(comp.get("type", "Process"), "⚙️")
            open_s, close_s = COMPONENT_SHAPES.get(comp.get("type", "Process"), ('["', '"]'))

            label = f"{icon} {comp['name']}"

            lines.append(f'        {comp_id}{open_s}{label}{close_s}')

        lines.append("    end")
        lines.append("")

    # Zone styles
    for zone_name in sorted_zones:
        style = _zone_style(zone_name)
        zone_id = _sanitize_id(zone_name)
        lines.append(f'    style {zone_id} fill:{style["fill"]},stroke:{style["stroke"]},stroke-dasharray:5')
    lines.append("")

    # Data flows — simple labels showing only what data moves
    for flow in flows:
        from_id = _sanitize_id(flow.get("from", ""))
        to_id = _sanitize_id(flow.get("to", ""))

        label = flow.get("data", "")

        # Dashed arrow for secrets/config flows
        is_secret = "secret" in label.lower() or "key" in label.lower() or "credential" in label.lower() or "vault" in flow.get("to", "").lower()
        arrow = "-.->|" if is_secret else "-->|"

        if label:
            lines.append(f'    {from_id} {arrow}"{label}"| {to_id}')
        else:
            simple_arrow = "-.->" if is_secret else "-->"
            lines.append(f'    {from_id} {simple_arrow} {to_id}')

    # Threat annotations — highlight affected components with red/orange borders
    if threats:
        lines.append("")
        lines.append("    classDef threat stroke:#c92a2a,stroke-width:3px")
        lines.append("    classDef high_sev stroke:#e67700,stroke-width:2px")
        for t in threats:
            severity = t.get("severity", "Medium")
            cls = "threat" if severity == "Critical" else "high_sev" if severity == "High" else ""
            for c in t.get("components", []):
                comp_id = _sanitize_id(c)
                if cls:
                    lines.append(f"    {comp_id}:::{cls}")

    return "\n".join(lines)


def generate_file(
    components: list[dict],
    flows: list[dict],
    threats: list[dict] | None = None,
    output_dir: str = ".",
) -> str:
    """Generate standalone .mmd file."""
    mermaid = generate_mermaid(components, flows, threats)

    mmd_path = f"{output_dir}/threat_model.mmd"
    with open(mmd_path, "w", encoding="utf-8") as f:
        f.write(mermaid)

    return mmd_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Mermaid threat model diagram")
    parser.add_argument("--input", help="JSON file with components and flows")
    parser.add_argument("--threats", help="JSON file with threat annotations")
    parser.add_argument("--output-dir", default=".", help="Output directory")
    args = parser.parse_args()

    if args.input:
        with open(args.input) as f:
            data = json.load(f)
    else:
        data = {
            "components": [
                {"name": "User", "type": "External Entity", "trust_zone": "Untrusted"},
                {"name": "API Gateway", "type": "Process", "trust_zone": "Trusted"},
                {"name": "LLM Service", "type": "AI Model", "trust_zone": "Trusted"},
                {"name": "Database", "type": "Data Store", "trust_zone": "High Trust"},
                {"name": "Key Vault", "type": "Data Store", "trust_zone": "High Trust"},
            ],
            "flows": [
                {"from": "User", "to": "API Gateway", "data": "Request"},
                {"from": "API Gateway", "to": "LLM Service", "data": "Prompt"},
                {"from": "LLM Service", "to": "Database", "data": "Embeddings"},
                {"from": "API Gateway", "to": "Key Vault", "data": "API keys"},
            ],
        }

    threats = None
    if args.threats:
        with open(args.threats) as f:
            threats = json.load(f).get("threats", [])

    mmd = generate_file(
        components=data.get("components", []),
        flows=data.get("flows", []),
        threats=threats,
        output_dir=args.output_dir,
    )
    print(f"Generated {mmd}")


if __name__ == "__main__":
    main()
