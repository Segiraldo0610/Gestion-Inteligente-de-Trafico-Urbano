"""
utils/reporter.py — Genera reportes HTML y JSON de los resultados de prueba.
"""

import json
import os
from datetime import datetime
from typing import List, Dict
from utils.config import TestConfig


class TestReporter:

    def __init__(self, config: TestConfig):
        self.config = config
        self._ts    = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── JSON ─────────────────────────────────────────────────────

    def save_json(self, results: List[Dict]) -> str:
        path = os.path.join(self.config.output_dir, f"reporte_{self._ts}.json")
        payload = {
            "proyecto":   "Gestión Inteligente de Tráfico Urbano",
            "entrega":    "Segunda Entrega",
            "generado":   datetime.now().isoformat(),
            "hosts":      {
                "PC1": self.config.host_pc1,
                "PC2": self.config.host_pc2,
                "PC3": self.config.host_pc3,
            },
            "resumen": {
                "total":   len(results),
                "pass":    sum(1 for r in results if r["status"] == "PASS"),
                "fail":    sum(1 for r in results if r["status"] == "FAIL"),
                "skip":    sum(1 for r in results if r["status"] == "SKIP"),
            },
            "pruebas": results,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"  → JSON: {path}")
        return path

    # ── HTML ─────────────────────────────────────────────────────

    def save_html(self, results: List[Dict]) -> str:
        path = os.path.join(self.config.output_dir, f"reporte_{self._ts}.html")
        total   = len(results)
        passed  = sum(1 for r in results if r["status"] == "PASS")
        failed  = sum(1 for r in results if r["status"] == "FAIL")
        skipped = sum(1 for r in results if r["status"] == "SKIP")
        pct     = round(passed / total * 100, 1) if total else 0

        rows = ""
        for r in results:
            badge = {
                "PASS": '<span class="badge pass">✔ PASS</span>',
                "FAIL": '<span class="badge fail">✘ FAIL</span>',
                "SKIP": '<span class="badge skip">⊘ SKIP</span>',
            }.get(r["status"], r["status"])
            error_cell = f'<span class="error">{r["error"]}</span>' if r.get("error") else "—"
            data_str = json.dumps(r.get("data", {}), ensure_ascii=False, indent=2)
            rows += f"""
            <tr class="row-{r['status'].lower()}">
              <td>{r['name']}</td>
              <td>{badge}</td>
              <td>{r['duration_ms']:.0f} ms</td>
              <td>{error_cell}</td>
              <td><details><summary>ver datos</summary><pre>{data_str}</pre></details></td>
            </tr>"""

        perf_rows = ""
        perf_results = [r for r in results if r["name"].startswith("P0")]
        for r in perf_results:
            d = r.get("data", {})
            if "registros_en_bd" in d:
                perf_rows += f"""
                <tr>
                  <td>{r['name']}</td>
                  <td>{d.get('escenario','')}</td>
                  <td>{d.get('eventos_enviados','')}</td>
                  <td>{d.get('registros_en_bd','')}</td>
                  <td>{d.get('tasa_por_minuto','')}</td>
                  <td>—</td>
                </tr>"""
            elif "media_ms" in d:
                perf_rows += f"""
                <tr>
                  <td>{r['name']}</td>
                  <td>{d.get('escenario','')}</td>
                  <td>—</td>
                  <td>—</td>
                  <td>—</td>
                  <td>{d.get('media_ms','')} / {d.get('mediana_ms','')} / {d.get('p95_ms','')} ms</td>
                </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Reporte de Pruebas — Tráfico Urbano ISD 2026</title>
<style>
  :root {{
    --c-bg:     #0f1117;
    --c-card:   #1a1d27;
    --c-border: #2e3150;
    --c-text:   #e2e8f0;
    --c-muted:  #8892a4;
    --c-pass:   #22c55e;
    --c-fail:   #ef4444;
    --c-skip:   #f59e0b;
    --c-accent: #6366f1;
    --font:     'JetBrains Mono', 'Fira Code', monospace;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--c-bg);
    color: var(--c-text);
    font-family: var(--font);
    font-size: 13px;
    line-height: 1.6;
    padding: 32px 24px;
  }}
  h1 {{ font-size: 22px; color: var(--c-accent); margin-bottom: 4px; }}
  h2 {{ font-size: 15px; color: var(--c-text); margin: 32px 0 12px; }}
  .meta {{ color: var(--c-muted); font-size: 12px; margin-bottom: 28px; }}
  .summary {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 32px;
  }}
  .card {{
    background: var(--c-card);
    border: 1px solid var(--c-border);
    border-radius: 8px;
    padding: 16px;
    text-align: center;
  }}
  .card .num  {{ font-size: 32px; font-weight: 700; }}
  .card .lbl  {{ font-size: 11px; color: var(--c-muted); text-transform: uppercase; letter-spacing: 1px; }}
  .card.pass  .num {{ color: var(--c-pass); }}
  .card.fail  .num {{ color: var(--c-fail); }}
  .card.skip  .num {{ color: var(--c-skip); }}
  .card.total .num {{ color: var(--c-accent); }}
  .bar-wrap {{ background: var(--c-card); border-radius: 6px; height: 8px; overflow: hidden; margin-bottom: 28px; }}
  .bar {{ height: 100%; background: linear-gradient(90deg, var(--c-pass), var(--c-accent)); border-radius: 6px; transition: width .6s; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--c-card); border-radius: 8px; overflow: hidden; }}
  th {{ background: #252840; color: var(--c-muted); font-size: 11px; text-transform: uppercase; letter-spacing: .8px; padding: 10px 12px; text-align: left; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid var(--c-border); vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  .row-fail td {{ background: rgba(239,68,68,.06); }}
  .row-skip td {{ background: rgba(245,158,11,.04); }}
  .badge {{ font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px; }}
  .badge.pass {{ background: rgba(34,197,94,.15);  color: var(--c-pass); }}
  .badge.fail {{ background: rgba(239,68,68,.15);  color: var(--c-fail); }}
  .badge.skip {{ background: rgba(245,158,11,.15); color: var(--c-skip); }}
  .error {{ color: var(--c-fail); font-size: 11px; }}
  pre {{ font-size: 11px; color: var(--c-muted); white-space: pre-wrap; word-break: break-all; margin-top: 6px; }}
  details summary {{ cursor: pointer; color: var(--c-accent); font-size: 11px; }}
  .hosts {{ display: flex; gap: 16px; margin-bottom: 24px; }}
  .host {{ background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px; padding: 8px 14px; font-size: 12px; }}
  .host span {{ color: var(--c-accent); font-weight: 700; }}
</style>
</head>
<body>
<h1>Reporte de Pruebas Automatizadas</h1>
<p class="meta">
  Proyecto ISD 2026-30 — Gestión Inteligente de Tráfico Urbano &nbsp;|&nbsp;
  Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</p>

<div class="hosts">
  <div class="host"><span>PC1</span> {self.config.host_pc1} (Broker/Sensores)</div>
  <div class="host"><span>PC2</span> {self.config.host_pc2} (Analítica/Semáforos)</div>
  <div class="host"><span>PC3</span> {self.config.host_pc3} (Monitoreo/BD)</div>
</div>

<div class="summary">
  <div class="card total"><div class="num">{total}</div><div class="lbl">Total</div></div>
  <div class="card pass"> <div class="num">{passed}</div><div class="lbl">Pasaron</div></div>
  <div class="card fail"> <div class="num">{failed}</div><div class="lbl">Fallaron</div></div>
  <div class="card skip"> <div class="num">{skipped}</div><div class="lbl">Omitidas</div></div>
</div>
<div class="bar-wrap"><div class="bar" style="width:{pct}%"></div></div>

<h2>Resultados por Prueba</h2>
<table>
  <thead>
    <tr><th>Prueba</th><th>Estado</th><th>Duración</th><th>Error</th><th>Datos</th></tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

{"" if not perf_rows else f'''
<h2>Tabla de Métricas de Rendimiento (Tabla 1)</h2>
<table>
  <thead>
    <tr>
      <th>Prueba</th><th>Escenario</th><th>Eventos enviados</th>
      <th>Almacenados BD (2 min)</th><th>Tasa (reg/min)</th><th>Latencia (media/med/p95)</th>
    </tr>
  </thead>
  <tbody>{perf_rows}</tbody>
</table>
'''}

</body>
</html>"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  → HTML: {path}")
        return path
