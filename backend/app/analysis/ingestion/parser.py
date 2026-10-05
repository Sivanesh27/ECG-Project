"""Flexible signal ingestion.

Understands (verified against the supplied sample dataset):
  <subject>/<YYYYMMDD_HHMMSS>/ecg/<n>.csv   columns: sample_index, ecg_value, is_pulse  (NO timestamps)
  <session>/index.csv                        columns: sno, chunk_id, chunk_start_time (YYYYmmddTHHMMSSffffff)
  <session>/hr.csv | corrected_hr_avg.csv | hr_quality.csv | acc_rms_avg.csv   columns: timestamp, data_item, value
  <session>/summary.csv                      one-row wide table (avg_hr, max_hr, training_load, zone_N_duration [ms], ...)
Also understands simple CSV/XLSX: (timestamp|time, ecg|rr|hr).

The ECG sampling rate is never assumed: it is estimated from chunk length / chunk spacing
(index.csv) or from timestamps, then snapped to a standard rate only if within 2 %.
"""
from __future__ import annotations

import io
import os
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

MAX_UNCOMPRESSED = 2 * 1024**3
MAX_FILES = 20000
MAX_RATIO = 200
SESSION_RE = re.compile(r"^\d{8}_\d{6}$")


class IngestError(ValueError):
    pass


@dataclass
class ParsedSession:
    key: str
    name: str
    subject_hint: Optional[str] = None
    start_time: Optional[pd.Timestamp] = None
    end_time: Optional[pd.Timestamp] = None
    ecg: Optional[pd.DataFrame] = None          # t (s from ecg_start), v, pulse, segment
    ecg_start: Optional[pd.Timestamp] = None
    ecg_fs: Optional[float] = None
    fs_source: str = ""
    hr: Optional[pd.DataFrame] = None           # t_abs, value
    corrected_hr: Optional[pd.DataFrame] = None
    hr_quality: Optional[pd.DataFrame] = None
    acc: Optional[pd.DataFrame] = None
    rr_ms: Optional[pd.DataFrame] = None        # t_s, rr_ms (RR-only uploads)
    summary: Optional[dict] = None
    quality: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    def availability(self) -> dict:
        return {
            "ecg": bool(self.ecg is not None and len(self.ecg) > 0),
            "hr": bool((self.hr is not None and len(self.hr) > 0) or self.corrected_hr is not None or self.rr_ms is not None),
            "corrected_hr": self.corrected_hr is not None,
            "hr_quality": self.hr_quality is not None,
            "movement": bool(self.acc is not None and len(self.acc) > 0),
            "summary": self.summary is not None,
        }


# ------------------------------------------------------------------ safety
def safe_zip_members(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = zf.infolist()
    if len(infos) > MAX_FILES:
        raise IngestError("ZIP contains too many files.")
    total, out = 0, []
    for i in infos:
        if i.is_dir():
            continue
        name = i.filename.replace("\\", "/")
        norm = posixpath.normpath(name)
        if norm.startswith("/") or norm.startswith("..") or "/../" in "/" + norm or re.match(r"^[A-Za-z]:", norm):
            raise IngestError(f"Unsafe path in ZIP rejected: {name!r}")
        if "__MACOSX" in norm or posixpath.basename(norm).startswith("."):
            continue
        total += i.file_size
        if i.compress_size and i.file_size / max(i.compress_size, 1) > MAX_RATIO and i.file_size > 50 * 1024**2:
            raise IngestError("Suspicious compression ratio (possible ZIP bomb).")
        out.append(i)
    if total > MAX_UNCOMPRESSED:
        raise IngestError("ZIP uncompressed size exceeds the limit.")
    return out


# ------------------------------------------------------------------ helpers
def _read_csv(data: bytes) -> pd.DataFrame:
    if isinstance(data, str):
        data = data.encode()
    try:
        return pd.read_csv(io.BytesIO(data), skipinitialspace=True, on_bad_lines="skip")
    except Exception as e:  # noqa: BLE001
        raise IngestError(f"Malformed CSV: {e}")


def _parse_ts(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        m = float(np.nanmedian(np.abs(s.astype(float)))) if len(s) else 0.0
        unit = "ns" if m > 1e17 else "us" if m > 1e14 else "ms" if m > 1e11 else "s"
        return pd.to_datetime(s, unit=unit, utc=True, errors="coerce")
    return pd.to_datetime(s, utc=True, errors="coerce", format="mixed")


def _long_series(data: bytes) -> pd.DataFrame:
    df = _read_csv(data)
    cols = {c.lower().strip(): c for c in df.columns}
    tcol = cols.get("timestamp") or cols.get("time")
    vcol = cols.get("value")
    if tcol is None or vcol is None:
        raise IngestError("No valid timestamp/value columns could be identified.")
    out = pd.DataFrame({"t_abs": _parse_ts(df[tcol]), "value": pd.to_numeric(df[vcol], errors="coerce")})
    return out.dropna(subset=["t_abs"]).sort_values("t_abs").reset_index(drop=True)


def _chunk_no(name: str) -> int:
    m = re.match(r"^(\d+)\.csv$", name)
    return int(m.group(1)) if m else -1


def estimate_fs(lengths: list[int], starts: list[pd.Timestamp]) -> Optional[float]:
    """Median of (chunk length / spacing to next chunk), using only full-size chunks (== largest chunk) so a short
    trailing chunk followed by a nearby one cannot bias the estimate."""
    est = []
    full = max(lengths) if lengths else 0
    for i in range(len(starts) - 1):
        dt = (starts[i + 1] - starts[i]).total_seconds()
        if 0 < dt < 120 and lengths[i] == full and lengths[i] >= 200:
            est.append(lengths[i] / dt)
    if not est:
        return None
    # chunk gaps (< 120 s) only ever LOWER the estimate, so take the most common value (ties -> the higher one)
    r = np.round(np.array(est) / np.median(est), 2)
    vals, counts = np.unique(r, return_counts=True)
    best = vals[np.flatnonzero(counts == counts.max())[-1]]
    return float(np.median(np.array(est)[r == best]))


def snap_fs(fs: float) -> float:
    common = [125, 128, 200, 250, 256, 360, 500, 512, 1000, 1024]
    best = min(common, key=lambda c: abs(c - fs))
    return float(best) if abs(best - fs) / best < 0.02 else round(fs, 2)


# ------------------------------------------------------------------ chunked (device export) session
def build_chunked_session(files: dict[str, bytes], prefix: str, fs_override: Optional[float] = None) -> ParsedSession:
    s = ParsedSession(key=prefix, name=posixpath.basename(prefix.rstrip("/")) or prefix)
    if SESSION_RE.match(s.name):
        s.start_time = pd.to_datetime(s.name, format="%Y%m%d_%H%M%S", utc=True)
    for fname, attr in (("hr.csv", "hr"), ("corrected_hr_avg.csv", "corrected_hr"),
                        ("hr_quality.csv", "hr_quality"), ("acc_rms_avg.csv", "acc")):
        if fname in files:
            try:
                setattr(s, attr, _long_series(files[fname]))
            except IngestError as e:
                s.warnings.append(f"{fname}: {e}")
    if "summary.csv" in files:
        try:
            df = _read_csv(files["summary.csv"])
            if len(df):
                row = df.iloc[0].to_dict()
                s.summary = {str(k).strip(): (None if pd.isna(v) else (v.item() if hasattr(v, "item") else v))
                             for k, v in row.items()}
                if s.summary.get("session_start_time"):
                    s.start_time = pd.to_datetime(s.summary["session_start_time"], utc=True)
        except IngestError as e:
            s.warnings.append(f"summary.csv: {e}")
    for d in (s.hr, s.corrected_hr, s.acc):
        if d is not None and len(d):
            s.start_time = s.start_time or d.t_abs.iloc[0]
            last = d.t_abs.iloc[-1]
            s.end_time = last if s.end_time is None else max(s.end_time, last)

    ecg_files = sorted([f for f in files if f.startswith("ecg/") and _chunk_no(f[4:]) >= 0],
                       key=lambda f: _chunk_no(f[4:]))
    if not ecg_files:
        s.warnings.append("No ECG chunks found for this session; ECG-derived HRV is unavailable.")
        return s

    starts = None
    if "index.csv" in files:
        idx = _read_csv(files["index.csv"])
        cols = {c.lower(): c for c in idx.columns}
        if "chunk_start_time" in cols:
            if "sno" in cols:
                idx = idx.sort_values(cols["sno"])
            ts = pd.to_datetime(idx[cols["chunk_start_time"]].astype(str), format="%Y%m%dT%H%M%S%f",
                                utc=True, errors="coerce")
            starts = ts.tolist()
    else:
        s.warnings.append("No index.csv: ECG chunk start times unknown.")

    frames, lens, bad_rows, dup_samples = [], [], 0, 0
    for f in ecg_files:
        df = _read_csv(files[f])
        cols = {c.lower(): c for c in df.columns}
        vcol = cols.get("ecg_value") or cols.get("ecg") or cols.get("value")
        if vcol is None:
            s.warnings.append(f"{f}: no ECG value column identified; skipped.")
            continue
        v = pd.to_numeric(df[vcol], errors="coerce")
        bad_rows += int(v.isna().sum())
        d = pd.DataFrame({"v": v})
        d["pulse"] = (pd.to_numeric(df[cols["is_pulse"]], errors="coerce").fillna(0).astype(int)
                      if "is_pulse" in cols else 0)
        if "sample_index" in cols:
            dup_samples += int(pd.to_numeric(df[cols["sample_index"]], errors="coerce").duplicated().sum())
        d["chunk"] = _chunk_no(f[4:])
        frames.append(d)
        lens.append(len(d))
    if not frames:
        s.warnings.append("ECG files were found but no valid ECG column could be identified.")
        return s

    st = None
    if starts is not None and len(starts) >= len(frames) and not any(pd.isna(x) for x in starts[:len(frames)]):
        st = starts[:len(frames)]
    elif starts is not None:
        s.warnings.append("Some chunk start times in index.csv are invalid.")
    fs = None
    fs_src = "estimated from chunk length / chunk spacing in index.csv"
    if st is not None:
        fs = estimate_fs(lens, st)
    if fs is None and fs_override and st is not None:
        fs, fs_src = float(fs_override), "user-configured sampling rate (could not be estimated from this session)"
        s.warnings.append(f"Sampling rate set manually to {fs_override:g} Hz for this session.")
    if st is None or fs is None:
        s.warnings.append("UNKNOWN SAMPLING RATE: could not be estimated from this session (need >= 2 consecutive "
                          "full ECG chunks with index.csv). Configure the sampling rate in Settings.")
        s.quality["unknown_fs_samples"] = int(sum(lens))
        s.quality["samples"] = int(sum(lens))
        return s
    fs = float(fs) if fs_src.startswith("user") else snap_fs(fs)
    s.ecg_fs, s.fs_source = fs, fs_src
    t_ref = st[0]
    parts, seg, gaps = [], 0, []
    for i, d in enumerate(frames):
        if i > 0:
            expected = st[i - 1] + pd.Timedelta(seconds=lens[i - 1] / fs)
            gap = (st[i] - expected).total_seconds()
            if abs(gap) > 0.5:
                seg += 1
                gaps.append({"after_chunk": int(frames[i - 1].chunk.iloc[0]), "gap_s": round(gap, 3)})
        d = d.copy()
        d["t"] = (st[i] - t_ref).total_seconds() + np.arange(len(d)) / fs
        d["segment"] = seg
        parts.append(d)
    ecg = pd.concat(parts, ignore_index=True).dropna(subset=["v"]).sort_values("t").reset_index(drop=True)
    s.ecg, s.ecg_start = ecg, t_ref
    s.quality.update({"samples": int(len(ecg)), "missing_samples": int(bad_rows), "duplicate_samples": int(dup_samples),
                      "malformed_rows": int(bad_rows), "n_chunks": len(frames), "n_segments": seg + 1, "gaps": gaps})
    if s.start_time is None:
        s.start_time = t_ref
    ecg_end = t_ref + pd.Timedelta(seconds=float(ecg.t.iloc[-1]))
    s.end_time = ecg_end if s.end_time is None else max(s.end_time, ecg_end)
    return s


# ------------------------------------------------------------------ simple csv
def build_simple_csv(name: str, data: bytes) -> ParsedSession:
    df = _read_csv(data)
    cols = {c.lower().strip(): c for c in df.columns}
    tcol = cols.get("timestamp") or cols.get("time") or cols.get("t")
    s = ParsedSession(key=name, name=os.path.splitext(name)[0])
    kind = next((k for k in ("ecg", "ecg_value", "rr", "rr_ms", "hr", "bpm", "heart_rate") if k in cols), None)
    if kind is None:
        raise IngestError("Unsupported CSV columns. Expected 'timestamp'/'time' plus one of: ecg, rr, hr.")
    vals = pd.to_numeric(df[cols[kind]], errors="coerce")
    abs_t = None
    if tcol is not None:
        raw = df[tcol]
        if pd.api.types.is_numeric_dtype(raw) and float(np.nanmedian(np.abs(raw))) < 1e8:
            tsec = pd.to_numeric(raw, errors="coerce").astype(float)           # relative time
            if kind.startswith("ecg") and np.nanmedian(np.diff(tsec.dropna().values[:1000]) if len(tsec) > 2 else [1]) > 1:
                tsec = tsec / 1000.0                                           # looks like milliseconds
        else:
            abs_t = _parse_ts(raw)
            tsec = (abs_t - abs_t.dropna().iloc[0]).dt.total_seconds() if abs_t.notna().any() else abs_t.astype(float)
    elif kind.startswith("rr"):
        tsec = pd.Series(np.cumsum(vals.fillna(0).values) / (1000.0 if np.nanmedian(vals) > 10 else 1.0))
    else:
        raise IngestError("Data was detected, but no valid timestamp column could be identified.")
    ok = vals.notna() & tsec.notna()
    if (~ok).any():
        s.warnings.append(f"Dropped {int((~ok).sum())} rows with missing/invalid values.")
    d = pd.DataFrame({"t": tsec[ok].astype(float).values, "v": vals[ok].values}).sort_values("t")
    dup = int(d.t.duplicated().sum())
    if dup:
        s.warnings.append(f"{dup} duplicate timestamps removed.")
        d = d.drop_duplicates("t")
    d = d.reset_index(drop=True)
    first = abs_t.dropna().iloc[0] if abs_t is not None and abs_t.notna().any() else pd.Timestamp.now(tz="UTC")
    s.start_time = first
    s.quality.update({"duplicate_samples": dup, "malformed_rows": int((~ok).sum())})
    if kind.startswith("ecg"):
        dt = np.diff(d.t.values)
        if len(dt) < 100:
            raise IngestError("Too few ECG samples.")
        fs = 1.0 / float(np.median(dt))
        s.ecg_fs, s.fs_source = snap_fs(fs), "estimated from timestamps"
        gap_idx = np.where(dt > 5.0 / s.ecg_fs)[0]
        seg = np.zeros(len(d), dtype=int)
        for g in gap_idx:
            seg[g + 1:] += 1
        d["segment"], d["pulse"] = seg, 0
        s.ecg, s.ecg_start = d, first
        s.end_time = first + pd.Timedelta(seconds=float(d.t.iloc[-1]))
        s.quality.update({"samples": len(d), "n_segments": int(seg.max()) + 1,
                          "gaps": [{"after_t": round(float(d.t.iloc[g]), 3), "gap_s": round(float(dt[g]), 3)} for g in gap_idx]})
    elif kind.startswith("rr"):
        rr = d.v.values.astype(float)
        if np.nanmedian(rr) < 10:
            rr = rr * 1000.0
        t = np.cumsum(rr) / 1000.0 if tcol is None else d.t.values
        s.rr_ms = pd.DataFrame({"t_s": t, "rr_ms": rr})
        s.end_time = first + pd.Timedelta(seconds=float(t[-1])) if len(t) else first
        s.warnings.append("RR-only upload: ECG processing skipped; HRV computed from the supplied RR intervals.")
    else:
        t_abs = first + pd.to_timedelta(d.t.values, unit="s")
        s.hr = pd.DataFrame({"t_abs": t_abs, "value": d.v.values})
        s.end_time = t_abs[-1] if len(t_abs) else first
        s.warnings.append("HR-only upload: ECG/RR-based HRV is unavailable.")
    return s


# ------------------------------------------------------------------ entry points
def detect_sessions_zip(raw: bytes, only: Optional[set] = None, fs_override: Optional[float] = None) -> list[ParsedSession]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise IngestError("The file is not a valid ZIP archive (it may be corrupted).")
    members = safe_zip_members(zf)
    markers = {"hr.csv", "summary.csv", "corrected_hr_avg.csv", "acc_rms_avg.csv", "hr_quality.csv", "index.csv"}
    groups: dict[str, dict[str, zipfile.ZipInfo]] = {}
    for m in members:
        p = posixpath.normpath(m.filename.replace("\\", "/"))
        d, b = posixpath.dirname(p), posixpath.basename(p)
        if posixpath.basename(d) == "ecg" and _chunk_no(b) >= 0:
            groups.setdefault(posixpath.dirname(d), {})["ecg/" + b] = m
        elif b in markers:
            groups.setdefault(d, {})[b] = m
    sessions: list[ParsedSession] = []
    for prefix, fm in sorted(groups.items()):
        if only is not None and prefix not in only:
            continue
        files = {k: zf.read(v) for k, v in fm.items()}
        sess = build_chunked_session(files, prefix, fs_override)
        parts = prefix.split("/")
        if len(parts) >= 2:
            sess.subject_hint = parts[-2]
        sessions.append(sess)
    if not sessions:
        for m in members:
            if m.filename.lower().endswith(".csv"):
                try:
                    sessions.append(build_simple_csv(posixpath.basename(m.filename), zf.read(m)))
                except IngestError:
                    continue
    if not sessions:
        raise IngestError("No sessions could be detected in this ZIP (no ecg/ chunks, hr.csv or recognisable CSV).")
    sessions.sort(key=lambda x: (x.start_time is None, x.start_time))
    return sessions


def detect_sessions(filename: str, raw: bytes, only: Optional[set] = None, fs_override: Optional[float] = None) -> list[ParsedSession]:
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".zip":
        return detect_sessions_zip(raw, only, fs_override)
    if ext == ".csv":
        return [build_simple_csv(os.path.basename(filename), raw)]
    if ext == ".xlsx":
        try:
            df = pd.read_excel(io.BytesIO(raw))
        except Exception as e:  # noqa: BLE001
            raise IngestError(f"Could not read XLSX: {e}")
        return [build_simple_csv(os.path.basename(filename), df.to_csv(index=False).encode())]
    raise IngestError("UNSUPPORTED FILE FORMAT: use .zip, .csv or .xlsx")
