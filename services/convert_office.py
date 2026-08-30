"""Office (ppt/pptx) -> PDF conversion via LibreOffice headless.

Cross-platform: Windows / Linux / macOS. Falls back gracefully
(find_soffice returns None) when LibreOffice is not installed.
"""
import os
import shutil
import subprocess
import threading

_lock = threading.Lock()

CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0

_WIN_PATHS = (
    ('PROGRAMFILES', 'LibreOffice/program/soffice.exe'),
    ('PROGRAMFILES(X86)', 'LibreOffice/program/soffice.exe'),
    ('LOCALAPPDATA', 'Programs/LibreOffice/program/soffice.exe'),
)


def find_soffice():
    exe = shutil.which('soffice') or shutil.which('libreoffice')
    if exe:
        return exe
    if os.name == 'nt':
        for env, tail in _WIN_PATHS:
            base = os.environ.get(env)
            if not base:
                continue
            cand = os.path.join(base, *tail.split('/'))
            if os.path.exists(cand):
                return cand
    return None


def convert_to_pdf(src_path, out_dir, timeout=240):
    soffice = find_soffice()
    if not soffice:
        return None
    os.makedirs(out_dir, exist_ok=True)
    cmd = [
        soffice, '--headless', '--norestore', '--nocrashreport', '--nologo',
        '--convert-to', 'pdf', '--outdir', out_dir, src_path,
    ]
    with _lock:
        try:
            subprocess.run(
                cmd, capture_output=True, timeout=timeout,
                creationflags=CREATE_NO_WINDOW,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
    name = os.path.splitext(os.path.basename(src_path))[0] + '.pdf'
    out = os.path.join(out_dir, name)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return out
    return None
