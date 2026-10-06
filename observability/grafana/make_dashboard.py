"""สร้าง dashboard "AI Ecosystem — CNC Tool Life" ของ Grafana (provisioning/dashboards/ai_ecosystem_overview.json)

แก้ panel ที่ไฟล์นี้แล้วรันใหม่ (Grafana โหลดไฟล์ที่เปลี่ยนเองภายใน ~10 วินาที)::

    python observability/grafana/make_dashboard.py

ชื่อ metric = "ai_ecosystem_" + ชื่อใน backend/core/observability.py (METRICS) และ app/features/health/telemetry.py (gauge)
"""
import json
import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "provisioning" / "dashboards" / "ai_ecosystem_overview.json"
PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}
TEMPO = {"type": "tempo", "uid": "tempo"}
BE = 'job="ai-ecosystem-backend"'
panels, _id, _y = [], [0], [0]


def nid():
    _id[0] += 1
    return _id[0]


def row(title):
    panels.append({"type": "row", "title": title, "id": nid(), "collapsed": False,
                   "gridPos": {"h": 1, "w": 24, "x": 0, "y": _y[0]}, "panels": []})
    _y[0] += 1


def tgt(expr, legend="", ref="A", instant=False, fmt=None):
    t = {"datasource": PROM, "editorMode": "code", "expr": expr, "legendFormat": legend, "refId": ref,
         "range": not instant, "instant": instant}
    if fmt:
        t["format"] = fmt
    return t


def panel(kind, title, targets, x, w, h, desc="", unit=None, ds=PROM, options=None, fc=None, overrides=None):
    defaults = {"unit": unit} if unit else {}
    defaults.update(fc or {})
    p = {"type": kind, "title": title, "description": desc, "id": nid(), "datasource": ds,
         "gridPos": {"h": h, "w": w, "x": x, "y": _y[0]}, "targets": targets,
         "fieldConfig": {"defaults": defaults, "overrides": overrides or []}, "options": options or {}}
    panels.append(p)
    return p


def thresholds(*steps):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for v, c in steps]}


def mapping(pairs):
    return [{"type": "value", "options": {str(k): {"text": t, "color": c, "index": i} for i, (k, t, c) in enumerate(pairs)}}]


TS = {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True}, "tooltip": {"mode": "multi", "sort": "none"}}
STAT = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "colorMode": "background",
        "graphMode": "none", "textMode": "value_and_name", "justifyMode": "auto", "orientation": "horizontal"}

# ───────────────────────────── ภาพรวม
row("ภาพรวมระบบ")
panel("stat", "การเชื่อมต่อบริการ", [tgt("ai_ecosystem_system_component_up", "{{component}}", instant=True)], 0, 6, 4,
      "DB / Redis / MinIO — ชุดเดียวกับ /api/v1/health/components", options=STAT,
      fc={"mappings": mapping([(1, "เชื่อมต่อ", "green"), (0, "หลุด", "red")]), "thresholds": thresholds((None, "red"), (1, "green"))})
panel("stat", "แบบจำลองที่โหลดอยู่", [tgt("ai_ecosystem_model_ready", "{{model}} · {{version}}", instant=True)], 6, 8, 4,
      "1 = โหลดจาก MinIO สำเร็จ + ผ่าน sha256 และ self-test", options={**STAT, "textMode": "name"},
      fc={"mappings": mapping([(1, "READY", "green"), (0, "ไม่พร้อม", "red")]), "thresholds": thresholds((None, "red"), (1, "green"))})
panel("stat", "รอผู้ตรวจยืนยัน", [tgt("ai_ecosystem_tool_vision_pending_reviews", "งานตรวจใบมีด", instant=True)], 14, 3, 4,
      "งานตรวจใบมีดสถานะ PENDING_REVIEW", options={**STAT, "textMode": "value"},
      fc={"thresholds": thresholds((None, "green"), (1, "orange"))})
panel("stat", "ใบเบิกดอกค้าง", [tgt("ai_ecosystem_tool_vision_open_requisitions", "{{status}}", instant=True)], 17, 4, 4,
      "OPEN = รอเบิกจากคลัง · ISSUED = เบิกแล้วรอติดตั้ง (เครื่องหยุดรอดอกใหม่)", options=STAT,
      fc={"thresholds": thresholds((None, "green"), (1, "orange"))})
panel("stat", "ค่าวัดจริงรอ retrain", [tgt('ai_ecosystem_tool_vision_retrain_pool{kind="all"}', "ใบ", instant=True)], 21, 3, 4,
      "ค่า VB ที่วัดจริงและยังไม่เคยใช้ฝึก", options={**STAT, "textMode": "value", "colorMode": "value"})
_y[0] += 4

# ───────────────────────────── RUL
row("Time series — RUL ดอกกัด (GRU direct-RUL)")
panel("timeseries", "RUL ที่เหลือ (นาทีของเวลาตัด)", [
    tgt("ai_ecosystem_tool_rul_remaining_life_minutes", "{{machine}}/{{tool}} P50", "A"),
    tgt("ai_ecosystem_tool_rul_remaining_life_p10_minutes", "{{machine}}/{{tool}} P10", "B")], 0, 12, 8,
      "P50 และขอบล่าง P10 (REPLACE_NOW เมื่อ P10 ≤ เกณฑ์นโยบาย) — ไม่มีค่าในช่วง break-in ของดอกใหม่", unit="m", options=TS,
      fc={"custom": {"lineWidth": 2, "showPoints": "never", "spanNulls": False}},
      overrides=[{"matcher": {"id": "byRegexp", "options": ".*P10"},
                  "properties": [{"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [6, 4]}}, {"id": "custom.lineWidth", "value": 1}]}])
panel("state-timeline", "คำแนะนำของแบบจำลองรายเครื่อง", [tgt("ai_ecosystem_tool_rul_recommendation_level", "{{machine}}/{{tool}}")], 12, 12, 8,
      "OK → WATCH (สึกเร่ง) → PLAN_REPLACEMENT → REPLACE_NOW (interlock หยุดป้อนรอผู้ควบคุม)",
      options={"showValue": "auto", "mergeValues": True, "rowHeight": 0.8, "legend": {"showLegend": False}},
      fc={"mappings": mapping([(0, "OK", "green"), (1, "WATCH", "yellow"), (2, "PLAN", "orange"), (3, "REPLACE_NOW", "red")]),
          "thresholds": thresholds((None, "green"), (1, "yellow"), (2, "orange"), (3, "red")), "color": {"mode": "thresholds"}})
_y[0] += 8
panel("timeseries", "Data drift ของอินพุต (|z| สูงสุด)", [tgt("ai_ecosystem_tool_rul_input_drift", "{{machine}}/{{tool}}")], 0, 8, 7,
      "ค่าเฉลี่ยรายรันของเซนเซอร์เทียบสถิติชุดฝึก — เกิน 3 = อินพุตต่างจากที่แบบจำลองเคยเห็น (ควรตรวจเซนเซอร์/งาน)", options=TS,
      fc={"custom": {"thresholdsStyle": {"mode": "line+area"}, "showPoints": "never"},
          "thresholds": thresholds((None, "transparent"), (3, "red"))})
panel("stat", "สถานะเครื่อง", [tgt("ai_ecosystem_tool_rul_stream_state == 1", "{{machine}}/{{tool}}: {{state}}", instant=True)], 8, 5, 7,
      "CUTTING · HOLD (รอผู้ควบคุมยืนยันถอดดอก) · COMPLETED (ถอดแล้ว)", options={**STAT, "textMode": "name", "colorMode": "none",
                                                                                 "orientation": "vertical"})
panel("timeseries", "เวลาพยากรณ์ RUL ต่อรัน (p95)", [
    tgt(f"histogram_quantile(0.95, sum by (le, machine) (rate(ai_ecosystem_tool_rul_inference_duration_seconds_bucket{{{BE}}}[5m])))",
        "{{machine}}")], 13, 6, 7, "สร้างหน้าต่างอินพุต 29 รัน + GRU ensemble บน CPU", unit="s", options=TS)
panel("bargauge", "ผลประเมินหลังถอดดอก (ดอกล่าสุดของแต่ละเครื่อง)", [
    tgt("ai_ecosystem_tool_rul_last_eval_mae_minutes", "{{machine}}/{{tool}} MAE ทั้งอายุ", "A", instant=True),
    tgt("ai_ecosystem_tool_rul_last_eval_mae_last20_minutes", "{{machine}}/{{tool}} MAE 20% ท้าย", "B", instant=True)], 19, 5, 7,
      "เทียบกับ VB จริงหลังถอดดอกเท่านั้น (เหมือนหน้า Reports) — ระหว่างใช้งานไม่มีค่าจริง", unit="m",
      options={"displayMode": "basic", "orientation": "horizontal", "showUnfilled": True,
               "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
      fc={"thresholds": thresholds((None, "green"), (2, "yellow"), (5, "red")), "min": 0})
_y[0] += 7
panel("timeseries", "จำนวนพยากรณ์ตามคำแนะนำ (ต่อ 5 นาที)", [
    tgt("sum by (recommendation) (increase(ai_ecosystem_tool_rul_predictions_total[5m]))", "{{recommendation}}")], 0, 12, 6,
      "1 พยากรณ์ต่อ 1 รันที่บันทึก (ทุกเครื่องรวมกัน)", options=TS,
      fc={"custom": {"drawStyle": "bars", "fillOpacity": 70, "stacking": {"mode": "normal"}}},
      overrides=[{"matcher": {"id": "byName", "options": n}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]}
                 for n, c in (("OK", "green"), ("WATCH", "yellow"), ("PLAN_REPLACEMENT", "orange"), ("REPLACE_NOW", "red"))])
panel("timeseries", "เวลาตัดสะสมของดอกบนเครื่อง", [tgt("ai_ecosystem_tool_rul_cutting_time_minutes", "{{machine}}/{{tool}}")], 12, 12, 6,
      "รีเซ็ตเป็น 0 เมื่อติดตั้งดอกใหม่", unit="m", options=TS)
_y[0] += 6

# ───────────────────────────── Vision
row("Vision — วัดรอยสึก VB จากภาพใบมีด (ResNet-18)")
panel("bargauge", "งานตรวจใบมีด (ช่วงเวลาที่เลือก)", [
    tgt("sum by (verdict) (increase(ai_ecosystem_tool_vision_inspections_total[$__range]))", "{{verdict}}", instant=True)], 0, 6, 7,
      "ผล AI ระดับดอก (VB เฉลี่ย 4 ใบ): OK < 103 · MONITOR 103–140 · REPLACE ≥ 140 µm", unit="none",
      options={"displayMode": "basic", "orientation": "horizontal", "showUnfilled": True,
               "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
      fc={"decimals": 0},
      overrides=[{"matcher": {"id": "byName", "options": n}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]}
                 for n, c in (("OK", "green"), ("MONITOR", "orange"), ("REPLACE", "red"))])
panel("piechart", "ที่มาของค่า VB ที่ผู้ตรวจยืนยัน", [
    tgt("sum by (source) (increase(ai_ecosystem_tool_vision_blade_reviews_total[$__range]))", "{{source}}", instant=True)], 6, 5, 7,
      "AI = ยอมรับค่า AI · MANUAL = ผู้ตรวจวัดจริงแล้วกรอกค่า (ใช้ retrain)",
      options={"pieType": "donut", "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True, "values": ["value"]},
               "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}, fc={"decimals": 0})
panel("stat", "MAE ของ AI เทียบค่าวัดจริง (สะสม)", [
    tgt("ai_ecosystem_tool_vision_measured_mae_um", "MAE", "A", instant=True),
    tgt("ai_ecosystem_tool_vision_measured_blades", "จำนวนใบที่วัด", "B", instant=True)], 11, 5, 7,
      "ทุกใบที่ผู้ตรวจวัดจริง (เก็บใน DB) — ผลทดสอบตอนฝึก: test ดอก 8–10 MAE 25.9 µm",
      options={**STAT, "colorMode": "value", "orientation": "vertical"},
      fc={"thresholds": thresholds((None, "green"), (26, "orange"), (35, "red"))},
      overrides=[{"matcher": {"id": "byName", "options": "MAE"}, "properties": [{"id": "unit", "value": "suffix: µm"}, {"id": "decimals", "value": 1}]},
                 {"matcher": {"id": "byName", "options": "จำนวนใบที่วัด"},
                  "properties": [{"id": "unit", "value": "none"}, {"id": "color", "value": {"mode": "fixed", "fixedColor": "text"}}]}])
panel("timeseries", "Pool ค่าวัดจริงสำหรับ retrain", [
    tgt('ai_ecosystem_tool_vision_retrain_pool{kind="new_tools"}', "ดอกใหม่ที่วัดจริง", "A"),
    tgt('ai_ecosystem_tool_vision_retrain_pool{kind="all"}', "ภาพทั้งหมด", "B"),
    tgt('ai_ecosystem_tool_vision_retrain_pool{kind="large_error"}', "ภาพที่ AI คลาด > 15 µm", "C")], 16, 8, 7,
      "retrain เริ่มอัตโนมัติเมื่อดอกใหม่ที่วัดจริงครบ 3 ดอก (เส้นแดง = VISION_RETRAIN_MIN_TOOLS)", options=TS,
      fc={"custom": {"thresholdsStyle": {"mode": "line"}, "showPoints": "never"}, "thresholds": thresholds((None, "transparent"), (3, "red")),
          "decimals": 0})
_y[0] += 7
panel("stat", "เวลาวัด VB ต่อดอก (เฉลี่ย, CPU)", [
    tgt(f"sum(ai_ecosystem_tool_vision_inference_duration_seconds_sum{{{BE}}}) / sum(ai_ecosystem_tool_vision_inference_duration_seconds_count{{{BE}}})",
        "เฉลี่ย", instant=True)], 0, 6, 5, "4 ภาพต่อ 1 ดอก — นับตั้งแต่ backend เริ่มทำงาน", unit="s",
      options={**STAT, "colorMode": "value", "textMode": "value"}, fc={"decimals": 2})
panel("bargauge", "งาน retrain (ช่วงเวลาที่เลือก)", [
    tgt("sum by (outcome) (increase(ai_ecosystem_tool_vision_retrain_jobs_total[$__range]))", "{{outcome}}", instant=True)], 6, 6, 5,
      "gate: MAE ดอก 7 แย่ลงไม่เกิน 1 µm และค่าที่วัดล่าสุดไม่แย่กว่าเดิม", unit="none",
      options={"displayMode": "basic", "orientation": "horizontal", "showUnfilled": True,
               "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}, fc={"decimals": 0},
      overrides=[{"matcher": {"id": "byName", "options": n}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]}
                 for n, c in (("gate_passed", "green"), ("gate_failed", "orange"), ("error", "red"))])
panel("stat", "เวลา retrain เฉลี่ย (GPU)", [
    tgt('sum(ai_ecosystem_tool_vision_retrain_duration_seconds_sum{job="ai-ecosystem-trainer-worker"}) / '
        'sum(ai_ecosystem_tool_vision_retrain_duration_seconds_count{job="ai-ecosystem-trainer-worker"})', "เฉลี่ย", instant=True)],
      12, 6, 5, "นับตั้งแต่ trainer-worker เริ่มทำงาน", unit="s", options={**STAT, "colorMode": "value", "textMode": "value"})
panel("bargauge", "การเปลี่ยนแบบจำลอง (ช่วงเวลาที่เลือก)", [
    tgt("sum by (action) (increase(ai_ecosystem_tool_vision_model_changes_total[$__range]))", "{{action}}", instant=True)], 18, 6, 5,
      "promote / reject candidate และสลับเวอร์ชัน (activate) โดยผู้ดูแล", unit="none",
      options={"displayMode": "basic", "orientation": "horizontal", "showUnfilled": True,
               "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}, fc={"decimals": 0})
_y[0] += 5

# ───────────────────────────── API
row("Backend API")
R = f'ai_ecosystem_http_server_duration_milliseconds'
panel("timeseries", "Request ต่อวินาที ตาม endpoint", [
    tgt(f"sum by (http_target) (rate({R}_count{{{BE}}}[1m]))", "{{http_target}}")], 0, 9, 8, "ไม่นับ health check และ WebSocket สตรีม",
      unit="reqps", options=TS)
panel("timeseries", "เวลาตอบสนอง p95 ตาม endpoint", [
    tgt(f"histogram_quantile(0.95, sum by (le, http_target) (rate({R}_bucket{{{BE}}}[5m])))", "{{http_target}}")], 9, 9, 8,
      unit="ms", options=TS)
panel("timeseries", "Error rate", [
    tgt(f'(sum(rate({R}_count{{{BE},http_status_code=~"5.."}}[5m])) or vector(0)) / sum(rate({R}_count{{{BE}}}[5m]))', "5xx", "A"),
    tgt(f'(sum(rate({R}_count{{{BE},http_status_code=~"4.."}}[5m])) or vector(0)) / sum(rate({R}_count{{{BE}}}[5m]))', "4xx", "B")], 18, 6, 4,
      "4xx รวม token หมดอายุ / ข้อผิดพลาดของขั้นตอนงาน", unit="percentunit", options=TS,
      overrides=[{"matcher": {"id": "byName", "options": "5xx"}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "red"}}]},
                 {"matcher": {"id": "byName", "options": "4xx"}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "orange"}}]}])
_y[0] += 4
panel("timeseries", "Latency ของบริการ", [tgt("ai_ecosystem_system_component_latency_milliseconds", "{{component}}")], 18, 6, 4,
      "เวลาตรวจการเชื่อมต่อ DB / Redis / MinIO", unit="ms", options=TS)
_y[0] += 4

# ───────────────────────────── Logs + traces
row("Logs & Traces")
panel("table", "Trace ของงานหลัก (Tempo)", [
    {"datasource": TEMPO, "refId": "A", "queryType": "traceql", "limit": 20, "tableType": "traces",
     "query": '{resource.service.name=~"ai-ecosystem.*" && name=~"tool_.*"}'}], 0, 24, 7,
      "ถอดดอก → ถ่ายภาพ/วัด VB (tool_life.tool_removed → tool_vision.capture_eol) และ retrain ข้ามคิว ARQ (tool_vision.retrain) — กด Trace ID เพื่อดูทั้งเส้นทาง",
      ds=TEMPO)
_y[0] += 7
panel("logs", "Log ของ backend และ trainer-worker (Loki)", [
    {"datasource": LOKI, "refId": "A", "editorMode": "code", "expr": '{service_name=~"ai-ecosystem.*"}', "queryType": "range"}],
      0, 24, 10, "INFO ขึ้นไป พร้อม trace_id (กดเพื่อเปิด trace ใน Tempo)", ds=LOKI,
      options={"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending", "enableLogDetails": True, "dedupStrategy": "none"})

dash = {
    "uid": "ai-ecosystem-overview", "title": "AI Ecosystem — CNC Tool Life", "tags": ["ai-ecosystem", "tool-life", "vision"],
    "timezone": "browser", "schemaVersion": 39, "version": 2, "refresh": "10s", "editable": True,
    "time": {"from": "now-1h", "to": "now"}, "graphTooltip": 1,
    "description": "ติดตามระบบ: บริการ, แบบจำลอง RUL (GRU) และวัด VB (ResNet-18), งานผู้ตรวจ, retrain, API, log และ trace",
    "panels": panels, "templating": {"list": []}, "annotations": {"list": []},
}
OUT.write_text(json.dumps(dash, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("panels", len(panels), "->", OUT)
