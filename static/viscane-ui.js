(() => {
  // Delegation keeps controls working after HTMX swaps Login/Register forms.
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-password-toggle]');
    if (!button) return;
    const target = document.getElementById(button.dataset.passwordToggle);
    if (!target) return;
      const show = target.type === 'password';
      target.type = show ? 'text' : 'password';
      const hiligaynon = document.documentElement.lang.toLowerCase().startsWith('hil');
      button.setAttribute('aria-label', show ? (hiligaynon ? 'Tagoa ang password' : 'Hide password') : (hiligaynon ? 'Ipakita ang password' : 'Show password'));
      button.setAttribute('aria-pressed', String(show));
      const icon = button.querySelector('ion-icon');
      if (icon) icon.setAttribute('name', show ? 'eye-off-outline' : 'eye-outline');
      const label = button.querySelector('span');
      if (label) label.textContent = show ? (hiligaynon ? 'Tagoa' : 'Hide') : (hiligaynon ? 'Ipakita' : 'Show');
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

  const confirmationCopy = {
    en: {
      'update-profile': ['Update profile?', 'Do you want to save these profile changes?', 'Yes, Update This', 'No, Keep Editing'],
      'update-password': ['Update password?', 'Do you want to change this password?', 'Yes, Update Password', 'No, Keep Editing'],
      'update-settings': ['Update system settings?', 'Do you want to save these system settings?', 'Yes, Save Changes', 'No, Keep Editing'],
      'update-role': ['Update account role?', (name) => `Do you want to update the role for ${name}?`, 'Yes, Update Role', 'No, Keep This'],
      'remove': ['Remove picture?', 'Do you want to remove this picture?', 'Yes, Remove This', 'No, Do Not Remove This'],
      'archive-admin': ['Archive admin account?', (name) => `Do you want to archive ${name}'s admin account?`, 'Yes, Archive This', 'No, Keep This'],
      'archive-farmer': ['Archive farmer account?', (name) => `Do you want to archive ${name}'s account?`, 'Yes, Archive This', 'No, Keep This'],
      'restore-farmer': ['Restore farmer account?', (name) => `Do you want to restore ${name}'s account?`, 'Yes, Restore This', 'No, Keep This'],
      'sign-out': ['Sign out?', 'Do you want to sign out of VISCANE?', 'Yes, Sign Out', 'No, Stay Here'],
    },
    hil: {
      'update-profile': ['Bag-uhon ang profile?', 'Gusto mo bala i-save ang mga pagbag-o sa profile?', 'Huo, Bag-uhon Ini', 'Indi, Magpadayon sa Pag-edit'],
      'update-password': ['Bag-uhon ang password?', 'Gusto mo bala bag-uhon ang password?', 'Huo, Bag-uhon ang Password', 'Indi, Magpadayon sa Pag-edit'],
      'update-settings': ['Bag-uhon ang settings?', 'Gusto mo bala i-save ang mga pagbag-o sa settings?', 'Huo, I-save Ini', 'Indi, Magpadayon sa Pag-edit'],
      'update-role': ['Bag-uhon ang papel sang account?', (name) => `Gusto mo bala bag-uhon ang papel sang account ni ${name}?`, 'Huo, Bag-uhon Ini', 'Indi, Ipabilin Ini'],
      'remove': ['Kuhaon ang hulagway?', 'Gusto mo bala kuhaon ini nga hulagway?', 'Huo, Kuhaon Ini', 'Indi, Ipabilin Ini'],
      'archive-admin': ['I-archive ang admin account?', (name) => `Gusto mo bala i-archive ang account ni ${name}?`, 'Huo, I-archive Ini', 'Indi, Ipabilin Ini'],
      'archive-farmer': ['I-archive ang farmer account?', (name) => `Gusto mo bala i-archive ang account ni ${name}?`, 'Huo, I-archive Ini', 'Indi, Ipabilin Ini'],
      'restore-farmer': ['Ibalik ang farmer account?', (name) => `Gusto mo bala ibalik ang account ni ${name}?`, 'Huo, Ibalik Ini', 'Indi, Ipabilin Ini'],
      'sign-out': ['Magguwa?', 'Gusto mo bala magguwa sa VISCANE?', 'Huo, Magguwa', 'Indi, Magpabilin Diri'],
    },
  };
  const copy = confirmationCopy[document.documentElement.lang === 'hil' ? 'hil' : 'en'];
  const overlay = document.createElement('div');
  overlay.className = 'vis-confirm-overlay';
  overlay.hidden = true;
  overlay.innerHTML = '<div class="vis-confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="vis-confirm-title" aria-describedby="vis-confirm-message"><span class="vis-confirm-icon" aria-hidden="true"><ion-icon name="help-circle-outline"></ion-icon></span><h2 id="vis-confirm-title"></h2><p id="vis-confirm-message"></p><div class="vis-confirm-actions"><button class="vis-confirm-cancel" type="button"></button><button class="vis-confirm-accept" type="button"></button></div></div>';
  document.body.append(overlay);
  const title = overlay.querySelector('#vis-confirm-title');
  const message = overlay.querySelector('#vis-confirm-message');
  const cancel = overlay.querySelector('.vis-confirm-cancel');
  const accept = overlay.querySelector('.vis-confirm-accept');
  const dialog = overlay.querySelector('.vis-confirm-dialog');
  const confirmedForms = new WeakSet();
  let pending = null;
  let previousFocus = null;

  function closeConfirmation(restoreFocus = true) {
    overlay.hidden = true;
    document.body.classList.remove('vis-confirm-open');
    pending = null;
    if (restoreFocus && previousFocus?.isConnected) previousFocus.focus();
  }

  function openConfirmation(action, target, submitter = null) {
    const details = copy[action];
    if (!details) return;
    previousFocus = document.activeElement;
    pending = { target, submitter };
    title.textContent = details[0];
    message.textContent = target.dataset.confirmMessage || (typeof details[1] === 'function' ? details[1](target.dataset.confirmSubject || 'this account') : details[1]);
    accept.textContent = details[2];
    cancel.textContent = details[3];
    dialog.classList.toggle('is-danger', ['remove', 'archive-admin', 'archive-farmer'].includes(action));
    overlay.hidden = false;
    document.body.classList.add('vis-confirm-open');
    cancel.focus();
  }

  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirmAction) return;
    if (confirmedForms.has(form)) return;
    event.preventDefault();
    openConfirmation(form.dataset.confirmAction, form, event.submitter);
  }, true);

  document.addEventListener('click', (event) => {
    const closeButton = event.target.closest('[data-close-profile-details]');
    if (closeButton) closeButton.closest('details')?.removeAttribute('open');
  });

  const profilePhotoInput = document.querySelector('[data-profile-photo-input]');
  const profilePhotoAvatar = document.querySelector('[data-profile-photo-avatar]');
  const profilePhotoPreview = document.querySelector('[data-profile-photo-preview]');
  let profilePhotoPreviewUrl = null;
  profilePhotoInput?.addEventListener('change', () => {
    const file = profilePhotoInput.files?.[0];
    if (!file || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) return;
    if (profilePhotoPreviewUrl) URL.revokeObjectURL(profilePhotoPreviewUrl);
    profilePhotoPreviewUrl = URL.createObjectURL(file);
    if (profilePhotoAvatar) profilePhotoAvatar.src = profilePhotoPreviewUrl;
    if (profilePhotoPreview) {
      profilePhotoPreview.src = profilePhotoPreviewUrl;
      profilePhotoPreview.hidden = false;
    }
  });

  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || (link.target && link.target !== '_self')) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin || !/^\/(?:admin-)?logout\/?$/.test(url.pathname)) return;
    event.preventDefault();
    openConfirmation('sign-out', link);
  });

  cancel.addEventListener('click', () => closeConfirmation());
  overlay.addEventListener('click', (event) => { if (event.target === overlay) closeConfirmation(); });
  accept.addEventListener('click', () => {
    const action = pending;
    closeConfirmation(false);
    if (!action) return;
    if (action.target instanceof HTMLFormElement) {
      confirmedForms.add(action.target);
      try {
        if (action.submitter?.form === action.target) action.target.requestSubmit(action.submitter);
        else action.target.requestSubmit();
      } finally {
        confirmedForms.delete(action.target);
      }
    } else {
      window.location.assign(action.target.href);
    }
  });
  document.addEventListener('keydown', (event) => {
    if (overlay.hidden) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeConfirmation();
    } else if (event.key === 'Tab') {
      if (event.shiftKey && document.activeElement === cancel) { event.preventDefault(); accept.focus(); }
      else if (!event.shiftKey && document.activeElement === accept) { event.preventDefault(); cancel.focus(); }
    }
  });
})();
