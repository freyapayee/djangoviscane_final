(() => {
  const configureAppShell = () => {
    const head = document.head;
    const ensureMeta = (name, content) => {
      let node = head.querySelector(`meta[name="${name}"]`);
      if (!node) {
        node = document.createElement('meta');
        node.name = name;
        head.append(node);
      }
      node.content = content;
    };

    if (!head.querySelector('link[rel="manifest"]')) {
      const manifest = document.createElement('link');
      manifest.rel = 'manifest';
      manifest.href = '/static/farmer-manifest.webmanifest';
      head.append(manifest);
    }
    ensureMeta('theme-color', '#0b6b38');
    ensureMeta('apple-mobile-web-app-capable', 'yes');
    ensureMeta('apple-mobile-web-app-status-bar-style', 'black-translucent');
    ensureMeta('apple-mobile-web-app-title', 'VISCANE');

    if ('serviceWorker' in navigator && window.isSecureContext) {
      navigator.serviceWorker.register('/service-worker.js', { scope: '/' }).catch(() => {
        // The farmer portal still works when the browser cannot register a worker.
      });
    }

    let installEvent = null;
    window.addEventListener('beforeinstallprompt', (event) => {
      event.preventDefault();
      installEvent = event;
      let button = document.querySelector('.farmer-install-button');
      if (!button) {
        button = document.createElement('button');
        button.type = 'button';
        button.className = 'farmer-install-button';
        button.innerHTML = '<ion-icon name="download-outline"></ion-icon> Install app';
        const actions = document.querySelector('.header-actions');
        if (actions) actions.append(button);
      }
      button.classList.add('is-visible');
      button.onclick = async () => {
        if (!installEvent) return;
        installEvent.prompt();
        await installEvent.userChoice;
        installEvent = null;
        button.classList.remove('is-visible');
      };
    });
  };

  configureAppShell();

  const infoNodes = Array.from(document.querySelectorAll('[data-farmer-info-text]'));
  const hiligaynon = document.documentElement.lang === 'hil';
  if (!infoNodes.length) {
    return;
  }

  const fmtDate = () => {
    try {
      if (hiligaynon) {
        return new Intl.DateTimeFormat('en-PH', { year: 'numeric', month: 'numeric', day: 'numeric' }).format(new Date());
      }
      return new Intl.DateTimeFormat(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric'
      }).format(new Date());
    } catch (_) {
      return new Date().toLocaleDateString();
    }
  };

  const setInfo = (text) => {
    infoNodes.forEach((node) => {
      node.textContent = text;
    });
  };

  const weatherText = (code) => {
    const c = Number(code);
    if (c === 0) return hiligaynon ? 'Matawhay' : 'Clear';
    if ([1, 2].includes(c)) return hiligaynon ? 'May panganod' : 'Partly cloudy';
    if (c === 3) return hiligaynon ? 'Mabugal nga panganod' : 'Cloudy';
    if ([45, 48].includes(c)) return hiligaynon ? 'May gabon' : 'Fog';
    if ([51, 53, 55, 56, 57].includes(c)) return hiligaynon ? 'Mahinay nga ulan' : 'Drizzle';
    if ([61, 63, 65, 66, 67, 80, 81, 82].includes(c)) return hiligaynon ? 'Ulan' : 'Rain';
    if ([71, 73, 75, 77, 85, 86].includes(c)) return hiligaynon ? 'Niyebe' : 'Snow';
    if ([95, 96, 99].includes(c)) return hiligaynon ? 'May dalugdog' : 'Thunder';
    return hiligaynon ? 'Panahon' : 'Weather';
  };

  const dateOnly = fmtDate();
  setInfo(dateOnly);

  if (!navigator.geolocation) {
    return;
  }

  navigator.geolocation.getCurrentPosition(
    async (position) => {
      const lat = Number(position.coords?.latitude);
      const lon = Number(position.coords?.longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        return;
      }

      try {
        const url = new URL('https://api.open-meteo.com/v1/forecast');
        url.searchParams.set('latitude', String(lat));
        url.searchParams.set('longitude', String(lon));
        url.searchParams.set('current', 'temperature_2m,weather_code');
        url.searchParams.set('timezone', 'auto');

        const response = await fetch(url.toString(), { method: 'GET' });
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        const current = payload?.current;
        const temp = Number(current?.temperature_2m);
        const code = Number(current?.weather_code);
        if (!Number.isFinite(temp)) {
          return;
        }

        const label = weatherText(code);
        const details = `${dateOnly} | ${Math.round(temp)}°C ${label}`;
        setInfo(details);
      } catch (_) {
        // Keep date-only info when weather fetch fails.
      }
    },
    () => {
      // User denied location; keep date-only info.
    },
    { enableHighAccuracy: false, timeout: 4000, maximumAge: 300000 }
  );
})();
