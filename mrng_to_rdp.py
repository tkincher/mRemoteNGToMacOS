#!/usr/bin/env python3

import xml.etree.ElementTree as ET
from pathlib import Path
import argparse
import getpass
import subprocess

FIELDS = [
    "Hostname", "Username", "Domain", "Port",
    "RDGatewayHostname", "RDGatewayUsername",
    "ConnectToConsole"
]

connections_summary = []

interactive_creds = {
    "sys_user": None,
    "sys_pass": None,
    "gw_user": None,
    "gw_pass": None
}


# --------------------------------------------------
# Keychain integration
# --------------------------------------------------

def keychain_store(server, account, password):
    """
    Store or replace an MRD-compatible internet password.
    """

    subprocess.run([
        "security", "delete-internet-password",
        "-s", server,
        "-a", account
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        "security", "add-internet-password",
        "-a", account,
        "-s", server,
        "-r", "rdp ",
        "-w", password
    ], check=True)


# --------------------------------------------------
# Interactive credential prompt
# --------------------------------------------------

def prompt_credentials():
    print("\nInteractive credential + keychain mode\n")

    interactive_creds["gw_user"] = input(
        "Enter gateway domain\\user: "
    ).strip()

    interactive_creds["gw_pass"] = getpass.getpass(
        "Gateway password: "
    )

    interactive_creds["sys_user"] = input(
        "Enter system domain\\user: "
    ).strip()

    interactive_creds["sys_pass"] = getpass.getpass(
        "System password: "
    )

    print("\nCredentials captured — will store in Keychain.\n")


# --------------------------------------------------
# XML inheritance resolution
# --------------------------------------------------

def resolve_props(node, inherited):
    props = inherited.copy()

    for field in FIELDS:
        inherit_flag = node.attrib.get(
            f"Inherit{field}", "false"
        ) == "true"

        if not inherit_flag and field in node.attrib:
            props[field] = node.attrib[field]

    return props


# --------------------------------------------------
# Credential helpers
# --------------------------------------------------

def system_username(props):
    if interactive_creds["sys_user"]:
        return interactive_creds["sys_user"]

    user = props.get("Username", "")
    domain = props.get("Domain", "")

    return f"{domain}\\{user}" if user and domain else user


def gateway_username(props):
    if interactive_creds["gw_user"]:
        return interactive_creds["gw_user"]

    return props.get("RDGatewayUsername", "")


# --------------------------------------------------
# RDP builder
# --------------------------------------------------

def build_rdp_lines(props):
    host = props.get("Hostname", "")
    port = props.get("Port", "3389")

    if host and port != "3389":
        host = f"{host}:{port}"

    user = system_username(props)
    gw_user = gateway_username(props)
    gw_host = props.get("RDGatewayHostname")

    lines = [
        "; Generated from mRemoteNG",
        "; Credentials stored in macOS Keychain",
        f"full address:s:{host}",
        f"username:s:{user}",
        f"administrative session:i:{1 if props.get('ConnectToConsole') == 'true' else 0}",
    ]

    if gw_host:
        lines.append(f"gatewayhostname:s:{gw_host}")
        lines.append("gatewayusagemethod:i:1")

    if gw_user:
        lines.append(f"gatewayusername:s:{gw_user}")

    return lines, host, user, gw_host or "none"


# --------------------------------------------------
# Re-entrant file update
# --------------------------------------------------

def update_or_write(outfile, new_lines):
    if outfile.exists():
        existing = outfile.read_text(
            encoding="utf-8"
        ).splitlines()

        def replace(prefix, value):
            for i, line in enumerate(existing):
                if line.startswith(prefix):
                    existing[i] = value
                    return
            existing.append(value)

        for line in new_lines:
            key = line.split(":", 1)[0] + ":"
            replace(key, line)

        outfile.write_text(
            "\n".join(existing),
            encoding="utf-8"
        )

    else:
        outfile.write_text(
            "\n".join(new_lines),
            encoding="utf-8"
        )


# --------------------------------------------------
# Connection writer
# --------------------------------------------------

def write_connection(name, props, outdir):
    lines, host, user, gw = build_rdp_lines(props)

    outfile = outdir / f"{name}.rdp"
    update_or_write(outfile, lines)

    # Keychain storage
    if interactive_creds["sys_pass"] and host:
        keychain_store(
            host.split(":")[0],
            interactive_creds["sys_user"],
            interactive_creds["sys_pass"]
        )

    if interactive_creds["gw_pass"] and gw != "none":
        keychain_store(
            gw,
            interactive_creds["gw_user"],
            interactive_creds["gw_pass"]
        )

    connections_summary.append({
        "name": name,
        "host": host,
        "user": user or "(prompt)",
        "gateway": gw
    })

    print("Updated:", outfile.name)


# --------------------------------------------------
# Tree walker
# --------------------------------------------------

def walk(node, inherited, outdir):
    props = resolve_props(node, inherited)

    if node.attrib.get("Type") == "Connection":
        name = node.attrib.get("Name", "connection")
        write_connection(name, props, outdir)

    for child in node.findall("Node"):
        walk(child, props, outdir)


# --------------------------------------------------
# README generator
# --------------------------------------------------

def write_readme(outdir):
    lines = [
        "# RDP Conversion Overview",
        "",
        "Credentials stored in macOS Keychain.",
        "",
        "| Name | Host | Username | Gateway |",
        "|------|------|----------|----------|",
    ]

    for c in connections_summary:
        lines.append(
            f"| {c['name']} | {c['host']} | {c['user']} | {c['gateway']} |"
        )

    (outdir / "README.md").write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("xml")
    parser.add_argument("outdir")
    parser.add_argument(
        "-p", "--prompt",
        action="store_true",
        help="interactive credential + keychain mode"
    )

    args = parser.parse_args()

    if args.prompt:
        prompt_credentials()

    xml_file = Path(args.xml)
    outdir = Path(args.outdir)
    outdir.mkdir(exist_ok=True)

    tree = ET.parse(xml_file)
    root = tree.getroot()

    for node in root.findall(".//Node"):
        if node.attrib.get("Type") == "Container":
            walk(node, {}, outdir)

    write_readme(outdir)

    print("\nDone.\n")


if __name__ == "__main__":
    main()
