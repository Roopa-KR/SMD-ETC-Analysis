// Shared site shell: responsive navigation, snapshot selection and keyboard search.
(() => {
  'use strict';
  const sidebar = document.getElementById('app-sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  const toggle = document.getElementById('sidebar-toggle');
  const close = document.getElementById('sidebar-close');
  function setOpen(open) {
    if (!sidebar || !backdrop) return;
    sidebar.classList.toggle('is-open', open);
    backdrop.hidden = !open;
    if (toggle) toggle.setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('sidebar-is-open', open);
  }
  toggle?.addEventListener('click', () => setOpen(true));
  close?.addEventListener('click', () => setOpen(false));
  backdrop?.addEventListener('click', () => setOpen(false));
  sidebar?.querySelectorAll('a').forEach(a => a.addEventListener('click', () => setOpen(false)));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') setOpen(false);
    if (event.key === '/' && !event.ctrlKey && !event.metaKey &&
        !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) {
      const search = document.querySelector('.global-search input[type="search"]');
      if (search) { event.preventDefault(); search.focus(); }
    }
  });
  document.querySelectorAll('[data-snapshot-navigation]').forEach(sel => sel.addEventListener('change', () => {
    const url = new URL(window.location.href);
    url.searchParams.set('snapshot', sel.value);
    window.location.assign(url.toString());
  }));
})();
// Consistent in-page directory filtering without changing underlying results.
(() => {
  'use strict';
  const input=document.querySelector('[data-directory-search]');
  if (!input) return;
  const rows=[...document.querySelectorAll('[data-directory-row]')];
  const empty=document.querySelector('[data-directory-empty]');
  function filter() {
    const text=input.value.trim().toLocaleLowerCase();
    let visible=0;
    rows.forEach(row=>{
      const match=row.textContent.toLocaleLowerCase().includes(text);
      row.hidden=!match;
      if(match) visible++;
    });
    if(empty) empty.hidden=visible>0 || !text;
  }
  input.addEventListener('input',filter);
})();
