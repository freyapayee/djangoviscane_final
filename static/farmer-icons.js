/* Local SVG fallback for farmer pages; no icon CDN or network required. */
(() => {
    const drawings = {
        home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/><path d="M2 10 12 2l10 8"/>',
        person: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0z"/>',
        document: '<path d="M6 2h8l5 5v15H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/><path d="M14 2v6h6M8 13h8M8 17h8"/>',
        sparkle: '<path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l1 2.5 2.5 1-2.5 1L19 23l-1-2.5-2.5-1 2.5-1zM5 2l.8 2.2L8 5l-2.2.8L5 8l-.8-2.2L2 5l2.2-.8z"/>',
        calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M7 14h2M12 14h2M17 14h.1M7 17h2M12 17h2"/>',
        clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        leaf: '<path d="M20 4C10 4 5 7 5 13a6 6 0 0 0 6 6c6 0 9-5 9-15Z"/><path d="M4 21c3-6 7-9 13-13"/>',
        camera: '<path d="M4 7h4l2-3h4l2 3h4a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z"/><circle cx="12" cy="13" r="4"/>',
        image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9" r="1.5"/><path d="m21 15-5-5L5 20"/>',
        menu: '<path d="M3 6h18M3 12h18M3 18h18"/>',
        weather: '<path d="M7.5 15a4.5 4.5 0 1 1 4.3-5.8 5.2 5.2 0 0 1 2.1-.4"/><path d="M7.5 3.5v1.2M2.8 5.5l.9.9M1.5 10.2h1.3M14.7 5.5l-.9.9M13.7 10.2h-1.2"/><path d="M8 18.5h9a3.5 3.5 0 0 0 .2-7 4.7 4.7 0 0 0-9.1 1.2A3 3 0 0 0 8 18.5Z"/>',
        notifications: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
        newspaper: '<path d="M4 4h15v17H5a2 2 0 0 1-2-2V6a2 2 0 0 1 1-2z"/><path d="M7 8h9M7 12h9M7 16h5M19 8h2v10a3 3 0 0 1-3 3"/>',
        arrow: '<path d="M4 12h15M13 5l7 7-7 7"/>',
        check: '<path d="m5 12 4 4L19 6"/>',
        close: '<path d="m6 6 12 12M18 6 6 18"/>',
        location: '<path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
        mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
        phone: '<path d="M7 3H4a1 1 0 0 0-1 1c0 9 8 17 17 17a1 1 0 0 0 1-1v-3l-5-2-2 3a14 14 0 0 1-7-7l3-2z"/>',
        lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 1 1 8 0v3"/>',
        scan: '<path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4M7 12h10"/>',
        chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
        info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
        language: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
        edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L9 17l-4 1 1-4z"/>',
        download: '<path d="M12 3v12M7 10l5 5 5-5M4 20h16"/>',
        save: '<path d="M4 3h14l3 3v15H3V4a1 1 0 0 1 1-1z"/><path d="M7 3v6h10V3M7 21v-8h10v8"/>',
        logout: '<path d="M10 17l5-5-5-5M15 12H3M12 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7"/>',
        calculator: '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M8 6h8v4H8zM8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01"/>',
        bug: '<path d="M8 8h8v10a4 4 0 0 1-8 0zM9 8a3 3 0 0 1 6 0M4 13h4M16 13h4M5 7l3 2M19 7l-3 2M5 19l3-2M19 19l-3-2M12 12v7"/>',
        help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4.3 1.7c-1 .9-1.8 1.3-1.8 2.8M12 17h.01"/>',
        default: '<circle cx="12" cy="12" r="9"/><path d="M8 12h8M12 8v8"/>'
    };
    const groups = {
        'home-outline': 'home', 'grid-outline': 'home', 'person-outline': 'person', 'person-circle-outline': 'person',
        'document-text-outline': 'document', 'analytics-outline': 'chart', 'bar-chart-outline': 'chart', 'stats-chart-outline': 'chart',
        'sparkles-outline': 'sparkle', sparkles: 'sparkle', 'calendar-outline': 'calendar', 'time-outline': 'clock',
        'leaf-outline': 'leaf', 'camera-outline': 'camera', camera: 'camera', 'images-outline': 'image', images: 'image',
        'menu-outline': 'menu', 'partly-sunny-outline': 'weather', 'notifications-outline': 'notifications',
        'newspaper-outline': 'newspaper', 'megaphone-outline': 'notifications', 'arrow-forward-outline': 'arrow',
        'chevron-forward-outline': 'arrow', 'chevron-back-outline': 'arrow', 'chevron-down-outline': 'arrow', 'chevron-down': 'arrow',
        checkmark: 'check', 'checkmark-circle-outline': 'check', 'close-outline': 'close', 'location-outline': 'location',
        'pin-outline': 'location', 'map-outline': 'location', 'mail-outline': 'mail', 'call-outline': 'phone', 'phone': 'phone',
        'lock-closed-outline': 'lock', 'scan-outline': 'scan', 'resize-outline': 'scan', 'information-circle-outline': 'info',
        'help-circle-outline': 'help', 'language': 'language', 'create-outline': 'edit', 'download-outline': 'download',
        'save-outline': 'save', 'log-out-outline': 'logout', 'calculator-outline': 'calculator', 'bug-outline': 'bug',
        'flask-outline': 'calculator', 'cut-outline': 'edit', 'compass-outline': 'scan', 'navigate-outline': 'arrow',
        'business-outline': 'home', 'layers-outline': 'document', 'git-branch-outline': 'document', 'bulb-outline': 'sparkle',
        'send-outline': 'arrow'
    };
    function replaceIcon(node) {
        if (!(node instanceof HTMLElement) || node.tagName !== 'ION-ICON' || node.dataset.localIcon === 'true') return;
        const name = node.getAttribute('name') || '';
        const computed = window.getComputedStyle(node);
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', 'currentColor');
        svg.setAttribute('stroke-width', '1.8');
        svg.setAttribute('stroke-linecap', 'round');
        svg.setAttribute('stroke-linejoin', 'round');
        svg.setAttribute('aria-hidden', node.getAttribute('aria-hidden') || 'true');
        svg.setAttribute('focusable', 'false');
        svg.classList.add('farmer-local-icon');
        const classes = node.getAttribute('class');
        if (classes) classes.split(/\s+/).forEach(value => value && svg.classList.add(value));
        const style = node.getAttribute('style');
        if (style) svg.setAttribute('style', style);
        // Ionicons sizing rules target the custom element. Preserve those resolved
        // dimensions and layout values on the local SVG replacement.
        const inheritedSize = computed.fontSize && computed.fontSize !== '0px' ? computed.fontSize : '1em';
        const dimension = value => (!value || value === 'auto' || value === 'normal' || value === '0' || value === '0px') ? inheritedSize : value;
        ['display', 'position', 'box-sizing', 'vertical-align', 'font-size', 'color',
            'opacity', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
            'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
            'flex', 'flex-basis', 'flex-grow', 'flex-shrink', 'align-self', 'order',
            'top', 'right', 'bottom', 'left', 'pointer-events', 'background-color',
            'border-radius', 'transform'].forEach(property => {
                const value = computed.getPropertyValue(property);
                if (value) svg.style.setProperty(property, value);
            });
        svg.style.setProperty('width', dimension(computed.getPropertyValue('width')));
        svg.style.setProperty('height', dimension(computed.getPropertyValue('height')));
        svg.dataset.localIcon = 'true';
        svg.innerHTML = drawings[groups[name]] || drawings.default;
        node.replaceWith(svg);
    }
    function scan(root) {
        if (root instanceof Element && root.matches('ion-icon')) replaceIcon(root);
        root.querySelectorAll?.('ion-icon').forEach(replaceIcon);
    }
    scan(document);
    new MutationObserver(changes => changes.forEach(change => change.addedNodes.forEach(scan)))
        .observe(document.documentElement, {childList: true, subtree: true});
})();
