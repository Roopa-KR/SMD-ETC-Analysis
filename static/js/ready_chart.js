// v10 shared chart: truck ready time before vs after adding operators.
// Presentation only. Every time, band (green/yellow/red) and ETC comes from
// calculations/ready_comparison.py, so the chart cannot disagree with the table or statuses.
(() => {
  'use strict';
  const MIN = 60000;
  const ms = iso => (iso ? Date.parse(iso) : null);
  const local = value => {  // ISO without zone, so the time shown is the warehouse clock time
    const d = new Date(value);
    const p = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  };

  function draw(container) {
    const id = container.dataset.chartId;
    const panel = document.getElementById(id);
    const source = document.getElementById(`${id}-data`);
    if (!panel || !source) return;
    const data = JSON.parse(source.textContent);
    const rows = data.scenarios;
    const plotted = rows.filter(r => r.ready_iso);
    if (!plotted.length) {  // the explanation is printed under the table; no empty plot
      if (data.message) { panel.hidden = true; return; }
      panel.classList.add('ready-chart-empty');
      panel.textContent = 'No measurable ready time at this snapshot.';
      return;
    }
    if (!window.Plotly) {
      panel.classList.add('ready-chart-empty');
      panel.textContent = 'Chart unavailable. The table below shows every calculated time.';
      return;
    }
    const colors = data.colors;
    const narrow = panel.clientWidth < 640;   // phones: row names above the bars, shorter labels
    const now = ms(data.now_iso), cutoff = ms(data.cutoff_iso), buffer = ms(data.buffer_deadline_iso);
    const readyTimes = plotted.map(r => ms(r.ready_iso));
    const lo = Math.min(now, buffer) - 10 * MIN;
    const hiData = Math.max(cutoff, ...readyTimes);
    const span = hiData - lo;
    const hi = hiData + Math.max(narrow ? 30 * MIN : 40 * MIN, span * (narrow ? 0.42 : 0.34));  // room for marker labels

    const keys = rows.map(r => r.key);
    const tickText = rows.map(r => `<b>${r.title.replace(' (confirmed)', '')}</b><br>${r.tick_note}`);

    const etc = {
      type: 'bar', orientation: 'h', name: 'ETC',
      y: plotted.map(r => r.key), base: plotted.map(() => local(now)),
      x: plotted.map(r => ms(r.ready_iso) - now),
      width: 0.34, marker: { color: colors.etc, opacity: 0.88 },
      text: plotted.map(r => (r.etc_minutes >= 28 ? `ETC ${r.etc_text}` : '')),
      textposition: 'inside', insidetextanchor: 'middle', constraintext: 'none',
      textfont: { color: '#ffffff', size: 12, family: 'Inter, system-ui, sans-serif' },
      hovertemplate: plotted.map(r => `<b>${r.title}</b><br>ETC ${r.etc_text} (from ${data.now_text} to ${r.ready_text})<extra></extra>`),
    };
    const ready = {
      type: 'scatter', mode: 'markers', name: 'Projected ready',
      y: plotted.map(r => r.key), x: plotted.map(r => local(ms(r.ready_iso))),
      marker: { size: narrow ? 15 : 17, color: plotted.map(r => colors[r.band]), line: { width: 2, color: '#1f2937' } },
      cliponaxis: false,
      hovertemplate: plotted.map(r => `<b>${r.title}</b><br>Projected ready ${r.ready_text} · ${r.band_label}`
        + `<br>${r.relation}<br>ETC ${r.etc_text}${r.bottleneck ? `<br>Slowest area: ${r.bottleneck}` : ''}<extra></extra>`),
    };
    const zone = (x0, x1, color) => ({ type: 'rect', xref: 'x', yref: 'paper', x0: local(x0), x1: local(x1), y0: 0, y1: 1,
      fillcolor: color, line: { width: 0 }, layer: 'below' });
    const vline = (x, dash, width, color) => ({ type: 'line', xref: 'x', yref: 'paper', x0: local(x), x1: local(x),
      y0: 0, y1: 1, line: { color, width, dash } });
    const shapes = [
      zone(lo, buffer, 'rgba(12,163,12,0.07)'),
      zone(buffer, cutoff, 'rgba(250,178,25,0.22)'),
      zone(cutoff, hi, 'rgba(208,59,59,0.08)'),
      vline(now, 'dot', 1.5, '#667085'),
      vline(buffer, 'dash', 2, '#344054'),
      vline(cutoff, 'solid', 2.5, '#101828'),
    ];
    const label = (x, text, anchor, y = 1.0) => ({ x: local(x), y, xref: 'x', yref: 'paper', text, showarrow: false,
      xanchor: anchor, yanchor: 'bottom', font: { size: 12, color: '#101828', family: 'Inter, system-ui, sans-serif' } });
    const annotations = [
      label(buffer, narrow ? `Buffer <b>${data.buffer_deadline_text}</b> ▸` : `Buffer deadline <b>${data.buffer_deadline_text}</b> ▸`, 'right'),
      label(cutoff, narrow ? `◂ Cutoff <b>${data.cutoff_text}</b>` : `◂ Pick cutoff <b>${data.cutoff_text}</b>`, 'left'),
    ];
    if (!narrow) annotations.push({ ...label(now, `Now ${data.now_text}`, 'left'), y: 0, yanchor: 'top', yshift: -22,
      font: { size: 11, color: '#475467' } });
    // Exact ready time + status word + distance to the relevant deadline, beside each marker
    // (status is never carried by colour alone). White backing keeps it readable over zone lines.
    plotted.forEach(r => annotations.push({
      x: local(ms(r.ready_iso)), y: r.key, xref: 'x', yref: 'y', xanchor: 'left', yanchor: 'middle',
      xshift: narrow ? 11 : 13, showarrow: false, align: 'left',
      text: narrow ? `<b>${r.ready_text}</b><br>${r.band_label}`
        : `<b>${r.ready_text}</b> · ${r.band_label}${r.etc_minutes < 28 ? ` (ETC ${r.etc_text})` : ''}<br>${r.relation_short}`,
      bgcolor: 'rgba(255,255,255,0.88)', borderpad: 2,
      font: { size: narrow ? 11 : 12, color: '#1f2937', family: 'Inter, system-ui, sans-serif' } }));
    if (narrow) rows.forEach(r => annotations.push({  // row name above its bar instead of a wide axis
      x: local(lo), y: r.key, xref: 'x', yref: 'y', xanchor: 'left', yanchor: 'bottom', yshift: 13,
      showarrow: false, align: 'left', font: { size: 11, color: '#1f2937' },
      text: r.key === 'before' ? '<b>Before</b> · current operators'
        : `<b>After</b> · ${r.reallocated ? `+${r.reallocated} reallocated ` : ''}${r.temporary ? `+${r.temporary} temporary ` : ''}· ${r.confirmed ? 'confirmed' : 'not allocated'}` }));
    rows.filter(r => !r.ready_iso && !r.all_picked).forEach(r => annotations.push({
      x: local(now), y: r.key, xref: 'x', yref: 'y', xanchor: 'left', showarrow: false,
      text: '<b>Ready time unknown</b> · no pick rate', font: { size: 12, color: '#475467' } }));

    Plotly.newPlot(panel, [etc, ready], {
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, system-ui, sans-serif', size: 11, color: '#475467' },
      height: (narrow ? 80 : 96) + rows.length * (narrow ? 92 : 84),
      margin: { t: 34, r: narrow ? 6 : 16, b: narrow ? 34 : 52, l: narrow ? 6 : 12 },
      showlegend: false, bargap: 0.5,
      xaxis: { type: 'date', range: [local(lo), local(hi)], tickformat: '%H:%M', showgrid: true,
        nticks: narrow ? 4 : 10, tickangle: 0,
        gridcolor: 'rgba(16,24,40,0.06)', zeroline: false, fixedrange: true, automargin: true },
      yaxis: { type: 'category', categoryorder: 'array', categoryarray: keys.slice().reverse(),
        tickvals: keys, ticktext: tickText, automargin: true, fixedrange: true, ticks: '',
        showticklabels: !narrow,
        tickfont: { size: 12, color: '#1f2937' } },
      shapes, annotations,
      hoverlabel: { bgcolor: '#1f2937', font: { color: '#fff', size: 12 } },
    }, { displayModeBar: false, responsive: true, scrollZoom: false }).catch(() => {
      panel.classList.add('ready-chart-empty');
      panel.textContent = 'Unable to draw the chart. The table below shows every calculated time.';
    });
  }

  document.querySelectorAll('[data-ready-chart]').forEach(draw);
})();
