#!/usr/bin/env python3

import xml.etree.ElementTree as ET
from pathlib import Path
import argparse

FIELDS = [
    "Hostname", "Username", "Domain", "Port",
    "RDGatewayHostname", "RDGatewayUsername",
    "ConnectToConsole"
]

connections_summary = []


def resolve_props(node, inherited):
    props = inherited.copy()

    for field in FIELDS:
        inherit_flag = node.attrib.get(f"Inherit{field}", "false") == "true"
        if not inherit_flag and field in node.attrib:
            props[field] = node.attrib[field]

    return props


def merge_gateway(props, default_gateway):
    gw = props.get("RDGatewayHostname")

    if not gw and default_gateway:
        props["RDGatewayHostname"] = default_gateway

    return props


def format_username(props):
    user = props.get("Username", "")
    domain = props.get("Domain", "")

    if user:
        return f"{domain}\\{user}" if domain else user
    return ""


def write_rdp(name, props, outdir):
    host = props.get("Hostname", "")
    port = props.get("Port", "3389")

    if host and port != "3389":
        host = f"{host}:{port}"

    user = format_username(props)

    lines = [
        "; Generated from mRemoteNG",
        "; Passwords intentionally omitted — MRD will prompt",
        f"full address:s:{host}",
        f"username:s:{user}",
        f"administrative session:i:{1 if props.get('ConnectToConsole') == 'true' else 0}",
    ]

    gw_host = props.get("RDGatewayHostname")
    gw_user = props.get("RDGatewayUsername")

    if gw_host:
        lines.append(f"gatewayhostname:s:{gw_host}")
        lines.append("gatewayusagemethod:i:1")

    if gw_user:
        lines.append(f"gatewayusername:s:{gw_user}")

    outfile = outdir / f"{name}.rdp"
    outfile.write_text("\n".join(lines), encoding="utf-8")

    connections_summary.append({
        "name": name,
        "host": host,
        "user": user or "(prompt)",
        "gateway": gw_host or "none"
    })

    print("Created:", outfile.name)


def walk(node, inherited, outdir, default_gateway):
    props = resolve_props(node, inherited)
    props = merge_gateway(props, default_gateway)

    if node.attrib.get("Type") == "Connection":
        name = node.attrib.get("Name", "connection")
        write_rdp(name, props, outdir)

    for child in node.findall("Node"):
        walk(child, props, outdir, default_gateway)


def write_readme(outdir):
    lines = [
        "# RDP Conversion Overview",
        "",
        "Connections generated from mRemoteNG export.",
        "",
        "Passwords are not included — Microsoft Remote Desktop will prompt.",
        "",
        "## Connections",
        "",
        "| Name | Host | Username | Gateway |",
        "|------|------|----------|----------|",
    ]

    for c in connections_summary:
        lines.append(
            f"| {c['name']} | {c['host']} | {c['user']} | {c['gateway']} |"
        )

    (outdir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("xml")
    parser.add_argument("outdir")
    parser.add_argument("--default-gateway", help="Fallback RD gateway")

    args = parser.parse_args()

    xml_file = Path(args.xml)
    outdir = Path(args.outdir)
    outdir.mkdir(exist_ok=True)

    tree = ET.parse(xml_file)
    root = tree.getroot()

    for node in root.findall(".//Node"):
        if node.attrib.get("Type") == "Container":
            walk(node, {}, outdir, args.default_gateway)

    write_readme(outdir)

    print("\nREADME generated.")


if __name__ == "__main__":
    main()
