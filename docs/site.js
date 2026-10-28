'use strict';
// This is an explicit scripted illustration. It never calls a model or a backend.
let count = 0;
let increment = 2;
const value = document.getElementById('count');
const verdict = document.getElementById('verdict');
document.getElementById('increase').addEventListener('click', () => { count += increment; value.textContent = String(count); });
document.getElementById('reset').addEventListener('click', () => { count = 0; value.textContent = '0'; });
document.getElementById('test').addEventListener('click', () => {
  // Reset first so each check evaluates the same one-click assertion independently.
  count = increment; value.textContent = String(count);
  const passed = count === 1;
  verdict.dataset.result = passed ? 'pass' : 'fail';
  verdict.textContent = passed ? 'PASS · one click produces 1, as required.' : 'FAIL · expected 1 after one click; observed 2.';
});
document.getElementById('correct').addEventListener('click', () => {
  increment = increment === 2 ? 1 : 2; count = 0; value.textContent = '0';
  document.getElementById('step').textContent = String(increment);
  document.getElementById('mode').textContent = increment === 1 ? 'Corrected +1 example' : 'Seeded +2 bug';
  document.getElementById('correct').textContent = increment === 1 ? 'Restore seeded bug' : 'Load corrected example';
  delete verdict.dataset.result;
  verdict.textContent = 'Example loaded. Run the same check again.';
});
document.getElementById('copy').addEventListener('click', async () => {
  const status = document.getElementById('copy-status');
  try {
    if (!navigator.clipboard) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(document.getElementById('install-command').textContent);
    status.textContent = 'Commands copied.';
  } catch (_) { status.textContent = 'Copy is unavailable here. Select the commands above and copy them manually.'; }
});
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
if ('IntersectionObserver' in window && !reduceMotion.matches) {
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) { entry.target.removeAttribute('data-pending'); observer.unobserve(entry.target); }
  }, { rootMargin: '0px 0px 40px 0px', threshold: 0.03 });
  for (const section of document.querySelectorAll('.reveal')) {
    if (section.getBoundingClientRect().top > innerHeight) section.setAttribute('data-pending', '');
    observer.observe(section);
  }
  reduceMotion.addEventListener('change', event => { if (event.matches) { observer.disconnect(); document.querySelectorAll('[data-pending]').forEach(node => node.removeAttribute('data-pending')); } });
}
