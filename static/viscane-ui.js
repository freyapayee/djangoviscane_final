(() => {
  // Delegation keeps controls working after HTMX swaps Login/Register forms.
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-password-toggle]');
    if (!button) return;
    const target = document.getElementById(button.dataset.passwordToggle);
    if (!target) return;
      const show = target.type === 'password';
      target.type = show ? 'text' : 'password';
      button.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      button.setAttribute('aria-pressed', String(show));
      const icon = button.querySelector('ion-icon');
      if (icon) icon.setAttribute('name', show ? 'eye-off-outline' : 'eye-outline');
      const label = button.querySelector('span');
      if (label) label.textContent = show ? 'Hide' : 'Show';
  });

  document.addEventListener('submit', (event) => {
      const form = event.target.closest('form[data-loading-form]');
      if (!form || event.defaultPrevented) return;
      const button = form.querySelector('[type="submit"]');
      if (button) {
        button.setAttribute('aria-busy', 'true');
        button.disabled = true;
      }
  });
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('[data-loading-form] [aria-busy="true"]').forEach((button) => {
      button.removeAttribute('aria-busy');
      button.disabled = false;
    });
  });

  document.querySelectorAll('[data-current-path]').forEach((nav) => {
    const path = window.location.pathname.replace(/\/$/, '') || '/';
    nav.querySelectorAll('a[href]').forEach((link) => {
      const href = new URL(link.href, window.location.origin).pathname.replace(/\/$/, '') || '/';
      const exact = href === '/admin' || href === '/superadmin' || href === '/homepage';
      if (path === href || (!exact && path.startsWith(`${href}/`))) {
        link.classList.add('is-active');
        link.setAttribute('aria-current', 'page');
      }
    });
  });
})();
