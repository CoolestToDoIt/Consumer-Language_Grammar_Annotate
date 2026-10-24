"""Portable experiment summary and SVG learning curves; no plotting dependency."""
from pathlib import Path
from statistics import mean

MODELS = ('memory', 'analogy', 'rules')
COLORS = {'memory': '#64748b', 'analogy': '#d97706', 'rules': '#0f766e'}


def write_report(report, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    runs = report['runs']
    lines = ['# Decipher Lab measured results', '', report['protocol'], '',
             'All models receive the same root anchors, support labels, stream and feedback schedule. Probe answers are never released. Accuracy is exact structured meaning accuracy.', '',
             '| Preset | Model | Roots only | After 1 support label | After 9 support labels | Final probe | Stream first guesses | Pending labels |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1050" height="390" viewBox="0 0 1050 390">',
           '<rect width="1050" height="390" fill="#f8fafc"/>',
           '<g font-family="sans-serif" fill="#0f172a">',
           '<text x="30" y="30" font-size="21">Untaught probe accuracy during the first nine teacher lessons</text>']
    for j, preset in enumerate('ABC'):
        left, top, width, height = 50 + j*345, 85, 275, 220
        svg.append(f'<text x="{left}" y="65" font-size="17">Preset {preset}</text>')
        for value in (0, .5, 1):
            y = top + height*(1-value)
            svg.append(f'<path d="M {left} {y} h {width}" stroke="#cbd5e1"/><text x="{left-32}" y="{y+5}" font-size="11">{value:.0%}</text>')
        for model in MODELS:
            selected = [r for r in runs if r['preset'] == preset and r['model'] == model]
            root = mean(r['root_only_accuracy'] for r in selected)
            first = mean(r['support_curve'][1]['accuracy'] for r in selected)
            support = mean(r['support_curve'][-1]['accuracy'] for r in selected)
            final = mean(r['curve'][-1]['accuracy'] for r in selected)
            stream = mean(r['stream_accuracy'] for r in selected)
            pending = mean(r['pending'] for r in selected)
            lines.append(f'| {preset} | {model} | {root:.1%} | {first:.1%} | {support:.1%} | {final:.1%} | {stream:.1%} | {pending:g} |')
            points = ' '.join(f'{left+i*width/9:.1f},{top+height*(1-mean(r["support_curve"][i]["accuracy"] for r in selected)):.1f}' for i in range(10))
            svg.append(f'<polyline points="{points}" fill="none" stroke="{COLORS[model]}" stroke-width="3"/>')
        for i in (0, 3, 6, 9):
            svg.append(f'<text x="{left+i*width/9}" y="325" font-size="12">{i}</text>')
        svg.append(f'<text x="{left+40}" y="348" font-size="12">Teacher sentence labels</text>')
    for i, model in enumerate(MODELS):
        svg.append(f'<text x="{300+i*160}" y="378" fill="{COLORS[model]}" font-size="14">● {model}</text>')
    svg.append('</g></svg>')
    lines += ['', '![Learning curves](learning-curves.svg)', '',
              '| Preset | Model | Normalized learning AUC | Mean prediction call (ms) | Mean feedback call (ms) |',
              '|---|---|---:|---:|---:|']
    for preset in 'ABC':
        for model in MODELS:
            selected = [r for r in runs if r['preset'] == preset and r['model'] == model]
            lines.append(f"| {preset} | {model} | {mean(r['auc'] for r in selected):.3f} | {mean(r['prediction_ms'] for r in selected):.3f} | {mean(r['feedback_call_ms'] for r in selected):.3f} |")
    lines += ['', 'AUC integrates the combined support and stream probe curve against arrived teacher-answer count, normalized by the observed answer-budget range. Prediction-call timing includes feedback due at that input step; feedback-call timing includes queuing or immediate updates. These short CPU timings are diagnostics, not a benchmark.', '',
              'Results average three deterministic randomized lexicons per preset. Support lessons use immediate feedback; the configured delay applies to the stream. Pending answers are not drained. The support budget is separate from the stream-label budget.', '',
              'This regular synthetic task becomes easy quickly. Exact memory is weak on disjoint probes; nearest-example copying is a stronger spelling baseline but cannot construct a new structured meaning. Nine generated languages are a demonstration, not evidence of arbitrary language decipherment. The chart uses support labels to expose the early learning transition; stream curves remain in the JSON report.']
    (directory/'learning-curves.svg').write_text('\n'.join(svg))
    (directory/'summary.md').write_text('\n'.join(lines) + '\n')
