#!/usr/bin/env python3
"""
=============================================================
Batería de Pruebas Automatizadas - Gestión Inteligente de Tráfico Urbano
ISD 2026-30 | Segunda Entrega
=============================================================
Uso:
    python run_tests.py [--host-pc1 IP] [--host-pc2 IP] [--host-pc3 IP]
                       [--suite all|functional|performance|fault]
                       [--report html|json|both]

Ejemplo:
    python run_tests.py --host-pc1 192.168.1.10 --host-pc2 192.168.1.11 \
                        --host-pc3 192.168.1.12 --suite all --report both
"""

import argparse
import sys
import time
import json
import os
from datetime import datetime

from tests.suite_funcional   import FunctionalTestSuite
from tests.suite_rendimiento import PerformanceTestSuite
from tests.suite_fallos      import FaultToleranceTestSuite
from utils.reporter          import TestReporter
from utils.config            import TestConfig


def parse_args():
    parser = argparse.ArgumentParser(
        description="Batería de pruebas automatizadas - Tráfico Urbano ISD"
    )
    parser.add_argument("--host-pc1", default="localhost", help="IP del PC1 (Broker/Sensores)")
    parser.add_argument("--host-pc2", default="localhost", help="IP del PC2 (Analítica/Semáforos)")
    parser.add_argument("--host-pc3", default="localhost", help="IP del PC3 (Monitoreo/BD principal)")
    parser.add_argument(
        "--suite", choices=["all", "functional", "performance", "fault"],
        default="all", help="Suite de pruebas a ejecutar"
    )
    parser.add_argument(
        "--report", choices=["html", "json", "both"],
        default="both", help="Formato del reporte de salida"
    )
    parser.add_argument("--output-dir", default="reports", help="Directorio de reportes")
    parser.add_argument("--timeout", type=int, default=10,
                        help="Timeout por prueba en segundos (default: 10)")
    return parser.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    config = TestConfig(
        host_pc1=args.host_pc1,
        host_pc2=args.host_pc2,
        host_pc3=args.host_pc3,
        timeout=args.timeout,
        output_dir=args.output_dir,
    )

    reporter = TestReporter(config)
    all_results = []

    print("\n" + "═" * 65)
    print("  BATERÍA DE PRUEBAS — Gestión Inteligente de Tráfico Urbano")
    print(f"  PC1={args.host_pc1}  PC2={args.host_pc2}  PC3={args.host_pc3}")
    print(f"  Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 65 + "\n")

    suites_to_run = []
    if args.suite in ("all", "functional"):
        suites_to_run.append(("FUNCIONAL",    FunctionalTestSuite(config)))
    if args.suite in ("all", "performance"):
        suites_to_run.append(("RENDIMIENTO",  PerformanceTestSuite(config)))
    if args.suite in ("all", "fault"):
        suites_to_run.append(("TOLERANCIA A FALLAS", FaultToleranceTestSuite(config)))

    for suite_name, suite in suites_to_run:
        print(f"\n{'─'*65}")
        print(f"  ▶  Suite: {suite_name}")
        print(f"{'─'*65}")
        results = suite.run()
        all_results.extend(results)
        _print_suite_summary(suite_name, results)

    # Reporte final
    print("\n" + "═" * 65)
    print("  RESUMEN GLOBAL")
    print("═" * 65)
    total   = len(all_results)
    passed  = sum(1 for r in all_results if r["status"] == "PASS")
    failed  = sum(1 for r in all_results if r["status"] == "FAIL")
    skipped = sum(1 for r in all_results if r["status"] == "SKIP")
    print(f"  Total: {total}  |  ✔ Pasaron: {passed}  |  ✘ Fallaron: {failed}  |  ⊘ Omitidas: {skipped}")

    if args.report in ("json", "both"):
        reporter.save_json(all_results)
    if args.report in ("html", "both"):
        reporter.save_html(all_results)

    print(f"\n  Reportes guardados en: {os.path.abspath(args.output_dir)}/")
    print("═" * 65 + "\n")
    sys.exit(0 if failed == 0 else 1)


def _print_suite_summary(name, results):
    for r in results:
        icon  = "✔" if r["status"] == "PASS" else ("⊘" if r["status"] == "SKIP" else "✘")
        badge = f"[{r['status']}]"
        dur   = f"{r.get('duration_ms', 0):.0f}ms"
        print(f"  {icon} {badge:6}  {r['name']:<45}  {dur:>7}")
        if r["status"] == "FAIL" and r.get("error"):
            print(f"         ↳ {r['error']}")


if __name__ == "__main__":
    main()
