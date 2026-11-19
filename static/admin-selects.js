(() => {
    const enhance = (select) => {
        if (select.dataset.customSelectReady === 'true' || select.multiple || select.size > 1) return;
        select.dataset.customSelectReady = 'true';
        const wrapper = document.createElement('div');
        wrapper.className = 'admin-custom-select';
        wrapper.dataset.open = 'false';
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);

        const required = select.required;
        select.required = false;
        select.classList.add('admin-custom-select-native');
        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'admin-custom-select-trigger';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');
        const label = document.createElement('span');
        const arrow = document.createElement('span');
        arrow.className = 'admin-custom-select-arrow';
        arrow.setAttribute('aria-hidden', 'true');
        trigger.append(label, arrow);
        const list = document.createElement('div');
        list.className = 'admin-custom-select-list';
        list.setAttribute('role', 'listbox');
        list.hidden = true;
        wrapper.append(trigger, list);

        const sync = () => {
            const option = select.options[select.selectedIndex];
            label.textContent = option ? option.textContent.trim() : '';
            trigger.setAttribute('aria-label', `${select.getAttribute('aria-label') || select.labels?.[0]?.textContent.trim() || 'Choose option'}: ${label.textContent}`);
            list.querySelectorAll('[role="option"]').forEach((item) => {
                const selected = item.dataset.value === select.value;
                item.setAttribute('aria-selected', String(selected));
                item.classList.toggle('is-selected', selected);
            });
        };
        const close = () => {
            wrapper.dataset.open = 'false';
            trigger.setAttribute('aria-expanded', 'false');
            list.hidden = true;
        };
        Array.from(select.options).forEach((option) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'admin-custom-select-option';
            item.setAttribute('role', 'option');
            item.dataset.value = option.value;
            item.textContent = option.textContent.trim();
            item.disabled = option.disabled;
            item.addEventListener('click', (event) => {
                // Prevent an enclosing label from reopening the hidden native select.
                event.preventDefault();
                select.value = option.value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                sync();
                close();
                trigger.focus();
            });
            list.appendChild(item);
        });
        trigger.addEventListener('click', (event) => {
            // Selects are often nested in labels; cancel the label's native activation.
            event.preventDefault();
            const opening = list.hidden;
            list.hidden = !opening;
            wrapper.dataset.open = String(opening);
            trigger.setAttribute('aria-expanded', String(opening));
            if (opening) list.querySelector('[aria-selected="true"]:not(:disabled)')?.focus();
        });
        trigger.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                if (list.hidden) trigger.click();
                else list.querySelector('[aria-selected="true"]:not(:disabled)')?.focus();
            }
        });
        list.addEventListener('keydown', (event) => {
            const options = [...list.querySelectorAll('[role="option"]:not(:disabled)')];
            const index = options.indexOf(document.activeElement);
            if (event.key === 'Escape') { close(); trigger.focus(); }
            else if (event.key === 'ArrowDown') { event.preventDefault(); options[Math.min(index + 1, options.length - 1)]?.focus(); }
            else if (event.key === 'ArrowUp') { event.preventDefault(); options[Math.max(index - 1, 0)]?.focus(); }
        });
        select.addEventListener('change', sync);
        select._adminCustomSelect = { wrapper, trigger, required };
        sync();

        const form = select.closest('form');
        if (form && required && !form.dataset.customSelectValidationReady) {
            form.dataset.customSelectValidationReady = 'true';
            form.addEventListener('submit', (event) => {
                const missing = [...form.querySelectorAll('select[data-custom-select-ready="true"]')].find((field) => field._adminCustomSelect?.required && !field.value);
                if (missing) {
                    event.preventDefault();
                    missing._adminCustomSelect.wrapper.classList.add('has-error');
                    missing._adminCustomSelect.trigger.focus();
                    missing._adminCustomSelect.trigger.click();
                }
            }, true);
        }
        trigger.addEventListener('click', () => wrapper.classList.remove('has-error'));
    };
    const initialize = () => document.querySelectorAll('body.ds-app select').forEach(enhance);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, { once: true });
    else initialize();
    document.addEventListener('click', (event) => {
        document.querySelectorAll('.admin-custom-select[data-open="true"]').forEach((wrapper) => {
            if (!wrapper.contains(event.target)) {
                wrapper.dataset.open = 'false';
                wrapper.querySelector('.admin-custom-select-trigger')?.setAttribute('aria-expanded', 'false');
                wrapper.querySelector('.admin-custom-select-list').hidden = true;
            }
        });
    });
})();
