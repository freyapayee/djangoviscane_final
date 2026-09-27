(() => {
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
