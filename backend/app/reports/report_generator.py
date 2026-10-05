"""Scientific PDF report (ReportLab + Matplotlib). Input is the plain dict produced by `assemble_context`."""
from __future__ import annotations
import io
from datetime import datetime, timezone
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ORANGE, BLACK, GRAY = "#FF6A00", "#0B0B0B", "#A0A0A0"
NA = "N/A"
ZONE_COLORS = ["#555555", "#FFB380", "#FF9A4D", "#FF7A18", "#E85D00", "#B33F00"]


def fmt(v, nd=1, unit=""):
    if v is None:
        return NA
    return f"{v:,.{nd}f}{(' ' + unit) if unit else ''}"


def _fig_png(fig) -> io.BytesIO:
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    b.seek(0)
    return b


def _style(ax, xl, yl):
    ax.set_xlabel(xl, fontsize=8); ax.set_ylabel(yl, fontsize=8)
    ax.tick_params(labelsize=7); ax.grid(alpha=0.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def chart_hr(ctx):
    h = ctx.get("hr_series")
    if not h or not h.get("t"):
        return None
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    t = np.array(h["t"]) / 60.0
    ax.plot(t, h["v"], color=ORANGE, lw=1.0)
    z = (ctx.get("training_results") or {}).get("zones")
    if z and z.get("zones"):
        for zz in z["zones"][1:]:
            ax.axhspan(zz["lo_bpm"], zz["hi_bpm"], color=ZONE_COLORS[zz["zone"] % 6], alpha=0.10)
    v = np.array(h["v"], float)
    ax.set_ylim(max(0, np.nanmin(v) - 8), np.nanmax(v) + 8)      # zone shading must not rescale the axis
    _style(ax, "Time (min)", "HR (bpm)")
    return _fig_png(fig)


def chart_zones(ctx):
    z = (ctx.get("training_results") or {}).get("zones")
    if not z or not z.get("zones"):
        return None
    fig, ax = plt.subplots(figsize=(7.2, 1.6))
    left = 0
    for zz in z["zones"]:
        ax.barh([0], [zz["percent"]], left=left, color=ZONE_COLORS[zz["zone"] % 6], label=zz["label"])
        left += zz["percent"]
    ax.set_xlim(0, 100); ax.set_yticks([]); ax.legend(fontsize=6, ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.35), frameon=False)
    _style(ax, "% of session", "")
    return _fig_png(fig)


def chart_rr(ctx):
    rr = ctx.get("rr")
    if not rr or not rr.get("t_s"):
        return None
    t, v, art = np.array(rr["t_s"]), np.array(rr["rr_ms"], float), np.array(rr["artifact"], bool)
    fig, ax = plt.subplots(figsize=(7.2, 2.2))
    ax.plot(t[~art], v[~art], ".", ms=2.5, color=ORANGE, label="normal")
    if art.any():
        ax.plot(t[art], v[art], "x", ms=4, color="black", label="artifact")
    ax.legend(fontsize=7, frameon=False)
    off = int(((v < 200) | (v > 2200)).sum())
    ax.set_ylim(200, 2200)                                   # artifact outliers must not flatten the real tachogram
    _style(ax, "Time from ECG start (s)" + (f"  ({off} off-scale artifact points not shown)" if off else ""), "RR (ms)")
    return _fig_png(fig)


def chart_psd(ctx):
    p = ((ctx.get("hrv") or {}).get("frequency") or {}).get("psd")
    if not p:
        return None
    f, v = np.array(p["f"]), np.array(p["p"])
    fig, ax = plt.subplots(figsize=(7.2, 2.2))
    ax.plot(f, v, color=ORANGE, lw=1.2)
    for (lo, hi), c, n in (((0.0033, 0.04), "#888", "VLF"), ((0.04, 0.15), ORANGE, "LF"), ((0.15, 0.4), "#222", "HF")):
        ax.axvspan(lo, hi, color=c, alpha=0.12); ax.text((lo + hi) / 2, ax.get_ylim()[1] * 0.9, n, ha="center", fontsize=7)
    ax.set_xlim(0, 0.5)
    _style(ax, "Frequency (Hz)", "PSD (ms²/Hz)")
    return _fig_png(fig)


def chart_mov(ctx):
    h = ctx.get("hr_series")
    if not h or not h.get("acc_t"):
        return None
    fig, ax = plt.subplots(figsize=(7.2, 2.0))
    ax.plot(np.array(h["acc_t"]) / 60.0, h["acc_v"], color="#666", lw=0.9)
    _style(ax, "Time (min)", "Acc. RMS (source units)")
    return _fig_png(fig)


def build_pdf(ctx: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="ECG / HRV Analysis Report", author="ECG/HRV Analytics")
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Title"], textColor=colors.HexColor(BLACK), fontSize=20, alignment=0)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=colors.HexColor(ORANGE), fontSize=12, spaceBefore=10, spaceAfter=4)
    B = ParagraphStyle("B", parent=ss["BodyText"], fontSize=8.5, leading=11)
    S = ParagraphStyle("S", parent=B, textColor=colors.HexColor("#666666"), fontSize=7.5)
    el = []

    def table(rows, widths=None, head=True):
        t = Table(rows, colWidths=widths, hAlign="LEFT")
        sty = [("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ROWBACKGROUNDS", (0, 1 if head else 0), (-1, -1), [colors.white, colors.HexColor("#F6F6F6")])]
        if head:
            sty += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLACK)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
        t.setStyle(TableStyle(sty))
        return t

    def img(b, w=176 * mm):
        if b is None:
            return Paragraph("Not available for this session.", S)
        im = Image(b); r = im.imageHeight / im.imageWidth; im.drawWidth = w; im.drawHeight = w * r
        return im

    s, sub, an = ctx["session"], ctx["subject"], ctx["analysis"]
    rec, q = an.get("recording", {}), an.get("quality", {})
    hrv, tr, mv = ctx.get("hrv") or {}, ctx.get("training_results") or {}, (ctx.get("movement_results") or {}).get("movement") or {}
    hr = (ctx.get("hr_series_stats") or {})
    calc = an.get("hr_calc", {})
    t, f = hrv.get("time") or {}, hrv.get("frequency") or {}

    el += [Paragraph("ECG / HRV ANALYSIS REPORT", H1),
           Paragraph(f"Subject: <b>{sub.get('name','')}</b> &nbsp;|&nbsp; Recording: <b>{s.get('sessionName','')}</b> &nbsp;|&nbsp; "
                     f"Analysis date: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", B), Spacer(1, 4)]
    for w in an.get("warnings", []):
        if w.get("level") in ("warn", "error"):
            el.append(Paragraph(f"<b>⚠ {w['message']}</b>", B))

    el.append(Paragraph("1. Subject Information", H2))
    el.append(table([["Name", "Age", "Gender", "Height", "Weight", "BMI (not diagnostic)", "Resting HR"],
                     [sub.get("name"), fmt(sub.get("age"), 0), sub.get("gender", NA), fmt(sub.get("height_cm"), 0, "cm"), fmt(sub.get("weight_kg"), 1, "kg"),
                      f"{fmt(sub.get('bmi'),1)} ({sub.get('bmi_category') or NA})", fmt(sub.get("resting_hr"), 0, "bpm")]]))
    el.append(Paragraph("2. Recording Information", H2))
    el.append(table([["Start", "Session duration", "Valid ECG", "ECG sampling", "ECG samples", "Length class"],
                     [str(rec.get("start_time") or NA)[:19], fmt((rec.get("session_duration_s") or 0) / 60, 1, "min") if rec.get("session_duration_s") else NA,
                      fmt(rec.get("ecg_valid_duration_s"), 0, "s") if rec.get("ecg_valid_duration_s") else NA, fmt(rec.get("ecg_fs_hz"), 0, "Hz"),
                      f"{rec.get('ecg_samples', 0):,}", rec.get("ecg_duration_class") or NA]]))
    el.append(Paragraph("3. Signal Quality", H2))
    el.append(table([["Status", "R-peaks", "RR intervals", "Accepted", "Flagged", "Artifact rate", "Signal quality"],
                     [q.get("status", NA), str(q.get("n_peaks", NA)), str(q.get("n_rr", NA)), str(q.get("accepted_beats", NA)),
                      str(q.get("flagged_beats", NA)), fmt(q.get("artifact_pct"), 1, "%"), fmt(q.get("signal_quality_pct"), 1, "%")]]))
    el.append(Paragraph("4. ECG Processing", H2))
    ep = an.get("ecg_processing") or {}
    fl = ep.get("filter") or {}
    el.append(Paragraph(f"Band-pass {fl.get('bandpass_hz', NA)} Hz (zero-phase Butterworth, order {fl.get('order', NA)}); powerline {fl.get('powerline_hz', NA)} Hz notch "
                        f"{'applied' if fl.get('notch_applied') else 'not required'} (spectral ratio {fl.get('powerline_ratio', NA)}). R-peak detector: {ep.get('detector', NA)}. "
                        f"Sampling rate source: {rec.get('fs_source') or NA}.", B))
    el.append(Paragraph("5. Heart Rate Summary", H2))
    sv = an.get("source_vs_calculated", {})
    rows = [["Metric", "Application calculated", "Source dataset", "Difference"]]
    for k, lab in (("avg_hr", "Average HR"), ("max_hr", "Max HR"), ("min_hr", "Min HR")):
        c = sv.get(k, {})
        rows.append([lab, fmt(c.get("calculated"), 2, "bpm"), fmt(c.get("source"), 2, "bpm"), fmt(c.get("difference"), 2)])
    rows.append(["Median HR", fmt(hr.get("median"), 1, "bpm"), "—", "—"])
    rows.append(["Theoretical HRmax (estimate)", fmt(calc.get("theoretical_hrmax"), 0, "bpm"), f"formula {calc.get('hrmax_formula')}", "—"])
    rows.append(["HR reserve (estimate)", fmt(calc.get("hr_reserve"), 0, "bpm"), "—", "—"])
    el.append(table(rows))
    el.append(Spacer(1, 4)); el.append(img(chart_hr(ctx)))
    el.append(Paragraph("Series source: " + str(hr.get("series_source") or NA) + ". Age-based HRmax is a population estimate, not a measured maximum.", S))
    zblock = [Paragraph("6. HR Zones", H2)]
    z = (tr.get("zones") or {}).get("zones")
    if z:
        zblock.append(table([["Zone", "Range (% HRmax)", "Range (bpm)", "Time", "% session", "Avg HR", "Peak HR"]] +
                        [[zz["label"], f"{zz['lo_pct']:.0f}–{zz['hi_pct']:.0f}", f"{zz['lo_bpm']:.0f}–{zz['hi_bpm']:.0f}", f"{zz['seconds']/60:.1f} min",
                          f"{zz['percent']:.1f}", fmt(zz["avg_hr"], 0), fmt(zz["peak_hr"], 0)] for zz in z]))
        zblock += [Spacer(1, 4), img(chart_zones(ctx))]
    else:
        zblock.append(Paragraph("N/A — age/HRmax or HR data not available.", B))
    el.append(KeepTogether(zblock))
    el.append(Paragraph("7. RR Analysis", H2))
    el.append(img(chart_rr(ctx)))
    el.append(table([["Mean RR", "Median RR", "Min RR", "Max RR", "Mean HR (ECG)"],
                     [fmt(t.get("mean_rr"), 1, "ms"), fmt(t.get("median_rr"), 1, "ms"), fmt(t.get("min_rr"), 0, "ms"), fmt(t.get("max_rr"), 0, "ms"), fmt(t.get("mean_hr"), 1, "bpm")]]))
    el.append(Paragraph("8. Time Domain HRV", H2))
    if t.get("withheld"):
        el.append(Paragraph("N/A — insufficient valid data (metrics withheld because of signal quality).", B))
    el.append(table([["SDNN", "RMSSD", "SDSD", "NN50", "pNN50", "NN20", "pNN20", "CVNN"],
                     [fmt(t.get("sdnn"), 1, "ms"), fmt(t.get("rmssd"), 1, "ms"), fmt(t.get("sdsd"), 1, "ms"), fmt(t.get("nn50"), 0), fmt(t.get("pnn50"), 1, "%"),
                      fmt(t.get("nn20"), 0), fmt(t.get("pnn20"), 1, "%"), fmt(t.get("cvnn"), 1, "%")]]))
    el.append(Paragraph("9. Frequency Domain HRV", H2))
    el.append(img(chart_psd(ctx)))
    el.append(table([["Metric", "Value", "Unit"], ["VLF", fmt(f.get("vlf"), 1), "ms²"], ["LF", fmt(f.get("lf"), 1), "ms²"], ["HF", fmt(f.get("hf"), 1), "ms²"],
                     ["LF/HF", fmt(f.get("lf_hf"), 2), "ratio"], ["Total power", fmt(f.get("total_power"), 1), "ms²"]], [40 * mm, 40 * mm, 30 * mm]))
    for n in f.get("notes", []):
        el.append(Paragraph(n, S))
    el.append(Paragraph(f"Method: {f.get('method', 'welch')} PSD; bands VLF 0.0033–0.04, LF 0.04–0.15, HF 0.15–0.40 Hz. LF/HF is not a direct index of sympathetic/parasympathetic balance.", S))
    el.append(Paragraph("10. Training Load", H2))
    src, cal = (tr.get("training") or {}).get("source") or {}, (tr.get("training") or {}).get("calculated") or {}
    el.append(table([["", "Source dataset", "Application calculated"],
                     ["Training load", fmt(src.get("training_load"), 3), fmt(cal.get("trimp"), 1) + " (Banister TRIMP)" if cal.get("trimp") is not None else NA],
                     ["Training intensity", fmt(src.get("training_intensity"), 3), fmt(cal.get("intensity"), 3) if cal.get("intensity") is not None else NA],
                     ["Duration", "—", fmt(cal.get("duration_min"), 1, "min") if cal.get("duration_min") else NA]]))
    el.append(Paragraph("The calculated value is a documented Banister TRIMP (Σ Δt·HRr·0.64·e^(b·HRr)); it is not the proprietary algorithm behind the source value.", S))
    el.append(Paragraph("11. Movement Load", H2))
    if mv.get("available"):
        c, sr = mv.get("calculated") or {}, mv.get("source") or {}
        el.append(table([["", "Source dataset", "Application calculated"], ["Movement load", fmt(sr.get("movement_load"), 3), fmt(c.get("load"), 3)],
                         ["Movement intensity", fmt(sr.get("movement_intensity"), 3), fmt(c.get("intensity"), 3)]]))
        el.append(img(chart_mov(ctx)))
    else:
        el.append(Paragraph("Movement data not available for this session.", B))
    el.append(Paragraph("12. Interpretation", H2))
    for it in ctx.get("interpretation", []):
        el.append(Paragraph(f"<b>{it['metric']}</b> {('— ' + it['value']) if it.get('value') else ''}: {it['text']}", B))
    el.append(Paragraph("13. Limitations", H2))
    for line in ["ECG in this dataset format is recorded in intermittent snapshots; HRV reflects only the valid ECG windows, not the whole session.",
                 "Ultra-short recordings (< 5 min) give approximate HRV; VLF and total power are withheld below 5 min.",
                 "Exercise strongly changes HR and HRV; metrics are not comparable with resting measurements.",
                 "RR artifact screening is interval-based and does not classify arrhythmias. Source-versus-calculated differences can arise from different preprocessing."]:
        el.append(Paragraph("• " + line, B))
    el.append(Paragraph("14. Processing Parameters", H2))
    p = an.get("parameters", {})
    el.append(Paragraph(f"HRmax formula: {p.get('hrmax_formula')} | zones: {p.get('zones')} | filter: {p.get('filter') or 'defaults'} | artifact: {p.get('artifact') or 'defaults'} | "
                        f"frequency: {p.get('freq') or 'defaults'}", S))
    el.append(Spacer(1, 6))
    from ..analysis.interpretation import DISCLAIMER
    el.append(Paragraph(DISCLAIMER, S))

    def footer(c, d):
        c.saveState(); c.setFont("Helvetica", 7); c.setFillColor(colors.HexColor(GRAY))
        c.drawString(16 * mm, 9 * mm, "ECG/HRV Analytics — research tool, not a medical device"); c.drawRightString(194 * mm, 9 * mm, f"Page {d.page}")
        c.setFillColor(colors.HexColor(ORANGE)); c.rect(16 * mm, 12 * mm, 178 * mm, 0.6, stroke=0, fill=1); c.restoreState()

    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
