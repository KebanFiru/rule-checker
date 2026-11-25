#!/usr/bin/env python3
"""Converts a DOCX to PDF with headless LibreOffice so the visual pass (Read tool on PDF pages) can be done for DOCX targets.
Standard library only. Never fails the workflow: if LibreOffice is missing or does not finish in time, it reports a
"visual pass skipped" status and exits 0.

Usage: docx_to_pdf.py FILE.docx [-o OUTDIR] [--timeout 60]
Writes OUTDIR/<stem>.pdf and OUTDIR/visual_status.json ({"status": "converted"|"skipped", "line": "...", ...}).
Works with no network and a read-only root filesystem: HOME and the LibreOffice profile live in a fresh temp directory.
"""
import argparse, json, os, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path


def find_soffice():
    return shutil.which("soffice") or shutil.which("libreoffice")


def soffice_version(exe):
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20,
                           env={**os.environ, "HOME": tempfile.gettempdir()})
        return (r.stdout.strip().splitlines() or ["LibreOffice"])[0]
    except Exception:
        return "LibreOffice"


def convert(docx, outdir, timeout):
    docx, outdir = Path(docx).resolve(), Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    exe = find_soffice()
    if not exe:
        return skipped("LibreOffice (soffice) not found")
    tmp = Path(tempfile.mkdtemp(prefix="lo-run-", dir=os.environ.get("TMPDIR", tempfile.gettempdir())))
    env = {**os.environ, "HOME": str(tmp), "TMPDIR": str(tmp)}
    cmd = [exe, f"-env:UserInstallation=file://{tmp}/profile", "--headless", "--norestore", "--nolockcheck",
           "--convert-to", "pdf", "--outdir", str(outdir), str(docx)]
    target = outdir / (docx.stem + ".pdf")
    if target.exists():
        target.unlink()
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        proc.communicate(timeout=timeout)
        reason = None
    except subprocess.TimeoutExpired:
        reason = f"conversion did not finish within {timeout} s"
    finally:
        try:                                              # soffice spawns soffice.bin: kill the whole process group
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
        version = soffice_version(exe) if reason is None else "LibreOffice"
        shutil.rmtree(tmp, ignore_errors=True)
    if reason:
        return skipped(reason)
    if not target.exists() or target.stat().st_size == 0:     # success is judged by the output, not the exit code
        return skipped("LibreOffice produced no PDF")
    return {"status": "converted", "pdf": str(target), "converter": version,
            "line": f"Visual pass: DOCX→PDF ({version.split(' (')[0]}); read the pages of {target.name} with the Read tool"}


def skipped(reason):
    return {"status": "skipped", "reason": reason, "line": f"⏭️ visual pass skipped ({reason})"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx"); ap.add_argument("-o", "--out", default="docx_pdf"); ap.add_argument("--timeout", type=float, default=60)
    a = ap.parse_args()
    t0 = time.time()
    res = convert(a.docx, a.out, a.timeout) if Path(a.docx).exists() else skipped(f"input not found: {a.docx}")
    res["seconds"] = round(time.time() - t0, 1)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "visual_status.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(res["line"])


if __name__ == "__main__":
    main()
