#!/usr/bin/env python3
"""
================================================================================
  Android BugReport Analyzer  — Generic, Multi-Build, Multi-Device
  Author  : GitHub Copilot (auto-generated)
  Version : 1.0.0

  Analyses one or more Android bugreport .txt files and produces:
    • Per-bugreport HTML report  (battery, ANR, crash, LMK, thermal, wakelocks)
    • Per-bugreport battery-drain PNG graph with per-hour anomaly annotation
    • Comparative HTML report + comparison PNG graph  (when ≥2 bugreports given)

  Usage:
    python bugreport_analyzer.py  <path1.txt>  [path2.txt ...]
                                  [-l LABEL1 LABEL2 ...]
                                  [-o OUTPUT_DIR]
                                  [-t "Report Title"]
                                  [--no-graph]

  Examples:
    # Single build
    python bugreport_analyzer.py bugreport_RC1.txt -l RC1

    # Two builds — individual + comparative
    python bugreport_analyzer.py rc1.txt st5.txt -l RC1 ST5 -o ./out

    # Three builds
    python bugreport_analyzer.py a.txt b.txt c.txt -l BuildA BuildB BuildC

================================================================================
"""

import re
import os
import sys
import json
import argparse
import textwrap
from datetime import datetime
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════════════════════
#  PALETTE / CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
CHART_COLORS = [
    '#00d4ff', '#ff6b35', '#00ff88', '#ffcc00', '#ff44aa',
    '#44aaff', '#ff8844', '#88ff44', '#cc44ff', '#ffff44',
]

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #0d0d1a;
       color: #e0e0e0; font-size: 14px; line-height: 1.6; }
.header { background: linear-gradient(135deg, #1a1a3e 0%, #0d1b2a 100%);
          border-bottom: 2px solid #00d4ff; padding: 28px 32px; }
.header h1 { color: #00d4ff; font-size: 22px; font-weight: 700; margin-bottom: 6px; }
.header .subtitle { color: #99aabb; font-size: 13px; }
.section { background: #111127; border: 1px solid #22224a; border-radius: 8px;
           margin: 18px 24px; padding: 18px 22px; }
.section h2 { color: #00d4ff; font-size: 16px; margin-bottom: 14px;
              border-bottom: 1px solid #22224a; padding-bottom: 8px; }
.section h3 { color: #88bbdd; font-size: 14px; margin: 12px 0 8px; }
.kpi-grid { display: flex; flex-wrap: wrap; gap: 14px; margin-bottom: 10px; }
.kpi-card { background: #181830; border: 1px solid #33335a; border-radius: 8px;
            padding: 14px 20px; min-width: 150px; text-align: center; flex: 1; }
.kpi-value { font-size: 26px; font-weight: 700; color: #ffffff; }
.kpi-value.green  { color: #00cc66; }
.kpi-value.orange { color: #ff8800; }
.kpi-value.red    { color: #ff4444; }
.kpi-label { font-size: 11px; color: #778899; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #1a1a40; color: #00d4ff; padding: 9px 12px; text-align: left;
     font-weight: 600; border-bottom: 1px solid #333; }
td { padding: 7px 12px; border-bottom: 1px solid #1e1e3a; vertical-align: top; }
tr:hover td { background: #191932; }
tr.critical td { background: #2a0808; }
tr.high td     { background: #1f1500; }
.bar-wrap { background: #0d0d1a; border-radius: 3px; height: 8px; margin-top: 4px; }
.bar-fill { height: 8px; border-radius: 3px; background: #00d4ff; }
.bar-fill.orange { background: #ff8800; }
.bar-fill.red    { background: #ff4444; }
.badge { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 10px;
         text-transform: uppercase; letter-spacing: 0.5px; vertical-align: middle; }
.badge-critical { background: #400000; color: #ff4444; border: 1px solid #ff4444; }
.badge-high     { background: #3a1a00; color: #ff8800; border: 1px solid #ff8800; }
.badge-medium   { background: #2a2a00; color: #ffcc00; border: 1px solid #ffcc00; }
.badge-normal   { background: #002a00; color: #00cc66; border: 1px solid #00cc66; }
.badge-info     { background: #001a2a; color: #00aaff; border: 1px solid #00aaff; }
.anr-box  { background: #200000; border: 1px solid #ff4444; border-radius: 6px;
            padding: 12px 16px; margin: 8px 0; }
.anr-box  h4 { color: #ff6666; margin-bottom: 6px; font-size: 13px; }
.anr-box  pre { color: #ffaaaa; font-size: 11px; white-space: pre-wrap; max-height: 160px;
                overflow-y: auto; font-family: Consolas, monospace; }
.crash-box{ background: #1a0010; border: 1px solid #ff44aa; border-radius: 6px;
            padding: 12px 16px; margin: 8px 0; }
.crash-box h4 { color: #ff88cc; margin-bottom: 6px; font-size: 13px; }
.crash-box pre{ color: #ffccee; font-size: 11px; white-space: pre-wrap; max-height: 160px;
                overflow-y: auto; font-family: Consolas, monospace; }
.thermal-box { background: #1a0800; border: 1px solid #ff8800; border-radius: 6px;
               padding: 12px 16px; margin: 8px 0; }
.img-container { text-align: center; margin: 16px 0; }
.img-container img { max-width: 100%; border-radius: 8px;
                     border: 1px solid #22224a; }
.comp-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
             gap: 18px; }
.verdict { font-size: 15px; font-weight: 600; padding: 14px 20px;
           border-radius: 8px; margin: 10px 0; }
.verdict.pass { background: #002a00; color: #00cc66; border: 1px solid #00cc66; }
.verdict.fail { background: #2a0000; color: #ff4444; border: 1px solid #ff4444; }
.verdict.warn { background: #2a1a00; color: #ffaa00; border: 1px solid #ffaa00; }
.nav { display: flex; gap: 10px; flex-wrap: wrap; margin: 12px 24px 0; }
.nav a { background: #1a1a3e; color: #00d4ff; padding: 6px 16px; border-radius: 20px;
         text-decoration: none; font-size: 12px; border: 1px solid #00d4ff; }
.nav a:hover { background: #00d4ff; color: #000; }
footer { text-align: center; color: #445566; font-size: 11px;
         padding: 24px; border-top: 1px solid #1a1a2e; margin-top: 20px; }
"""

# ── INTERACTIVE CSS (replaces / extends the static CSS above) ────────────────
CSS = """
/* ── Reset & base ── */
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Arial,sans-serif;background:#0d0d1a;color:#e0e0e0;font-size:14px;line-height:1.6}
/* ── Header ── */
.header{background:linear-gradient(135deg,#1a1a3e 0%,#0d1b2a 100%);border-bottom:2px solid #00d4ff;padding:24px 32px}
.header h1{color:#00d4ff;font-size:22px;font-weight:700;margin-bottom:6px}
.header .subtitle{color:#99aabb;font-size:13px}
/* ── Nav bar ── */
.nav{display:flex;gap:10px;flex-wrap:wrap;margin:12px 24px 0}
.nav a{background:#1a1a3e;color:#00d4ff;padding:6px 16px;border-radius:20px;text-decoration:none;font-size:12px;border:1px solid #00d4ff;transition:all .2s}
.nav a:hover{background:#00d4ff;color:#000}
/* ── Sidebar TOC ── */
#toc{position:fixed;top:0;left:0;height:100vh;width:210px;background:#0c0c22;border-right:1px solid #22224a;overflow-y:auto;padding:16px 0;z-index:999;transform:translateX(-210px);transition:transform .3s}
#toc.open{transform:translateX(0)}
#toc-toggle{position:fixed;top:14px;left:14px;z-index:1000;background:#1a1a3e;border:1px solid #00d4ff;color:#00d4ff;padding:5px 10px;border-radius:6px;cursor:pointer;font-size:12px;line-height:1}
#toc h3{color:#00d4ff;font-size:11px;text-transform:uppercase;letter-spacing:1px;padding:8px 16px;border-bottom:1px solid #22224a;margin-bottom:6px}
#toc a{display:block;padding:5px 16px;color:#aabbcc;text-decoration:none;font-size:12px;transition:background .15s}
#toc a:hover,#toc a.active{background:#1a1a3e;color:#00d4ff}
body.toc-open{padding-left:210px}
/* ── Section ── */
.section{background:#111127;border:1px solid #22224a;border-radius:8px;margin:18px 24px;overflow:hidden}
.section-header{display:flex;align-items:center;justify-content:space-between;padding:14px 22px;cursor:pointer;user-select:none;border-bottom:1px solid #22224a;transition:background .15s}
.section-header:hover{background:#181835}
.section-header h2{color:#00d4ff;font-size:16px;font-weight:700;display:flex;align-items:center;gap:8px;margin:0}
.toggle-icon{color:#00d4ff;font-size:18px;transition:transform .25s;flex-shrink:0}
.section-header.collapsed .toggle-icon{transform:rotate(-90deg)}
.section-body{padding:18px 22px}
.section-body.hidden{display:none}
.section-body h3{color:#88bbdd;font-size:14px;margin:14px 0 8px}
/* ── KPI cards ── */
.kpi-grid{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:14px}
.kpi-card{background:#181830;border:1px solid #33335a;border-radius:8px;padding:14px 20px;min-width:150px;text-align:center;flex:1;transition:border-color .2s,transform .2s;cursor:default}
.kpi-card:hover{border-color:#00d4ff;transform:translateY(-2px)}
.kpi-value{font-size:26px;font-weight:700;color:#fff}
.kpi-value.green{color:#00cc66}.kpi-value.orange{color:#ff8800}.kpi-value.red{color:#ff4444}
.kpi-label{font-size:11px;color:#778899;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
/* ── Chart containers ── */
.chart-wrap{position:relative;background:#0e0e22;border-radius:8px;border:1px solid #22224a;margin:10px 0;padding:12px}
.chart-toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.chart-toolbar label{font-size:12px;color:#99aabb}
.chart-toolbar select,.chart-toolbar input[type=range]{background:#1a1a3e;color:#e0e0e0;border:1px solid #33335a;border-radius:4px;padding:3px 7px;font-size:12px}
.chart-toolbar button{background:#1a1a3e;color:#00d4ff;border:1px solid #00d4ff;border-radius:4px;padding:4px 12px;font-size:12px;cursor:pointer;transition:all .15s}
.chart-toolbar button:hover{background:#00d4ff;color:#000}
.chart-toolbar button.active{background:#00d4ff;color:#000}
.chart-hint{font-size:11px;color:#556677;margin-top:6px;text-align:center}
/* ── Tables ── */
.tbl-wrap{overflow-x:auto;margin-top:8px}
.tbl-filter{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
.tbl-filter input{background:#1a1a3e;color:#e0e0e0;border:1px solid #33335a;border-radius:4px;padding:4px 10px;font-size:12px;flex:1;min-width:160px}
.tbl-filter select{background:#1a1a3e;color:#e0e0e0;border:1px solid #33335a;border-radius:4px;padding:4px 8px;font-size:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#1a1a40;color:#00d4ff;padding:9px 12px;text-align:left;font-weight:600;border-bottom:1px solid #333;cursor:pointer;user-select:none;white-space:nowrap}
th:hover{background:#1f1f50}
th.sort-asc::after{content:' ▲';font-size:10px}
th.sort-desc::after{content:' ▼';font-size:10px}
td{padding:7px 12px;border-bottom:1px solid #1e1e3a;vertical-align:top}
tr:hover td{background:#191932}
tr.critical td{background:#2a0808}
tr.high td{background:#1f1500}
tr.filtered-out{display:none}
/* ── Progress bars ── */
.bar-wrap{background:#0d0d1a;border-radius:3px;height:8px;margin-top:4px}
.bar-fill{height:8px;border-radius:3px;background:#00d4ff;transition:width .4s}
.bar-fill.orange{background:#ff8800}.bar-fill.red{background:#ff4444}
/* ── Badges ── */
.badge{font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;text-transform:uppercase;letter-spacing:.5px;vertical-align:middle}
.badge-critical{background:#400000;color:#ff4444;border:1px solid #ff4444}
.badge-high{background:#3a1a00;color:#ff8800;border:1px solid #ff8800}
.badge-medium{background:#2a2a00;color:#ffcc00;border:1px solid #ffcc00}
.badge-normal{background:#002a00;color:#00cc66;border:1px solid #00cc66}
.badge-info{background:#001a2a;color:#00aaff;border:1px solid #00aaff}
/* ── Event boxes ── */
.evt-box{border-radius:6px;margin:8px 0;overflow:hidden}
.evt-box.anr{background:#200000;border:1px solid #ff4444}
.evt-box.crash{background:#1a0010;border:1px solid #ff44aa}
.evt-box.thermal{background:#1a0800;border:1px solid #ff8800}
.evt-header{padding:10px 14px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-size:13px}
.evt-header:hover{filter:brightness(1.2)}
.evt-body{padding:10px 14px;border-top:1px solid #333;display:none}
.evt-body.open{display:block}
.evt-body pre{color:#ffaaaa;font-size:11px;white-space:pre-wrap;max-height:200px;overflow-y:auto;font-family:Consolas,monospace;background:#0d0d1a;padding:8px;border-radius:4px;margin-top:6px}
/* ── Tabs ── */
.tabs{display:flex;gap:0;border-bottom:1px solid #33335a;margin-bottom:14px}
.tab-btn{background:transparent;border:none;border-bottom:2px solid transparent;color:#778899;padding:8px 18px;cursor:pointer;font-size:13px;transition:all .15s}
.tab-btn.active{color:#00d4ff;border-bottom-color:#00d4ff}
.tab-btn:hover:not(.active){color:#aabbcc}
.tab-panel{display:none}.tab-panel.active{display:block}
/* ── Verdict ── */
.verdict{font-size:15px;font-weight:600;padding:14px 20px;border-radius:8px;margin:10px 0}
.verdict.pass{background:#002a00;color:#00cc66;border:1px solid #00cc66}
.verdict.fail{background:#2a0000;color:#ff4444;border:1px solid #ff4444}
.verdict.warn{background:#2a1a00;color:#ffaa00;border:1px solid #ffaa00}
/* ── Comp grid ── */
.comp-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}
/* ── RCA items ── */
.rca-item{background:#0d0d1a;border-left:3px solid #555;padding:10px 16px;margin:6px 0;border-radius:0 6px 6px 0}
.rca-item.critical{border-left-color:#ff4444}
.rca-item.high{border-left-color:#ff8800}
.rca-item.normal{border-left-color:#00cc66}
/* ── Floating pill ── */
#summary-pill{position:fixed;bottom:20px;right:20px;background:#1a1a3e;border:1px solid #00d4ff;border-radius:12px;padding:10px 16px;font-size:12px;color:#ccc;z-index:900;cursor:pointer;max-width:260px;box-shadow:0 4px 20px rgba(0,0,0,.5);line-height:1.5}
#summary-pill:hover{background:#00d4ff;color:#000}
/* ── Image ── */
.img-container{text-align:center;margin:16px 0}
.img-container img{max-width:100%;border-radius:8px;border:1px solid #22224a}
/* ── Range slider label ── */
.range-val{font-weight:700;color:#00d4ff;min-width:32px;display:inline-block}
/* ── Footer ── */
footer{text-align:center;color:#445566;font-size:11px;padding:24px;border-top:1px solid #1a1a2e;margin-top:20px}
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_duration_ms(s):
    """Parse battery history time-token (e.g. '3h11m44s398ms') → milliseconds.
    Must check 'ms' BEFORE 'm' to avoid misreading '155ms' as 155 minutes."""
    ms = 0
    m = re.match(r'(\d+)h', s);
    if m: ms += int(m.group(1)) * 3_600_000; s = s[m.end():]
    m = re.match(r'(\d+)m(?!s)', s)
    if m: ms += int(m.group(1)) * 60_000; s = s[m.end():]
    m = re.match(r'(\d+)s', s)
    if m: ms += int(m.group(1)) * 1_000; s = s[m.end():]
    m = re.match(r'(\d+)ms', s)
    if m: ms += int(m.group(1))
    return ms


def duration_str_to_seconds(s):
    """'19h 48m 47s 535ms' → total seconds (float)."""
    total = 0.0
    for unit, mult in [('d', 86400), ('h', 3600), ('m', 60), ('s', 1), ('ms', 0.001)]:
        mo = re.search(rf'(\d+)\s*{unit}\b', s)
        if mo:
            total += int(mo.group(1)) * mult
    return total


def _level_at_ms(h_sorted, t_ms):
    """Binary-ish scan: last battery level at or before t_ms."""
    lvl = h_sorted[0]['level'] if h_sorted else 100
    for p in h_sorted:
        if p['ms'] <= t_ms:
            lvl = p['level']
        else:
            break
    return lvl


def _badge(text, cls='info'):
    return f'<span class="badge badge-{cls}">{text}</span>'


def _severity(value, warn_thresh, crit_thresh):
    if value >= crit_thresh:
        return 'critical'
    if value >= warn_thresh:
        return 'high'
    return ''


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — BATTERY HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

def parse_battery_history(path, batterystats_line):
    """
    Extract battery level timeline from Android battery history.

    Timestamps in history are ABSOLUTE offsets from RESET (not incremental).
    Format:
      0 (2) 100 c0980002 ...       ← initial state at T=0
      +155ms (1) 100 c0900002      ← T = 0.155 s
      +3h11m44s398ms (2) 099 ...   ← T = 3 h 11 m 44.398 s
    """
    history, screen_events, wl_events = [], [], []
    current_volt, current_screen = 0, True

    pat_abs   = re.compile(r'^\s+0\s+\((\d+)\)\s+(\d{1,3})\s+([0-9a-fA-F]{8})(.*)')
    pat_delta = re.compile(
        r'^\s+\+((?:\d+h)?(?:\d+m(?!s))?(?:\d+s)?(?:\d+ms)?)\s+\((\d+)\)\s+(\d{1,3})\s+([0-9a-fA-F]{8})(.*)')

    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for lineno, line in enumerate(fh, 1):
            if lineno < batterystats_line:
                continue
            if lineno > batterystats_line + 600_000:
                break
            stripped = line.lstrip()
            if (': time: [' in line or stripped.startswith('Stats:') or
                    stripped.startswith('Details:') or stripped.startswith('/proc/stat')):
                continue
            m = pat_abs.match(line)
            if m:
                _, lvl, _, rest = m.groups()
                vm = re.search(r'volt=(\d+)', rest or '')
                if vm: current_volt = int(vm.group(1))
                if '-screen' in (rest or ''): current_screen = False; screen_events.append((0, 'off'))
                elif '+screen' in (rest or ''): current_screen = True; screen_events.append((0, 'on'))
                history.append({'ms': 0, 'level': int(lvl), 'volt': current_volt, 'screen': current_screen})
                continue
            m = pat_delta.match(line)
            if m:
                dur_str, _, lvl, _, rest = m.groups()
                abs_ms = _parse_duration_ms(dur_str)
                vm = re.search(r'volt=(\d+)', rest or '')
                if vm: current_volt = int(vm.group(1))
                if '-screen' in (rest or ''): current_screen = False; screen_events.append((abs_ms, 'off'))
                elif '+screen' in (rest or ''): current_screen = True; screen_events.append((abs_ms, 'on'))
                lw = re.search(r'longwake=(\S+:"[^"]+")', rest or '')
                if lw: wl_events.append((abs_ms, lw.group(1)))
                history.append({'ms': abs_ms, 'level': int(lvl), 'volt': current_volt, 'screen': current_screen})

    return history, screen_events, wl_events


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — POWER USE / WAKELOCKS
# ═══════════════════════════════════════════════════════════════════════════════

def parse_estimated_power(lines, start_line, uid_map):
    result = {'capacity': 0, 'computed_drain': 0.0, 'actual_drain': '', 'global': {}, 'per_uid': []}
    in_sec = False
    for i in range(start_line, min(start_line + 300, len(lines))):
        l = lines[i].strip()
        if 'Estimated power use (mAh)' in l:
            in_sec = True; continue
        if not in_sec: continue
        if l.startswith('All kernel wake locks:') or l.startswith('DUMP OF SERVICE'): break
        m = re.match(r'Capacity:\s*(\d+),\s*Computed drain:\s*([\d.]+),\s*actual drain:\s*([\d.eE+\-]+)', l)
        if m:
            result['capacity'] = int(m.group(1))
            result['computed_drain'] = float(m.group(2))
            result['actual_drain'] = m.group(3)
            continue
        for key in ['screen', 'cpu', 'sensors', 'wifi', 'wakelock', 'idle', 'bluetooth', 'gnss']:
            mo = re.match(rf'^{key}:\s*([\d.]+)', l)
            if mo: result['global'][key] = float(mo.group(1))
        m = re.match(r'(?:UID\s+)?([\w]+):\s*([\d.]+)(.*)', l)
        if m and not l.startswith('Capacity') and not l.startswith('Global'):
            uid = m.group(1).strip()
            if uid and not uid.startswith('#') and uid[0].isalnum():
                total = float(m.group(2)); rest = m.group(3) or ''
                pkg = uid_map.get(uid, uid)
                entry = {'uid': uid, 'package': pkg, 'total_mah': total, 'detail': rest[:140]}
                for comp in ['cpu', 'wifi', 'wakelock', 'sensors', 'audio', 'bluetooth']:
                    cm = re.search(rf'{comp}=([\d.]+)', rest)
                    if cm: entry[comp] = float(cm.group(1))
                result['per_uid'].append(entry)
    result['per_uid'].sort(key=lambda x: x['total_mah'], reverse=True)
    return result


def parse_kernel_wakelocks(lines, start_line):
    wl, in_sec = [], False
    for i in range(start_line, min(start_line + 120, len(lines))):
        l = lines[i].strip()
        if 'All kernel wake locks:' in l: in_sec = True; continue
        if not in_sec: continue
        if l.startswith('All partial wake locks:') or l.startswith('DUMP OF SERVICE'): break
        m = re.match(r'Kernel Wake lock (.+?):\s*(.+?)\s*\((\d+) times\)', l)
        if m:
            wl.append({'name': m.group(1), 'duration': m.group(2),
                       'duration_sec': duration_str_to_seconds(m.group(2)),
                       'count': int(m.group(3))})
    return wl


def parse_partial_wakelocks(lines, start_line):
    wl, in_sec = [], False
    for i in range(start_line, min(start_line + 5000, len(lines))):
        l = lines[i].strip()
        if 'All partial wake locks:' in l: in_sec = True; continue
        if not in_sec: continue
        if l.startswith('DUMP OF SERVICE') or (l.startswith('All ') and in_sec and i > start_line + 5): break
        m = re.match(r'Wake lock ([\w]+)\s+(.+?):\s*(.+?)\s*\((\d+) times\)', l)
        if m:
            wl.append({'uid': m.group(1), 'name': m.group(2),
                       'duration': m.group(3),
                       'duration_sec': duration_str_to_seconds(m.group(3)),
                       'count': int(m.group(4))})
    return wl


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — ANR (Application Not Responding)
# ═══════════════════════════════════════════════════════════════════════════════

def parse_anrs(lines):
    """
    Detect ANRs from multiple sources:
      • 'ANR in <package>' log lines
      • 'Subject: ANR' in DropBox section
      • am_anr event log lines
    Returns list of dicts with time, process, reason, traces snippet.
    """
    anrs = []
    seen = set()

    # Pattern 1: ActivityManager ANR log line
    # E.g. "02-19 18:30:05.123  1000  2541  ANR in com.example.app (com.example.app/.MainActivity)"
    pat_am = re.compile(
        r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+\S+\s+\S+\s+ANR in\s+(\S+)(.*?)$')
    # Pattern 2: DropBox subject
    pat_db = re.compile(r'Subject:\s*(ANR in .+?)$', re.IGNORECASE)
    # Pattern 3: am_anr event tag
    pat_ev = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?am_anr[:\s]+\[.*?\]')
    # Pattern 4: "ANR in" anywhere in logcat
    pat_simple = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?ANR in\s+(\S+)')

    collect_trace = False
    trace_lines = []
    current_anr = None

    for i, line in enumerate(lines):
        # Start trace collection after ANR headline
        if collect_trace:
            trace_lines.append(line.rstrip())
            if len(trace_lines) >= 30 or (line.strip() == '' and len(trace_lines) > 5):
                if current_anr:
                    current_anr['trace'] = '\n'.join(trace_lines[:30])
                collect_trace = False; trace_lines = []; current_anr = None
            continue

        m = pat_am.search(line)
        if m:
            key = (m.group(1)[:13], m.group(2))
            if key not in seen:
                seen.add(key)
                entry = {'time': m.group(1), 'process': m.group(2),
                         'reason': m.group(3).strip()[:200], 'trace': '', 'source': 'ActivityManager'}
                anrs.append(entry); current_anr = entry; collect_trace = True; trace_lines = []
            continue

        m = pat_db.search(line)
        if m:
            key = ('dropbox', m.group(1)[:40])
            if key not in seen:
                seen.add(key)
                anrs.append({'time': '', 'process': m.group(1), 'reason': 'DropBox ANR',
                             'trace': '', 'source': 'DropBox'})
            continue

        m = pat_simple.search(line)
        if m:
            key = (m.group(1)[:13], m.group(2))
            if key not in seen:
                seen.add(key)
                anrs.append({'time': m.group(1), 'process': m.group(2),
                             'reason': line.strip()[:200], 'trace': '', 'source': 'logcat'})
            continue

    return anrs


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — CRASH / EXCEPTION / FATAL
# ═══════════════════════════════════════════════════════════════════════════════

def parse_crashes(lines):
    """
    Detect crashes from:
      • FATAL EXCEPTION lines (Java crash)
      • Process <pkg> (pid N) has died (native crash / OOM kill)
      • DropBox Subject: crash / native_crash
      • am_crash event log
    """
    crashes = []
    seen = set()

    pat_fatal   = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?FATAL EXCEPTION')
    pat_died    = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?Process\s+(\S+)\s+\(pid\s+(\d+)\)\s+has died')
    pat_am_cr   = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?am_crash[:\s]+\[.*?\]')
    pat_db_cr   = re.compile(r'Subject:\s*(crash|native_crash[^,\n]*)', re.IGNORECASE)
    pat_sigsegv = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?(SIGSEGV|SIGABRT|SIGFPE|SIGBUS|Fatal signal)')
    pat_except  = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?(java\.lang\.\w+Exception|java\.lang\.Error)')

    collect = False; coll_lines = []; current = None

    for i, line in enumerate(lines):
        if collect:
            coll_lines.append(line.rstrip())
            if len(coll_lines) >= 25 or (line.strip() == '' and len(coll_lines) > 5):
                if current: current['trace'] = '\n'.join(coll_lines[:25])
                collect = False; coll_lines = []; current = None
            continue

        m = pat_fatal.search(line)
        if m:
            # Next line usually has the process name
            next_line = lines[i + 1].rstrip() if i + 1 < len(lines) else ''
            proc = re.search(r'Process:\s*(\S+)', next_line)
            key = (m.group(1)[:13], 'FATAL')
            if key not in seen:
                seen.add(key)
                entry = {'time': m.group(1), 'type': 'Java FATAL',
                         'process': proc.group(1) if proc else 'unknown',
                         'signal': 'FATAL EXCEPTION', 'trace': '', 'source': 'logcat'}
                crashes.append(entry); current = entry; collect = True; coll_lines = []
            continue

        m = pat_died.search(line)
        if m:
            key = (m.group(1)[:13], m.group(2))
            if key not in seen:
                seen.add(key)
                crashes.append({'time': m.group(1), 'type': 'Process Died',
                                'process': m.group(2), 'signal': f'PID {m.group(3)} died',
                                'trace': line.strip()[:200], 'source': 'logcat'})
                seen.add(key)
            continue

        m = pat_sigsegv.search(line)
        if m:
            key = (m.group(1)[:13], m.group(2))
            if key not in seen:
                seen.add(key)
                entry = {'time': m.group(1), 'type': 'Native Crash',
                         'process': 'unknown', 'signal': m.group(2),
                         'trace': '', 'source': 'logcat'}
                crashes.append(entry); current = entry; collect = True; coll_lines = [line.rstrip()]
                seen.add(key)
            continue

        m = pat_except.search(line)
        if m:
            key = (m.group(1)[:13], m.group(2))
            if key not in seen:
                seen.add(key)
                entry = {'time': m.group(1), 'type': 'Java Exception',
                         'process': 'unknown', 'signal': m.group(2),
                         'trace': '', 'source': 'logcat'}
                crashes.append(entry); current = entry; collect = True; coll_lines = [line.rstrip()]
                seen.add(key)
            continue

        m = pat_db_cr.search(line)
        if m:
            key = ('dropbox', m.group(1)[:40])
            if key not in seen:
                seen.add(key)
                crashes.append({'time': '', 'type': 'DropBox', 'process': m.group(1),
                                'signal': 'DropBox crash entry', 'trace': '', 'source': 'DropBox'})
            continue

    return crashes


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — LOW MEMORY KILLER (LMK)
# ═══════════════════════════════════════════════════════════════════════════════

def parse_lmk(lines):
    """
    Detect Low Memory Killer events.
    • Kernel LMK:  'lowmemorykiller: Killing <proc> (<N> kB)...'
    • ActivityManager OOM: 'Process <pkg> killed by LMK'
    • am_low_memory event
    """
    events = []
    seen = set()
    pat_lmk1 = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?lowmemorykiller.*?Killing\s+\'?(\S+?)\'?\s+\((\d+)\s*(?:kB|KB)?', re.IGNORECASE)
    pat_lmk2 = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?Killing\s+(\S+)\s+.*?adj=(\d+)', re.IGNORECASE)
    pat_lmk3 = re.compile(r'am_low_memory[:\s]+\[(\d+)\]')
    pat_lmk4 = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?Process\s+(\S+)\s+killed.*?(?:low|memory|LMK)', re.IGNORECASE)

    lmk_count = 0
    for line in lines:
        m = pat_lmk1.search(line)
        if m:
            key = (m.group(1)[:13], m.group(2))
            if key not in seen:
                seen.add(key)
                events.append({'time': m.group(1), 'process': m.group(2),
                               'size_kb': int(m.group(3)), 'adj': '', 'source': 'kernel LMK'})
            continue
        m = pat_lmk2.search(line)
        if m:
            key = (m.group(1)[:13], m.group(2))
            if key not in seen:
                seen.add(key)
                events.append({'time': m.group(1), 'process': m.group(2),
                               'size_kb': 0, 'adj': m.group(3), 'source': 'ActivityManager'})
            continue
        m = pat_lmk3.search(line)
        if m:
            lmk_count += 1
        m = pat_lmk4.search(line)
        if m:
            key = (m.group(1)[:13], m.group(2))
            if key not in seen:
                seen.add(key)
                events.append({'time': m.group(1), 'process': m.group(2),
                               'size_kb': 0, 'adj': '', 'source': 'ActivityManager'})

    return events, lmk_count


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — THERMAL
# ═══════════════════════════════════════════════════════════════════════════════

def parse_thermal(lines):
    """
    Detect thermal events:
      • 'thermal_throttle' log tag
      • temperature sensor readings from thermald / ThermalService
      • 'cpu freq throttled' kernel messages
      • temperature values in battery history (temp=NNN in 0.1°C units)
    """
    events = []
    temps = {}       # zone → max temp seen (°C)
    throttle_count = 0
    seen = set()

    pat_throttle = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?(thermal_throttl|cpu throttl|freq.*throttl)', re.IGNORECASE)
    pat_temp_log = re.compile(r'(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+).*?temp(?:erature)?[=:\s]+([\d.]+)', re.IGNORECASE)
    pat_bat_temp = re.compile(r'\btemp=(\d+)\b')   # battery history: temp in 0.1 °C
    pat_zone     = re.compile(r'([\w-]+)(?:_temp|Temp):\s*([\d.]+)\s*(?:C|°C)?', re.IGNORECASE)
    pat_tservice = re.compile(r'ThermalService.*?(\w[\w_-]+):\s*([\d.]+)\s*(?:C|°C)?', re.IGNORECASE)

    for line in lines:
        m = pat_throttle.search(line)
        if m:
            throttle_count += 1
            key = m.group(1)[:13]
            if key not in seen:
                seen.add(key)
                events.append({'time': m.group(1), 'event': m.group(2).strip(), 'temp': '', 'zone': ''})

        m = pat_bat_temp.search(line)
        if m:
            t_c = int(m.group(1)) / 10.0
            temps['battery'] = max(temps.get('battery', 0), t_c)

        m = pat_zone.search(line)
        if m:
            zone = m.group(1).lower()
            val  = float(m.group(2))
            if 0 < val < 200:   # sanity
                temps[zone] = max(temps.get(zone, 0), val)

        m = pat_tservice.search(line)
        if m:
            zone = m.group(1).lower()
            val  = float(m.group(2))
            if 0 < val < 200:
                temps[zone] = max(temps.get(zone, 0), val)

    return events, temps, throttle_count


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 7 — DEVICE / BUILD INFO
# ═══════════════════════════════════════════════════════════════════════════════

def parse_device_info(lines):
    info = {}
    pat = {
        'model':       re.compile(r'ro\.product\.model\s*[=:]\s*(.+)'),
        'device':      re.compile(r'ro\.product\.device\s*[=:]\s*(.+)'),
        'build':       re.compile(r'ro\.build\.description\s*[=:]\s*(.+)'),
        'fingerprint': re.compile(r'ro\.build\.fingerprint\s*[=:]\s*(.+)'),
        'android_ver': re.compile(r'ro\.build\.version\.release\s*[=:]\s*(.+)'),
        'sdk':         re.compile(r'ro\.build\.version\.sdk\s*[=:]\s*(\d+)'),
        'kernel':      re.compile(r'Linux version\s+(\S+)'),
        'serial':      re.compile(r'(?:ro\.serialno|ro\.boot\.serialno)\s*[=:]\s*(\S+)'),
        'build_id':    re.compile(r'ro\.build\.id\s*[=:]\s*(.+)'),
        'build_date':  re.compile(r'ro\.build\.date\s*[=:]\s*(.+)'),
        'brand':       re.compile(r'ro\.product\.brand\s*[=:]\s*(.+)'),
        'manufacturer':re.compile(r'ro\.product\.manufacturer\s*[=:]\s*(.+)'),
        'radio':       re.compile(r'gsm\.version\.baseband\s*[=:]\s*(.+)'),
        'uptime':      re.compile(r'up\s+([\d]+)\s+(?:days?,\s*)?([\d:]+)\b'),
    }
    for line in lines:
        for key, p in pat.items():
            if key in info:
                continue
            m = p.search(line)
            if m:
                info[key] = m.group(1).strip() if len(m.groups()) == 1 else ' '.join(m.groups())
    return info


def parse_uid_map(lines, batterystats_line):
    """Extract UID→package from battery history header fg/top lines."""
    uid_map = {}
    pat = re.compile(r'0\s+\(\d+\)\s+\d{2,3}\s+[0-9a-fA-F]{8}\s+(?:fg|top|longwake)=(u\d+[a-z0-9]*):"([^"]+)"')
    for i, line in enumerate(lines):
        if i < batterystats_line - 1:
            continue
        if i > batterystats_line + 2000:
            break
        m = pat.search(line)
        if m:
            uid_map[m.group(1)] = m.group(2)
    return uid_map


def parse_battery_metadata(lines, batterystats_line):
    meta = {}
    for i in range(batterystats_line, min(batterystats_line + 40000, len(lines))):
        l = lines[i].strip()
        if not meta.get('start_time'):
            m = re.match(r'Start clock time:\s*(\S+)', l)
            if m: meta['start_time'] = m.group(1)
        if not meta.get('total_run_time'):
            m = re.match(r'Total run time:\s*(.+)', l)
            if m: meta['total_run_time'] = m.group(1)
        if not meta.get('time_on_battery') and 'Time on battery:' in l:
            meta['time_on_battery'] = l
        if not meta.get('screen_off_time') and 'Screen off time:' in l:
            meta['screen_off_time'] = l
        if 'Estimated power use' in l:
            break
    return meta


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 8 — ANOMALY DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_battery_anomalies(history, avg_drain_mah_hr, capacity_mah,
                             expected_drain_mah_hr=None):
    anomalies = []
    if not history or capacity_mah == 0 or avg_drain_mah_hr <= 0:
        return anomalies
    # Use caller-supplied expected rate as the anomaly baseline when provided;
    # otherwise fall back to 1.5× the computed average.
    baseline = (expected_drain_mah_hr
                if (expected_drain_mah_hr and expected_drain_mah_hr > 0)
                else avg_drain_mah_hr)
    h_sorted = sorted(history, key=lambda x: x['ms'])
    max_ms = h_sorted[-1]['ms']
    hr_ms = 3_600_000
    for hr in range(int(max_ms / hr_ms) + 1):
        sl = _level_at_ms(h_sorted, hr * hr_ms)
        el = _level_at_ms(h_sorted, (hr + 1) * hr_ms)
        drop = sl - el
        if drop <= 0:
            continue
        drain_mah = drop * capacity_mah / 100
        if drain_mah > baseline * 1.5:
            anomalies.append({
                'hour': hr, 't_start_hr': hr, 't_end_hr': hr + 1,
                'drain_pct': drop, 'drain_mah': drain_mah,
                'vs_avg': drain_mah / avg_drain_mah_hr,
            })
    return anomalies


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 9 — MASTER PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def parse_bugreport(path, label, thresholds=None):
    thresholds = thresholds or {}
    print(f"\n  ▶  Parsing [{label}]  {os.path.basename(path)} ...")

    # ── First pass: locate section start lines ──────────────────────────────
    secs = {}
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for lineno, line in enumerate(fh, 1):
            ls = line.strip()
            if 'DUMP OF SERVICE batterystats' in ls and 'batterystats' not in secs:
                secs['batterystats'] = lineno
            if 'battery_discharge:' in ls and 'discharge_event' not in secs:
                secs['discharge_event'] = (lineno, ls)
            if 'Estimated power use (mAh)' in ls and 'est_power' not in secs:
                secs['est_power'] = lineno
            if 'All kernel wake locks:' in ls and 'kernel_wl' not in secs:
                secs['kernel_wl'] = lineno
            if 'All partial wake locks:' in ls and 'partial_wl' not in secs:
                secs['partial_wl'] = lineno

    print(f"     Sections found: {list(secs.keys())}")

    # ── Load full file ───────────────────────────────────────────────────────
    print(f"     Loading file...", end=' ', flush=True)
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        all_lines = fh.readlines()
    print(f"{len(all_lines):,} lines")

    bs_line = secs.get('batterystats', 0)
    ep_line = secs.get('est_power', bs_line)
    kw_line = secs.get('kernel_wl', ep_line)
    pw_line = secs.get('partial_wl', kw_line)

    # ── Device & build info ──────────────────────────────────────────────────
    device_info = parse_device_info(all_lines)

    # ── UID map from history header ──────────────────────────────────────────
    uid_map = parse_uid_map(all_lines, bs_line)

    # ── Battery discharge event ──────────────────────────────────────────────
    discharge = {}
    if 'discharge_event' in secs:
        m = re.search(r'\[(\d+),(\d+),(\d+)\]', secs['discharge_event'][1])
        if m:
            dur_ms = int(m.group(1))
            discharge = {
                'duration_ms': dur_ms,
                'start_pct': int(m.group(2)),
                'end_pct': int(m.group(3)),
                'drain_pct': int(m.group(2)) - int(m.group(3)),
                'duration_hr': dur_ms / 3_600_000,
            }

    # ── Estimated power use ──────────────────────────────────────────────────
    power_data = parse_estimated_power(all_lines, ep_line - 1, uid_map)

    # ── Wakelocks ────────────────────────────────────────────────────────────
    kwakelocks = parse_kernel_wakelocks(all_lines, kw_line - 1)
    pwakelocks = parse_partial_wakelocks(all_lines, pw_line - 1)

    # ── Battery metadata ─────────────────────────────────────────────────────
    meta = parse_battery_metadata(all_lines, bs_line)

    # ── Derived drain metrics ────────────────────────────────────────────────
    capacity = thresholds.get('expected_capacity') or power_data['capacity'] or 4647
    # NOTE: dur_hr is re-computed AFTER history fallback (see below)

    # ── Battery history level timeline ───────────────────────────────────────
    print(f"     Parsing battery history...", end=' ', flush=True)
    history, screen_events, wl_events = parse_battery_history(path, bs_line)
    print(f"{len(history)} entries")

    # ── Fallback: derive discharge info from history when event line missing ──
    if history and (not discharge or discharge.get('duration_ms', 0) == 0):
        hs = sorted(history, key=lambda x: x['ms'])
        dur_ms   = hs[-1]['ms']
        start_pct = hs[0]['level']
        end_pct   = hs[-1]['level']
        discharge = {
            'duration_ms': dur_ms,
            'start_pct':   start_pct,
            'end_pct':     end_pct,
            'drain_pct':   start_pct - end_pct,
            'duration_hr': dur_ms / 3_600_000,
        }
        print(f"     (discharge derived from history: "
              f"{start_pct}%→{end_pct}% over {discharge['duration_hr']:.2f}h)")

    # Compute final drain rate (after fallback may have updated discharge)
    dur_hr           = discharge.get('duration_hr', 1)
    drain_mah_per_hr = (power_data['computed_drain'] or 0) / max(dur_hr, 0.01)

    # ── ANR ──────────────────────────────────────────────────────────────────
    print(f"     Scanning ANRs...", end=' ', flush=True)
    anrs = parse_anrs(all_lines)
    print(f"{len(anrs)} found")

    # ── Crashes ──────────────────────────────────────────────────────────────
    print(f"     Scanning crashes...", end=' ', flush=True)
    crashes = parse_crashes(all_lines)
    print(f"{len(crashes)} found")

    # ── LMK ──────────────────────────────────────────────────────────────────
    lmk_events, lmk_count = parse_lmk(all_lines)
    print(f"     LMK events: {len(lmk_events)}  (am_low_memory count: {lmk_count})")

    # ── Thermal ──────────────────────────────────────────────────────────────
    thermal_events, peak_temps, throttle_count = parse_thermal(all_lines)
    print(f"     Thermal throttles: {throttle_count}  peak temps: {peak_temps}")

    # ── Anomaly detection ────────────────────────────────────────────────────
    anomalies = detect_battery_anomalies(
        history, drain_mah_per_hr, capacity,
        expected_drain_mah_hr=thresholds.get('expected_drain'))

    return {
        'label':            label,
        'path':             path,
        'sections':         secs,
        'device_info':      device_info,
        'uid_map':          uid_map,
        'discharge':        discharge,
        'power_data':       power_data,
        'kernel_wakelocks': kwakelocks,
        'partial_wakelocks': pwakelocks,
        'meta':             meta,
        'drain_mah_per_hr': drain_mah_per_hr,
        'history':          history,
        'screen_events':    screen_events,
        'wl_events':        wl_events,
        'anomalies':        anomalies,
        'anrs':             anrs,
        'crashes':          crashes,
        'lmk_events':       lmk_events,
        'lmk_count':        lmk_count,
        'thermal_events':   thermal_events,
        'peak_temps':       peak_temps,
        'throttle_count':   throttle_count,
        'thresholds':       thresholds,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 10 — GRAPH GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def _plot_colors(n):
    cycle = CHART_COLORS
    return [cycle[i % len(cycle)] for i in range(n)]


def generate_individual_graph(data, output_path):
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("  [!] matplotlib not installed — skipping graphs (pip install matplotlib)")
        return False

    history  = data['history']
    label    = data['label']
    discharge= data['discharge']
    power    = data['power_data']
    capacity = power['capacity'] or 4647
    computed = power['computed_drain']
    avg_mah  = data['drain_mah_per_hr']

    if not history:
        print(f"  [!] No history for {label}")
        return False

    h_sorted = sorted(history, key=lambda x: x['ms'])
    # deduplicate for line plot
    plot_pts, prev = [], None
    for p in h_sorted:
        if p['level'] != prev: plot_pts.append(p); prev = p['level']
    times  = [p['ms'] / 3_600_000 for p in plot_pts]
    levels = [p['level']           for p in plot_pts]

    hr_ms = 3_600_000
    max_ms = h_sorted[-1]['ms']
    hr_drains = []
    for hr in range(int(max_ms / hr_ms) + 1):
        sl = _level_at_ms(h_sorted, hr * hr_ms)
        el = _level_at_ms(h_sorted, (hr + 1) * hr_ms)
        drop = sl - el
        mah  = max(0, drop * capacity / 100)
        hr_drains.append((hr + 0.5, mah))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), facecolor='#1a1a2e')
    fig.patch.set_facecolor('#1a1a2e')

    # ── Top: Level % curve ──
    for ax in (ax1, ax2): ax.set_facecolor('#16213e')
    ax1.plot(times, levels, color='#00d4ff', linewidth=2, zorder=3)
    ax1.fill_between(times, levels, alpha=0.15, color='#00d4ff')
    ax1.set_ylim(0, 105)
    ax1.set_yticks(range(0, 101, 10))
    ax1.set_yticklabels([f'{v}%' for v in range(0, 101, 10)])
    ax1.set_xlim(0, max(times) if times else 24)
    ax1.set_ylabel('Battery Level (%)', color='#ccc', fontsize=11)
    ax1.tick_params(colors='#ccc'); ax1.grid(True, color='#333', linestyle='--', alpha=0.5)
    for sp in ax1.spines.values(): sp.set_color('#444')

    # Anomaly highlights
    for an in data['anomalies']:
        ax1.axvspan(an['t_start_hr'], an['t_end_hr'], alpha=0.22, color='red', zorder=2)
        ax1.text(an['t_start_hr'] + 0.1, min(levels) + 2,
                 f"⚠ H{an['hour']+1}\n{an['drain_mah']:.0f}mAh",
                 color='#ff4444', fontsize=7, zorder=5,
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='#330000', alpha=0.8))

    # Hourly drain bars (twin axis)
    ax1b = ax1.twinx()
    bx = [h[0] for h in hr_drains]; by = [h[1] for h in hr_drains]
    _g_thr  = data.get('thresholds', {})
    _g_crit = _g_thr.get('crit_drain', 80.0)
    _g_warn = _g_thr.get('warn_drain', 40.0)
    bc = ['#ff4444' if y > _g_crit else '#ffaa00' if y > _g_warn else '#00aa44' for y in by]
    ax1b.bar(bx, by, width=0.8, alpha=0.35, color=bc, zorder=1)
    ax1b.set_ylabel('Hourly Drain (mAh)', color='#ffaa00', fontsize=9)
    ax1b.tick_params(colors='#ffaa00')
    if avg_mah: ax1b.axhline(avg_mah, color='#ffaa00', linestyle=':', alpha=0.7)
    if _g_thr.get('expected_drain'):
        ax1b.axhline(_g_thr['expected_drain'], color='#00aaff', linestyle='--',
                     alpha=0.85, linewidth=1.5)

    # Screen events
    for t_ms, state in data['screen_events'][:80]:
        ax1.axvline(t_ms / 3_600_000, color='#ffff00' if state == 'on' else '#555500',
                    alpha=0.35, linewidth=0.8, linestyle=':')

    start = data['meta'].get('start_time', '')
    ax1.set_title(
        f"Battery Level — {label}  |  Session start: {start}\n"
        f"Drain: {discharge.get('start_pct',100)}%→{discharge.get('end_pct','?')}%  "
        f"({discharge.get('drain_pct','?')}% = {computed:.0f} mAh / "
        f"{discharge.get('duration_hr',0):.1f} h)  Avg: {avg_mah:.1f} mAh/hr",
        color='white', fontsize=11, pad=8)

    legend_patches = [
        mpatches.Patch(color='#00d4ff', label='Battery %'),
        mpatches.Patch(color='#ff4444', alpha=0.7, label=f'Critical (>{_g_crit:.0f} mAh/hr) ⚠'),
        mpatches.Patch(color='#ffaa00', alpha=0.7, label=f'Warning  (>{_g_warn:.0f} mAh/hr)'),
        mpatches.Patch(color='#00aa44', alpha=0.7, label='Normal'),
        mpatches.Patch(color='#ffff00', alpha=0.5, label='Screen events'),
    ]
    if _g_thr.get('expected_drain'):
        legend_patches.insert(1, mpatches.Patch(
            color='#00aaff', alpha=0.9,
            label=f'Expected {_g_thr["expected_drain"]:.0f} mAh/hr'))
    ax1.legend(handles=legend_patches, loc='upper right', facecolor='#222',
               edgecolor='#555', labelcolor='white', fontsize=8)

    # ── Bottom: Per-UID stacked bar ──
    top_n   = min(15, len(power['per_uid']))
    uids    = power['per_uid'][:top_n]
    xlabels = [f"{u['uid']}\n{u['package'][:22]}" for u in uids]
    totals  = [u['total_mah']      for u in uids]
    cpu_v   = [u.get('cpu', 0)     for u in uids]
    wifi_v  = [u.get('wifi', 0)    for u in uids]
    wl_v    = [u.get('wakelock',0) for u in uids]
    oth_v   = [max(0, t - c - w - wk) for t, c, w, wk in zip(totals, cpu_v, wifi_v, wl_v)]

    xs = range(top_n)
    ax2.bar(xs, cpu_v,  0.65, label='CPU',      color='#e74c3c', alpha=0.9)
    ax2.bar(xs, wifi_v, 0.65, bottom=cpu_v,     label='WiFi',     color='#3498db', alpha=0.9)
    b3_bot = [c + w for c, w in zip(cpu_v, wifi_v)]
    ax2.bar(xs, wl_v,   0.65, bottom=b3_bot,    label='Wakelock', color='#f39c12', alpha=0.9)
    b4_bot = [c + w + wk for c, w, wk in zip(cpu_v, wifi_v, wl_v)]
    ax2.bar(xs, oth_v,  0.65, bottom=b4_bot,    label='Other',    color='#9b59b6', alpha=0.9)

    for xi, t in zip(xs, totals):
        if t > 0.5: ax2.text(xi, t + 0.3, f'{t:.1f}', ha='center', va='bottom',
                              color='white', fontsize=7, fontweight='bold')

    ax2.set_xticks(list(xs)); ax2.set_xticklabels(xlabels, rotation=35, ha='right',
                                                  fontsize=7, color='#ccc')
    ax2.set_ylabel('Power Use (mAh)', color='#ccc', fontsize=11)
    ax2.set_title(f"Per-UID Power Breakdown — {label}  |  Total: {computed:.0f} mAh",
                  color='white', fontsize=11)
    ax2.legend(facecolor='#222', edgecolor='#555', labelcolor='white', fontsize=9, loc='upper right')
    ax2.tick_params(colors='#ccc'); ax2.grid(True, axis='y', color='#333', linestyle='--', alpha=0.5)
    for sp in ax2.spines.values(): sp.set_color('#444')

    plt.tight_layout(pad=2)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()
    print(f"  ✓  Graph: {output_path}")
    return True


def generate_comparison_graph(all_data, output_path, title):
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    n = len(all_data)
    fig, axes = plt.subplots(1, n, figsize=(10 * n, 9), facecolor='#1a1a2e')
    if n == 1: axes = [axes]
    fig.patch.set_facecolor('#1a1a2e')
    fig.suptitle(title, color='white', fontsize=13, fontweight='bold', y=0.98)

    clrs = _plot_colors(n)

    for ax, d, clr in zip(axes, all_data, clrs):
        ax.set_facecolor('#16213e')
        h = d['history']
        if not h: continue
        hs = sorted(h, key=lambda x: x['ms'])
        pp, prev = [], None
        for p in hs:
            if p['level'] != prev: pp.append(p); prev = p['level']
        ts = [p['ms'] / 3_600_000 for p in (pp or hs)]
        lvs = [p['level'] for p in (pp or hs)]
        ax.plot(ts, lvs, color=clr, linewidth=2.5)
        ax.fill_between(ts, lvs, alpha=0.18, color=clr)
        ax.set_ylim(0, 105)
        ax.set_yticks(range(0, 101, 10))
        ax.set_yticklabels([f'{v}%' for v in range(0, 101, 10)])
        ax.set_xlim(0, max(ts))
        ax.set_xlabel('Hours from session start', color='#ccc')
        ax.set_ylabel('Battery Level (%)', color='#ccc')
        ax.tick_params(colors='#ccc')
        for sp in ax.spines.values(): sp.set_color('#444')
        ax.grid(True, color='#333', linestyle='--', alpha=0.5)

        disc = d['discharge']; pd = d['power_data']
        ax.set_title(
            f"{d['label']}\n"
            f"{disc.get('start_pct',100)}%→{disc.get('end_pct','?')}%  "
            f"({disc.get('drain_pct','?')}% = {pd['computed_drain']:.0f} mAh)\n"
            f"{disc.get('duration_hr',0):.1f}h  |  avg {d['drain_mah_per_hr']:.1f} mAh/hr",
            color='white', fontsize=11)

        # Anomaly spans
        for an in d['anomalies']:
            ax.axvspan(an['t_start_hr'], an['t_end_hr'], alpha=0.22, color='red')
            ax.text(an['t_start_hr'] + 0.08, min(lvs) + 1,
                    f"H{an['hour']+1}:{an['drain_mah']:.0f}mAh",
                    color='#ff4444', fontsize=6,
                    bbox=dict(boxstyle='round,pad=0.1', facecolor='#330000', alpha=0.8))

        # Per-hour drain labels
        cap = pd['capacity'] or 4647; avg = d['drain_mah_per_hr']
        max_ms = hs[-1]['ms'] if hs else 0
        for hr in range(min(25, int(max_ms / 3_600_000) + 1)):
            sl = _level_at_ms(hs, hr * 3_600_000)
            el = _level_at_ms(hs, (hr + 1) * 3_600_000)
            mah = max(0, (sl - el) * cap / 100)
            if mah > 0:
                yp = max(min(lvs) + 3, sl - (sl - el) / 2)
                fc = '#440000' if mah > avg * 1.5 else '#333300' if mah > avg else '#003300'
                ax.text(hr + 0.5, yp, f'{mah:.0f}', color='#ffdddd' if mah > avg * 1.5 else '#ddddaa',
                        fontsize=6, ha='center', va='center',
                        bbox=dict(boxstyle='round,pad=0.1', facecolor=fc, alpha=0.65))

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()
    print(f"  ✓  Comparison graph: {output_path}")
    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 11 — HTML REPORT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _html_head(title):
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{CSS}</style>
<!-- Chart.js + zoom/pan plugin (CDN) -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8/hammer.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
<script>
// ── Global error handler ── catches chart init errors without blocking others
window.onerror = function(msg, url, line, col, err) {{
  console.error('[BugReport Analyzer] JS Error:', msg, 'at line', line, err);
  return false;
}};

// ── Global interactive JS ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function(){{

  /* Sidebar TOC */
  const tocBtn = document.getElementById('toc-toggle');
  const toc    = document.getElementById('toc');
  if(tocBtn && toc){{
    tocBtn.onclick = function(){{
      toc.classList.toggle('open');
      document.body.classList.toggle('toc-open');
    }};
  }}

  /* Collapse / expand sections */
  document.querySelectorAll('.section-header').forEach(function(hdr){{
    hdr.onclick = function(){{
      const body = hdr.nextElementSibling;
      body.classList.toggle('hidden');
      hdr.classList.toggle('collapsed');
    }};
  }});

  /* Collapsible event boxes */
  document.querySelectorAll('.evt-header').forEach(function(h){{
    h.onclick = function(){{
      const b = h.nextElementSibling;
      if(b) b.classList.toggle('open');
    }};
  }});

  /* Tabs */
  document.querySelectorAll('.tab-btn').forEach(function(btn){{
    btn.onclick = function(){{
      const group = btn.dataset.group;
      document.querySelectorAll('[data-group="'+group+'"]').forEach(function(b){{
        b.classList.remove('active');
      }});
      document.querySelectorAll('[data-panel="'+group+'"]').forEach(function(p){{
        p.classList.remove('active');
      }});
      btn.classList.add('active');
      const panel = document.getElementById(btn.dataset.target);
      if(panel) panel.classList.add('active');
    }};
  }});

  /* Sortable tables */
  document.querySelectorAll('th[data-sort]').forEach(function(th){{
    th.onclick = function(){{
      const table = th.closest('table');
      const tbody = table.querySelector('tbody');
      const colIdx = Array.from(th.parentNode.children).indexOf(th);
      const dir    = th.classList.contains('sort-asc') ? -1 : 1;
      table.querySelectorAll('th').forEach(function(t){{ t.classList.remove('sort-asc','sort-desc'); }});
      th.classList.add(dir===1?'sort-asc':'sort-desc');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort(function(a,b){{
        const av = a.cells[colIdx]?a.cells[colIdx].dataset.sort||a.cells[colIdx].innerText:'';
        const bv = b.cells[colIdx]?b.cells[colIdx].dataset.sort||b.cells[colIdx].innerText:'';
        const an = parseFloat(av), bn = parseFloat(bv);
        if(!isNaN(an)&&!isNaN(bn)) return (an-bn)*dir;
        return av.localeCompare(bv)*dir;
      }});
      rows.forEach(function(r){{ tbody.appendChild(r); }});
    }};
  }});

  /* Table text filter */
  document.querySelectorAll('.tbl-filter input[data-target]').forEach(function(inp){{
    inp.oninput = function(){{
      const tbl   = document.getElementById(inp.dataset.target);
      if(!tbl) return;
      const val   = inp.value.toLowerCase();
      tbl.querySelectorAll('tbody tr').forEach(function(r){{
        r.classList.toggle('filtered-out', !r.innerText.toLowerCase().includes(val));
      }});
    }};
  }});

  /* Table column filter (select) */
  document.querySelectorAll('.tbl-filter select[data-target]').forEach(function(sel){{
    sel.onchange = function(){{
      const tbl = document.getElementById(sel.dataset.target);
      if(!tbl) return;
      const colIdx = parseInt(sel.dataset.col||'0');
      const val    = sel.value;
      tbl.querySelectorAll('tbody tr').forEach(function(r){{
        if(!val){{ r.classList.remove('filtered-out'); return; }}
        const cell = r.cells[colIdx];
        r.classList.toggle('filtered-out', !(cell&&cell.innerText.toLowerCase().includes(val.toLowerCase())));
      }});
    }};
  }});

  /* TOC active link on scroll */
  const allSections = document.querySelectorAll('.section[id]');
  const tocLinks    = document.querySelectorAll('#toc a');
  window.addEventListener('scroll',function(){{
    let cur='';
    allSections.forEach(function(s){{
      if(s.getBoundingClientRect().top<120) cur=s.id;
    }});
    tocLinks.forEach(function(a){{
      a.classList.toggle('active', a.getAttribute('href')==='#'+cur);
    }});
  }});

  /* Summary pill click → scroll to RCA */
  const pill = document.getElementById('summary-pill');
  if(pill) pill.onclick=function(){{
    const rca = document.getElementById('rca');
    if(rca) rca.scrollIntoView({{behavior:'smooth'}});
  }};

}});

/* ── Chart helpers ── */
function makeLineChart(canvasId, labels, datasets, opts){{
  const ctx = document.getElementById(canvasId);
  if(!ctx) return null;
  return new Chart(ctx,{{
    type:'line',
    data:{{labels:labels, datasets:datasets}},
    options:Object.assign({{
      responsive:true,
      animation:{{duration:400}},
      interaction:{{mode:'index',intersect:false}},
      plugins:{{
        legend:{{labels:{{color:'#ccc',font:{{size:11}}}}}},
        tooltip:{{
          backgroundColor:'#1a1a3e',
          borderColor:'#00d4ff',
          borderWidth:1,
          titleColor:'#00d4ff',
          bodyColor:'#e0e0e0',
          callbacks:{{}}
        }},
        zoom:{{
          pan:{{enabled:true,mode:'x'}},
          zoom:{{
            wheel:{{enabled:true}},
            pinch:{{enabled:true}},
            mode:'x',
            onZoom: function(ctx){{
              const btn = document.querySelector('[data-reset="'+canvasId+'"]');
              if(btn) btn.style.display='inline-block';
            }}
          }}
        }}
      }},
      scales:{{
        x:{{ticks:{{color:'#99aabb',maxRotation:30}},grid:{{color:'#1e1e3a'}}}},
        y:{{ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}}
      }}
    }}, opts||{{}})
  }});
}}

function makeBarChart(canvasId, labels, datasets, opts){{
  const ctx = document.getElementById(canvasId);
  if(!ctx) return null;
  return new Chart(ctx,{{
    type:'bar',
    data:{{labels:labels, datasets:datasets}},
    options:Object.assign({{
      responsive:true,
      animation:{{duration:400}},
      interaction:{{mode:'index',intersect:false}},
      plugins:{{
        legend:{{labels:{{color:'#ccc',font:{{size:11}}}}}},
        tooltip:{{
          backgroundColor:'#1a1a3e',borderColor:'#00d4ff',borderWidth:1,
          titleColor:'#00d4ff',bodyColor:'#e0e0e0'
        }}
      }},
      scales:{{
        x:{{ticks:{{color:'#99aabb',maxRotation:40}},grid:{{color:'#1e1e3a'}}}},
        y:{{ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}}
      }}
    }},opts||{{}})
  }});
}}

function makePieChart(canvasId, labels, values, colors){{
  const ctx = document.getElementById(canvasId);
  if(!ctx) return null;
  return new Chart(ctx,{{
    type:'doughnut',
    data:{{labels:labels,datasets:[{{data:values,backgroundColor:colors,borderColor:'#111127',borderWidth:2}}]}},
    options:{{
      responsive:true,
      animation:{{duration:400}},
      plugins:{{
        legend:{{position:'right',labels:{{color:'#ccc',font:{{size:11}},boxWidth:14}}}},
        tooltip:{{
          backgroundColor:'#1a1a3e',borderColor:'#00d4ff',borderWidth:1,
          titleColor:'#00d4ff',bodyColor:'#e0e0e0',
          callbacks:{{
            label:function(ctx){{
              const total=ctx.dataset.data.reduce(function(a,b){{return a+b;}},0);
              const pct=total?((ctx.parsed/total)*100).toFixed(1):'0';
              return ctx.label+': '+ctx.parsed.toFixed(2)+' mAh ('+pct+'%)';
            }}
          }}
        }}
      }}
    }}
  }});
}}
</script>
</head><body>
<button id="toc-toggle">☰ TOC</button>
<nav id="toc"><h3>Sections</h3>
__TOC_LINKS__
</nav>"""


def _kpi(value, label, css_class=''):
    return (f'<div class="kpi-card">'
            f'<div class="kpi-value {css_class}">{value}</div>'
            f'<div class="kpi-label">{label}</div></div>')


def _bar(val, max_val, cls=''):
    pct = min(100, round(val / max_val * 100)) if max_val > 0 else 0
    return f'<div class="bar-wrap"><div class="bar-fill {cls}" style="width:{pct}%"></div></div>'


def _table(headers, rows, row_class_fn=None):
    th = ''.join(f'<th>{h}</th>' for h in headers)
    trs = ''
    for r in rows:
        cls = row_class_fn(r) if row_class_fn else ''
        tds = ''.join(f'<td>{c}</td>' for c in r)
        trs += f'<tr class="{cls}">{tds}</tr>'
    return f'<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'


def _duration_badge(sec, warn=3600, crit=43200):
    """Colour-code a duration (seconds)."""
    h = int(sec // 3600); mi = int((sec % 3600) // 60); s = int(sec % 60)
    txt = f'{h}h {mi}m {s}s' if h else f'{mi}m {s}s'
    cls = 'critical' if sec >= crit else 'high' if sec >= warn else 'normal'
    return f'{txt} {_badge(cls.upper(), cls)}'


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 12 — INDIVIDUAL HTML REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def generate_individual_report(data, graph_filename, output_path, all_labels):
    """Generate a fully interactive individual HTML report for one bugreport."""
    d    = data
    lbl  = d['label']
    di   = d['device_info']
    disc = d['discharge']
    pw   = d['power_data']
    cap  = pw['capacity'] or 4647
    computed = pw['computed_drain']
    avg_mah  = d['drain_mah_per_hr']
    dur_hr   = disc.get('duration_hr', 0)

    thr        = d.get('thresholds', {})
    _crit_dr   = thr.get('crit_drain',  80.0)
    _warn_dr   = thr.get('warn_drain',  40.0)
    _exp_dr    = thr.get('expected_drain')
    _exp_hrs   = thr.get('expected_hours')
    _min_anr   = thr.get('min_anr',   1)
    _min_crash = thr.get('min_crash', 1)
    _min_lmk   = thr.get('min_lmk',  5)
    _crit_tmp  = thr.get('crit_temp', 80.0)
    _warn_tmp  = thr.get('warn_temp', 45.0)
    drain_cls = 'red' if avg_mah > _crit_dr else 'orange' if avg_mah > _warn_dr else 'green'

    # ── TOC links ─────────────────────────────────────────────────────────────
    toc_sections = [
        ('battery',  '🔋 Battery Overview'),
        ('hourly',   '📊 Hourly Discharge'),
        ('power',    '⚡ Power Use (UID)'),
        ('power_pie','🥧 Power Distribution'),
        ('kwl',      '🔒 Kernel Wakelocks'),
        ('pwl',      '📱 App Wakelocks'),
        ('anr',      '🚫 ANR Events'),
        ('crash',    '💥 Crashes'),
        ('lmk',      '🗑 LMK Events'),
        ('thermal',  '🌡 Thermal'),
        ('rca',      '🔍 Root Cause'),
    ]
    toc_html = '\n'.join(f'<a href="#{sid}">{sname}</a>' for sid, sname in toc_sections)

    nav_links = [f'<a href="{x}_Individual_Report.html">{x}</a>' for x in all_labels if x != lbl]
    if len(all_labels) > 1:
        nav_links.append('<a href="Comparative_Report.html">📊 Comparative</a>')

    # ── Battery history data (for Chart.js) ───────────────────────────────────
    h_sorted = sorted(d['history'], key=lambda x: x['ms']) if d['history'] else []
    # level timeline (deduplicated)
    plot_pts, prev = [], None
    for p in h_sorted:
        if p['level'] != prev:
            plot_pts.append(p); prev = p['level']
    chart_times  = [round(p['ms'] / 3_600_000, 3) for p in (plot_pts or h_sorted)]
    chart_levels = [p['level'] for p in (plot_pts or h_sorted)]
    chart_volts  = [p.get('volt', 0) for p in (plot_pts or h_sorted)]

    # hourly data
    hr_ms = 3_600_000
    max_ms = h_sorted[-1]['ms'] if h_sorted else 0
    hr_labels, hr_drain_mah, hr_drain_pct = [], [], []
    for hr in range(int(max_ms / hr_ms) + 1):
        sl = _level_at_ms(h_sorted, hr * hr_ms)
        el = _level_at_ms(h_sorted, (hr + 1) * hr_ms)
        drop = sl - el
        mah  = max(0, drop * cap / 100)
        hr_labels.append(f'H{hr+1}')
        hr_drain_mah.append(round(mah, 2))
        hr_drain_pct.append(drop)

    # bar colours for hourly chart
    hr_colors = []
    for m in hr_drain_mah:
        if m > _crit_dr:
            hr_colors.append('#ff4444')
        elif m > _warn_dr:
            hr_colors.append('#ffaa00')
        else:
            hr_colors.append('#00aa44')

    # anomaly annotations list (for chart reference lines)
    anomaly_hr_list = [str(a['hour']) for a in d['anomalies']]

    # per-uid power chart data (top 15)
    top_uids    = pw['per_uid'][:15]
    uid_labels  = [f"{u['uid']} | {u['package'][:20]}" for u in top_uids]
    uid_cpu     = [round(u.get('cpu', 0), 2)      for u in top_uids]
    uid_wifi    = [round(u.get('wifi', 0), 2)     for u in top_uids]
    uid_wl      = [round(u.get('wakelock', 0), 2) for u in top_uids]
    uid_other   = [round(max(0, u['total_mah'] - u.get('cpu',0) - u.get('wifi',0) - u.get('wakelock',0)), 2) for u in top_uids]
    uid_total   = [round(u['total_mah'], 2) for u in top_uids]

    # power pie data (top 10 by uid, rest grouped)
    pie_labels_raw = [u['package'][:26] for u in pw['per_uid'][:10]]
    pie_vals_raw   = [round(u['total_mah'], 2) for u in pw['per_uid'][:10]]
    if len(pw['per_uid']) > 10:
        rest = sum(u['total_mah'] for u in pw['per_uid'][10:])
        pie_labels_raw.append('Other')
        pie_vals_raw.append(round(rest, 2))
    pie_colors = CHART_COLORS[:len(pie_labels_raw)]

    # global power component pie
    glob = pw['global']
    g_labels = [k.capitalize() for k in glob]
    g_vals   = [round(v, 2) for v in glob.values()]
    g_colors = CHART_COLORS[:len(g_labels)]

    # wakelock bar chart
    kwl_sorted = sorted(d['kernel_wakelocks'], key=lambda x: x['duration_sec'], reverse=True)[:15]
    kwl_names  = [w['name'][:30] for w in kwl_sorted]
    kwl_secs   = [round(w['duration_sec'], 0) for w in kwl_sorted]
    kwl_counts = [w['count'] for w in kwl_sorted]

    pwl_sorted = sorted(d['partial_wakelocks'], key=lambda x: x['duration_sec'], reverse=True)[:15]
    pwl_names  = [f"{w['uid']}:{w['name'][:22]}" for w in pwl_sorted]
    pwl_secs   = [round(w['duration_sec'], 0) for w in pwl_sorted]
    pwl_counts = [w['count'] for w in pwl_sorted]

    # screen events for annotation overlay
    screen_on_hrs  = [round(t / 3_600_000, 3) for t, st in d['screen_events'] if st == 'on']
    screen_off_hrs = [round(t / 3_600_000, 3) for t, st in d['screen_events'] if st == 'off']

    # ── Build HTML ─────────────────────────────────────────────────────────────
    html = _html_head(f"BugReport Analysis — {lbl}").replace('__TOC_LINKS__', toc_html)

    html += f"""
<div class="header">
  <h1>🔋 Android BugReport Analysis — {lbl}</h1>
  <div class="subtitle">
    {di.get('model','Unknown Device')} &nbsp;|&nbsp;
    Android {di.get('android_ver','?')} (SDK {di.get('sdk','?')}) &nbsp;|&nbsp;
    Build: <strong>{di.get('build','?')}</strong><br>
    Kernel: {di.get('kernel','?')} &nbsp;|&nbsp;
    Serial: {di.get('serial','?')} &nbsp;|&nbsp;
    Session start: {d['meta'].get('start_time','?')}
  </div>
</div>
<div class="nav">{''.join(nav_links)}</div>
"""

    # ── 1. Battery Overview ───────────────────────────────────────────────────
    html += '<div class="section" id="battery">'
    html += '''<div class="section-header"><h2>🔋 Battery Overview</h2><span class="toggle-icon">▼</span></div>'''
    html += '<div class="section-body">'
    html += '<div class="kpi-grid">'
    html += _kpi(f"{disc.get('start_pct',100)}% → {disc.get('end_pct','?')}%", "Total Drain")
    html += _kpi(f"{computed:.0f} mAh", "Computed Drain",
                 'red' if computed > 1500 else 'orange' if computed > 600 else 'green')
    html += _kpi(f"{avg_mah:.1f} mAh/hr", "Avg Drain Rate", drain_cls)
    html += _kpi(f"{dur_hr:.1f} h", "Session Duration")
    html += _kpi(f"{cap} mAh", "Battery Capacity")
    html += _kpi(f"{len(d['anomalies'])}", "Anomaly Hours",
                 'red' if d['anomalies'] else 'green')
    html += _kpi(f"{disc.get('drain_pct','?')}%", "Drain %",
                 'red' if disc.get('drain_pct', 0) > 30 else 'orange' if disc.get('drain_pct', 0) > 15 else 'green')
    html += _kpi(f"{pw.get('computed_drain',0)/max(cap,1)*100:.1f}%", "% of Capacity", '')
    html += '</div>'

    # Battery level timeline chart with controls
    html += f'''
<div class="chart-wrap">
  <div class="chart-toolbar">
    <label>View:</label>
    <button class="active" onclick="setBatteryView('level',this)">🔋 Level %</button>
    <button onclick="setBatteryView('voltage',this)">⚡ Voltage (mV)</button>
    <button onclick="setBatteryView('both',this)">Both</button>
    &nbsp;|&nbsp;
    <label>Overlay:</label>
    <button onclick="toggleScreenOverlay()" id="screen-overlay-btn">📱 Screen Events</button>
    <button onclick="toggleAnomalyOverlay()" id="anomaly-overlay-btn">⚠ Anomalies</button>
    &nbsp;|&nbsp;
    <button onclick="batteryChart.resetZoom(); document.querySelector(\"[data-reset='batteryChartCanvas']\").style.display='none'">🔍 Reset Zoom</button>
    <button data-reset="batteryChartCanvas" style="display:none;background:#ff4444;color:#fff;border-color:#ff4444" onclick="batteryChart.resetZoom();this.style.display='none'">Reset Zoom ✕</button>
  </div>
  <canvas id="batteryChartCanvas" height="110"></canvas>
  <p class="chart-hint">🖱 Scroll to zoom • Drag to pan • Click legend to toggle series • Hover for details</p>
</div>
'''

    # Anomaly detail cards
    if d['anomalies']:
        html += '<h3>⚠ Elevated Drain Hours (click to expand)</h3>'
        for an in d['anomalies']:
            html += f'''<div class="evt-box anr">
  <div class="evt-header">
    <span style="color:#ff6666">⚠ Hour {an['hour']+1}
      &nbsp;(T+{an['t_start_hr']:.0f}h – T+{an['t_end_hr']:.0f}h)</span>
    <span style="color:#ff4444;font-weight:700">{an['drain_mah']:.0f} mAh
      ({an['drain_pct']}%) — {an['vs_avg']:.1f}× avg</span>
  </div>
  <div class="evt-body">
    <p>Drain this hour: <strong>{an['drain_mah']:.0f} mAh</strong> ({an['drain_pct']}%)
       &nbsp;|&nbsp; vs average: <strong style="color:#ff4444">{an['vs_avg']:.1f}×</strong>
       &nbsp;|&nbsp; avg = {avg_mah:.1f} mAh/hr</p>
    <p style="margin-top:6px;color:#778899">Battery fell from ~{an['drain_pct']+int(disc.get('end_pct',0))}%
       level area during this window. Check wakelock and CPU activity for this hour.</p>
  </div>
</div>'''
    html += '</div></div>'  # section-body + section

    # ── 2. Hourly Discharge Chart ─────────────────────────────────────────────
    html += '<div class="section" id="hourly">'
    html += '''<div class="section-header"><h2>📊 Hourly Discharge Analysis</h2><span class="toggle-icon">▼</span></div>'''
    html += '<div class="section-body">'
    html += f'''
<div class="chart-wrap">
  <div class="chart-toolbar">
    <label>Metric:</label>
    <button class="active" onclick="setHourlyMetric('mah',this)">mAh</button>
    <button onclick="setHourlyMetric('pct',this)">%</button>
    &nbsp;|&nbsp;
    <label>Sort:</label>
    <button onclick="sortHourly('desc',this)">Highest First</button>
    <button onclick="sortHourly('asc',this)">Lowest First</button>
    <button class="active" onclick="sortHourly('orig',this)">Chronological</button>
    &nbsp;|&nbsp;
    <label>Threshold: <span class="range-val" id="threshold-val">{avg_mah:.0f}</span> mAh</label>
    <input type="range" id="threshold-range" min="0" max="{max(hr_drain_mah or [avg_mah*2, 1]):.0f}"
           value="{avg_mah:.0f}" step="1"
           oninput="updateThreshold(this.value)">
  </div>
  <canvas id="hourlyChartCanvas" height="85"></canvas>
  <p class="chart-hint">Red bars = above threshold. Hover for exact values. Use metric buttons to switch between mAh and % drain.</p>
</div>

<h3>Hourly Discharge Table</h3>
<div class="tbl-filter">
  <input type="text" placeholder="🔍 Filter hours..." data-target="hourly-table">
  <select data-target="hourly-table" data-col="2">
    <option value="">All severity</option>
    <option value="🔴">🔴 High</option>
    <option value="🟡">🟡 Medium</option>
    <option value="🟢">🟢 Normal</option>
  </select>
</div>
<div class="tbl-wrap">
<table id="hourly-table">
  <thead><tr>
    <th data-sort>Hour</th>
    <th data-sort>mAh Drain</th>
    <th data-sort>% Drain</th>
    <th data-sort>Status</th>
    <th data-sort>vs Average</th>
  </tr></thead>
  <tbody>
'''
    for i, (mah, pct) in enumerate(zip(hr_drain_mah, hr_drain_pct)):
        ratio = mah / avg_mah if avg_mah > 0 else 0
        if mah > avg_mah * 1.5:
            status = '🔴 High'
            row_cls = 'critical'
        elif mah > avg_mah:
            status = '🟡 Medium'
            row_cls = 'high'
        else:
            status = '🟢 Normal'
            row_cls = ''
        html += f'<tr class="{row_cls}"><td data-sort="{i}">{hr_labels[i]}</td>'
        html += f'<td data-sort="{mah:.2f}">{mah:.2f} mAh</td>'
        html += f'<td data-sort="{pct:.1f}">{pct:.1f}%</td>'
        html += f'<td>{status}</td>'
        html += f'<td data-sort="{ratio:.2f}">{ratio:.2f}×</td></tr>\n'
    html += '</tbody></table></div></div></div>'

    # ── 3. Estimated Power Use per UID ────────────────────────────────────────
    html += '<div class="section" id="power">'
    html += '''<div class="section-header"><h2>⚡ Estimated Power Use (per UID)</h2><span class="toggle-icon">▼</span></div>'''
    html += '<div class="section-body">'
    html += '''
<div class="tabs">
  <button class="tab-btn active" data-group="power-tabs" data-target="power-chart-tab">📊 Chart</button>
  <button class="tab-btn" data-group="power-tabs" data-target="power-table-tab">📋 Table</button>
</div>
<div id="power-chart-tab" class="tab-panel active">
'''
    html += f'''
<div class="chart-wrap">
  <div class="chart-toolbar">
    <label>Components:</label>
    <button class="active" onclick="setPowerView('stacked',this)">Stacked</button>
    <button onclick="setPowerView('grouped',this)">Grouped</button>
    <button onclick="setPowerView('total',this)">Total Only</button>
    &nbsp;|&nbsp;
    <label>Top N:</label>
    <select onchange="filterTopN(parseInt(this.value))">
      <option value="5">Top 5</option>
      <option value="10" selected>Top 10</option>
      <option value="15">Top 15</option>
    </select>
  </div>
  <canvas id="powerBarCanvas" height="95"></canvas>
  <p class="chart-hint">Hover for component breakdown. Click legend to show/hide components.</p>
</div>
</div>
<div id="power-table-tab" class="tab-panel">
'''
    if pw['per_uid']:
        max_mah = pw['per_uid'][0]['total_mah']
        html += '''<div class="tbl-filter">
  <input type="text" placeholder="🔍 Filter by UID or package..." data-target="power-table">
  <select data-target="power-table" data-col="2">
    <option value="">All</option>
    <option value="critical">High Drain</option>
  </select>
</div><div class="tbl-wrap">'''
        html += '<table id="power-table"><thead><tr>'
        for h in ['UID', 'Package', 'Total (mAh)', 'CPU (mAh)', 'WiFi (mAh)', 'Wakelock (mAh)', 'Sensors (mAh)']:
            html += f'<th data-sort>{h}</th>'
        html += '</tr></thead><tbody>'
        for u in pw['per_uid'][:30]:
            t = u['total_mah']
            sev_cls = 'critical' if t > avg_mah else 'high' if t > avg_mah * 0.5 else ''
            pct_of_total = t / computed * 100 if computed > 0 else 0
            html += f'<tr class="{sev_cls}">'
            html += f'<td data-sort="{u["uid"]}">{u["uid"]}</td>'
            html += f'<td>{_esc(u["package"])}</td>'
            html += f'<td data-sort="{t:.4f}">{t:.2f}{_bar(t, max_mah, "red" if t > avg_mah else "orange" if t > avg_mah * 0.5 else "")}<small style="color:#556677"> {pct_of_total:.1f}%</small></td>'
            html += f'<td data-sort="{u.get("cpu",0):.4f}">{u.get("cpu",0):.2f}</td>'
            html += f'<td data-sort="{u.get("wifi",0):.4f}">{u.get("wifi",0):.2f}</td>'
            html += f'<td data-sort="{u.get("wakelock",0):.4f}">{u.get("wakelock",0):.2f}</td>'
            html += f'<td data-sort="{u.get("sensors",0):.4f}">{u.get("sensors",0):.2f}</td>'
            html += '</tr>\n'
        html += '</tbody></table></div>'
    html += '</div></div></div>'  # power-table-tab, section-body, section

    # ── 4. Power Distribution Pie ─────────────────────────────────────────────
    html += '<div class="section" id="power_pie">'
    html += '''<div class="section-header"><h2>🥧 Power Distribution</h2><span class="toggle-icon">▼</span></div>'''
    html += '<div class="section-body">'
    html += '''
<div class="tabs">
  <button class="tab-btn active" data-group="pie-tabs" data-target="pie-uid-tab">By UID</button>
  <button class="tab-btn" data-group="pie-tabs" data-target="pie-component-tab">By Component</button>
</div>
<div id="pie-uid-tab" class="tab-panel active">
<div class="chart-wrap"><canvas id="powerPieCanvas" height="55"></canvas>
<p class="chart-hint">Hover slices for mAh and %. Click legend to toggle.</p></div>
</div>
<div id="pie-component-tab" class="tab-panel">
<div class="chart-wrap"><canvas id="globalPieCanvas" height="55"></canvas>
<p class="chart-hint">Global power breakdown by component type.</p></div>
</div>
'''
    html += '</div></div>'

    # ── 5. Kernel Wakelocks ───────────────────────────────────────────────────
    html += '<div class="section" id="kwl">'
    html += '''<div class="section-header"><h2>🔒 Kernel Wakelocks</h2><span class="toggle-icon">▼</span></div>'''
    html += '<div class="section-body">'
    if d['kernel_wakelocks']:
        html += '''
<div class="chart-wrap">
  <div class="chart-toolbar">
    <label>View:</label>
    <button class="active" onclick="setKwlView('duration',this)">Duration (s)</button>
    <button onclick="setKwlView('count',this)">Count</button>
  </div>
  <canvas id="kwlChartCanvas" height="75"></canvas>
  <p class="chart-hint">Click bar to highlight row in table. Hover for details.</p>
</div>
'''
        max_sec = max((w['duration_sec'] for w in d['kernel_wakelocks']), default=1)
        html += '''<div class="tbl-filter"><input type="text" placeholder="🔍 Filter wakelocks..." data-target="kwl-table"></div>'''
        html += '<div class="tbl-wrap"><table id="kwl-table"><thead><tr>'
        for h in ['Wakelock Name', 'Duration', 'Count', 'Hold %']:
            html += f'<th data-sort>{h}</th>'
        html += '</tr></thead><tbody>'
        for w in d['kernel_wakelocks']:
            hold_pct = w['duration_sec'] / max(dur_hr * 3600, 1) * 100
            row_cls  = 'critical' if w['duration_sec'] > dur_hr * 3600 * 0.5 else 'high' if w['duration_sec'] > dur_hr * 3600 * 0.2 else ''
            html += f'<tr class="{row_cls}"><td>{_esc(w["name"])}</td>'
            html += f'<td data-sort="{w["duration_sec"]:.0f}">{_duration_badge(w["duration_sec"], 3600, dur_hr*3600*0.5)}</td>'
            html += f'<td data-sort="{w["count"]}">{w["count"]:,}</td>'
            html += f'<td data-sort="{hold_pct:.2f}">{hold_pct:.1f}%{_bar(hold_pct, 100, "red" if hold_pct > 50 else "orange" if hold_pct > 20 else "")}</td></tr>\n'
        html += '</tbody></table></div>'
    else:
        html += '<p style="color:#00cc66">✅ No kernel wakelocks found.</p>'
    html += '</div></div>'

    # ── 6. Partial (App) Wakelocks ────────────────────────────────────────────
    html += '<div class="section" id="pwl">'
    html += '''<div class="section-header"><h2>📱 App (Partial) Wakelocks</h2><span class="toggle-icon">▼</span></div>'''
    html += '<div class="section-body">'
    if d['partial_wakelocks']:
        html += '''
<div class="chart-wrap">
  <div class="chart-toolbar">
    <label>View:</label>
    <button class="active" onclick="setPwlView('duration',this)">Duration (s)</button>
    <button onclick="setPwlView('count',this)">Count</button>
  </div>
  <canvas id="pwlChartCanvas" height="75"></canvas>
</div>
'''
        html += '''<div class="tbl-filter">
  <input type="text" placeholder="🔍 Filter by UID or name..." data-target="pwl-table">
  <select data-target="pwl-table" data-col="0">
    <option value="">All UIDs</option>
'''
        seen_uids = []
        for w in d['partial_wakelocks']:
            if w['uid'] not in seen_uids:
                seen_uids.append(w['uid'])
                html += f'<option value="{w["uid"]}">{w["uid"]}</option>\n'
        html += '</select></div>'
        html += '<div class="tbl-wrap"><table id="pwl-table"><thead><tr>'
        for h in ['UID', 'Wakelock Name', 'Duration', 'Count', 'Hold %']:
            html += f'<th data-sort>{h}</th>'
        html += '</tr></thead><tbody>'
        pwl_display = sorted(d['partial_wakelocks'], key=lambda x: x['duration_sec'], reverse=True)[:40]
        max_pwl = pwl_display[0]['duration_sec'] if pwl_display else 1
        for w in pwl_display:
            hold_pct = w['duration_sec'] / max(dur_hr * 3600, 1) * 100
            row_cls  = 'critical' if w['duration_sec'] > dur_hr * 3600 * 0.5 else 'high' if w['duration_sec'] > dur_hr * 3600 * 0.2 else ''
            html += f'<tr class="{row_cls}"><td data-sort="{_esc(w["uid"])}">{_esc(w["uid"])}</td>'
            html += f'<td>{_esc(w["name"])}</td>'
            html += f'<td data-sort="{w["duration_sec"]:.0f}">{_duration_badge(w["duration_sec"], 3600, dur_hr*3600*0.5)}</td>'
            html += f'<td data-sort="{w["count"]}">{w["count"]:,}</td>'
            html += f'<td data-sort="{hold_pct:.2f}">{hold_pct:.1f}%{_bar(hold_pct, 100, "red" if hold_pct>50 else "orange" if hold_pct>20 else "")}</td></tr>\n'
        html += '</tbody></table></div>'
    else:
        html += '<p style="color:#00cc66">✅ No partial wakelocks found.</p>'
    html += '</div></div>'

    # ── 7. ANR ────────────────────────────────────────────────────────────────
    html += f'<div class="section" id="anr">'
    html += f'''<div class="section-header"><h2>🚫 ANR Events ({len(d["anrs"])})</h2><span class="toggle-icon">▼</span></div>'''
    html += '<div class="section-body">'
    if d['anrs']:
        html += '''<div class="tbl-filter">
  <input type="text" placeholder="🔍 Filter ANRs..." data-target="anr-table">
  <select data-target="anr-table" data-col="2">
    <option value="">All sources</option>
    <option value="ActivityManager">ActivityManager</option>
    <option value="DropBox">DropBox</option>
    <option value="logcat">logcat</option>
  </select>
</div>
<div class="tbl-wrap">
<table id="anr-table"><thead><tr>
  <th data-sort>Time</th><th data-sort>Process</th><th data-sort>Source</th><th>Reason</th><th>Trace</th>
</tr></thead><tbody>'''
        for a in d['anrs'][:40]:
            has_trace = bool(a.get('trace'))
            trace_id = f'anr-trace-{id(a)}'
            html += f'<tr><td>{_esc(a["time"])}</td><td>{_esc(a["process"])}</td>'
            html += f'<td>{_badge(a["source"],"info")}</td>'
            html += f'<td style="font-size:11px">{_esc(a["reason"][:200])}</td>'
            html += f'<td>'
            if has_trace:
                html += f'<button onclick="document.getElementById(\'{trace_id}\').classList.toggle(\'open\')" style="background:#1a1a3e;color:#00d4ff;border:1px solid #00d4ff;border-radius:4px;padding:2px 8px;font-size:11px;cursor:pointer">▶ Trace</button>'
                html += f'<div id="{trace_id}" class="evt-body" style="background:#200000"><pre>{_esc(a["trace"][:800])}</pre></div>'
            else:
                html += '—'
            html += '</td></tr>\n'
        html += '</tbody></table></div>'
    else:
        html += '<p style="color:#00cc66">✅ No ANRs detected.</p>'
    html += '</div></div>'

    # ── 8. Crashes ────────────────────────────────────────────────────────────
    html += f'<div class="section" id="crash">'
    html += f'''<div class="section-header"><h2>💥 Crashes ({len(d["crashes"])})</h2><span class="toggle-icon">▼</span></div>'''
    html += '<div class="section-body">'
    if d['crashes']:
        html += '''<div class="tbl-filter">
  <input type="text" placeholder="🔍 Filter crashes..." data-target="crash-table">
  <select data-target="crash-table" data-col="1">
    <option value="">All types</option>
    <option value="Java FATAL">Java FATAL</option>
    <option value="Native">Native Crash</option>
    <option value="Process Died">Process Died</option>
    <option value="DropBox">DropBox</option>
  </select>
</div>
<div class="tbl-wrap">
<table id="crash-table"><thead><tr>
  <th data-sort>Time</th><th data-sort>Type</th><th data-sort>Process</th><th>Signal</th><th>Trace</th>
</tr></thead><tbody>'''
        for c in d['crashes'][:40]:
            has_trace = bool(c.get('trace'))
            trace_id = f'crash-trace-{id(c)}'
            sev_cls = 'critical' if 'FATAL' in c['type'] or 'Native' in c['type'] else 'high'
            html += f'<tr class="{sev_cls}"><td>{_esc(c["time"])}</td>'
            html += f'<td>{_badge(c["type"],"critical" if "FATAL" in c["type"] or "Native" in c["type"] else "high")}</td>'
            html += f'<td>{_esc(c["process"])}</td>'
            html += f'<td style="font-size:11px">{_esc(c["signal"][:80])}</td>'
            html += f'<td>'
            if has_trace:
                html += f'<button onclick="document.getElementById(\'{trace_id}\').classList.toggle(\'open\')" style="background:#1a0010;color:#ff44aa;border:1px solid #ff44aa;border-radius:4px;padding:2px 8px;font-size:11px;cursor:pointer">▶ Trace</button>'
                html += f'<div id="{trace_id}" class="evt-body" style="background:#1a0010"><pre>{_esc(c["trace"][:800])}</pre></div>'
            else:
                html += '—'
            html += '</td></tr>\n'
        html += '</tbody></table></div>'
    else:
        html += '<p style="color:#00cc66">✅ No crashes detected.</p>'
    html += '</div></div>'

    # ── 9. LMK ────────────────────────────────────────────────────────────────
    lmk_badge = _badge(f"{len(d['lmk_events'])} kills", 'high' if d['lmk_events'] else 'normal')
    html += f'<div class="section" id="lmk">'
    html += f'<div class="section-header"><h2>🗑 Low Memory Killer (LMK) {lmk_badge}</h2><span class="toggle-icon">▼</span></div>'
    html += '<div class="section-body">'
    if d['lmk_events']:
        html += '''<div class="tbl-filter">
  <input type="text" placeholder="🔍 Filter by process..." data-target="lmk-table">
  <select data-target="lmk-table" data-col="4">
    <option value="">All sources</option>
    <option value="kernel LMK">Kernel LMK</option>
    <option value="ActivityManager">ActivityManager</option>
  </select>
</div>
<div class="tbl-wrap">
<table id="lmk-table"><thead><tr>
  <th data-sort>Time</th><th data-sort>Process</th><th data-sort>RSS</th><th data-sort>ADJ</th><th data-sort>Source</th>
</tr></thead><tbody>'''
        for e in d['lmk_events'][:50]:
            html += f'<tr><td>{_esc(e["time"])}</td><td>{_esc(e["process"])}</td>'
            html += f'<td data-sort="{e["size_kb"]}">{e["size_kb"]:,} KB' if e['size_kb'] else '<td>—'
            html += f'</td><td>{_esc(str(e.get("adj","—")))}</td><td>{_esc(e["source"])}</td></tr>\n'
        html += '</tbody></table></div>'
    else:
        html += '<p style="color:#00cc66">✅ No LMK events detected.</p>'
    html += '</div></div>'

    # ── 10. Thermal ───────────────────────────────────────────────────────────
    throttle_badge = _badge(f"{d['throttle_count']} throttles", 'high' if d['throttle_count'] > 5 else 'normal')
    html += f'<div class="section" id="thermal">'
    html += f'<div class="section-header"><h2>🌡 Thermal {throttle_badge}</h2><span class="toggle-icon">▼</span></div>'
    html += '<div class="section-body">'
    if d['peak_temps']:
        temp_items = sorted(d['peak_temps'].items(), key=lambda x: x[1], reverse=True)
        t_zones  = [z[:25] for z, _ in temp_items[:20]]
        t_vals   = [v for _, v in temp_items[:20]]
        t_colors = ['#ff4444' if v > 80 else '#ff8800' if v > 45 else '#00aa44' for v in t_vals]
        html += f'''
<div class="chart-wrap">
  <div class="chart-toolbar">
    <label>Threshold: <span class="range-val" id="temp-thresh-val">45</span>°C</label>
    <input type="range" id="temp-thresh-range" min="20" max="120" value="45" step="1"
           oninput="updateTempThreshold(this.value)">
    <button onclick="thermalChart.resetZoom()">🔍 Reset Zoom</button>
  </div>
  <canvas id="thermalChartCanvas" height="60"></canvas>
  <p class="chart-hint">Bars above threshold highlighted in red. Drag/scroll to zoom.</p>
</div>
'''
        html += '''<div class="tbl-filter"><input type="text" placeholder="🔍 Filter zones..." data-target="thermal-table"></div>'''
        html += '<div class="tbl-wrap"><table id="thermal-table"><thead><tr>'
        for h in ['Thermal Zone', 'Peak Temp (°C)', 'Status']:
            html += f'<th data-sort>{h}</th>'
        html += '</tr></thead><tbody>'
        for zone, val in temp_items[:30]:
            status_badge = _badge('HOT', 'critical') if val > 80 else _badge('WARM', 'high') if val > 45 else _badge('OK', 'normal')
            row_cls = 'critical' if val > 80 else 'high' if val > 45 else ''
            html += f'<tr class="{row_cls}"><td>{_esc(zone)}</td>'
            html += f'<td data-sort="{val:.1f}">{val:.1f} °C</td>'
            html += f'<td>{status_badge}</td></tr>\n'
        html += '</tbody></table></div>'
        if d['thermal_events'][:10]:
            html += '<h3>Recent Throttle Events (click to expand)</h3>'
            for te in d['thermal_events'][:10]:
                html += f'''<div class="evt-box thermal">
  <div class="evt-header"><span style="color:#ff8800">⚠ {_esc(te["time"])}</span>
  <span>{_esc(te["event"])}</span></div>
</div>'''
    elif d['thermal_events']:
        for te in d['thermal_events'][:10]:
            html += f'<p style="color:#ff8800;font-size:12px">⚠ {_esc(te["time"])} {_esc(te["event"])}</p>'
    else:
        html += '<p style="color:#00cc66">✅ No thermal issues detected.</p>'
    html += '</div></div>'

    # ── 11. Root Cause Summary ────────────────────────────────────────────────
    html += '<div class="section" id="rca">'
    html += '''<div class="section-header"><h2>🔍 Root Cause Summary</h2><span class="toggle-icon">▼</span></div>'''
    html += '<div class="section-body">'
    rca_items = []
    # Expected session duration
    if _exp_hrs and dur_hr > 0:
        if dur_hr < _exp_hrs * 0.85:
            shortfall = _exp_hrs - dur_hr
            rca_items.append(('critical',
                f'Session ended early: {dur_hr:.1f}h actual vs {_exp_hrs:.1f}h expected '
                f'(⚡ {shortfall:.1f}h short — device may have drained prematurely)'))
        elif dur_hr < _exp_hrs:
            rca_items.append(('high',
                f'Session slightly short: {dur_hr:.1f}h actual vs {_exp_hrs:.1f}h expected'))
    # Drain rate vs thresholds
    if _exp_dr and avg_mah > _exp_dr:
        over  = avg_mah - _exp_dr
        sev   = 'critical' if avg_mah > _crit_dr else 'high'
        rca_items.append((sev,
            f'Drain {avg_mah:.1f} mAh/hr exceeds expected {_exp_dr:.1f} mAh/hr '
            f'(+{over:.1f} mAh/hr = +{over/_exp_dr*100:.0f}% over target)'))
    elif avg_mah > _crit_dr:
        rca_items.append(('critical',
            f'Excessive battery drain: {avg_mah:.1f} mAh/hr (critical threshold: {_crit_dr:.0f} mAh/hr)'))
    elif avg_mah > _warn_dr:
        rca_items.append(('high',
            f'Elevated battery drain: {avg_mah:.1f} mAh/hr (warning threshold: {_warn_dr:.0f} mAh/hr)'))
    for w in sorted(d['partial_wakelocks'], key=lambda x: x['duration_sec'], reverse=True)[:3]:
        if w['duration_sec'] > dur_hr * 3600 * 0.8:
            rca_items.append(('critical', f'<strong>{_esc(w["name"])}</strong> (UID {_esc(w["uid"])}) wakelock held for {_duration_badge(w["duration_sec"])} — prevents deep sleep'))
    for w in d['kernel_wakelocks'][:3]:
        if w['duration_sec'] > dur_hr * 3600 * 0.5:
            rca_items.append(('high', f'Kernel wakelock <strong>{_esc(w["name"])}</strong> active {_duration_badge(w["duration_sec"])}'))
    if len(d['anrs']) >= _min_anr:
        rca_items.append(('high', f'{len(d["anrs"])} ANR event(s) detected — may cause user-visible hangs'))
    fatal_crashes = [c for c in d['crashes'] if 'FATAL' in c['type'] or 'Native' in c['type']]
    if fatal_crashes:
        rca_items.append(('critical', f'{len(fatal_crashes)} fatal/native crash(es) detected'))
    elif len(d['crashes']) >= _min_crash:
        rca_items.append(('high', f'{len(d["crashes"])} crash event(s) detected'))
    if len(d['lmk_events']) >= _min_lmk:
        rca_items.append(('high', f'{len(d["lmk_events"])} LMK kills — possible memory pressure'))
    if d['throttle_count'] > 5:
        rca_items.append(('high', f'{d["throttle_count"]} thermal throttle events — possible overheating'))
    for u in pw['per_uid'][:5]:
        if u.get('cpu', 0) > 30:
            rca_items.append(('high', f'UID {_esc(u["uid"])} ({_esc(u["package"])}) consuming {u["cpu"]:.1f} mAh on CPU'))
    if not rca_items:
        rca_items.append(('normal', 'No significant issues detected.'))

    rca_counts = {'critical': 0, 'high': 0, 'normal': 0}
    for sev, msg in rca_items:
        rca_counts[sev] = rca_counts.get(sev, 0) + 1
        html += f'<div class="rca-item {sev}">{_badge(sev.upper(), sev)} {msg}</div>'

    html += '</div></div>'

    # ── Floating summary pill ─────────────────────────────────────────────────
    pill_color = '#ff4444' if rca_counts.get('critical', 0) else '#ff8800' if rca_counts.get('high', 0) else '#00cc66'
    html += f'''<div id="summary-pill" style="border-color:{pill_color}">
🔍 {lbl} — {rca_counts.get("critical",0)} critical &nbsp; {rca_counts.get("high",0)} high<br>
🔋 {avg_mah:.1f} mAh/hr &nbsp; | &nbsp; {dur_hr:.1f}h session<br>
<span style="font-size:10px;color:#778899">Click → Root Cause</span>
</div>'''

    # ── Chart initialization script ───────────────────────────────────────────
    # Build JS arrays (use json.dumps for safe JS serialization)
    j_times   = json.dumps(chart_times)
    j_levels  = json.dumps(chart_levels)
    j_volts   = json.dumps(chart_volts)
    j_hr_lbl  = json.dumps(hr_labels)
    j_hr_mah  = json.dumps(hr_drain_mah)
    j_hr_pct  = json.dumps(hr_drain_pct)
    j_hr_col  = json.dumps(hr_colors)
    j_uid_lbl = json.dumps(uid_labels)
    j_uid_cpu = json.dumps(uid_cpu)
    j_uid_wf  = json.dumps(uid_wifi)
    j_uid_wl  = json.dumps(uid_wl)
    j_uid_oth = json.dumps(uid_other)
    j_uid_tot = json.dumps(uid_total)
    j_pie_lbl = json.dumps(pie_labels_raw)
    j_pie_val = json.dumps(pie_vals_raw)
    j_pie_col = json.dumps(pie_colors)
    j_g_lbl   = json.dumps(g_labels)
    j_g_val   = json.dumps(g_vals)
    j_g_col   = json.dumps(g_colors)
    j_kwl_n   = json.dumps(kwl_names)
    j_kwl_s   = json.dumps(kwl_secs)
    j_kwl_c   = json.dumps(kwl_counts)
    j_pwl_n   = json.dumps(pwl_names)
    j_pwl_s   = json.dumps(pwl_secs)
    j_pwl_c   = json.dumps(pwl_counts)
    j_t_zones = json.dumps(t_zones if d['peak_temps'] else [])
    j_t_vals  = json.dumps(t_vals  if d['peak_temps'] else [])
    j_t_cols  = json.dumps(t_colors if d['peak_temps'] else [])
    j_avg_mah = json.dumps(round(avg_mah, 2))
    j_scrn_on = json.dumps(screen_on_hrs[:40])
    j_scrn_off= json.dumps(screen_off_hrs[:40])

    # Pre-build anomaly annotation JS lines (avoids f-string nesting hell)
    _ann_lines = []
    for _a in d['anomalies']:
        _ann_lines.append(
            f"  anns['an{_a['hour']}'] = {{type:'box',"
            f"xMin:{_a['t_start_hr']},xMax:{_a['t_end_hr']},"
            f"backgroundColor:'rgba(255,0,0,0.15)',borderColor:'#ff4444',borderWidth:1,"
            f"label:{{content:'H{_a['hour']+1}: {_a['drain_mah']:.0f}mAh',"
            f"display:true,color:'#ff6666',font:{{size:9}}}}}};"
        )
    j_ann_lines = '\n'.join(_ann_lines)

    html += f"""
<script>
// ── Data ──────────────────────────────────────────────────────────────────────
const _times   = {j_times};
const _levels  = {j_levels};
const _volts   = {j_volts};
const _hrLbl   = {j_hr_lbl};
const _hrMah   = {j_hr_mah};
const _hrPct   = {j_hr_pct};
const _hrCol   = {j_hr_col};
const _uidLbl  = {j_uid_lbl};
const _uidCpu  = {j_uid_cpu};
const _uidWifi = {j_uid_wf};
const _uidWl   = {j_uid_wl};
const _uidOth  = {j_uid_oth};
const _uidTot  = {j_uid_tot};
const _pieLbl  = {j_pie_lbl};
const _pieVal  = {j_pie_val};
const _pieCol  = {j_pie_col};
const _gLbl    = {j_g_lbl};
const _gVal    = {j_g_val};
const _gCol    = {j_g_col};
const _kwlN    = {j_kwl_n};
const _kwlS    = {j_kwl_s};
const _kwlC    = {j_kwl_c};
const _pwlN    = {j_pwl_n};
const _pwlS    = {j_pwl_s};
const _pwlC    = {j_pwl_c};
const _tZones  = {j_t_zones};
const _tVals   = {j_t_vals};
const _tCols   = {j_t_cols};
const _avgMah  = {j_avg_mah};
const _scrnOn  = {j_scrn_on};
const _scrnOff = {j_scrn_off};

// ── Battery timeline chart ─────────────────────────────────────────────────
let batteryChart = null;
let _showScreen = false, _showAnomaly = false;

function buildBatteryDatasets(view){{
  const ds = [];
  if(view==='level'||view==='both'){{
    ds.push({{
      label:'Battery Level (%)',
      data:_times.map((t,i)=>{{return {{x:t,y:_levels[i]}};}}),
      borderColor:'#00d4ff',backgroundColor:'rgba(0,212,255,0.12)',
      fill:true,tension:0.3,pointRadius:0,yAxisID:'yL'
    }});
  }}
  if(view==='voltage'||view==='both'){{
    ds.push({{
      label:'Voltage (mV)',
      data:_times.map((t,i)=>{{return {{x:t,y:_volts[i]}};}}),
      borderColor:'#ffcc00',backgroundColor:'rgba(255,204,0,0.08)',
      fill:false,tension:0.3,pointRadius:0,yAxisID:view==='both'?'yV':'yL'
    }});
  }}
  if(_showScreen){{
    _scrnOn.forEach(function(t){{
      ds.push({{label:'Screen ON',data:[{{x:t,y:0}},{{x:t,y:105}}],
        borderColor:'rgba(255,255,0,0.5)',borderWidth:1,pointRadius:0,
        borderDash:[4,4],fill:false,yAxisID:'yL',showLine:true,tension:0}});
    }});
    _scrnOff.forEach(function(t){{
      ds.push({{label:'Screen OFF',data:[{{x:t,y:0}},{{x:t,y:105}}],
        borderColor:'rgba(85,85,0,0.5)',borderWidth:1,pointRadius:0,
        borderDash:[4,4],fill:false,yAxisID:'yL',showLine:true,tension:0}});
    }});
  }}
  return ds;
}}

function buildBatteryScales(view){{
  const scales = {{
    x:{{type:'linear',title:{{display:true,text:'Hours from session start',color:'#99aabb'}},
         ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}},
    yL:{{min:view==='voltage'?null:0,max:view==='voltage'?null:100,beginAtZero:view!=='voltage',
          title:{{display:true,text:view==='voltage'?'Voltage (mV)':'Battery Level (%)',color:'#99aabb'}},
          ticks:{{color:'#99aabb',stepSize:view==='voltage'?null:10,
            callback:function(value){{ return view==='voltage' ? value : value + '%'; }}
          }},grid:{{color:'#1e1e3a'}}}}
  }};
  if(view==='both'){{
    scales.yV = {{position:'right',title:{{display:true,text:'Voltage (mV)',color:'#ffcc00'}},
                  ticks:{{color:'#ffcc00'}},grid:{{drawOnChartArea:false}}}};
  }}
  return scales;
}}

let _battView = 'level';

function setBatteryView(view, btn){{
  _battView = view;
  document.querySelectorAll('.chart-toolbar button[onclick*=setBatteryView]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  if(batteryChart){{
    batteryChart.data.datasets = buildBatteryDatasets(view);
    batteryChart.options.scales = buildBatteryScales(view);
    batteryChart.update();
  }}
}}

function toggleScreenOverlay(){{
  _showScreen = !_showScreen;
  const btn = document.getElementById('screen-overlay-btn');
  if(btn) btn.classList.toggle('active', _showScreen);
  setBatteryView(_battView, null);
}}

function toggleAnomalyOverlay(){{
  _showAnomaly = !_showAnomaly;
  const btn = document.getElementById('anomaly-overlay-btn');
  if(btn) btn.classList.toggle('active', _showAnomaly);
  // rebuild chart with/without annotation plugin annotations
  if(batteryChart){{
    batteryChart.options.plugins.annotation = _showAnomaly ? buildAnnotations() : {{}};
    batteryChart.update();
  }}
}}

function buildAnnotations(){{
  const anns = {{}};
  {j_ann_lines}
  return {{annotations:anns}};
}}

window.addEventListener('load', function(){{
  try {{
  const ctx = document.getElementById('batteryChartCanvas');
  if(!ctx||!_times.length) return;
  batteryChart = new Chart(ctx, {{
    type:'line',
    data:{{datasets: buildBatteryDatasets('level')}},
    options:{{
      responsive:true,
      animation:{{duration:500}},
      interaction:{{mode:'index',intersect:false}},
      plugins:{{
        legend:{{labels:{{color:'#ccc',font:{{size:11}},filter:function(item){{return !item.text.startsWith('Screen');}}  }}}},
        tooltip:{{
          backgroundColor:'#1a1a3e',borderColor:'#00d4ff',borderWidth:1,
          titleColor:'#00d4ff',bodyColor:'#e0e0e0',
          callbacks:{{
            title:function(items){{return 'T+'+items[0].parsed.x.toFixed(2)+'h';}},
            label:function(ctx){{
              if(ctx.dataset.label.startsWith('Screen')) return null;
              return ctx.dataset.label+': '+ctx.parsed.y.toFixed(1)+(ctx.dataset.yAxisID==='yL'?'%':' mV');
            }}
          }}
        }},
        zoom:{{
          pan:{{enabled:true,mode:'x'}},
          zoom:{{wheel:{{enabled:true}},pinch:{{enabled:true}},mode:'x'}}
        }}
      }},
      scales: buildBatteryScales('level')
    }}
  }});
  }} catch(e){{ console.error('Battery chart error:', e); }}
}});

// ── Hourly chart ──────────────────────────────────────────────────────────────
let hourlyChart = null;
let _hrMetric   = 'mah';
let _hrSortOrig = Array.from({{length:_hrLbl.length}},(v,i)=>i);
let _hrOrder    = [..._hrSortOrig];
let _hrThresh   = _avgMah;

function getHrData(){{ return _hrMetric==='mah'?_hrMah:_hrPct; }}
function getHrColors(data){{
  return data.map(v=> v > _hrThresh*1.5 ? '#ff4444' : v > _hrThresh ? '#ffaa00' : '#00aa44');
}}

function buildHourlyChart(){{
  const data   = _hrOrder.map(i=>getHrData()[i]);
  const labels = _hrOrder.map(i=>_hrLbl[i]);
  const colors = getHrColors(data);
  if(hourlyChart){{
    hourlyChart.data.labels = labels;
    hourlyChart.data.datasets[0].data   = data;
    hourlyChart.data.datasets[0].backgroundColor = colors;
    hourlyChart.data.datasets[0].label = _hrMetric==='mah'?'Drain (mAh)':'Drain (%)';
    hourlyChart.update();
    return;
  }}
  const ctx = document.getElementById('hourlyChartCanvas');
  if(!ctx) return;
  hourlyChart = new Chart(ctx, {{
    type:'bar',
    data:{{labels:labels, datasets:[{{
      label:'Drain (mAh)', data:data, backgroundColor:colors,
      borderColor:'#333', borderWidth:1
    }}]}},
    options:{{
      responsive:true,
      animation:{{duration:300}},
      interaction:{{mode:'index',intersect:false}},
      plugins:{{
        legend:{{labels:{{color:'#ccc'}}}},
        tooltip:{{
          backgroundColor:'#1a1a3e',borderColor:'#00d4ff',borderWidth:1,
          titleColor:'#00d4ff',bodyColor:'#e0e0e0',
          callbacks:{{
            label:function(ctx){{
              const suffix = _hrMetric==='mah'?' mAh':'%';
              const ratio  = _hrMah[_hrOrder[ctx.dataIndex]] / (_avgMah||1);
              return 'Drain: '+ctx.parsed.y.toFixed(2)+suffix+' ('+ratio.toFixed(2)+'x avg)';
            }}
          }}
        }},
        annotation:{{
          annotations:{{
            avgLine:{{type:'line',yMin:_hrThresh,yMax:_hrThresh,
                      borderColor:'#ffaa00',borderWidth:1.5,
                      borderDash:[6,4],
                      label:{{content:'Avg '+_hrThresh.toFixed(1)+(_hrMetric==='mah'?' mAh':'%'),display:true,color:'#ffaa00',font:{{size:10}}}}}}
          }}
        }}
      }},
      scales:{{
        x:{{ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}},
        y:{{title:{{display:true,text:_hrMetric==='mah'?'mAh':'%',color:'#99aabb'}},
             ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}}
      }}
    }}
  }});
}}

function setHourlyMetric(m, btn){{
  _hrMetric = m;
  document.querySelectorAll('.chart-toolbar button[onclick*=setHourlyMetric]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  buildHourlyChart();
}}

function sortHourly(order, btn){{
  document.querySelectorAll('.chart-toolbar button[onclick*=sortHourly]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  if(order==='desc') _hrOrder = [..._hrSortOrig].sort((a,b)=>_hrMah[b]-_hrMah[a]);
  else if(order==='asc') _hrOrder = [..._hrSortOrig].sort((a,b)=>_hrMah[a]-_hrMah[b]);
  else _hrOrder = [..._hrSortOrig];
  buildHourlyChart();
}}

function updateThreshold(val){{
  _hrThresh = parseFloat(val);
  document.getElementById('threshold-val').textContent = parseFloat(val).toFixed(0);
  buildHourlyChart();
}}

window.addEventListener('load', function(){{ try{{ buildHourlyChart(); }}catch(e){{console.error('Hourly chart error:',e);}} }});

// ── Power bar chart ───────────────────────────────────────────────────────────
let powerBarChart = null;
let _powerView = 'stacked';
let _topN = 10;

function buildPowerChart(){{
  const n = Math.min(_topN, _uidLbl.length);
  const lbls = _uidLbl.slice(0,n);
  const stacked = _powerView==='stacked';
  const dsets = _powerView==='total' ? [{{
      label:'Total',data:_uidTot.slice(0,n),backgroundColor:'#00d4ff',borderColor:'#0099bb',borderWidth:1
    }}] : [
    {{label:'CPU',   data:_uidCpu.slice(0,n),  backgroundColor:'#e74c3c',borderColor:'#c0392b',borderWidth:1}},
    {{label:'WiFi',  data:_uidWifi.slice(0,n), backgroundColor:'#3498db',borderColor:'#2980b9',borderWidth:1}},
    {{label:'WakeLock',data:_uidWl.slice(0,n), backgroundColor:'#f39c12',borderColor:'#d68910',borderWidth:1}},
    {{label:'Other', data:_uidOth.slice(0,n),  backgroundColor:'#9b59b6',borderColor:'#7d3c98',borderWidth:1}}
  ];
  if(powerBarChart){{
    powerBarChart.data.labels   = lbls;
    powerBarChart.data.datasets = dsets;
    powerBarChart.options.scales.x.stacked = stacked;
    powerBarChart.options.scales.y.stacked = stacked;
    powerBarChart.update();
    return;
  }}
  const ctx = document.getElementById('powerBarCanvas');
  if(!ctx) return;
  powerBarChart = new Chart(ctx,{{
    type:'bar',
    data:{{labels:lbls, datasets:dsets}},
    options:{{
      responsive:true,animation:{{duration:300}},
      interaction:{{mode:'index',intersect:false}},
      plugins:{{
        legend:{{labels:{{color:'#ccc',font:{{size:11}}}}}},
        tooltip:{{backgroundColor:'#1a1a3e',borderColor:'#00d4ff',borderWidth:1,
                   titleColor:'#00d4ff',bodyColor:'#e0e0e0',
                   callbacks:{{label:function(c){{return c.dataset.label+': '+c.parsed.y.toFixed(2)+' mAh';}}}}}}
      }},
      scales:{{
        x:{{stacked:stacked,ticks:{{color:'#99aabb',maxRotation:40}},grid:{{color:'#1e1e3a'}}}},
        y:{{stacked:stacked,title:{{display:true,text:'mAh',color:'#99aabb'}},
             ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}}
      }}
    }}
  }});
}}

function setPowerView(v, btn){{
  _powerView=v;
  document.querySelectorAll('.chart-toolbar button[onclick*=setPowerView]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  buildPowerChart();
}}

function filterTopN(n){{ _topN=n; buildPowerChart(); }}

window.addEventListener('load', function(){{ try{{ buildPowerChart(); }}catch(e){{console.error('Power chart error:',e);}} }});

// ── Pie charts ────────────────────────────────────────────────────────────────
window.addEventListener('load', function(){{
  try{{
    makePieChart('powerPieCanvas', _pieLbl, _pieVal, _pieCol);
    if(_gLbl.length) makePieChart('globalPieCanvas', _gLbl, _gVal, _gCol);
  }}catch(e){{console.error('Pie chart error:',e);}}
}});

// ── Kernel wakelock chart ─────────────────────────────────────────────────────
let kwlChart = null;
let _kwlView = 'duration';
function buildKwlChart(){{
  const data   = _kwlView==='duration'?_kwlS:_kwlC;
  const label  = _kwlView==='duration'?'Duration (s)':'Count';
  const colors = _kwlView==='duration'
    ? _kwlS.map(s=>s>({dur_hr*3600*0.5:.0f})?'#ff4444':s>({dur_hr*3600*0.2:.0f})?'#ffaa00':'#00aa44')
    : _kwlC.map(()=>'#44aaff');
  if(kwlChart){{
    kwlChart.data.datasets[0].data=data;
    kwlChart.data.datasets[0].backgroundColor=colors;
    kwlChart.data.datasets[0].label=label;
    kwlChart.options.scales.y.title.text=label;
    kwlChart.update(); return;
  }}
  const ctx=document.getElementById('kwlChartCanvas');
  if(!ctx) return;
  kwlChart=new Chart(ctx,{{type:'bar',
    data:{{labels:_kwlN,datasets:[{{label:label,data:data,backgroundColor:colors,borderWidth:1}}]}},
    options:{{responsive:true,animation:{{duration:300}},
      interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{labels:{{color:'#ccc'}}}},
        tooltip:{{backgroundColor:'#1a1a3e',borderColor:'#00d4ff',borderWidth:1,titleColor:'#00d4ff',bodyColor:'#e0e0e0',
          callbacks:{{label:function(c){{return _kwlView==='duration'?
            c.dataset.label+': '+c.parsed.y+'s ('+Math.floor(c.parsed.y/3600)+'h '+Math.floor((c.parsed.y%3600)/60)+'m)':
            c.dataset.label+': '+c.parsed.y;}}}}}}
      }},
      scales:{{x:{{ticks:{{color:'#99aabb',maxRotation:45}},grid:{{color:'#1e1e3a'}}}},
                y:{{title:{{display:true,text:label,color:'#99aabb'}},ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}}}}
    }}
  }});
}}
function setKwlView(v,btn){{
  _kwlView=v;
  document.querySelectorAll('.chart-toolbar button[onclick*=setKwlView]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  buildKwlChart();
}}
window.addEventListener('load',function(){{ try{{ if(_kwlN.length) buildKwlChart(); }}catch(e){{console.error('KWL chart error:',e);}} }});

// ── App wakelock chart ────────────────────────────────────────────────────────
let pwlChart=null, _pwlView='duration';
function buildPwlChart(){{
  const data  =_pwlView==='duration'?_pwlS:_pwlC;
  const label =_pwlView==='duration'?'Duration (s)':'Count';
  const colors=_pwlView==='duration'
    ?_pwlS.map(s=>s>({dur_hr*3600*0.5:.0f})?'#ff4444':s>({dur_hr*3600*0.2:.0f})?'#ffaa00':'#00aa44')
    :_pwlC.map(()=>'#ff88ff');
  if(pwlChart){{pwlChart.data.datasets[0].data=data;pwlChart.data.datasets[0].backgroundColor=colors;
    pwlChart.data.datasets[0].label=label;pwlChart.options.scales.y.title.text=label;pwlChart.update();return;}}
  const ctx=document.getElementById('pwlChartCanvas');
  if(!ctx) return;
  pwlChart=new Chart(ctx,{{type:'bar',
    data:{{labels:_pwlN,datasets:[{{label:label,data:data,backgroundColor:colors,borderWidth:1}}]}},
    options:{{responsive:true,animation:{{duration:300}},
      interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{labels:{{color:'#ccc'}}}},
        tooltip:{{backgroundColor:'#1a1a3e',borderColor:'#00d4ff',borderWidth:1,titleColor:'#00d4ff',bodyColor:'#e0e0e0',
          callbacks:{{label:function(c){{return _pwlView==='duration'?
            c.dataset.label+': '+c.parsed.y+'s':c.dataset.label+': '+c.parsed.y;}}}}}}
      }},
      scales:{{x:{{ticks:{{color:'#99aabb',maxRotation:45}},grid:{{color:'#1e1e3a'}}}},
                y:{{title:{{display:true,text:label,color:'#99aabb'}},ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}}}}
    }}
  }});
}}
function setPwlView(v,btn){{
  _pwlView=v;
  document.querySelectorAll('.chart-toolbar button[onclick*=setPwlView]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  buildPwlChart();
}}
window.addEventListener('load',function(){{ try{{ if(_pwlN.length) buildPwlChart(); }}catch(e){{console.error('PWL chart error:',e);}} }});

// ── Thermal chart ─────────────────────────────────────────────────────────────
let thermalChart=null, _tempThresh=45;
function buildThermalChart(){{
  const colors=_tVals.map(v=>v>_tempThresh?'#ff4444':v>35?'#ffaa00':'#00aa44');
  if(thermalChart){{thermalChart.data.datasets[0].backgroundColor=colors;thermalChart.update();return;}}
  const ctx=document.getElementById('thermalChartCanvas');
  if(!ctx||!_tZones.length) return;
  thermalChart=new Chart(ctx,{{type:'bar',
    data:{{labels:_tZones,datasets:[{{label:'Peak Temp (°C)',data:_tVals,backgroundColor:colors,borderWidth:1}}]}},
    options:{{responsive:true,animation:{{duration:300}},
      interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{labels:{{color:'#ccc'}}}},
        tooltip:{{backgroundColor:'#1a1a3e',borderColor:'#00d4ff',borderWidth:1,titleColor:'#00d4ff',bodyColor:'#e0e0e0',
          callbacks:{{label:function(c){{return 'Peak: '+c.parsed.y.toFixed(1)+'°C'+(c.parsed.y>80?' 🔥 CRITICAL':c.parsed.y>45?' ⚠ WARM':'');}}}}}}
      }},
      scales:{{x:{{ticks:{{color:'#99aabb',maxRotation:45}},grid:{{color:'#1e1e3a'}}}},
                y:{{title:{{display:true,text:'°C',color:'#99aabb'}},ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}}}}
    }}
  }});
}}
function updateTempThreshold(val){{
  _tempThresh=parseFloat(val);
  document.getElementById('temp-thresh-val').textContent=val;
  buildThermalChart();
}}
window.addEventListener('load',function(){{ try{{ if(_tZones.length) buildThermalChart(); }}catch(e){{console.error('Thermal chart error:',e);}} }});
</script>
"""
    html += f'<footer>Generated by Android BugReport Analyzer &nbsp;|&nbsp; {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</footer>'
    html += '</body></html>'

    with open(output_path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print(f"  ✓  Report: {output_path}")


def _esc(s):
    """HTML-escape a string."""
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 13 — COMPARATIVE HTML REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def generate_comparative_report(all_data, comp_graph_filename, output_path, title):
    """Generate fully interactive comparative report with Chart.js."""
    n = len(all_data)

    # ── TOC links ─────────────────────────────────────────────────────────────
    toc_sections = [
        ('comp-battery',   '🔋 Battery Comparison'),
        ('comp-timeline',  '📈 Level Timeline'),
        ('comp-hourly',    '📊 Hourly Discharge'),
        ('comp-power',     '⚡ Power Comparison'),
        ('comp-stability', '🚨 Stability'),
        ('comp-wakelocks', '🔒 Wakelock Comparison'),
        ('comp-delta',     '📈 Delta Analysis'),
    ]
    toc_html = '\n'.join(f'<a href="#{sid}">{sname}</a>' for sid, sname in toc_sections)

    html = _html_head(f"Comparative Analysis — {title}").replace('__TOC_LINKS__', toc_html)
    html += f"""
<div class="header">
  <h1>📊 Comparative Battery &amp; Stability Analysis</h1>
  <div class="subtitle">{_esc(title)} &nbsp;|&nbsp; {n} build(s) compared</div>
</div>
<div class="nav">
"""
    for d in all_data:
        html += f'<a href="{d["label"]}_Individual_Report.html">📄 {d["label"]}</a>'
    html += '</div>'

    # ── 1. Battery Comparison KPIs ────────────────────────────────────────────
    html += '<div class="section" id="comp-battery">'
    html += '<div class="section-header"><h2>🔋 Battery Drain Comparison</h2><span class="toggle-icon">▼</span></div>'
    html += '<div class="section-body">'
    _comp_thr  = all_data[0].get('thresholds', {}) if all_data else {}
    _comp_crit = _comp_thr.get('crit_drain',  80.0)
    _comp_warn = _comp_thr.get('warn_drain',  40.0)
    _comp_exp  = _comp_thr.get('expected_drain')
    _comp_exph = _comp_thr.get('expected_hours')
    html += '<div class="kpi-grid">'
    for d in all_data:
        disc = d['discharge']; pw = d['power_data']
        html += _kpi(d['label'], 'Build', '')
        html += _kpi(f"{disc.get('drain_pct','?')}%", f"{d['label']} Drain %",
                     'red' if disc.get('drain_pct', 0) > 30 else 'orange' if disc.get('drain_pct', 0) > 15 else 'green')
        html += _kpi(f"{pw['computed_drain']:.0f} mAh", f"{d['label']} Total",
                     'red' if pw['computed_drain'] > 1500 else 'orange' if pw['computed_drain'] > 600 else 'green')
        html += _kpi(f"{d['drain_mah_per_hr']:.1f} mAh/hr", f"{d['label']} Rate",
                     'red' if d['drain_mah_per_hr'] > _comp_crit
                     else 'orange' if d['drain_mah_per_hr'] > _comp_warn else 'green')
        dur_h    = disc.get('duration_hr', 0)
        dur_color = ('' if not _comp_exph
                     else 'red'    if dur_h < _comp_exph * 0.85
                     else 'orange' if dur_h < _comp_exph
                     else 'green')
        html += _kpi(f"{dur_h:.1f}h", f"{d['label']} Duration", dur_color)
    html += '</div>'
    if n >= 2:
        rates = [(d['label'], d['drain_mah_per_hr']) for d in all_data]
        best  = min(rates, key=lambda x: x[1])
        worst = max(rates, key=lambda x: x[1])
        ratio = worst[1] / best[1] if best[1] > 0 else 1
        vc    = 'fail' if ratio > 2 else 'warn' if ratio > 1.3 else 'pass'
        html += (f'<div class="verdict {vc}">Best: {_esc(best[0])} @ {best[1]:.1f} mAh/hr'
                 f' &nbsp;|&nbsp; Worst: {_esc(worst[0])} @ {worst[1]:.1f} mAh/hr'
                 f' &nbsp;|&nbsp; Ratio: <strong>{ratio:.1f}&times;</strong> difference</div>')
    # ── Expected drain vs actual (shown only when --expected-drain was set) ──
    if _comp_exp:
        exp_parts = []
        for d in all_data:
            act  = d['drain_mah_per_hr']
            diff = act - _comp_exp
            if diff > 0:
                pct     = diff / _comp_exp * 100
                col     = '#ff4444' if act > _comp_crit else '#ff8800'
                exp_parts.append(
                    f'<span style="color:{col}">{_esc(d["label"])}: {act:.1f} '
                    f'vs {_comp_exp:.1f} expected (+{diff:.1f} mAh/hr = +{pct:.0f}%)</span>')
            else:
                exp_parts.append(
                    f'<span style="color:#00cc66">{_esc(d["label"])}: {act:.1f} '
                    f'vs {_comp_exp:.1f} expected ({diff:.1f} mAh/hr \u2714)</span>')
        html += (f'<div class="verdict" style="border-left-color:#00aaff;background:#0a1a2a">'
                 f'&#128203; <strong>Expected {_comp_exp:.1f}\u00a0mAh/hr:</strong> &nbsp;'
                 + ' &nbsp;|&nbsp; '.join(exp_parts) + '</div>')
    # ── Expected session duration vs actual ───────────────────────────────────
    if _comp_exph:
        dur_parts = []
        for d in all_data:
            act_h = d['discharge'].get('duration_hr', 0)
            diff  = act_h - _comp_exph
            if diff < -0.25 * _comp_exph:
                dur_parts.append(
                    f'<span style="color:#ff4444">{_esc(d["label"])}: {act_h:.1f}h '
                    f'(short by {-diff:.1f}h &#x26A0;)</span>')
            elif diff < 0:
                dur_parts.append(
                    f'<span style="color:#ff8800">{_esc(d["label"])}: {act_h:.1f}h '
                    f'(short by {-diff:.1f}h)</span>')
            else:
                dur_parts.append(
                    f'<span style="color:#00cc66">{_esc(d["label"])}: {act_h:.1f}h \u2714</span>')
        html += (f'<div class="verdict" style="border-left-color:#00aaff;background:#0a1a2a">'
                 f'&#9200; <strong>Expected session {_comp_exph:.1f}\u00a0h:</strong> &nbsp;'
                 + ' &nbsp;|&nbsp; '.join(dur_parts) + '</div>')
    html += '</div></div>'

    # ── 2. Battery Level Timeline (multi-line) ────────────────────────────────
    html += '<div class="section" id="comp-timeline">'
    html += '<div class="section-header"><h2>📈 Battery Level Timeline — All Builds</h2><span class="toggle-icon">▼</span></div>'
    html += '<div class="section-body">'
    html += '''
<div class="chart-wrap">
  <div class="chart-toolbar">
    <label>Smooth:</label>
    <button class="active" onclick="setCompSmooth(0.3,this)">Smooth</button>
    <button onclick="setCompSmooth(0,this)">Sharp</button>
    &nbsp;|&nbsp;
    <button onclick="compTimelineChart.resetZoom()">🔍 Reset Zoom</button>
    <label style="margin-left:8px">Zoom: Scroll wheel / Pinch</label>
  </div>
  <canvas id="compTimelineCanvas" height="60"></canvas>
  <p class="chart-hint">Scroll to zoom • Drag to pan • Click legend to show/hide builds</p>
</div>
'''
    html += '</div></div>'

    # ── 3. Hourly Discharge Comparison ───────────────────────────────────────
    html += '<div class="section" id="comp-hourly">'
    html += '<div class="section-header"><h2>📊 Hourly Discharge — Build Comparison</h2><span class="toggle-icon">▼</span></div>'
    html += '<div class="section-body">'
    html += '''
<div class="chart-wrap">
  <div class="chart-toolbar">
    <label>Metric:</label>
    <button class="active" onclick="setCompHourlyMetric(\'mah\',this)">mAh</button>
    <button onclick="setCompHourlyMetric(\'pct\',this)">%</button>
    &nbsp;|&nbsp;
    <label>View:</label>
    <button class="active" onclick="setCompHourlyView(\'grouped\',this)">Grouped</button>
    <button onclick="setCompHourlyView(\'stacked\',this)">Stacked</button>
    &nbsp;|&nbsp;
    <button onclick="compHourlyChart.resetZoom()">🔍 Reset Zoom</button>
  </div>
  <canvas id="compHourlyCanvas" height="70"></canvas>
  <p class="chart-hint">Compare per-hour drain across all builds side by side. Hover for exact values.</p>
</div>
'''
    # Worst-hour comparison table
    html += '<h3>Worst Drain Hour per Build</h3><div class="tbl-wrap"><table><thead><tr>'
    for h in ['Build', 'Worst Hour', 'Drain (mAh)', 'Drain (%)', 'vs Avg']:
        html += f'<th data-sort>{h}</th>'
    html += '</tr></thead><tbody>'
    for d in all_data:
        h_sorted = sorted(d['history'], key=lambda x: x['ms']) if d['history'] else []
        cap      = d['power_data']['capacity'] or 4647
        avg      = d['drain_mah_per_hr']
        max_ms   = h_sorted[-1]['ms'] if h_sorted else 0
        worst_mah, worst_hr, worst_pct = 0, 0, 0
        for hr in range(int(max_ms / 3_600_000) + 1):
            sl  = _level_at_ms(h_sorted, hr * 3_600_000)
            el  = _level_at_ms(h_sorted, (hr + 1) * 3_600_000)
            mah = max(0, (sl - el) * cap / 100)
            if mah > worst_mah:
                worst_mah = mah; worst_hr = hr; worst_pct = sl - el
        ratio = worst_mah / avg if avg > 0 else 0
        row_cls = 'critical' if ratio > 1.5 else 'high' if ratio > 1 else ''
        html += (f'<tr class="{row_cls}"><td>{_esc(d["label"])}</td>'
                 f'<td>H{worst_hr+1}</td><td>{worst_mah:.1f} mAh</td>'
                 f'<td>{worst_pct:.1f}%</td><td>{ratio:.2f}×</td></tr>\n')
    html += '</tbody></table></div>'
    html += '</div></div>'

    # ── 4. Power Comparison ────────────────────────────────────────────────────
    html += '<div class="section" id="comp-power">'
    html += '<div class="section-header"><h2>⚡ Power Consumption — Side by Side</h2><span class="toggle-icon">▼</span></div>'
    html += '<div class="section-body">'
    html += '''
<div class="chart-wrap">
  <div class="chart-toolbar">
    <label>Component:</label>
    <select id="comp-power-comp-sel" onchange="updateCompPowerChart(this.value)">
      <option value="total">Total mAh</option>
      <option value="cpu">CPU</option>
      <option value="wifi">WiFi</option>
      <option value="wakelock">WakeLock</option>
    </select>
    <label style="margin-left:8px">Top N:</label>
    <select onchange="updateCompPowerN(parseInt(this.value))">
      <option value="5">Top 5</option>
      <option value="10" selected>Top 10</option>
      <option value="15">Top 15</option>
    </select>
  </div>
  <canvas id="compPowerCanvas" height="75"></canvas>
  <p class="chart-hint">Compare power consumption per UID across builds. Hover to see per-build values.</p>
</div>
'''
    # Per-build power summary table
    html += '<div class="comp-grid">'
    for d in all_data:
        pw = d['power_data']
        html += f'<div><h3 style="color:#00d4ff;margin-bottom:8px">{_esc(d["label"])}</h3>'
        html += '<div class="tbl-filter"><input type="text" placeholder="🔍 Filter..." data-target="' + f'comp-power-tbl-{_esc(d["label"])}">'
        html += '</div><div class="tbl-wrap"><table id="' + f'comp-power-tbl-{_esc(d["label"])}">'
        html += '<thead><tr><th data-sort>UID</th><th data-sort>Package</th><th data-sort>Total mAh</th><th data-sort>CPU</th><th data-sort>WL</th></tr></thead><tbody>'
        for u in pw['per_uid'][:15]:
            t = u['total_mah']
            sev = 'critical' if t > d['drain_mah_per_hr'] else 'high' if t > d['drain_mah_per_hr'] * 0.5 else ''
            html += (f'<tr class="{sev}"><td>{_esc(u["uid"])}</td>'
                     f'<td style="font-size:11px">{_esc(u["package"][:26])}</td>'
                     f'<td data-sort="{t:.4f}">{t:.2f}</td>'
                     f'<td data-sort="{u.get("cpu",0):.4f}">{u.get("cpu",0):.2f}</td>'
                     f'<td data-sort="{u.get("wakelock",0):.4f}">{u.get("wakelock",0):.2f}</td></tr>\n')
        html += '</tbody></table></div></div>'
    html += '</div></div></div>'

    # ── 5. Stability Comparison ────────────────────────────────────────────────
    html += '<div class="section" id="comp-stability">'
    html += '<div class="section-header"><h2>🚨 Stability Comparison</h2><span class="toggle-icon">▼</span></div>'
    html += '<div class="section-body">'
    html += '''
<div class="chart-wrap">
  <canvas id="compStabilityCanvas" height="50"></canvas>
  <p class="chart-hint">Radar chart of stability metrics per build. Larger area = more issues.</p>
</div>
'''
    html += '<div class="comp-grid">'
    for d in all_data:
        fatal = len([c for c in d['crashes'] if 'FATAL' in c['type'] or 'Native' in c['type']])
        html += f'<div><h3 style="color:#00d4ff;margin-bottom:8px">{_esc(d["label"])}</h3><table><tbody>'
        metrics = [
            ('ANRs',             len(d['anrs']),          'critical' if d['anrs'] else 'normal'),
            ('Fatal Crashes',    fatal,                   'critical' if fatal else 'normal'),
            ('Total Crashes',    len(d['crashes']),       'high' if d['crashes'] else 'normal'),
            ('LMK Kills',        len(d['lmk_events']),   'high' if d['lmk_events'] else 'normal'),
            ('Thermal Throttles',d['throttle_count'],    'high' if d['throttle_count'] > 5 else 'normal'),
            ('Anomaly Hours',    len(d['anomalies']),    'high' if d['anomalies'] else 'normal'),
            ('Avg Drain mAh/hr', f"{d['drain_mah_per_hr']:.1f}", 'red' if d['drain_mah_per_hr'] > 80 else 'orange' if d['drain_mah_per_hr'] > 40 else 'normal'),
        ]
        for name, val, cls in metrics:
            html += f'<tr><td style="color:#aabbcc">{name}</td><td>{_badge(str(val), cls)}</td></tr>'
        html += '</tbody></table></div>'
    html += '</div></div></div>'

    # ── 6. Wakelock Comparison ────────────────────────────────────────────────
    html += '<div class="section" id="comp-wakelocks">'
    html += '<div class="section-header"><h2>🔒 Wakelock Comparison</h2><span class="toggle-icon">▼</span></div>'
    html += '<div class="section-body">'
    html += '''
<div class="chart-wrap">
  <div class="chart-toolbar">
    <label>Type:</label>
    <button class="active" onclick="setCompWlType(\'kernel\',this)">Kernel WL</button>
    <button onclick="setCompWlType(\'app\',this)">App WL</button>
    &nbsp;|&nbsp;
    <label>Metric:</label>
    <button class="active" onclick="setCompWlMetric(\'duration\',this)">Duration</button>
    <button onclick="setCompWlMetric(\'count\',this)">Count</button>
  </div>
  <canvas id="compWlCanvas" height="65"></canvas>
</div>
'''
    html += '<div class="comp-grid">'
    for d in all_data:
        dur_hr = d['discharge'].get('duration_hr', 1)
        html += f'<div><h3 style="color:#00d4ff;margin-bottom:6px">{_esc(d["label"])} — Kernel</h3>'
        if d['kernel_wakelocks']:
            html += '<div class="tbl-wrap"><table><thead><tr><th data-sort>Name</th><th data-sort>Duration</th><th data-sort>Count</th></tr></thead><tbody>'
            for w in d['kernel_wakelocks'][:10]:
                rc = 'critical' if w['duration_sec'] > dur_hr * 3600 * 0.5 else 'high' if w['duration_sec'] > dur_hr * 3600 * 0.2 else ''
                html += f'<tr class="{rc}"><td style="font-size:11px">{_esc(w["name"][:35])}</td><td data-sort="{w["duration_sec"]:.0f}">{_duration_badge(w["duration_sec"])}</td><td>{w["count"]:,}</td></tr>\n'
            html += '</tbody></table></div>'
        else:
            html += '<p style="color:#556677;font-size:12px">None found</p>'
        html += f'<h3 style="color:#00d4ff;margin:10px 0 6px">{_esc(d["label"])} — App WL (Top 5)</h3>'
        top_pwl = sorted(d['partial_wakelocks'], key=lambda x: x['duration_sec'], reverse=True)[:5]
        if top_pwl:
            html += '<div class="tbl-wrap"><table><thead><tr><th>UID</th><th>Name</th><th data-sort>Duration</th></tr></thead><tbody>'
            for w in top_pwl:
                rc = 'critical' if w['duration_sec'] > dur_hr * 3600 * 0.5 else ''
                html += f'<tr class="{rc}"><td>{_esc(w["uid"])}</td><td style="font-size:11px">{_esc(w["name"][:28])}</td><td data-sort="{w["duration_sec"]:.0f}">{_duration_badge(w["duration_sec"])}</td></tr>\n'
            html += '</tbody></table></div>'
        else:
            html += '<p style="color:#556677;font-size:12px">None found</p>'
        html += '</div>'
    html += '</div></div></div>'

    # ── 7. Delta Analysis (2-build) ───────────────────────────────────────────
    if n >= 2:
        html += '<div class="section" id="comp-delta">'
        html += '<div class="section-header"><h2>📈 Component-Level Delta Analysis</h2><span class="toggle-icon">▼</span></div>'
        html += '<div class="section-body">'
        d0, d1 = all_data[0], all_data[1]
        html += f'''
<div class="chart-wrap">
  <div class="chart-toolbar">
    <label>Sort:</label>
    <button class="active" onclick="sortDeltaChart(\'abs\',this)">|Delta| Largest</button>
    <button onclick="sortDeltaChart(\'inc\',this)">Increased Only</button>
    <button onclick="sortDeltaChart(\'dec\',this)">Decreased Only</button>
  </div>
  <canvas id="compDeltaCanvas" height="75"></canvas>
  <p class="chart-hint">Red bars = {_esc(d1["label"])} uses more. Green = {_esc(d1["label"])} uses less.</p>
</div>
'''
        uids0 = {u['uid']: u for u in d0['power_data']['per_uid']}
        uids1 = {u['uid']: u for u in d1['power_data']['per_uid']}
        all_uids = sorted(set(uids0) | set(uids1),
                          key=lambda u: abs(uids0.get(u, {}).get('total_mah', 0) -
                                           uids1.get(u, {}).get('total_mah', 0)), reverse=True)[:30]
        html += '''<div class="tbl-filter">
  <input type="text" placeholder="🔍 Filter delta table..." data-target="delta-table">
  <select data-target="delta-table" data-col="4">
    <option value="">All</option>
    <option value="+">Increased</option>
    <option value="-">Decreased</option>
  </select>
</div>
<div class="tbl-wrap">
<table id="delta-table"><thead><tr>
'''
        for h in ['UID', 'Package', f'{_esc(d0["label"])} (mAh)', f'{_esc(d1["label"])} (mAh)', 'Delta (mAh)', 'CPU Δ', 'WiFi Δ', 'WL Δ']:
            html += f'<th data-sort>{h}</th>'
        html += '</tr></thead><tbody>'
        for uid in all_uids:
            u0 = uids0.get(uid, {}); u1 = uids1.get(uid, {})
            t0 = u0.get('total_mah', 0); t1 = u1.get('total_mah', 0)
            delta = t1 - t0
            pkg   = u0.get('package') or u1.get('package') or uid
            clr   = '#ff4444' if delta > 5 else '#00cc66' if delta < -3 else '#cccccc'
            c_delta = u1.get('cpu', 0) - u0.get('cpu', 0)
            w_delta = u1.get('wifi', 0) - u0.get('wifi', 0)
            wl_delta= u1.get('wakelock', 0) - u0.get('wakelock', 0)
            row_cls = 'critical' if delta > 10 else 'high' if delta > 5 else ''
            html += (f'<tr class="{row_cls}"><td data-sort="{uid}">{_esc(uid)}</td>'
                     f'<td style="font-size:11px">{_esc(pkg[:32])}</td>'
                     f'<td data-sort="{t0:.4f}">{t0:.2f}</td>'
                     f'<td data-sort="{t1:.4f}">{t1:.2f}</td>'
                     f'<td data-sort="{delta:.4f}"><span style="color:{clr};font-weight:700">{delta:+.2f}</span></td>'
                     f'<td data-sort="{c_delta:.4f}"><span style="color:{"#ff4444" if c_delta>2 else "#00cc66" if c_delta<-1 else "#ccc"}">{c_delta:+.2f}</span></td>'
                     f'<td data-sort="{w_delta:.4f}"><span style="color:{"#ff4444" if w_delta>2 else "#00cc66" if w_delta<-1 else "#ccc"}">{w_delta:+.2f}</span></td>'
                     f'<td data-sort="{wl_delta:.4f}"><span style="color:{"#ff4444" if wl_delta>2 else "#00cc66" if wl_delta<-1 else "#ccc"}">{wl_delta:+.2f}</span></td></tr>\n')
        html += '</tbody></table></div></div></div>'

    # ── Chart initialization ──────────────────────────────────────────────────
    clrs = CHART_COLORS[:n]

    # Build timeline JS data per build
    timeline_datasets_js = '[\n'
    for i, d in enumerate(all_data):
        h_sorted = sorted(d['history'], key=lambda x: x['ms']) if d['history'] else []
        pts, prev = [], None
        for p in h_sorted:
            if p['level'] != prev: pts.append(p); prev = p['level']
        xs = [round(p['ms'] / 3_600_000, 3) for p in (pts or h_sorted)]
        ys = [p['level'] for p in (pts or h_sorted)]
        disc = d['discharge']
        _tl_pts_js = '[' + ','.join(f'{{x:{xi},y:{yi}}}' for xi, yi in zip(xs, ys)) + ']'
        timeline_datasets_js += f"""  {{
    label: '{_esc(d["label"])} ({disc.get("drain_pct","?") }% drain)',
    data: {_tl_pts_js},
    borderColor: '{clrs[i]}', backgroundColor: '{clrs[i]}22',
    fill: false, tension: 0.3, pointRadius: 0, yAxisID: 'y'
  }},\n"""
    timeline_datasets_js += ']'

    # Hourly JS data per build
    max_hrs = 0
    hr_data_per_build = []
    for d in all_data:
        h_sorted = sorted(d['history'], key=lambda x: x['ms']) if d['history'] else []
        cap      = d['power_data']['capacity'] or 4647
        max_ms   = h_sorted[-1]['ms'] if h_sorted else 0
        hrs      = int(max_ms / 3_600_000) + 1
        max_hrs  = max(max_hrs, hrs)
        mah_list, pct_list = [], []
        for hr in range(hrs):
            sl  = _level_at_ms(h_sorted, hr * 3_600_000)
            el  = _level_at_ms(h_sorted, (hr + 1) * 3_600_000)
            mah_list.append(round(max(0, (sl - el) * cap / 100), 2))
            pct_list.append(sl - el)
        hr_data_per_build.append({'mah': mah_list, 'pct': pct_list})

    hourly_labels_js = json.dumps([f'H{i+1}' for i in range(max_hrs)])
    hourly_mah_ds_js = '[\n'
    hourly_pct_ds_js = '[\n'
    for i, (d, hd) in enumerate(zip(all_data, hr_data_per_build)):
        padded_mah = hd['mah'] + [0] * (max_hrs - len(hd['mah']))
        padded_pct = hd['pct'] + [0] * (max_hrs - len(hd['pct']))
        hourly_mah_ds_js += f"  {{label:'{_esc(d['label'])}',data:{json.dumps(padded_mah)},backgroundColor:'{clrs[i]}',borderColor:'{clrs[i]}',borderWidth:1}},\n"
        hourly_pct_ds_js += f"  {{label:'{_esc(d['label'])}',data:{json.dumps(padded_pct)},backgroundColor:'{clrs[i]}',borderColor:'{clrs[i]}',borderWidth:1}},\n"
    hourly_mah_ds_js += ']'
    hourly_pct_ds_js += ']'

    # Power comparison data (all UIDs union)
    all_uid_set = []
    for d in all_data:
        for u in d['power_data']['per_uid'][:15]:
            if u['uid'] not in all_uid_set:
                all_uid_set.append(u['uid'])
    all_uid_set = all_uid_set[:15]
    uid_map_list = [{u['uid']: u for u in d['power_data']['per_uid']} for d in all_data]
    comp_power_total_ds = '[\n'
    comp_power_cpu_ds   = '[\n'
    comp_power_wifi_ds  = '[\n'
    comp_power_wl_ds    = '[\n'
    for i, d in enumerate(all_data):
        um = uid_map_list[i]
        tot_vals  = [round(um.get(u, {}).get('total_mah', 0), 2) for u in all_uid_set]
        cpu_vals  = [round(um.get(u, {}).get('cpu', 0), 2)       for u in all_uid_set]
        wifi_vals = [round(um.get(u, {}).get('wifi', 0), 2)      for u in all_uid_set]
        wl_vals   = [round(um.get(u, {}).get('wakelock', 0), 2)  for u in all_uid_set]
        comp_power_total_ds += f"  {{label:'{_esc(d['label'])}',data:{json.dumps(tot_vals)}, backgroundColor:'{clrs[i]}', borderColor:'{clrs[i]}',borderWidth:1}},\n"
        comp_power_cpu_ds   += f"  {{label:'{_esc(d['label'])}',data:{json.dumps(cpu_vals)},  backgroundColor:'{clrs[i]}', borderColor:'{clrs[i]}',borderWidth:1}},\n"
        comp_power_wifi_ds  += f"  {{label:'{_esc(d['label'])}',data:{json.dumps(wifi_vals)}, backgroundColor:'{clrs[i]}', borderColor:'{clrs[i]}',borderWidth:1}},\n"
        comp_power_wl_ds    += f"  {{label:'{_esc(d['label'])}',data:{json.dumps(wl_vals)},   backgroundColor:'{clrs[i]}', borderColor:'{clrs[i]}',borderWidth:1}},\n"
    comp_power_total_ds += ']'; comp_power_cpu_ds += ']'
    comp_power_wifi_ds  += ']'; comp_power_wl_ds  += ']'

    # Stability radar
    stab_labels = ['ANRs', 'Fatal Crashes', 'Total Crashes', 'LMK Kills', 'Thermal', 'Anomaly Hrs']
    stab_ds_js = '[\n'
    for i, d in enumerate(all_data):
        fatal = len([c for c in d['crashes'] if 'FATAL' in c['type'] or 'Native' in c['type']])
        vals = [len(d['anrs']), fatal, len(d['crashes']), len(d['lmk_events']),
                d['throttle_count'], len(d['anomalies'])]
        stab_ds_js += f"  {{label:'{_esc(d['label'])}',data:{json.dumps(vals)},borderColor:'{clrs[i]}',backgroundColor:'{clrs[i]}33',pointBackgroundColor:'{clrs[i]}'}},\n"
    stab_ds_js += ']'

    # Wakelock charts
    kwl_names_all  = list(dict.fromkeys(w['name'][:30] for d in all_data for w in d['kernel_wakelocks'][:10]))[:20]
    kwl_dur_ds_js  = '[\n'
    kwl_cnt_ds_js  = '[\n'
    for i, d in enumerate(all_data):
        kwl_map = {w['name']: w for w in d['kernel_wakelocks']}
        dur_vals = [round(kwl_map.get(n, {}).get('duration_sec', 0), 0) for n in kwl_names_all]
        cnt_vals = [kwl_map.get(n, {}).get('count', 0) for n in kwl_names_all]
        kwl_dur_ds_js += f"  {{label:'{_esc(d['label'])}',data:{json.dumps(dur_vals)},backgroundColor:'{clrs[i]}',borderColor:'{clrs[i]}',borderWidth:1}},\n"
        kwl_cnt_ds_js += f"  {{label:'{_esc(d['label'])}',data:{json.dumps(cnt_vals)},backgroundColor:'{clrs[i]}',borderColor:'{clrs[i]}',borderWidth:1}},\n"
    kwl_dur_ds_js += ']'; kwl_cnt_ds_js += ']'

    pwl_names_all = list(dict.fromkeys(f"{w['uid']}:{w['name'][:20]}" for d in all_data for w in sorted(d['partial_wakelocks'], key=lambda x: x['duration_sec'], reverse=True)[:8]))[:20]
    pwl_dur_ds_js = '[\n'; pwl_cnt_ds_js = '[\n'
    for i, d in enumerate(all_data):
        pwl_map = {f"{w['uid']}:{w['name']}": w for w in d['partial_wakelocks']}
        dur_vals = [round(next((v.get('duration_sec', 0) for k, v in pwl_map.items() if k.startswith(nm[:22])), 0), 0) for nm in pwl_names_all]
        cnt_vals = [next((v.get('count', 0) for k, v in pwl_map.items() if k.startswith(nm[:22])), 0) for nm in pwl_names_all]
        pwl_dur_ds_js += f"  {{label:'{_esc(d['label'])}',data:{json.dumps(dur_vals)},backgroundColor:'{clrs[i]}',borderColor:'{clrs[i]}',borderWidth:1}},\n"
        pwl_cnt_ds_js += f"  {{label:'{_esc(d['label'])}',data:{json.dumps(cnt_vals)},backgroundColor:'{clrs[i]}',borderColor:'{clrs[i]}',borderWidth:1}},\n"
    pwl_dur_ds_js += ']'; pwl_cnt_ds_js += ']'

    # Delta chart data
    delta_uids_js = json.dumps(all_uids[:25]) if n >= 2 else '[]'
    delta_vals_js = '[]'
    delta_cols_js = '[]'
    if n >= 2:
        d0, d1 = all_data[0], all_data[1]
        uids0 = {u['uid']: u for u in d0['power_data']['per_uid']}
        uids1 = {u['uid']: u for u in d1['power_data']['per_uid']}
        deltas = [round(uids1.get(u, {}).get('total_mah', 0) - uids0.get(u, {}).get('total_mah', 0), 2)
                  for u in all_uids[:25]]
        d_cols = ['#ff4444' if v > 0 else '#00cc66' for v in deltas]
        delta_vals_js = json.dumps(deltas)
        delta_cols_js = json.dumps(d_cols)

    html += f"""
<script>
// ── Comparative charts ────────────────────────────────────────────────────────
const _compTlDs    = {timeline_datasets_js};
const _compHrLbl   = {hourly_labels_js};
const _compHrMahDs = {hourly_mah_ds_js};
const _compHrPctDs = {hourly_pct_ds_js};
const _compPwTotDs = {comp_power_total_ds};
const _compPwCpuDs = {comp_power_cpu_ds};
const _compPwWfDs  = {comp_power_wifi_ds};
const _compPwWlDs  = {comp_power_wl_ds};
const _compPwUids  = {json.dumps(all_uid_set)};
const _stabLbls    = {json.dumps(stab_labels)};
const _stabDs      = {stab_ds_js};
const _kwlNms      = {json.dumps(kwl_names_all)};
const _kwlDurDs    = {kwl_dur_ds_js};
const _kwlCntDs    = {kwl_cnt_ds_js};
const _pwlNms      = {json.dumps(pwl_names_all)};
const _pwlDurDs    = {pwl_dur_ds_js};
const _pwlCntDs    = {pwl_cnt_ds_js};
const _deltaUids   = {delta_uids_js};
const _deltaVals   = {delta_vals_js};
const _deltaCols   = {delta_cols_js};

const _baseChartOpts = {{
  responsive:true, animation:{{duration:300}},
  interaction:{{mode:'index',intersect:false}},
  plugins:{{
    legend:{{labels:{{color:'#ccc',font:{{size:11}}}}}},
    tooltip:{{backgroundColor:'#1a1a3e',borderColor:'#00d4ff',borderWidth:1,titleColor:'#00d4ff',bodyColor:'#e0e0e0'}}
  }},
  scales:{{
    x:{{ticks:{{color:'#99aabb',maxRotation:40}},grid:{{color:'#1e1e3a'}}}},
    y:{{ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}}
  }}
}};

// Timeline
let compTimelineChart = null;
window.addEventListener('load', function(){{
  try {{
  const ctx = document.getElementById('compTimelineCanvas');
  if(!ctx) return;
  compTimelineChart = new Chart(ctx,{{
    type:'line',
    data:{{datasets: _compTlDs}},
    options:Object.assign(JSON.parse(JSON.stringify(_baseChartOpts)),{{
      plugins:Object.assign(JSON.parse(JSON.stringify(_baseChartOpts.plugins)),{{
        zoom:{{pan:{{enabled:true,mode:'x'}},zoom:{{wheel:{{enabled:true}},pinch:{{enabled:true}},mode:'x'}}}}
      }}),
      scales:{{
        x:{{type:'linear',title:{{display:true,text:'Hours from session start',color:'#99aabb'}},
             ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}},
        y:{{min:0,max:100,beginAtZero:true,
             title:{{display:true,text:'Battery Level (%)',color:'#99aabb'}},
             ticks:{{color:'#99aabb',stepSize:10,
               callback:function(value){{ return value + '%'; }}
             }},grid:{{color:'#1e1e3a'}}}}
      }}
    }})
  }});
  }} catch(e){{ console.error('Comparative timeline chart error:', e); }}
}});
function setCompSmooth(v, btn){{
  document.querySelectorAll('.chart-toolbar button[onclick*=setCompSmooth]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  if(compTimelineChart){{
    compTimelineChart.data.datasets.forEach(ds=>ds.tension=v);
    compTimelineChart.update();
  }}
}}

// Hourly
let compHourlyChart = null;
let _compHrMetric = 'mah', _compHrView = 'grouped';
function buildCompHourlyChart(){{
  const ds = _compHrMetric==='mah'?_compHrMahDs:_compHrPctDs;
  const stacked = _compHrView==='stacked';
  if(compHourlyChart){{
    compHourlyChart.data.datasets = ds;
    compHourlyChart.options.scales.x.stacked = stacked;
    compHourlyChart.options.scales.y.stacked = stacked;
    compHourlyChart.update(); return;
  }}
  const ctx=document.getElementById('compHourlyCanvas');
  if(!ctx) return;
  compHourlyChart=new Chart(ctx,{{type:'bar',data:{{labels:_compHrLbl,datasets:ds}},
    options:Object.assign(JSON.parse(JSON.stringify(_baseChartOpts)),{{
      plugins:Object.assign(JSON.parse(JSON.stringify(_baseChartOpts.plugins)),{{
        zoom:{{pan:{{enabled:true,mode:'x'}},zoom:{{wheel:{{enabled:true}},pinch:{{enabled:true}},mode:'x'}}}}
      }}),
      scales:{{
        x:{{stacked:stacked,ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}},
        y:{{stacked:stacked,title:{{display:true,text:_compHrMetric==='mah'?'mAh':'%',color:'#99aabb'}},
             ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}}
      }}
    }})
  }});
}}
function setCompHourlyMetric(m,btn){{
  _compHrMetric=m;
  document.querySelectorAll('.chart-toolbar button[onclick*=setCompHourlyMetric]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  buildCompHourlyChart();
}}
function setCompHourlyView(v,btn){{
  _compHrView=v;
  document.querySelectorAll('.chart-toolbar button[onclick*=setCompHourlyView]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  buildCompHourlyChart();
}}
window.addEventListener('load',function(){{ try{{ buildCompHourlyChart(); }}catch(e){{console.error('Comp hourly chart error:',e);}} }});

// Power comparison
let compPowerChart=null, _compPwComp='total', _compPwN=10;
function getCompPwDs(){{
  if(_compPwComp==='cpu')   return _compPwCpuDs;
  if(_compPwComp==='wifi')  return _compPwWfDs;
  if(_compPwComp==='wakelock') return _compPwWlDs;
  return _compPwTotDs;
}}
function buildCompPowerChart(){{
  const ds    = getCompPwDs();
  const lbls  = _compPwUids.slice(0,_compPwN);
  const sliced= ds.map(d=>Object.assign({{}},d,{{data:d.data.slice(0,_compPwN)}}));
  if(compPowerChart){{
    compPowerChart.data.labels=lbls;
    compPowerChart.data.datasets=sliced;
    compPowerChart.update(); return;
  }}
  const ctx=document.getElementById('compPowerCanvas');
  if(!ctx) return;
  compPowerChart=new Chart(ctx,{{type:'bar',data:{{labels:lbls,datasets:sliced}},
    options:Object.assign(JSON.parse(JSON.stringify(_baseChartOpts)),{{
      scales:{{
        x:{{ticks:{{color:'#99aabb',maxRotation:40}},grid:{{color:'#1e1e3a'}}}},
        y:{{title:{{display:true,text:'mAh',color:'#99aabb'}},ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}}
      }}
    }})
  }});
}}
function updateCompPowerChart(comp){{
  _compPwComp=comp;
  buildCompPowerChart();
}}
function updateCompPowerN(n){{
  _compPwN=n;
  buildCompPowerChart();
}}
window.addEventListener('load',function(){{ try{{ buildCompPowerChart(); }}catch(e){{console.error('Comp power chart error:',e);}} }});

// Stability radar
window.addEventListener('load',function(){{
  try{{
  const ctx=document.getElementById('compStabilityCanvas');
  if(!ctx||!_stabDs.length) return;
  new Chart(ctx,{{type:'radar',data:{{labels:_stabLbls,datasets:_stabDs}},
    options:{{responsive:true,animation:{{duration:400}},
      plugins:{{legend:{{labels:{{color:'#ccc',font:{{size:11}}}}}},
        tooltip:{{backgroundColor:'#1a1a3e',borderColor:'#00d4ff',borderWidth:1,titleColor:'#00d4ff',bodyColor:'#e0e0e0'}}}},
      scales:{{r:{{ticks:{{color:'#99aabb',backdropColor:'transparent',stepSize:1}},
                   grid:{{color:'#22224a'}},pointLabels:{{color:'#ccc',font:{{size:11}}}}}}}}
    }}
  }});
  }}catch(e){{console.error('Stability radar error:',e);}}
}});

// Wakelock comparison
let compWlChart=null, _compWlType='kernel', _compWlMetric='duration';
function buildCompWlChart(){{
  const isKernel=_compWlType==='kernel';
  const isDur=_compWlMetric==='duration';
  const lbls = isKernel?_kwlNms:_pwlNms;
  const ds   = isKernel?(isDur?_kwlDurDs:_kwlCntDs):(isDur?_pwlDurDs:_pwlCntDs);
  const yLbl = isDur?'Duration (s)':'Count';
  if(compWlChart){{
    compWlChart.data.labels=lbls;
    compWlChart.data.datasets=ds;
    compWlChart.options.scales.y.title.text=yLbl;
    compWlChart.update(); return;
  }}
  const ctx=document.getElementById('compWlCanvas');
  if(!ctx||!lbls.length) return;
  compWlChart=new Chart(ctx,{{type:'bar',data:{{labels:lbls,datasets:ds}},
    options:Object.assign(JSON.parse(JSON.stringify(_baseChartOpts)),{{
      scales:{{
        x:{{ticks:{{color:'#99aabb',maxRotation:45}},grid:{{color:'#1e1e3a'}}}},
        y:{{title:{{display:true,text:yLbl,color:'#99aabb'}},ticks:{{color:'#99aabb'}},grid:{{color:'#1e1e3a'}}}}
      }}
    }})
  }});
}}
function setCompWlType(t,btn){{
  _compWlType=t;
  document.querySelectorAll('.chart-toolbar button[onclick*=setCompWlType]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  if(compWlChart){{ compWlChart.destroy(); compWlChart=null; }}
  buildCompWlChart();
}}
function setCompWlMetric(m,btn){{
  _compWlMetric=m;
  document.querySelectorAll('.chart-toolbar button[onclick*=setCompWlMetric]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  buildCompWlChart();
}}
window.addEventListener('load',function(){{ try{{ buildCompWlChart(); }}catch(e){{console.error('Comp WL chart error:',e);}} }});

// Delta chart
let compDeltaChart=null;
let _deltaOrig = [...Array(_deltaUids.length).keys()];
let _deltaOrder = [..._deltaOrig];
function buildDeltaChart(){{
  const lbls  = _deltaOrder.map(i=>_deltaUids[i]);
  const vals  = _deltaOrder.map(i=>_deltaVals[i]);
  const cols  = _deltaOrder.map(i=>_deltaCols[i]);
  if(compDeltaChart){{
    compDeltaChart.data.labels=lbls;
    compDeltaChart.data.datasets[0].data=vals;
    compDeltaChart.data.datasets[0].backgroundColor=cols;
    compDeltaChart.update(); return;
  }}
  const ctx=document.getElementById('compDeltaCanvas');
  if(!ctx||!_deltaUids.length) return;
  compDeltaChart=new Chart(ctx,{{type:'bar',data:{{labels:lbls,datasets:[{{
    label:'Delta mAh (Build2 - Build1)',data:vals,backgroundColor:cols,borderWidth:1
  }}]}},
    options:Object.assign(JSON.parse(JSON.stringify(_baseChartOpts)),{{
      plugins:Object.assign(JSON.parse(JSON.stringify(_baseChartOpts.plugins)),{{
        tooltip:{{backgroundColor:'#1a1a3e',borderColor:'#00d4ff',borderWidth:1,titleColor:'#00d4ff',bodyColor:'#e0e0e0',
          callbacks:{{label:function(c){{return 'Δ: '+(c.parsed.y>0?'+':'')+c.parsed.y.toFixed(2)+' mAh';}}}}}}
      }}),
      scales:{{
        x:{{ticks:{{color:'#99aabb',maxRotation:40}},grid:{{color:'#1e1e3a'}}}},
        y:{{title:{{display:true,text:'Δ mAh',color:'#99aabb'}},ticks:{{color:'#99aabb'}},
             grid:{{color:'#1e1e3a'}},
             afterSetDimensions:function(ax){{ ax.options.min=Math.min(..._deltaVals)*1.1; ax.options.max=Math.max(..._deltaVals)*1.1; }}
           }}
      }}
    }})
  }});
}}
function sortDeltaChart(mode,btn){{
  document.querySelectorAll('.chart-toolbar button[onclick*=sortDeltaChart]').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  if(mode==='abs')      _deltaOrder=[..._deltaOrig].sort((a,b)=>Math.abs(_deltaVals[b])-Math.abs(_deltaVals[a]));
  else if(mode==='inc') _deltaOrder=[..._deltaOrig].filter(i=>_deltaVals[i]>0).sort((a,b)=>_deltaVals[b]-_deltaVals[a]);
  else if(mode==='dec') _deltaOrder=[..._deltaOrig].filter(i=>_deltaVals[i]<0).sort((a,b)=>_deltaVals[a]-_deltaVals[b]);
  buildDeltaChart();
}}
window.addEventListener('load',function(){{ try{{ buildDeltaChart(); }}catch(e){{console.error('Delta chart error:',e);}} }});
</script>
"""
    html += f'<footer>Generated by Android BugReport Analyzer &nbsp;|&nbsp; {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</footer>'
    html += '</body></html>'

    with open(output_path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print(f"  ✓  Comparative report: {output_path}")


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 14 — MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""\
            Android BugReport Analyzer
            ─────────────────────────
            Analyse one or more Android bugreport .txt files.
            Produces per-bugreport HTML report + graph, and (if ≥2 given)
            a comparative HTML report + comparison graph.
            """),
        epilog=textwrap.dedent("""\
            Examples:
              # Single bugreport
              python bugreport_analyzer.py bugreport_RC1.txt -l RC1

              # Two builds (individual + comparative)
              python bugreport_analyzer.py rc1.txt st5.txt -l RC1 ST5 -o ./out

              # Three builds with custom title
              python bugreport_analyzer.py a.txt b.txt c.txt \\
                    -l BuildA BuildB BuildC \\
                    -t "Sprint-42 Regression Analysis"
            """))

    parser.add_argument('paths', nargs='+', metavar='BUGREPORT',
                        help='Path(s) to bugreport .txt file(s)')
    parser.add_argument('-l', '--labels', nargs='+', metavar='LABEL',
                        help='Short labels for each bugreport (same order as paths). '
                             'Defaults to "Build1", "Build2", …')
    parser.add_argument('-o', '--output', metavar='DIR', default=None,
                        help='Output directory (default: directory of first bugreport)')
    parser.add_argument('-t', '--title', default=None,
                        help='Report title (default: auto-generated)')
    parser.add_argument('--no-graph', action='store_true',
                        help='Skip graph generation (faster, no matplotlib needed)')

    # ── Analysis threshold / expectation flags ─────────────────────────────
    thr_grp = parser.add_argument_group(
        'Analysis Thresholds',
        'Override defaults used for KPI colour-coding, anomaly detection, and RCA verdicts.')
    thr_grp.add_argument(
        '--expected-hours', type=float, default=None, metavar='H',
        help='Expected session run duration in hours (e.g. 20.0).  '
             'Sessions shorter than 85%% of this are flagged as critical in RCA.')
    thr_grp.add_argument(
        '--expected-drain', type=float, default=None, metavar='MAH_HR',
        help='Expected battery drain rate mAh/hr (e.g. 35.0).  '
             'Used as the anomaly detection baseline and RCA target instead of the '
             'computed average.  Also shown as a reference line on graphs.')
    thr_grp.add_argument(
        '--warn-drain', type=float, default=40.0, metavar='MAH_HR',
        help='Drain rate mAh/hr at or above which KPIs show WARNING.  Default: 40')
    thr_grp.add_argument(
        '--crit-drain', type=float, default=80.0, metavar='MAH_HR',
        help='Drain rate mAh/hr at or above which KPIs show CRITICAL.  Default: 80')
    thr_grp.add_argument(
        '--expected-capacity', type=int, default=None, metavar='MAH',
        help='Override the battery capacity in mAh (e.g. 4500).  '
             'Useful when bugreport capacity parsing returns 0.')
    thr_grp.add_argument(
        '--warn-temp', type=float, default=45.0, metavar='C',
        help='Thermal zone temperature \u00b0C at or above which RCA shows WARNING.  Default: 45')
    thr_grp.add_argument(
        '--crit-temp', type=float, default=80.0, metavar='C',
        help='Thermal zone temperature \u00b0C at or above which RCA shows CRITICAL.  Default: 80')
    thr_grp.add_argument(
        '--min-anr', type=int, default=1, metavar='N',
        help='ANR count at or above which RCA flags the issue.  Default: 1')
    thr_grp.add_argument(
        '--min-crash', type=int, default=1, metavar='N',
        help='Crash count at or above which RCA flags the issue.  Default: 1')
    thr_grp.add_argument(
        '--min-lmk', type=int, default=5, metavar='N',
        help='LMK kill count at or above which RCA flags memory pressure.  Default: 5')

    args = parser.parse_args()

    paths = args.paths
    labels = args.labels or [f'Build{i+1}' for i in range(len(paths))]

    thresholds = {
        'expected_hours':    args.expected_hours,
        'expected_drain':    args.expected_drain,
        'warn_drain':        args.warn_drain,
        'crit_drain':        args.crit_drain,
        'expected_capacity': args.expected_capacity,
        'warn_temp':         args.warn_temp,
        'crit_temp':         args.crit_temp,
        'min_anr':           args.min_anr,
        'min_crash':         args.min_crash,
        'min_lmk':           args.min_lmk,
    }

    # Validate
    if len(labels) != len(paths):
        parser.error(f'Number of labels ({len(labels)}) must match number of paths ({len(paths)})')

    for p in paths:
        if not os.path.isfile(p):
            parser.error(f'File not found: {p}')

    out_dir = args.output or os.path.dirname(os.path.abspath(paths[0]))
    # Strip stray trailing quotes/spaces that Windows shells leave when a
    # quoted path ends with a backslash  e.g.  -o "C:\Logs\ST5\"
    out_dir = out_dir.strip().strip('"').strip("'").rstrip('\\').rstrip('/') or '.'
    os.makedirs(out_dir, exist_ok=True)

    title = args.title or (
        f"BugReport Analysis — {', '.join(labels)} — {datetime.now().strftime('%Y-%m-%d')}")

    print('=' * 70)
    print('  Android BugReport Analyzer')
    print('=' * 70)
    print(f"  Bugreports : {len(paths)}")
    for p, l in zip(paths, labels):
        print(f"    [{l}]  {p}")
    print(f"  Output dir : {out_dir}")
    print(f"  Title      : {title}")
    print(f"  Thresholds : warn-drain={args.warn_drain:.0f} mAh/hr  "
          f"crit-drain={args.crit_drain:.0f} mAh/hr  "
          f"min-anr={args.min_anr}  min-crash={args.min_crash}  min-lmk={args.min_lmk}")
    if args.expected_hours    is not None:
        print(f"    Expected session   : {args.expected_hours:.1f} h")
    if args.expected_drain    is not None:
        print(f"    Expected drain     : {args.expected_drain:.1f} mAh/hr")
    if args.expected_capacity is not None:
        print(f"    Battery capacity   : {args.expected_capacity} mAh (override)")
    print('=' * 70)

    # ── Parse all bugreports ──────────────────────────────────────────────────
    all_data = []
    for path, label in zip(paths, labels):
        data = parse_bugreport(path, label, thresholds)
        all_data.append(data)

    # ── Generate individual reports & graphs ──────────────────────────────────
    all_labels = [d['label'] for d in all_data]
    for data in all_data:
        lbl = data['label']
        graph_file = f'{lbl}_Battery_Drain_Graph.png'
        graph_path = os.path.join(out_dir, graph_file)
        report_path = os.path.join(out_dir, f'{lbl}_Individual_Report.html')

        if not args.no_graph:
            generate_individual_graph(data, graph_path)

        generate_individual_report(data, graph_file if not args.no_graph else None,
                                   report_path, all_labels)

    # ── Generate comparative report (only if ≥2 bugreports) ──────────────────
    if len(all_data) >= 2:
        comp_graph_file = 'Comparative_Drain_Graph.png'
        comp_graph_path = os.path.join(out_dir, comp_graph_file)
        comp_report_path = os.path.join(out_dir, 'Comparative_Report.html')

        if not args.no_graph:
            generate_comparison_graph(all_data, comp_graph_path, title)

        generate_comparative_report(
            all_data,
            comp_graph_file if not args.no_graph else None,
            comp_report_path,
            title)

    # ── Summary ───────────────────────────────────────────────────────────────
    print('\n' + '=' * 70)
    print('  ✅  ALL REPORTS GENERATED')
    print('=' * 70)
    for data in all_data:
        lbl = data['label']
        disc = data['discharge']; pw = data['power_data']
        print(f"\n  [{lbl}]")
        print(f"    Battery   : {disc.get('start_pct',100)}% → {disc.get('end_pct','?')}%  "
              f"({pw['computed_drain']:.0f} mAh in {disc.get('duration_hr',0):.1f}h  "
              f"@ {data['drain_mah_per_hr']:.1f} mAh/hr)")
        print(f"    ANRs      : {len(data['anrs'])}")
        print(f"    Crashes   : {len(data['crashes'])}")
        print(f"    LMK kills : {len(data['lmk_events'])}")
        print(f"    Anomalies : {len(data['anomalies'])} hours elevated drain")
        print(f"    Report    : {os.path.join(out_dir, lbl + '_Individual_Report.html')}")
        if not args.no_graph:
            print(f"    Graph     : {os.path.join(out_dir, lbl + '_Battery_Drain_Graph.png')}")

    if len(all_data) >= 2:
        print(f"\n  Comparative report : {os.path.join(out_dir, 'Comparative_Report.html')}")

    print('=' * 70)


if __name__ == '__main__':
    main()
