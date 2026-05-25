"""Render evaluation reports as HTML via Jinja2."""

from __future__ import annotations

from pathlib import Path

from shared.models import EvalRunReport

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Eval — {{ report.system_label }}</title>
  <style>
    :root { --pass: #0a7; --fail: #c33; --muted: #666; }
    body { font-family: system-ui, sans-serif; margin: 2rem; color: #111; max-width: 1200px; }
    h1 { margin-bottom: 0.25rem; }
    .meta { color: var(--muted); margin-bottom: 1rem; }
    .summary { display: flex; gap: 1.5rem; flex-wrap: wrap; margin: 1rem 0 1.5rem; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.25rem; min-width: 140px; }
    .card strong { font-size: 1.75rem; display: block; }
    .card.pass strong { color: var(--pass); }
    .card.fail strong { color: var(--fail); }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 0.92rem; }
    th, td { border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: left; vertical-align: top; }
    th { background: #f5f5f5; position: sticky; top: 0; }
    .pass { color: var(--pass); font-weight: 600; }
    .fail { color: var(--fail); font-weight: 600; }
    .alert { background: #fff3cd; border: 1px solid #ffc107; padding: 0.75rem; border-radius: 4px; margin: 0.5rem 0; }
    pre { white-space: pre-wrap; font-size: 0.85rem; background: #fafafa; padding: 0.5rem; margin: 0; }
    .gt { color: var(--muted); font-size: 0.85rem; margin-top: 0.35rem; }
    details { margin-top: 0.35rem; }
  </style>
</head>
<body>
  <h1>RAG Evaluation — {{ report.system_label }}</h1>
  <p class="meta">
    {{ report.run_at.strftime('%Y-%m-%d %H:%M UTC') }} ·
    {{ report.num_samples }} samples ·
    commit {{ report.git_commit or 'n/a' }}
  </p>

  <div class="summary">
    <div class="card {{ 'pass' if pass_rate >= 0.75 else 'fail' }}">
      <strong>{{ '%.0f'|format(pass_rate * 100) }}%</strong>
      Pass rate ({{ passed }}/{{ report.num_samples }})
    </div>
    {% for name, value in key_metrics %}
    <div class="card">
      <strong>{{ '%.2f'|format(value) }}</strong>
      {{ name }}
    </div>
    {% endfor %}
  </div>

  <h2>Aggregate metrics</h2>
  <table>
    <tr><th>Metric</th><th>Mean</th></tr>
    {% for name, value in report.aggregate_metrics.items()|sort %}
    <tr><td>{{ name }}</td><td>{{ '%.3f'|format(value) }}</td></tr>
    {% endfor %}
  </table>

  {% if report.regression_alerts %}
  <h2>Regression alerts</h2>
  {% for alert in report.regression_alerts %}
  <div class="alert">{{ alert }}</div>
  {% endfor %}
  {% endif %}

  <h2>Sample results</h2>
  <table>
    <tr>
      <th>ID</th><th>Pass</th><th>Question</th><th>Retrieval</th><th>Metrics</th><th>Answer</th>
    </tr>
    {% for r in report.sample_results %}
    <tr>
      <td>{{ r.sample_id }}</td>
      <td class="{{ 'pass' if r.passed else 'fail' }}">{{ 'PASS' if r.passed else 'FAIL' }}</td>
      <td>{{ r.query }}</td>
      <td>{{ retrieval_summary(r) }}</td>
      <td>{% for m in r.metrics if m.name != 'latency_ms' %}{{ m.name }}={{ '%.2f'|format(m.value) }}<br>{% endfor %}</td>
      <td>
        {% if r.generated_answer %}
        <pre>{{ r.generated_answer[:500] }}{% if r.generated_answer|length > 500 %}…{% endif %}</pre>
        {% else %}
        <em>(retrieve-only)</em>
        {% endif %}
        <div class="gt"><strong>GT:</strong> {{ r.ground_truth_answer[:200] }}{% if r.ground_truth_answer|length > 200 %}…{% endif %}</div>
      </td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
"""


def _retrieval_summary(result) -> str:
    for m in result.metrics:
        if m.name == "retrieval_page_recall" and not m.details.get("skipped"):
            pages = m.details.get("retrieved_pages", [])
            expected = m.details.get("expected_pages", [])
            return f"pages {pages} (want ~{expected})"
        if m.name == "retrieval_chunk_type_recall" and not m.details.get("skipped"):
            got = m.details.get("retrieved_types", [])
            want = m.details.get("expected", "?")
            hit = "✓" if m.value >= 1.0 else "✗"
            return f"{hit} types {got} (want {want})"
    return "—"


def render_html_report(report: EvalRunReport) -> str:
    try:
        from jinja2 import Template
    except ImportError:
        raise ImportError("Install jinja2: pip install jinja2") from None

    passed = sum(1 for r in report.sample_results if r.passed)
    pass_rate = passed / report.num_samples if report.num_samples else 0.0
    priority = (
        "retrieval_page_recall",
        "retrieval_chunk_type_recall",
        "context_keyword_recall",
        "faithfulness",
        "ragas_faithfulness",
        "answer_keyword_overlap",
    )
    key_metrics = [
        (name, report.aggregate_metrics[name])
        for name in priority
        if name in report.aggregate_metrics
    ][:4]

    template = Template(TEMPLATE)
    template.globals["retrieval_summary"] = _retrieval_summary
    return template.render(
        report=report,
        passed=passed,
        pass_rate=pass_rate,
        key_metrics=key_metrics,
    )


def save_html_report(report: EvalRunReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html_report(report), encoding="utf-8")
    return path
