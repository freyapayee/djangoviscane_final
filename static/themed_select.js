(() => {
    const selects = document.querySelectorAll('select[data-themed-select]');
    if (!selects.length) return;

    let openMenu = null;

    for (const select of selects) {
        const choices = [...select.options].filter((option) => !option.disabled && option.value);
        if (!choices.length) continue;

        const wrapper = document.createElement('div');
        wrapper.className = 'themed-select';

        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'themed-select-trigger';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');
        const label = select.closest('label')?.querySelector('.profile-detail-label')?.textContent.trim() || select.closest('.stat-card')?.querySelector('.stat-label')?.textContent.trim() || select.name;
        trigger.setAttribute('aria-label', label);

        const value = document.createElement('span');
        value.className = 'themed-select-value';
        const chevron = document.createElement('ion-icon');
        chevron.setAttribute('name', 'chevron-down-outline');
        chevron.setAttribute('aria-hidden', 'true');
        trigger.append(value, chevron);

        const menu = document.createElement('div');
        menu.className = 'themed-select-menu';
        menu.id = `themed-select-${select.name}`;
        menu.setAttribute('role', 'listbox');
        menu.setAttribute('aria-label', label);
        menu.hidden = true;
        trigger.setAttribute('aria-controls', menu.id);

        const buttons = choices.map((choice) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'themed-select-option';
            button.setAttribute('role', 'option');
            button.setAttribute('aria-selected', 'false');
            button.tabIndex = -1;
            button.dataset.value = choice.value;
            button.textContent = choice.textContent.trim();
            menu.append(button);
            return button;
        });

        const update = () => {
            const selected = select.selectedOptions[0];
            value.textContent = selected?.textContent.trim() || '';
            trigger.setAttribute('aria-label', `${label}: ${value.textContent}`);
            trigger.classList.toggle('is-placeholder', !select.value);
            trigger.classList.remove('is-invalid');
            for (const button of buttons) {
                button.setAttribute('aria-selected', String(button.dataset.value === select.value));
            }
        };

        const close = (returnFocus = false) => {
            menu.hidden = true;
            wrapper.classList.remove('is-open', 'is-up');
            wrapper.closest('.profile-detail-row')?.classList.remove('themed-select-row-open');
            wrapper.closest('.stat-card')?.classList.remove('themed-select-card-open');
            trigger.setAttribute('aria-expanded', 'false');
            if (openMenu === wrapper) openMenu = null;
            if (returnFocus) trigger.focus();
        };

        const open = (focusOption = false) => {
            if (openMenu && openMenu !== wrapper) openMenu.closeThemedMenu();
            menu.hidden = false;
            wrapper.classList.add('is-open');
            wrapper.closest('.profile-detail-row')?.classList.add('themed-select-row-open');
            wrapper.closest('.stat-card')?.classList.add('themed-select-card-open');
            trigger.setAttribute('aria-expanded', 'true');
            openMenu = wrapper;
            const rect = trigger.getBoundingClientRect();
            const below = window.innerHeight - rect.bottom;
            const above = rect.top;
            const preferredHeight = select.name === 'hectares' ? 440 : 300;
            const up = below < Math.min(menu.scrollHeight, preferredHeight) && above > below;
            wrapper.classList.toggle('is-up', up);
            menu.style.maxHeight = `${Math.max(100, Math.min(preferredHeight, (up ? above : below) - 16))}px`;
            if (focusOption) {
                const active = buttons.find((button) => button.dataset.value === select.value) || buttons[0];
                active.focus();
                active.scrollIntoView({ block: 'nearest' });
            }
        };

        wrapper.closeThemedMenu = close;
        trigger.addEventListener('click', (event) => {
            event.preventDefault();
            menu.hidden ? open(true) : close();
        });
        trigger.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                open(true);
            }
        });
        menu.addEventListener('click', (event) => {
            const button = event.target.closest('.themed-select-option');
            if (!button) return;
            event.preventDefault();
            select.value = button.dataset.value;
            select.dispatchEvent(new Event('change', { bubbles: true }));
            close(true);
        });
        menu.addEventListener('keydown', (event) => {
            const index = buttons.indexOf(document.activeElement);
            let next = index;
            if (event.key === 'ArrowDown') next = Math.min(buttons.length - 1, index + 1);
            else if (event.key === 'ArrowUp') next = Math.max(0, index - 1);
            else if (event.key === 'Home') next = 0;
            else if (event.key === 'End') next = buttons.length - 1;
            else if (event.key === 'Escape') {
                event.preventDefault();
                close(true);
                return;
            } else return;
            event.preventDefault();
            buttons[next].focus();
            buttons[next].scrollIntoView({ block: 'nearest' });
        });
        select.addEventListener('change', update);
        select.addEventListener('invalid', (event) => {
            event.preventDefault();
            trigger.classList.add('is-invalid');
            trigger.focus();
        });

        wrapper.append(trigger, menu);
        select.after(wrapper);
        select.classList.add('is-enhanced');
        select.tabIndex = -1;
        update();
    }

    document.addEventListener('pointerdown', (event) => {
        if (openMenu && !openMenu.contains(event.target)) openMenu.closeThemedMenu();
    });
    window.addEventListener('resize', () => openMenu?.closeThemedMenu());
})();
