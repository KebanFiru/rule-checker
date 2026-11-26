#!/usr/bin/env python3
"""Environment check (standard library only): which libraries/tools are available and therefore which checks can run.

Usage: env_check.py [--json OUT.json] [--md OUT.md]
Prints a summary; the JSON/Markdown go into the report's "Environment" section (`matrix.py coverage --env OUT.json`).
Works in a Docker container, a plain Python sandbox (e.g. a chat environment) or on a host.
"""
import argparse, importlib.metadata as md, json, platform, shutil, subprocess, sys


def dist_version(*names):
    for n in names:
        try:
            return md.version(n)
        except md.PackageNotFoundError:
            continue
    return None


def tool_version(cmd, *args, timeout=20):
    path = shutil.which(cmd)
    if not path:
        return None, None
    try:
        r = subprocess.run([path, *args], capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or r.stderr).strip().splitlines()
        return path, (out[0] if out else "?")
    except Exception as e:
        return path, f"present, version unknown ({type(e).__name__})"


def collect():
    py = platform.python_version()
    libs = {"pypdf": dist_version("pypdf"), "pdfplumber": dist_version("pdfplumber"), "PyYAML": dist_version("PyYAML", "pyyaml")}
    tools = {}
    for label, cmd, args in (("pdftotext", "pdftotext", ("-v",)), ("soffice", "soffice", ("--version",)), ("docker", "docker", ("--version",))):
        path, ver = tool_version(cmd, *args)
        if cmd == "soffice" and not path:
            path, ver = tool_version("libreoffice", "--version")
        tools[label] = {"path": path, "version": ver}
    have = lambda k: bool(libs.get(k))
    pdftotext = bool(tools["pdftotext"]["path"]); soffice = bool(tools["soffice"]["path"])
    caps = {
        "pdf_text": pdftotext or have("pypdf"),
        "pdf_second_opinion": pdftotext and have("pypdf"),
        "docx_text_comments_tracked_changes": True,
        "process_model": have("PyYAML"),
        "pdf_tables_pdfplumber": have("pdfplumber"),
        "docx_visual_pass_libreoffice": soffice,
    }
    unavailable = []
    if not caps["pdf_text"]: unavailable.append("PDF text extraction (neither pdftotext nor pypdf found): PDF targets/references cannot be processed by scripts; read the PDFs with the Read tool")
    elif not caps["pdf_second_opinion"]: unavailable.append("independent PDF second opinion (needs both pdftotext and pypdf): extraction disagreements will not be detected automatically")
    if not have("pypdf"): unavailable.append("image and drawing detection for the visual inventory (pypdf missing): every page must be read for the visual pass")
    if not caps["process_model"]: unavailable.append("process model / invariants / impact analysis (PyYAML missing)")
    if not caps["pdf_tables_pdfplumber"]: unavailable.append("cell-level PDF table extraction (pdfplumber missing): tables come from the -layout text with ' | ' separated cells")
    if not caps["docx_visual_pass_libreoffice"]: unavailable.append("DOCX visual pass (LibreOffice missing): DOCX targets cannot be rendered; ask for a PDF export or skip the visual pass")
    return {"python": py, "platform": platform.platform(), "libraries": libs, "tools": tools, "capabilities": caps, "unavailable_checks": unavailable}


def to_md(e):
    L = ["## Environment", f"- Python {e['python']} ({e['platform']})"]
    for k, v in e["libraries"].items():
        L.append(f"- {k}: {v or 'not available'}")
    for k, v in e["tools"].items():
        if k == "docker": continue
        L.append(f"- {k}: {v['version'] if v['path'] else 'not available'}")
    L.append("- Checks that cannot be done in this environment:" + (" none" if not e["unavailable_checks"] else ""))
    L += [f"  - {u}" for u in e["unavailable_checks"]]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--json"); ap.add_argument("--md")
    a = ap.parse_args(); e = collect(); e["md"] = to_md(e)
    print(e["md"], end="")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh: json.dump(e, fh, ensure_ascii=False, indent=1)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh: fh.write(e["md"])


if __name__ == "__main__":
    main()
