(function () {
    const modal = document.getElementById('farmer-tutorial');
    if (!modal) return;

    const steps = Array.from(modal.querySelectorAll('.farmer-tutorial-step'));
    const indicators = Array.from(modal.querySelectorAll('.farmer-tutorial-progress span'));
    const back = document.getElementById('farmer-tutorial-back');
    const next = document.getElementById('farmer-tutorial-next');
    const close = document.getElementById('farmer-tutorial-close');
    let current = 0;

    function renderStep() {
        steps.forEach((step, index) => {
            const active = index === current;
            step.hidden = !active;
            step.classList.toggle('is-active', active);
        });
        indicators.forEach((indicator, index) => indicator.classList.toggle('is-active', index === current));
        back.hidden = current === 0;
        next.textContent = current === steps.length - 1 ? 'Get started' : 'Next';
    }

    function finish() {
        modal.remove();
        document.body.classList.remove('tutorial-open');
    }

    next.addEventListener('click', () => {
        if (current === steps.length - 1) finish();
        else { current += 1; renderStep(); }
    });
    back.addEventListener('click', () => { if (current > 0) { current -= 1; renderStep(); } });
    close.addEventListener('click', finish);
    modal.addEventListener('click', (event) => { if (event.target === modal) finish(); });
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape') finish(); });

    renderStep();
    close.focus();
}());
