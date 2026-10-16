'use strict';

// Motion is cosmetic: native links, forms, history and focus remain in control.
// No request, storage, navigation interception or persistent hidden state.
(() => {
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const active = new Set();
  const channels = new WeakMap();
  const entranceSelector = '.panel,.opportunity,.metric,.setup-card,.job-row,.table-wrap,.empty,[data-motion-enter]';
  const easing = 'cubic-bezier(.2,.75,.25,1)';
  let pageTransition = false;

  const animate = (element, keyframes, options, channel = 'feedback') => {
    if (preference.matches || document.hidden || !element?.animate || !element.getClientRects().length) return;
    const owned = channels.get(element) || new Map();
    owned.get(channel)?.cancel();
    try {
      const animation = element.animate(keyframes, {easing, ...options});
      owned.set(channel, animation);
      channels.set(element, owned);
      active.add(animation);
      const release = () => {
        active.delete(animation);
        if (owned.get(channel) === animation) owned.delete(channel);
      };
      animation.finished.then(release, release);
    } catch (_) {
      // Unsupported animation properties never affect the underlying action.
    }
  };

  const enter = (element, delay = 0) => animate(element, [
    {opacity: .55, translate: '0 9px'},
    {opacity: 1, translate: '0 0'},
  ], {duration: 360, delay, fill: 'backwards'}, 'entrance');

  const cancelAll = () => {
    for (const animation of active) animation.cancel();
    active.clear();
  };

  // Only the first visible layer enters; nested cards do not move twice.
  const enterPage = () => {
    if (pageTransition || preference.matches) return;
    Array.from(document.querySelectorAll(entranceSelector))
      .filter(element => !element.parentElement?.closest(entranceSelector) && element.getClientRects().length)
      .slice(0, 12)
      .forEach((element, index) => enter(element, Math.min(index * 35, 140)));
  };

  document.documentElement.setAttribute('data-motion-ready', '');
  window.addEventListener('pagereveal', event => {
    // The browser supplies the page animation when both pages opted in.
    if (event.viewTransition) {
      pageTransition = true;
      cancelAll();
    }
  });
  window.requestAnimationFrame(enterPage);

  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const element = event.target instanceof Element ? event.target.closest('button,a[href],summary,[data-motion-interactive]') : null;
    if (!element || element.matches(':disabled,[aria-disabled="true"]')) return;
    if (element instanceof HTMLAnchorElement) {
      if (element.hasAttribute('download') || (element.target && element.target !== '_self')) return;
      const destination = new URL(element.href, location.href);
      if (destination.origin !== location.origin || !['http:', 'https:'].includes(destination.protocol)) return;
    }
    // Keyboard-generated clicks follow the same finite feedback as a pointer.
    animate(element, [{scale: '.975'}, {scale: '1'}], {duration: 210});
  }, {passive: true});

  document.addEventListener('change', event => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== 'checkbox') return;
    if (input.matches('[data-service-choice]')) {
      animate(input.nextElementSibling, [{scale: '.96'}, {scale: '1'}], {duration: 240});
    }
  }, {passive: true});

  // Native details keeps its accessibility and works with JavaScript disabled.
  document.addEventListener('toggle', event => {
    if (!(event.target instanceof HTMLDetailsElement) || !event.target.open) return;
    const content = event.target.querySelector('.mini-guide-content,[data-motion-details]');
    if (content) enter(content);
  }, {capture: true, passive: true});

  // Cancel only animations created here. BFCache must restore a usable page,
  // with no stale pressed state or replay of all the initial entrances.
  window.addEventListener('pagehide', cancelAll);
  window.addEventListener('pageshow', event => {
    if (event.persisted) cancelAll();
  });
  preference.addEventListener('change', event => {
    if (event.matches) cancelAll();
  });
})();
