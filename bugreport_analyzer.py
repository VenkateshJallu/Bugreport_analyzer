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

def detect_battery_anomalies(history, avg_drain_mah_hr, capacity_mah):
    anomalies = []
    if not history or capacity_mah == 0 or avg_drain_mah_hr <= 0:
        return anomalies
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
        if drain_mah > avg_drain_mah_hr * 1.5:
            anomalies.append({
                'hour': hr, 't_start_hr': hr, 't_end_hr': hr + 1,
                'drain_pct': drop, 'drain_mah': drain_mah,
                'vs_avg': drain_mah / avg_drain_mah_hr,
            })
    return anomalies


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 9 — MASTER PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def parse_bugreport(path, label):
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
    capacity = power_data['capacity'] or 4647
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
    anomalies = detect_battery_anomalies(history, drain_mah_per_hr, capacity)

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
    ax1.set_ylim(max(0, min(levels) - 5), 105)
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
    bc = ['#ff4444' if y > avg_mah * 1.5 else '#ffaa00' if y > avg_mah else '#00aa44' for y in by]
    ax1b.bar(bx, by, width=0.8, alpha=0.35, color=bc, zorder=1)
    ax1b.set_ylabel('Hourly Drain (mAh)', color='#ffaa00', fontsize=9)
    ax1b.tick_params(colors='#ffaa00')
    if avg_mah: ax1b.axhline(avg_mah, color='#ffaa00', linestyle=':', alpha=0.7)

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
        mpatches.Patch(color='#ff4444', alpha=0.7, label=f'>1.5× avg ({avg_mah*1.5:.0f} mAh/hr) ⚠'),
        mpatches.Patch(color='#ffaa00', alpha=0.7, label=f'>avg ({avg_mah:.0f} mAh/hr)'),
        mpatches.Patch(color='#00aa44', alpha=0.7, label='Normal'),
        mpatches.Patch(color='#ffff00', alpha=0.5, label='Screen events'),
    ]
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
        ax.set_ylim(max(0, min(lvs) - 5), 105)
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
</head><body>"""


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
    """Generate a full individual HTML report for one bugreport."""
    d   = data
    lbl = d['label']
    di  = d['device_info']
    disc= d['discharge']
    pw  = d['power_data']
    cap = pw['capacity'] or 4647
    computed = pw['computed_drain']
    avg_mah  = d['drain_mah_per_hr']
    dur_hr   = disc.get('duration_hr', 0)

    # Determine colour for drain KPI
    if avg_mah > 80:  drain_cls = 'red'
    elif avg_mah > 40: drain_cls = 'orange'
    else:             drain_cls = 'green'

    html  = _html_head(f"BugReport Analysis — {lbl}")
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
"""

    # Nav links
    nav_links = [f'<a href="{x}_Individual_Report.html">{x}</a>' for x in all_labels if x != lbl]
    if len(all_labels) > 1:
        nav_links.append('<a href="Comparative_Report.html">📊 Comparative</a>')
    if nav_links:
        html += '<div class="nav">' + ''.join(nav_links) + '</div>'

    # ── Battery KPIs ─────────────────────────────────────────────────────────
    html += '<div class="section" id="battery"><h2>🔋 Battery Overview</h2>'
    html += '<div class="kpi-grid">'
    html += _kpi(f"{disc.get('start_pct',100)}% → {disc.get('end_pct','?')}%", "Total Drain (%)")
    html += _kpi(f"{computed:.0f} mAh", "Computed Drain",
                 'red' if computed > 1500 else 'orange' if computed > 600 else 'green')
    html += _kpi(f"{avg_mah:.1f} mAh/hr", "Avg Drain Rate", drain_cls)
    html += _kpi(f"{dur_hr:.1f} h", "Session Duration")
    html += _kpi(f"{cap} mAh", "Battery Capacity")
    html += _kpi(f"{len(d['anomalies'])}", "Anomaly Hours",
                 'red' if d['anomalies'] else 'green')
    html += '</div>'

    # Graph
    if graph_filename:
        html += f'<div class="img-container"><img src="{graph_filename}" alt="Battery Drain Graph"/></div>'
        html += """<p style="color:#778899;font-size:12px;text-align:center">
        <strong>Top panel:</strong> Blue line = battery % over time. Bars = per-hour drain
        (red &gt;1.5×avg, orange &gt;avg, green normal). Yellow dashes = screen on/off events.<br>
        <strong>Bottom panel:</strong> Per-UID power breakdown (CPU / WiFi / Wakelock / Other).</p>"""

    # Anomaly detail
    if d['anomalies']:
        html += '<h3>⚠ Elevated Drain Hours</h3>'
        for an in d['anomalies']:
            html += (f'<div style="background:#1a0000;border:1px solid #ff4444;border-radius:6px;'
                     f'padding:10px 14px;margin:6px 0;">'
                     f'<strong style="color:#ff6666">Hour {an["hour"]+1}'
                     f' (T+{an["t_start_hr"]:.0f}h – T+{an["t_end_hr"]:.0f}h)</strong>'
                     f' &nbsp; Drain: <strong>{an["drain_mah"]:.0f} mAh</strong>'
                     f' ({an["drain_pct"]}%) &nbsp; vs avg: '
                     f'<strong style="color:#ff4444">{an["vs_avg"]:.1f}×</strong></div>')
    html += '</div>'

    # ── Estimated Power Use ───────────────────────────────────────────────────
    html += '<div class="section" id="power"><h2>⚡ Estimated Power Use (per UID)</h2>'
    if pw['per_uid']:
        max_mah = pw['per_uid'][0]['total_mah']
        rows = []
        for u in pw['per_uid'][:30]:
            t = u['total_mah']
            rows.append([
                u['uid'],
                u['package'],
                f"{t:.2f}{_bar(t, max_mah, 'red' if t > avg_mah else 'orange' if t > avg_mah * 0.5 else '')}",
                f"{u.get('cpu', 0):.2f}",
                f"{u.get('wifi', 0):.2f}",
                f"{u.get('wakelock', 0):.2f}",
                f"{u.get('sensors', 0):.2f}",
            ])
        html += _table(['UID', 'Package', 'Total (mAh)', 'CPU', 'WiFi', 'Wakelock', 'Sensors'],
                       rows, lambda r: 'critical' if float(r[2].split('<')[0]) > avg_mah else '')
    html += '</div>'

    # ── Kernel Wakelocks ─────────────────────────────────────────────────────
    html += '<div class="section" id="kwl"><h2>🔒 Kernel Wakelocks</h2>'
    if d['kernel_wakelocks']:
        max_sec = max((w['duration_sec'] for w in d['kernel_wakelocks']), default=1)
        rows = [(w['name'],
                 _duration_badge(w['duration_sec'], 3600, dur_hr * 3600 * 0.5),
                 f"{w['count']:,}",
                 _bar(w['duration_sec'], max_sec, 'red' if w['duration_sec'] > dur_hr * 3600 * 0.5 else 'orange'))
                for w in d['kernel_wakelocks']]
        html += _table(['Wakelock Name', 'Duration', 'Count', ''], rows)
    else:
        html += '<p style="color:#778899">No kernel wakelocks found.</p>'
    html += '</div>'

    # ── Partial Wakelocks ────────────────────────────────────────────────────
    html += '<div class="section" id="pwl"><h2>📱 Partial (App) Wakelocks</h2>'
    if d['partial_wakelocks']:
        max_sec = max((w['duration_sec'] for w in d['partial_wakelocks']), default=1)
        rows = [(w['uid'], w['name'],
                 _duration_badge(w['duration_sec'], 3600, dur_hr * 3600 * 0.5),
                 f"{w['count']:,}")
                for w in sorted(d['partial_wakelocks'], key=lambda x: x['duration_sec'], reverse=True)[:40]]
        html += _table(['UID', 'Wakelock Name', 'Duration', 'Count'], rows)
    else:
        html += '<p style="color:#778899">No partial wakelocks found.</p>'
    html += '</div>'

    # ── ANRs ─────────────────────────────────────────────────────────────────
    html += f'<div class="section" id="anr"><h2>🚫 ANR Events ({len(d["anrs"])})</h2>'
    if d['anrs']:
        for a in d['anrs'][:20]:
            trace_html = f'<pre>{_esc(a["trace"][:800])}</pre>' if a.get('trace') else ''
            html += (f'<div class="anr-box">'
                     f'<h4>⏱ {a["time"]}  &nbsp; Process: <strong>{_esc(a["process"])}</strong>'
                     f'  &nbsp; {_badge(a["source"], "info")}</h4>'
                     f'<p>{_esc(a["reason"][:300])}</p>{trace_html}</div>')
    else:
        html += '<p style="color:#00cc66">✅ No ANRs detected.</p>'
    html += '</div>'

    # ── Crashes ──────────────────────────────────────────────────────────────
    html += f'<div class="section" id="crash"><h2>💥 Crashes ({len(d["crashes"])})</h2>'
    if d['crashes']:
        for c in d['crashes'][:20]:
            trace_html = f'<pre>{_esc(c["trace"][:800])}</pre>' if c.get('trace') else ''
            html += (f'<div class="crash-box">'
                     f'<h4>💥 {c["time"]}  &nbsp; <strong>{_esc(c["type"])}</strong>'
                     f'  — {_esc(c["process"])}  &nbsp; {_badge(c["signal"][:40], "high")}</h4>'
                     f'{trace_html}</div>')
    else:
        html += '<p style="color:#00cc66">✅ No crashes detected.</p>'
    html += '</div>'

    # ── LMK ──────────────────────────────────────────────────────────────────
    html += (f'<div class="section" id="lmk"><h2>🗑 Low Memory Killer (LMK)'
             f'  {_badge(str(len(d["lmk_events"])) + " kills", "high" if d["lmk_events"] else "normal")}</h2>')
    if d['lmk_events']:
        rows = [(e['time'], e['process'], f"{e['size_kb']:,} KB" if e['size_kb'] else '—',
                 e.get('adj',''), e['source'])
                for e in d['lmk_events'][:30]]
        html += _table(['Time', 'Process', 'RSS', 'ADJ', 'Source'], rows)
    else:
        html += '<p style="color:#00cc66">✅ No LMK events detected.</p>'
    html += '</div>'

    # ── Thermal ──────────────────────────────────────────────────────────────
    html += (f'<div class="section" id="thermal"><h2>🌡 Thermal'
             f'  {_badge(str(d["throttle_count"]) + " throttle events", "high" if d["throttle_count"] > 5 else "normal")}</h2>')
    if d['peak_temps']:
        rows = sorted(d['peak_temps'].items(), key=lambda x: x[1], reverse=True)
        t_rows = [(zone, f'{val:.1f} °C',
                   _badge('HOT', 'critical') if val > 80 else
                   _badge('WARM', 'high') if val > 45 else
                   _badge('OK', 'normal'))
                  for zone, val in rows[:20]]
        html += _table(['Zone', 'Peak Temperature', 'Status'], t_rows)
    if d['thermal_events'][:5]:
        html += '<h3>Recent Throttle Events</h3>'
        for te in d['thermal_events'][:10]:
            html += f'<p style="color:#ff8800;font-size:12px">⚠ {te["time"]}  {te["event"]}</p>'
    if not d['peak_temps'] and not d['thermal_events']:
        html += '<p style="color:#00cc66">✅ No thermal issues detected.</p>'
    html += '</div>'

    # ── Root Cause Summary ────────────────────────────────────────────────────
    html += '<div class="section" id="rca"><h2>🔍 Root Cause Summary</h2>'
    rca_items = []

    # Battery drain issues
    if avg_mah > 80:
        rca_items.append(('critical', f'Excessive battery drain: {avg_mah:.1f} mAh/hr (expected &lt;40 mAh/hr for standby)'))
    elif avg_mah > 40:
        rca_items.append(('high', f'Elevated battery drain: {avg_mah:.1f} mAh/hr'))

    # Long-held partial wakelocks
    for w in sorted(d['partial_wakelocks'], key=lambda x: x['duration_sec'], reverse=True)[:3]:
        if w['duration_sec'] > dur_hr * 3600 * 0.8:
            rca_items.append(('critical',
                              f'<strong>{w["name"]}</strong> (UID {w["uid"]}) wakelock held for '
                              f'{_duration_badge(w["duration_sec"])} — prevents deep sleep'))

    # Kernel wakelock high hold time
    for w in d['kernel_wakelocks'][:3]:
        if w['duration_sec'] > dur_hr * 3600 * 0.5:
            rca_items.append(('high',
                              f'Kernel wakelock <strong>{w["name"]}</strong> active '
                              f'{_duration_badge(w["duration_sec"])}'))

    # ANR
    if d['anrs']:
        rca_items.append(('high', f'{len(d["anrs"])} ANR event(s) detected — may cause user-visible hangs'))

    # Crashes
    fatal_crashes = [c for c in d['crashes'] if 'FATAL' in c['type'] or 'Native' in c['type']]
    if fatal_crashes:
        rca_items.append(('critical', f'{len(fatal_crashes)} fatal/native crash(es) detected'))
    elif d['crashes']:
        rca_items.append(('high', f'{len(d["crashes"])} crash event(s) detected'))

    # LMK
    if len(d['lmk_events']) > 5:
        rca_items.append(('high', f'{len(d["lmk_events"])} LMK kills — possible memory pressure'))

    # Thermal throttle
    if d['throttle_count'] > 5:
        rca_items.append(('high', f'{d["throttle_count"]} thermal throttle events — possible overheating'))

    # High-CPU UIDs
    for u in pw['per_uid'][:5]:
        if u.get('cpu', 0) > 30:
            rca_items.append(('high',
                              f'UID {u["uid"]} ({u["package"]}) consuming {u["cpu"]:.1f} mAh on CPU'))

    if not rca_items:
        rca_items.append(('normal', 'No significant issues detected.'))

    cls_map = {'critical': 'critical', 'high': 'high', 'normal': 'normal'}
    badge_map = {'critical': 'critical', 'high': 'high', 'normal': 'normal'}
    for severity, msg in rca_items:
        html += (f'<div style="background:#0d0d1a;border-left:3px solid '
                 f'{"#ff4444" if severity=="critical" else "#ff8800" if severity=="high" else "#00cc66"}'
                 f';padding:10px 16px;margin:6px 0;border-radius:0 6px 6px 0;">'
                 f'{_badge(severity.upper(), badge_map.get(severity,"info"))} {msg}</div>')

    html += '</div>'

    # ── Footer ────────────────────────────────────────────────────────────────
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
    n = len(all_data)
    html = _html_head(f"Comparative Analysis — {title}")
    html += f"""
<div class="header">
  <h1>📊 Comparative Battery & Stability Analysis</h1>
  <div class="subtitle">{title} &nbsp;|&nbsp; {n} build(s) compared</div>
</div>
<div class="nav">
"""
    for d in all_data:
        html += f'<a href="{d["label"]}_Individual_Report.html">📄 {d["label"]}</a>'
    html += '</div>'

    # ── Battery comparison KPIs ───────────────────────────────────────────────
    html += '<div class="section"><h2>🔋 Battery Drain Comparison</h2>'
    html += '<div class="kpi-grid">'
    for d in all_data:
        disc = d['discharge']; pw = d['power_data']
        html += _kpi(f"{d['label']}", "Build")
        html += _kpi(f"{disc.get('drain_pct','?')}%", f"{d['label']} Drain %",
                     'red' if disc.get('drain_pct', 0) > 30 else 'orange' if disc.get('drain_pct', 0) > 15 else 'green')
        html += _kpi(f"{pw['computed_drain']:.0f} mAh", f"{d['label']} Total",
                     'red' if pw['computed_drain'] > 1500 else 'orange' if pw['computed_drain'] > 600 else 'green')
        html += _kpi(f"{d['drain_mah_per_hr']:.1f} mAh/hr", f"{d['label']} Rate",
                     'red' if d['drain_mah_per_hr'] > 80 else 'orange' if d['drain_mah_per_hr'] > 40 else 'green')
    html += '</div>'

    # Relative comparison
    if n >= 2:
        rates = [(d['label'], d['drain_mah_per_hr']) for d in all_data]
        best  = min(rates, key=lambda x: x[1])
        worst = max(rates, key=lambda x: x[1])
        ratio = worst[1] / best[1] if best[1] > 0 else 1
        verdict_cls = 'fail' if ratio > 2 else 'warn' if ratio > 1.3 else 'pass'
        html += f'<div class="verdict {verdict_cls}">'
        html += f'Best: {best[0]} @ {best[1]:.1f} mAh/hr &nbsp;|&nbsp; '
        html += f'Worst: {worst[0]} @ {worst[1]:.1f} mAh/hr &nbsp;|&nbsp; '
        html += f'Ratio: {ratio:.1f}× difference'
        html += '</div>'

    # Comparison graph
    if comp_graph_filename:
        html += f'<div class="img-container"><img src="{comp_graph_filename}" alt="Comparison Graph"/></div>'
    html += '</div>'

    # ── Side-by-side power table ──────────────────────────────────────────────
    html += '<div class="section"><h2>⚡ Power Use — Side by Side</h2>'
    html += '<div class="comp-grid">'
    for d in all_data:
        pw = d['power_data']
        max_mah = pw['per_uid'][0]['total_mah'] if pw['per_uid'] else 1
        html += f'<div><h3>{d["label"]}</h3>'
        rows = [(u['uid'], u['package'][:28], f"{u['total_mah']:.2f}",
                 f"{u.get('cpu',0):.2f}", f"{u.get('wakelock',0):.2f}")
                for u in pw['per_uid'][:15]]
        html += _table(['UID', 'Package', 'mAh', 'CPU', 'WL'], rows)
        html += '</div>'
    html += '</div></div>'

    # ── ANR / Crash / LMK comparison ─────────────────────────────────────────
    html += '<div class="section"><h2>🚨 Stability Comparison</h2>'
    html += '<div class="comp-grid">'
    for d in all_data:
        lbl = d['label']
        html += f'<div><h3>{lbl}</h3>'
        html += '<table><tbody>'
        html += f'<tr><td>ANRs</td><td>{_badge(str(len(d["anrs"])), "critical" if d["anrs"] else "normal")}</td></tr>'
        fatal = len([c for c in d['crashes'] if 'FATAL' in c['type'] or 'Native' in c['type']])
        html += f'<tr><td>Fatal Crashes</td><td>{_badge(str(fatal), "critical" if fatal else "normal")}</td></tr>'
        html += f'<tr><td>Total Crashes</td><td>{_badge(str(len(d["crashes"])), "high" if d["crashes"] else "normal")}</td></tr>'
        html += f'<tr><td>LMK kills</td><td>{_badge(str(len(d["lmk_events"])), "high" if d["lmk_events"] else "normal")}</td></tr>'
        html += f'<tr><td>Thermal Throttles</td><td>{_badge(str(d["throttle_count"]), "high" if d["throttle_count"] > 5 else "normal")}</td></tr>'
        html += f'<tr><td>Battery Anomaly Hours</td><td>{_badge(str(len(d["anomalies"])), "high" if d["anomalies"] else "normal")}</td></tr>'
        html += '</tbody></table></div>'
    html += '</div></div>'

    # ── Wakelock comparison ───────────────────────────────────────────────────
    html += '<div class="section"><h2>🔒 Wakelock Comparison</h2>'
    html += '<div class="comp-grid">'
    for d in all_data:
        html += f'<div><h3>{d["label"]} — Kernel Wakelocks</h3>'
        rows = [(w['name'][:40], _duration_badge(w['duration_sec']), f"{w['count']:,}")
                for w in d['kernel_wakelocks'][:10]]
        html += _table(['Name', 'Duration', 'Count'], rows) if rows else '<p>None found</p>'
        html += f'<h3>{d["label"]} — App Wakelocks (Top 5)</h3>'
        rows = [(w['uid'], w['name'][:30], _duration_badge(w['duration_sec']))
                for w in sorted(d['partial_wakelocks'], key=lambda x: x['duration_sec'], reverse=True)[:5]]
        html += _table(['UID', 'Name', 'Duration'], rows) if rows else '<p>None found</p>'
        html += '</div>'
    html += '</div></div>'

    # ── Delta analysis (component-level diff for 2 builds) ───────────────────
    if n == 2:
        d0, d1 = all_data
        html += '<div class="section"><h2>📈 Component-Level Delta Analysis</h2>'
        uids0 = {u['uid']: u for u in d0['power_data']['per_uid']}
        uids1 = {u['uid']: u for u in d1['power_data']['per_uid']}
        all_uids = sorted(set(uids0) | set(uids1),
                          key=lambda u: abs(uids0.get(u, {}).get('total_mah', 0) -
                                           uids1.get(u, {}).get('total_mah', 0)), reverse=True)
        rows = []
        for uid in all_uids[:25]:
            u0 = uids0.get(uid, {}); u1 = uids1.get(uid, {})
            t0 = u0.get('total_mah', 0); t1 = u1.get('total_mah', 0)
            delta = t1 - t0
            pkg = u0.get('package') or u1.get('package') or uid
            clr = '#ff4444' if delta > 10 else '#00cc66' if delta < -5 else '#cccccc'
            rows.append([uid, pkg[:32],
                         f'{t0:.2f}', f'{t1:.2f}',
                         f'<span style="color:{clr};font-weight:600">{delta:+.2f}</span>'])
        html += _table([f'UID', 'Package', f'{d0["label"]} (mAh)',
                        f'{d1["label"]} (mAh)', 'Delta (mAh)'], rows)
        html += '</div>'

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

    args = parser.parse_args()

    paths = args.paths
    labels = args.labels or [f'Build{i+1}' for i in range(len(paths))]

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
    print('=' * 70)

    # ── Parse all bugreports ──────────────────────────────────────────────────
    all_data = []
    for path, label in zip(paths, labels):
        data = parse_bugreport(path, label)
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
