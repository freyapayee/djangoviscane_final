(function () {
    const stateKey = 'viscane-farmer-tour';
    const steps = [
        { path: '/homepage', target: 'home-scan', title: 'Start with a sugarcane scan', description: 'This button opens the camera flow where you can scan a stalk or upload a photo for AI analysis.', next: '/scan/new' },
        { path: '/scan/new', target: 'scan-upload', title: 'Choose a photo or use your camera', description: 'Try Choose photo to select an image from your phone, or Use camera to capture a new one.', next: '/farmer/recommendations' },
        { path: '/farmer/recommendations', target: 'recommendations', title: 'Review your recommendations', description: 'After a calculation, this page shows the next best actions for harvest, pests, fertilizer, weeding, and plowing.', next: '/farmer/agronomic-logs' },
        { path: '/farmer/agronomic-logs', target: 'input-logs', title: 'Check your Input Logs', description: 'Your saved inputs, scan details, calculation results, and recommendation history are kept here.', next: '/farmer/settings' },
        { path: '/farmer/settings', target: 'profile-settings', title: 'Manage your Profile', description: 'Update your profile details, profile picture, password, and account settings from this page.', next: null }
    ];

    const stateKeyValue = window.location.pathname.replace(/\/$/, '') || '/';
    const launch = document.getElementById('farmer-tutorial');
    let saved = null;
    try { saved = JSON.parse(sessionStorage.getItem(stateKey) || 'null'); } catch (_) { saved = null; }
    if (launch && !saved) saved = { step: 0 };
    if (!saved || !steps[saved.step] || steps[saved.step].path !== stateKeyValue) return;

    const step = steps[saved.step];
    const target = document.querySelector(`[data-tour-target="${step.target}"]`);
    if (!target) return;
    sessionStorage.setItem(stateKey, JSON.stringify(saved));
    document.body.classList.add('has-farmer-tour');

    const modal = launch || document.body.appendChild(document.createElement('div'));
    modal.id = 'farmer-tutorial';
    modal.className = 'farmer-tutorial-backdrop is-guided-tour';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'farmer-tour-title');
    modal.innerHTML = `
        <div class="farmer-tutorial-dialog farmer-tour-card">
            <button class="farmer-tutorial-close" type="button" id="farmer-tutorial-close" aria-label="Skip tour"><ion-icon name="close-outline" aria-hidden="true"></ion-icon></button>
            <div class="farmer-tutorial-progress" aria-hidden="true">${steps.map((_, index) => `<span class="${index === saved.step ? 'is-active' : ''}"></span>`).join('')}</div>
            <div class="farmer-tutorial-icon"><ion-icon name="navigate-outline" aria-hidden="true"></ion-icon></div>
            <p class="farmer-tutorial-kicker">Guided tour · ${saved.step + 1} of ${steps.length}</p>
            <h2 id="farmer-tour-title">${step.title}</h2>
            <p class="farmer-tour-description">${step.description}</p>
            <p class="farmer-tour-hint"><ion-icon name="hand-left-outline" aria-hidden="true"></ion-icon> The highlighted area is the feature to try.</p>
            <div class="farmer-tutorial-actions">
                <button class="btn ghost farmer-tutorial-back" type="button" id="farmer-tutorial-back" ${saved.step === 0 ? 'hidden' : ''}>Back</button>
                <button class="btn primary farmer-tutorial-next" type="button" id="farmer-tutorial-next">${step.next ? 'Continue tour' : 'Finish tour'}</button>
            </div>
        </div>`;

    target.classList.add('farmer-tour-target');
    target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    const finish = () => { sessionStorage.removeItem(stateKey); target.classList.remove('farmer-tour-target'); document.body.classList.remove('has-farmer-tour'); modal.remove(); };
    const navigate = (index) => { sessionStorage.setItem(stateKey, JSON.stringify({ step: index })); window.location.href = steps[index].path; };
    modal.querySelector('#farmer-tutorial-close').addEventListener('click', finish);
    modal.querySelector('#farmer-tutorial-back').addEventListener('click', () => { if (saved.step > 0) navigate(saved.step - 1); });
    modal.querySelector('#farmer-tutorial-next').addEventListener('click', () => { if (step.next) navigate(saved.step + 1); else finish(); });
    modal.addEventListener('click', (event) => { if (event.target === modal) finish(); });
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape') finish(); });
    modal.querySelector('#farmer-tutorial-close').focus({ preventScroll: true });
    window.addEventListener('pagehide', () => target.classList.remove('farmer-tour-target'), { once: true });
}());
