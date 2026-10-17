(() => {
    const menu = document.getElementById('farmer-menu');
    const toggle = document.getElementById('farmer-menu-toggle');
    if (!menu || !toggle) return;
    let latest = null;
    let busy = false;
    const count = document.getElementById('farmer-notification-count');
    const status = document.getElementById('farmer-notification-status');
    const suggestionStatus = document.getElementById('farmer-suggestion-status');
    const list = document.getElementById('farmer-announcement-list');
    const translate = text => document.documentElement.lang === 'hil' ? (window.farmerMenuLabels[text] || text) : text;
    function render(data) {
        latest = data;
        const unread = data.unread_announcements + data.unread_suggestions;
        count.hidden = !unread;
        count.textContent = unread > 99 ? '99+' : String(unread);
        const message = unread ? `${translate('New announcements')}: ${data.unread_announcements}. ${translate('New suggestions')}: ${data.unread_suggestions}.` : translate('No new notifications.');
        if (status.textContent !== message) status.textContent = message;
        suggestionStatus.textContent = data.suggestion_id ? translate('Your saved scan suggestions are available in Input Logs.') : translate('Suggestions will appear after a scan assessment.');
        list.replaceChildren();
        for (const item of data.announcements) {
            const article = document.createElement('article');
            article.className = 'list-row';
            const copy = document.createElement('div');
            const title = document.createElement('h4');
            title.textContent = item.title;
            const body = document.createElement('p');
            body.textContent = item.message;
            const date = document.createElement('time');
            date.dateTime = item.created_at;
            date.textContent = new Date(item.created_at).toLocaleString();
            copy.append(title, body, date);
            article.append(copy);
            list.append(article);
        }
        if (!data.announcements.length) list.textContent = translate('No announcements yet. New admin updates will appear here.');
    }
    async function refresh() {
        if (busy || document.hidden) return;
        busy = true;
        try {
            const response = await fetch('/farmer/notifications', {headers: {Accept: 'application/json'}});
            if (response.ok && response.headers.get('content-type')?.includes('application/json')) render(await response.json());
        } catch (_) { /* Keep existing content available if the network drops. */ }
        finally { busy = false; }
    }
    toggle.addEventListener('click', () => {
        menu.showModal();
        toggle.setAttribute('aria-expanded', 'true');
        document.body.classList.add('farmer-menu-open');
        refresh();
    });
    document.getElementById('farmer-menu-close').addEventListener('click', () => menu.close());
    menu.addEventListener('click', event => {
        if (event.target === menu) {
            const rect = menu.getBoundingClientRect();
            if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) menu.close();
        }
    });
    menu.addEventListener('close', () => {
        toggle.setAttribute('aria-expanded', 'false');
        document.body.classList.remove('farmer-menu-open');
        toggle.focus();
    });
    const markRead = document.createElement('button');
    markRead.type = 'button';
    markRead.className = 'btn light';
    markRead.textContent = translate('Mark notifications as read');
    menu.querySelector('.farmer-menu-links').after(markRead);
    markRead.addEventListener('click', async () => {
        if (!latest) return;
        markRead.disabled = true;
        try {
            const response = await fetch('/farmer/notifications', {
                method: 'POST',
                headers: {'X-CSRFToken': menu.querySelector('[name=csrfmiddlewaretoken]').value},
                body: new URLSearchParams({announcement_id: latest.announcement_id, suggestion_id: latest.suggestion_id})
            });
            if (!response.ok) throw new Error('Request failed');
            render(await response.json());
        } catch (_) { suggestionStatus.textContent = translate('Could not mark notifications as read. Please try again.'); }
        finally { markRead.disabled = false; }
    });
    refresh();
    setInterval(refresh, 30000);
    document.addEventListener('visibilitychange', refresh);
})();
