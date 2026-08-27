/* MessCheck front-end behaviour: nav drawer, theme, tabs, collapsible
   categories, flash dismissal, and the delete confirm gate. */
(function () {
    'use strict';

    /* ---------------------------------------------------------- nav ---- */
    var toggle = document.querySelector('.nav-toggle');
    var nav = document.getElementById('site-nav');
    var backdrop = document.querySelector('.nav-backdrop');

    function setNav(open) {
        if (!nav || !toggle) return;
        nav.classList.toggle('open', open);
        toggle.setAttribute('aria-expanded', String(open));
        toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
        if (backdrop) backdrop.hidden = !open;
        document.body.style.overflow = open ? 'hidden' : '';
    }

    if (toggle) {
        toggle.addEventListener('click', function () {
            setNav(toggle.getAttribute('aria-expanded') !== 'true');
        });
    }
    if (backdrop) backdrop.addEventListener('click', function () { setNav(false); });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') setNav(false);
    });
    // A resize past the breakpoint leaves the drawer state stale otherwise.
    window.addEventListener('resize', function () {
        if (window.innerWidth > 780) setNav(false);
    });

    /* -------------------------------------------------------- theme ---- */
    var themeButton = document.querySelector('.theme-toggle');
    if (themeButton) {
        themeButton.addEventListener('click', function () {
            var root = document.documentElement;
            var current = root.dataset.theme;
            if (!current) {
                var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                current = prefersDark ? 'dark' : 'light';
            }
            var next = current === 'dark' ? 'light' : 'dark';
            root.dataset.theme = next;
            try { localStorage.setItem('messcheck-theme', next); } catch (e) {}
        });
    }

    /* --------------------------------------------------------- tabs ---- */
    document.querySelectorAll('[data-tabs]').forEach(function (group) {
        var tabs = Array.prototype.slice.call(group.querySelectorAll('.tab'));

        function select(name, push) {
            tabs.forEach(function (tab) {
                var on = tab.dataset.tab === name;
                tab.setAttribute('aria-selected', String(on));
                tab.setAttribute('tabindex', on ? '0' : '-1');
                var panel = document.getElementById(tab.getAttribute('aria-controls'));
                if (panel) panel.hidden = !on;
            });
            if (push && window.history.replaceState) {
                var url = new URL(window.location.href);
                url.searchParams.set('tab', name);
                window.history.replaceState({}, '', url);
            }
        }

        tabs.forEach(function (tab, index) {
            tab.addEventListener('click', function () { select(tab.dataset.tab, true); });
            tab.addEventListener('keydown', function (e) {
                var delta = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
                if (!delta) return;
                e.preventDefault();
                var next = tabs[(index + delta + tabs.length) % tabs.length];
                next.focus();
                select(next.dataset.tab, true);
            });
        });

        var initial = group.dataset.tabs;
        if (initial && tabs.some(function (t) { return t.dataset.tab === initial; })) {
            select(initial, false);
        }
    });

    /* ------------------------------------------- collapsible groups ---- */
    document.querySelectorAll('.category-head').forEach(function (head) {
        head.addEventListener('click', function () {
            var open = head.getAttribute('aria-expanded') === 'true';
            head.setAttribute('aria-expanded', String(!open));
            var body = document.getElementById(head.getAttribute('aria-controls'));
            if (body) body.hidden = open;
        });
    });

    /* ------------------------------------------------------ flashes ---- */
    document.querySelectorAll('.flash-close').forEach(function (button) {
        button.addEventListener('click', function () {
            var flash = button.closest('.flash');
            if (flash) flash.remove();
        });
    });

    /* ------------------------------ delete gate: name must match -------- */
    document.querySelectorAll('[data-confirm-name]').forEach(function (form) {
        var expected = form.dataset.confirmName.trim().toLowerCase();
        var input = form.querySelector('input[name="inspector_name_confirm"]');
        var submit = form.querySelector('button[type="submit"], input[type="submit"]');
        if (!input || !submit) return;

        function sync() {
            submit.disabled = input.value.trim().toLowerCase() !== expected;
        }
        input.addEventListener('input', sync);
        sync();
    });

    /* ------------------------- checklist progress as boxes are ticked --- */
    var progress = document.querySelector('[data-progress]');
    if (progress) {
        var boxes = document.querySelectorAll('.check-row input[type="checkbox"]');
        var bar = progress.querySelector('.meter span');
        var label = progress.querySelector('[data-progress-label]');

        function update() {
            var done = 0;
            boxes.forEach(function (box) { if (box.checked) done += 1; });
            var percent = boxes.length ? Math.round((done / boxes.length) * 100) : 0;
            if (bar) bar.style.width = percent + '%';
            if (label) label.textContent = done + ' of ' + boxes.length + ' verified (' + percent + '%)';
            var meter = progress.querySelector('.meter');
            if (meter) {
                meter.classList.remove('meter-ok', 'meter-warn', 'meter-danger');
                meter.classList.add(percent >= 80 ? 'meter-ok' : percent >= 50 ? 'meter-warn' : 'meter-danger');
            }
        }
        boxes.forEach(function (box) { box.addEventListener('change', update); });
        update();
    }
})();
