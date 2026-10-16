(() => {
  'use strict';
  const menu = document.getElementById('mobileMenu');
  const nav = document.getElementById('sideNav');
  const shade = document.getElementById('mobileShade');
  function close() { if (nav) nav.classList.remove('open'); if (shade) shade.hidden = true; }
  if (menu && nav && shade) {
    menu.addEventListener('click', () => { nav.classList.toggle('open'); shade.hidden = !nav.classList.contains('open'); });
    shade.addEventListener('click', close);
    window.addEventListener('keydown', ev => { if (ev.key === 'Escape') close(); });
  }
  // Presentation-only ticking clock. Persisted UTC events remain authoritative.
  const clocks = document.querySelectorAll('.shop-clock[data-running="true"]');
  if (clocks.length) {
    const start = Date.now();
    const hms = total => {
      const hours = Math.floor(total / 3600).toString().padStart(2,'0');
      const mins = Math.floor(total % 3600 / 60).toString().padStart(2,'0');
      const secs = Math.floor(total % 60).toString().padStart(2,'0');
      return `${hours}:${mins}:${secs}`;
    };
    const render = () => {
      const added = Math.max(0, Math.floor((Date.now() - start) / 1000));
      clocks.forEach(el => { el.textContent = hms(Number(el.dataset.seconds || 0) + added); });
    };
    render(); window.setInterval(render, 1000);
  }
  const answer = document.getElementById('answer');
  const evidence = document.getElementById('evidence');
  if (answer && evidence && answer.tagName === 'SELECT') {
    const update = () => {
      const required = (answer.value === 'Yes' && evidence.dataset.requiredYes === 'true') ||
                       (answer.value === 'No' && evidence.dataset.requiredNo === 'true');
      evidence.required = required;
    };
    answer.addEventListener('change', update); update();
  }
})();
