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

  /* Reveal on scroll
     - Never hides anything already on screen at load, so first paint is never
       blank (the hero and the top of book pages use CSS load-in instead).
     - Stagger is by position among siblings, so a row of cards goes left to
       right, not in page-wide index order.
     - Once revealed, the reveal classes are removed so each element gets its
       own hover transitions back. */
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  // Image-led blocks only. Text people are reading (headings, lists, quotes,
  // contact details) stays put — it used to be 21 moving elements per page.
  var targets = document.querySelectorAll('.cards > .card, .release-media, .release-body');

  if (!reduce && 'IntersectionObserver' in window) {
    var finish = function (el) {
      el.classList.remove('reveal', 'in');
      el.style.removeProperty('--rd');
    };
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        io.unobserve(el);
        el.classList.add('in');
        el.addEventListener('transitionend', function done(e) {
          if (e.target !== el || e.propertyName !== 'transform') return;
          el.removeEventListener('transitionend', done);
          finish(el);
        });
        // Safety net if transitionend never fires (tab hidden, etc.).
        setTimeout(function () { finish(el); }, 1200);
      });
    }, { rootMargin: '0px 0px -6% 0px', threshold: 0.1 });

    var fold = window.innerHeight;
    targets.forEach(function (el) {
      if (el.getBoundingClientRect().top < fold) return;   // on screen already
      var sibs = [].filter.call(el.parentNode.children, function (c) {
        return c.matches && c.matches(el.tagName.toLowerCase() + (el.className ? '.' + el.className.trim().split(/\s+/)[0] : ''));
      });
      var i = Math.min(sibs.indexOf(el), 4);
      el.classList.add('reveal');
      el.style.setProperty('--rd', (i > 0 ? i * 70 : 0) + 'ms');
      io.observe(el);
    });
  }

  /* Lazy images fade in when they arrive instead of popping. */
  document.documentElement.classList.add('js');
  [].forEach.call(document.querySelectorAll('img[loading="lazy"]'), function (img) {
    var mark = function () { img.classList.add('is-loaded'); };
    if (img.complete && img.naturalWidth) mark();
    else {
      img.addEventListener('load', mark, { once: true });
      img.addEventListener('error', mark, { once: true });   // never stay invisible
    }
  });

  /* Footer year */
  document.getElementById('year').textContent = new Date().getFullYear();
})();
