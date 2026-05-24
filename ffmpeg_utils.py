# -*- coding: utf-8 -*-
"""
FFmpeg helper utilities for finding, downloading, installing, and running FFmpeg/FFprobe commands.
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile
import traceback
import uuid
from typing import Optional

from aqt import mw
from aqt.qt import QWidget, QProgressDialog, Qt, QMessageBox
from aqt.utils import tooltip, showWarning

from ._tr import tr
from .constants import FFMPEG_DOWNLOAD_URL, CHUNK_SIZE, WAVEFORM_SAMPLE_RATE

# Add-on paths
ADDON_ROOT = os.path.dirname(__file__)
BUNDLED_FFMPEG_DIR = os.path.join(ADDON_ROOT, "bin")


class FFmpegNotFoundError(RuntimeError):
    pass


def _config() -> dict:
    # Use the parent addon folder name for config resolution
    addon_name = os.path.basename(ADDON_ROOT)
    return mw.addonManager.getConfig(addon_name) or {}


def _subprocess_kwargs() -> dict:
    kwargs = {"capture_output": True, "text": True}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return kwargs


def _ffmpeg_binary() -> str:
    cfg_path = _config().get("ffmpeg_path") or ""
    if cfg_path and os.path.isfile(cfg_path):
        return cfg_path

    # Bundled inside add-on (after user auto-installed)
    exe_name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    bundled = os.path.join(BUNDLED_FFMPEG_DIR, exe_name)
    if os.path.isfile(bundled):
        return bundled

    # In PATH
    for name in ("ffmpeg", "ffmpeg.exe"):
        found = shutil.which(name)
        if found:
            return found
    raise FFmpegNotFoundError(tr("ffmpeg_not_found"))


def _is_ffmpeg_available() -> bool:
    try:
        _ffmpeg_binary()
        return True
    except FFmpegNotFoundError:
        return False


def _download_with_progress(url: str, dest: str, parent: QWidget) -> bool:
    """Download *url* to *dest* with a QProgressDialog. Returns True on success."""
    progress = QProgressDialog(
        tr("ffmpeg_downloading"), tr("ffmpeg_cancel"), 0, 100, parent,
    )
    progress.setWindowTitle(tr("ffmpeg_install_title"))
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setValue(0)

    cancelled = {"flag": False}
    progress.canceled.connect(lambda: cancelled.__setitem__("flag", True))

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "anki-audio-cutter/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as out:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            while True:
                if cancelled["flag"]:
                    return False
                chunk = resp.read(CHUNK_SIZE)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                dl_mb = downloaded // (1024 * 1024)
                if total:
                    pct = int(downloaded * 100 / total)
                    progress.setValue(pct)
                    progress.setLabelText(
                        tr("ffmpeg_download_progress",
                           downloaded=dl_mb,
                           total=total // (1024 * 1024))
                    )
                else:
                    progress.setLabelText(
                        tr("ffmpeg_download_progress_unknown", downloaded=dl_mb)
                    )
                mw.app.processEvents()
        progress.setValue(100)
        return True
    finally:
        progress.close()


def install_ffmpeg_windows(parent: QWidget) -> bool:
    """Download ffmpeg-release-essentials.zip and extract into bin/."""
    if not sys.platform.startswith("win"):
        showWarning(tr("ffmpeg_install_win_only"), parent=parent)
        return False

    answer = QMessageBox.question(
        parent,
        tr("ffmpeg_install_title"),
        tr("ffmpeg_install_confirm"),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return False

    os.makedirs(BUNDLED_FFMPEG_DIR, exist_ok=True)
    zip_path = os.path.join(BUNDLED_FFMPEG_DIR, "ffmpeg.zip")

    try:
        if not _download_with_progress(FFMPEG_DOWNLOAD_URL, zip_path, parent):
            try:
                os.remove(zip_path)
            except OSError:
                pass
            return False
    except Exception as exc:
        traceback.print_exc()
        showWarning(tr("ffmpeg_download_error", error=exc), parent=parent)
        return False

    # Extract — only grab ffmpeg.exe and ffprobe.exe from the bin/ dir
    progress = QProgressDialog(tr("ffmpeg_extracting"), None, 0, 0, parent)
    progress.setWindowTitle(tr("ffmpeg_install_title"))
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setCancelButton(None)
    progress.show()
    mw.app.processEvents()

    try:
        with zipfile.ZipFile(zip_path) as zf:
            wanted = ("ffmpeg.exe", "ffprobe.exe")
            for member in zf.namelist():
                base = os.path.basename(member).lower()
                if base in wanted and "/bin/" in member.replace("\\", "/").lower():
                    target = os.path.join(BUNDLED_FFMPEG_DIR, base)
                    with zf.open(member) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        os.remove(zip_path)
    except Exception as exc:
        traceback.print_exc()
        progress.close()
        showWarning(tr("ffmpeg_extract_error", error=exc), parent=parent)
        return False
    finally:
        progress.close()

    # Verify
    final_exe = os.path.join(BUNDLED_FFMPEG_DIR, "ffmpeg.exe")
    if not os.path.isfile(final_exe):
        showWarning(tr("ffmpeg_extract_not_found"), parent=parent)
        return False

    tooltip(tr("ffmpeg_install_success"), parent=parent, period=2000)
    return True


def _probe_duration(src_path: str) -> float:
    """Get duration (seconds) via ffprobe (if available) or ffmpeg -i."""
    ffmpeg = _ffmpeg_binary()
    ffprobe = ffmpeg
    base = os.path.basename(ffmpeg).lower()
    if "ffmpeg" in base:
        candidate = os.path.join(
            os.path.dirname(ffmpeg), base.replace("ffmpeg", "ffprobe")
        )
        if os.path.isfile(candidate):
            ffprobe = candidate

    if ffprobe != ffmpeg:
        cmd = [
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            src_path,
        ]
        try:
            res = subprocess.run(cmd, **_subprocess_kwargs())
            return float((res.stdout or "").strip())
        except Exception:
            pass

    # Fallback: parse from ffmpeg -i stderr.
    try:
        res = subprocess.run([ffmpeg, "-i", src_path], **_subprocess_kwargs())
        m = re.search(r"Duration:\s+(\d+):(\d+):([\d.]+)", res.stderr or "")
        if m:
            h, mm, ss = int(m.group(1)), int(m.group(2)), float(m.group(3))
            return h * 3600 + mm * 60 + ss
    except Exception:
        traceback.print_exc()
    return 0.0


def _cut_audio_to_media(
    src_path: str, start: float, end: float, media_dir: str
) -> str:
    """Cut segment [start, end] from src_path, save to media_dir, return filename."""
    if end <= start:
        raise ValueError("end must be greater than start")

    cfg = _config()
    fmt = (cfg.get("output_format") or "mp3").lower()
    bitrate = cfg.get("output_bitrate") or "128k"
    ffmpeg = _ffmpeg_binary()

    out_name = f"audiocut_{uuid.uuid4().hex[:12]}.{fmt}"
    out_path = os.path.join(media_dir, out_name)
    duration = end - start

    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}", "-i", src_path,
        "-t", f"{duration:.3f}",
    ]
    if fmt == "mp3":
        cmd += ["-c:a", "libmp3lame", "-b:a", bitrate]
    elif fmt == "ogg":
        cmd += ["-c:a", "libvorbis", "-b:a", bitrate]
    elif fmt == "wav":
        cmd += ["-c:a", "pcm_s16le"]
    elif fmt in ("m4a", "aac"):
        cmd += ["-c:a", "aac", "-b:a", bitrate]
    else:
        cmd += ["-c:a", "copy"]
    cmd.append(out_path)

    res = subprocess.run(cmd, **_subprocess_kwargs())
    if res.returncode != 0:
        raise RuntimeError(
            tr("ffmpeg_cut_error", error=(res.stderr or "").strip())
        )
    if not os.path.exists(out_path):
        raise RuntimeError("ffmpeg produced no output file.")
    return out_name


def extract_waveform(src_path: str) -> list[float]:
    """Extract audio amplitude profile using FFmpeg, resampled and normalized."""
    try:
        ffmpeg = _ffmpeg_binary()
    except Exception:
        return []

    # Downmix to mono, resample to WAVEFORM_SAMPLE_RATE Hz, format to raw float32 LE
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", src_path, "-ac", "1",
        "-filter:a", f"aresample={WAVEFORM_SAMPLE_RATE}",
        "-f", "f32le", "-"
    ]

    try:
        # Prevent window popup on Windows
        startupinfo = None
        if sys.platform.startswith("win"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0 # SW_HIDE

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print("FFmpeg extract_waveform error:", stderr.decode("utf-8", errors="ignore"))
            return []

        num_floats = len(stdout) // 4
        if num_floats == 0:
            return []

        # Unpack raw floats (4 bytes each)
        raw_floats = struct.unpack(f"{num_floats}f", stdout[:num_floats * 4])

        # Take absolute amplitude profile
        abs_floats = [abs(f) for f in raw_floats]

        # Normalize to [0.0, 1.0]
        max_val = max(abs_floats) if abs_floats else 0.0
        if max_val > 0.0:
            normalized = [f / max_val for f in abs_floats]
        else:
            normalized = abs_floats

        return normalized
    except Exception:
        traceback.print_exc()
        return []


def get_ffmpeg_version() -> str:
    """Return the installed FFmpeg version string (e.g. '6.1.1'), or '' on failure."""
    try:
        ffmpeg = _ffmpeg_binary()
        res = subprocess.run([ffmpeg, "-version"], **_subprocess_kwargs())
        m = re.search(r'ffmpeg version (\S+)', res.stdout or "")
        if m:
            # Strip any trailing non-numeric suffix (e.g. '-essentials_build-...')
            raw = m.group(1)
            parts = raw.split("-")
            return parts[0] if parts else raw
        return ""
    except Exception:
        traceback.print_exc()
        return ""


def check_ffmpeg_latest_version() -> str:
    """Fetch the latest FFmpeg release version from gyan.dev. Returns '' on failure."""
    try:
        # Fetch the direct version text file first (preferred)
        req = urllib.request.Request(
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.ver",
            headers={"User-Agent": "anki-audio-cutter/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ver = resp.read().decode("utf-8", errors="ignore").strip()
            if ver and re.match(r'^[0-9.]+$', ver):
                return ver
    except Exception:
        traceback.print_exc()

    # Fallback to scraping HTML if the direct file fails
    try:
        req = urllib.request.Request(
            "https://www.gyan.dev/ffmpeg/builds/",
            headers={"User-Agent": "anki-audio-cutter/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            page = resp.read().decode("utf-8", errors="ignore")
        m = re.search(r'id="release-version"\s*>\s*([\d.]+)', page)
        if m:
            return m.group(1)
        m = re.search(r'release:\s*([\d.]+)', page)
        if m:
            return m.group(1)
    except Exception:
        traceback.print_exc()
    return ""


def update_ffmpeg_windows(parent: QWidget) -> bool:
    """Check if FFmpeg is outdated and re-install if a newer version is available.

    Returns True if an update was performed, False otherwise.
    """
    current = get_ffmpeg_version()
    latest = check_ffmpeg_latest_version()
    if not latest:
        return False
    if current == latest:
        return False
    return install_ffmpeg_windows(parent)

