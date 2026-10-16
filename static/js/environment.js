// v13 environment trends. Presentation only: every value comes from calculations/environment.py.
// Two single-axis charts (temperature, humidity) instead of one dual-axis chart. Colour follows the
// zone (fixed zone order, assigned server-side), suspect readings are ringed, and the table under
// the charts holds every value for readers who cannot use the plot.
(() => {
  'use strict';
  const source = document.getElementById('env-trend-data');
  if (!source) return;
  const series = JSON.parse(source.textContent);
  if (!series.length) return;

  function draw(elementId, field, unit, decimals) {
    const el = document.getElementById(elementId);
    if (!el) return;
    if (!window.Plotly) {
      el.classList.add('ready-chart-empty');
      el.textContent = 'Chart unavailable. The table below lists every reading.';
      return;
    }
    const traces = series.map(s => ({
      type: 'scatter', mode: 'lines+markers', name: s.zone + (s.synthetic ? ' (SYNTHETIC)' : ''),
      x: s.times, y: s[field],
      line: {color: s.color, width: 2, dash: s.synthetic ? 'dot' : 'solid'},
      marker: {color: s.color, size: s.suspect.map(flag => (flag ? 11 : 0.1)),
               symbol: s.suspect.map(flag => (flag ? 'circle-open' : 'circle')), line: {width: 2, color: s.color}},
      customdata: s.suspect.map(flag => (flag ? ' · suspect' : '')),
      hovertemplate: `%{y:.${decimals}f} ${unit}%{customdata}<extra>${s.zone}</extra>`,
    }));
    const narrow = el.clientWidth < 520;
    const layout = {
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      font: {family: 'Inter, system-ui, sans-serif', size: 10, color: '#5f6e84'},
      margin: {t: 8, r: 12, b: narrow ? 90 : 70, l: 44}, height: narrow ? 300 : 280,
      hovermode: 'x unified', hoverlabel: {bgcolor: '#1e2c45', font: {color: '#ffffff', size: 11}},
      legend: {orientation: 'h', y: -0.28, font: {size: 10}},
      xaxis: {type: 'date', tickformat: '%H:%M', showgrid: false, tickfont: {size: 9}},
      yaxis: {title: {text: unit, font: {size: 10}}, gridcolor: '#eff2f6', zeroline: false, tickfont: {size: 9}},
    };
    window.Plotly.newPlot(el, traces, layout, {displayModeBar: false, responsive: true}).catch(() => {
      el.textContent = 'Chart unavailable. The table below lists every reading.';
    });
  }

  draw('env-temp-chart', 'temperature', '°C', 1);
  draw('env-rh-chart', 'humidity', '%RH', 0);
})();
