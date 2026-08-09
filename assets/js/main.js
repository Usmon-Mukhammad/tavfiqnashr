/* TAVFIQNASHR — welcome site interactions */
(function () {
  'use strict';

  var header = document.querySelector('.site-header');
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('nav');
  var backdrop = document.querySelector('.nav-backdrop');
  var toTop = document.querySelector('.to-top');
  var MOBILE = '(max-width: 760px)';

  /* Chevron affordance on the mobile menu rows (hidden by CSS on desktop) */
  [].forEach.call(nav.querySelectorAll('a:not(.btn)'), function (a) {
    var chev = document.createElement('span');
    chev.className = 'nav-chev';
    chev.setAttribute('aria-hidden', 'true');
    chev.textContent = '›';
    a.appendChild(chev);
  });

  function setMenu(open) {
    nav.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('nav-locked', open);

    if (open) {
      backdrop.hidden = false;
      /* next frame, so the opacity transition actually runs */
      requestAnimationFrame(function () { backdrop.classList.add('show'); });
    } else {
      backdrop.classList.remove('show');
      setTimeout(function () {
        if (!nav.classList.contains('open')) backdrop.hidden = true;
      }, 300);
    }
  }

  toggle.addEventListener('click', function () {
    setMenu(!nav.classList.contains('open'));
  });

  backdrop.addEventListener('click', function () { setMenu(false); });

  nav.addEventListener('click', function (e) {
    if (e.target.closest('a') && nav.classList.contains('open')) setMenu(false);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && nav.classList.contains('open')) {
      setMenu(false);
      toggle.focus();
    }
  });

  /* Leaving mobile width with the menu open would strand the scroll lock */
  var mq = window.matchMedia(MOBILE);
  var onChange = function (e) { if (!e.matches && nav.classList.contains('open')) setMenu(false); };
  if (mq.addEventListener) mq.addEventListener('change', onChange);
  else if (mq.addListener) mq.addListener(onChange);

  /* Sticky header shadow + back-to-top visibility */
  function onScroll() {
    var y = window.scrollY;
    header.classList.toggle('is-stuck', y > 8);
    toTop.classList.toggle('show', y > 600);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* Reveal on scroll */
  var targets = document.querySelectorAll(
    '.section-head, .about-text, .about-figure, .release-media, .release-body, ' +
    '.card, .series li, .quotes blockquote, .contact-lead, .ccard, .stats'
  );

  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });

    targets.forEach(function (el, i) {
      el.classList.add('reveal');
      el.style.transitionDelay = (i % 4) * 70 + 'ms';
      io.observe(el);
    });
  }

  /* Footer year */
  document.getElementById('year').textContent = new Date().getFullYear();
})();
