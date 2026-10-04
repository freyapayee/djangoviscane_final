(() => {
    const sectionIds = ['recent-scans', 'scan-gallery'];
    if (!sectionIds.every((id) => document.getElementById(id))) return;

    let currentRequest = null;
    let appliedUrl = new URL(window.location.href);

    const pageKey = (url) => sectionIds.map((id) =>
        url.searchParams.get(id === 'recent-scans' ? 'recent_page' : 'gallery_page') || '1'
    ).join(':');

    const syncOtherSection = (changedId, url) => {
        const otherId = sectionIds.find((id) => id !== changedId);
        const other = document.getElementById(otherId);
        const changedParameter = changedId === 'recent-scans' ? 'recent_page' : 'gallery_page';
        const changedPage = url.searchParams.get(changedParameter) || '1';
        for (const link of other.querySelectorAll('.scan-section-pagination a')) {
            const destination = new URL(link.href);
            destination.searchParams.set(changedParameter, changedPage);
            link.href = destination.pathname + destination.search + destination.hash;
        }
        if (otherId === 'recent-scans') {
            for (const form of other.querySelectorAll('.recent-picture-remove-form')) {
                const destination = new URL(form.action);
                destination.searchParams.set(changedParameter, changedPage);
                form.action = destination.pathname + destination.search;
            }
        }
    };

    async function loadPages(url, ids, addHistory = false) {
        if (currentRequest) {
            currentRequest.controller.abort();
            currentRequest.ids.forEach((id) => {
                const section = document.getElementById(id);
                section?.classList.remove('is-page-loading');
                section?.removeAttribute('aria-busy');
            });
        }
        const controller = new AbortController();
        currentRequest = { controller, ids };
        ids.forEach((id) => {
            const section = document.getElementById(id);
            section.classList.add('is-page-loading');
            section.setAttribute('aria-busy', 'true');
        });

        try {
            const replacements = await Promise.all(ids.map(async (id) => {
                const requestUrl = new URL(url);
                requestUrl.searchParams.set('scan_section', id);
                requestUrl.hash = '';
                const response = await fetch(requestUrl, {
                    credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    signal: controller.signal,
                });
                if (!response.ok || response.redirected) throw new Error('Pagination request failed');
                const documentPart = new DOMParser().parseFromString(await response.text(), 'text/html');
                const section = documentPart.getElementById(id);
                if (!section) throw new Error('Pagination response was incomplete');
                return section;
            }));
            if (controller.signal.aborted) return;
            ids.forEach((id, index) => {
                replacements[index].classList.add('is-page-entering');
                document.getElementById(id).replaceWith(replacements[index]);
            });
            if (ids.length === 1) syncOtherSection(ids[0], url);
            if (addHistory) history.pushState({ scanPagination: true }, '', url.pathname + url.search + url.hash);
            appliedUrl = new URL(url);
            if (addHistory) {
                const count = replacements[0].querySelector('.scan-page-count');
                if (count) {
                    count.tabIndex = -1;
                    count.focus({ preventScroll: true });
                }
            }
        } catch (error) {
            if (error.name !== 'AbortError') window.location.assign(url.href);
        } finally {
            if (currentRequest?.controller === controller) {
                currentRequest = null;
                ids.forEach((id) => {
                    const section = document.getElementById(id);
                    section?.classList.remove('is-page-loading');
                    section?.removeAttribute('aria-busy');
                });
            }
        }
    }

    document.addEventListener('click', (event) => {
        const link = event.target.closest('.scan-sections .scan-section-pagination a[href]');
        if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const section = link.closest('#recent-scans, #scan-gallery');
        const url = new URL(link.href);
        if (!section || url.origin !== window.location.origin || url.pathname !== window.location.pathname) return;
        event.preventDefault();
        loadPages(url, [section.id], true);
    });

    window.addEventListener('popstate', () => {
        const url = new URL(window.location.href);
        if (pageKey(url) !== pageKey(appliedUrl)) loadPages(url, sectionIds);
        else appliedUrl = url;
    });
})();
