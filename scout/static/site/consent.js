/* Google Tag Manager, only with the visitor's agreement.
   Served at /site-consent.js with the container ID filled in (SCOUT_GTM_ID in scout/config.py).

   UK law (PECR and UK GDPR) needs a visitor's OK before analytics cookies are set, so nothing
   from Google loads until they press Accept. Their choice is remembered on their device, and any
   link or button marked data-cookie-choice (the privacy page has one) lets them change it.
   Consent is set to "denied" for everything first; Accept grants analytics only, never advertising. */
(() => {
  const GTM_ID = "{{GTM_ID}}";
  const KEY = "scout-cookie-choice"; // "yes" or "no"
  if (!GTM_ID) return;

  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  gtag("consent", "default", {
    ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied", analytics_storage: "denied",
  });

  const remembered = () => { try { return localStorage.getItem(KEY); } catch (err) { return null; } };
  const remember = (choice) => { try { localStorage.setItem(KEY, choice); } catch (err) { /* private browsing */ } };

  let loaded = false;
  function loadTagManager() {
    if (loaded) return;
    loaded = true;
    gtag("consent", "update", { analytics_storage: "granted" });
    window.dataLayer.push({ "gtm.start": new Date().getTime(), event: "gtm.js" });
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://www.googletagmanager.com/gtm.js?id=" + encodeURIComponent(GTM_ID);
    document.head.appendChild(script);
  }

  function forgetAnalyticsCookies() {
    const host = location.hostname;
    document.cookie.split(";").map((c) => c.split("=")[0].trim()).filter((name) => name.startsWith("_ga"))
      .forEach((name) => {
        for (const domain of ["", host, "." + host.replace(/^www\./, "")]) {
          document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/` + (domain ? `; domain=${domain}` : "");
        }
      });
  }

  let banner = null;
  function choose(choice) {
    remember(choice);
    if (choice === "yes") {
      loadTagManager();
    } else {
      if (loaded) gtag("consent", "update", { analytics_storage: "denied" });
      forgetAnalyticsCookies();
    }
    if (banner) banner.hidden = true;
  }

  function showBanner() {
    if (!banner) {
      const style = document.createElement("style");
      style.textContent = `
        .cookie-choice { position: fixed; z-index: 1000; left: 16px; right: 16px; bottom: 16px; max-width: 34rem; margin: 0 auto;
          background: #141414; color: #fff; border: 2px solid #fff; border-radius: 18px; padding: 16px 18px;
          box-shadow: 0 10px 30px rgb(0 0 0 / 0.3); font: 400 0.98rem/1.5 "Outfit", system-ui, sans-serif; }
        .cookie-choice[hidden] { display: none; }
        .cookie-choice p { margin: 0 0 12px; }
        .cookie-choice a { color: #ffd2c2; }
        .cookie-choice .choices { display: flex; flex-wrap: wrap; gap: 10px; }
        .cookie-choice button { flex: 1 1 8rem; min-height: 44px; padding: 8px 16px; border-radius: 999px; cursor: pointer;
          font: 700 0.98rem "Outfit", system-ui, sans-serif; background: #fff; color: #141414; border: 2px solid #fff; }
        .cookie-choice button:focus-visible { outline: 3px solid #ffd2c2; outline-offset: 3px; }`;
      document.head.appendChild(style);
      banner = document.createElement("section");
      banner.className = "cookie-choice";
      banner.setAttribute("aria-label", "Cookie choice");
      banner.innerHTML =
        '<p><strong>Can we count your visit?</strong> If you agree, Google Analytics sets cookies so we can see ' +
        'which pages people read. Nothing is used for advertising. <a href="/privacy#cookies">More about this</a></p>' +
        '<div class="choices"><button type="button" data-choice="yes">Accept</button>' +
        '<button type="button" data-choice="no">No thanks</button></div>';
      banner.addEventListener("click", (event) => {
        const button = event.target.closest("[data-choice]");
        if (button) choose(button.dataset.choice);
      });
      document.body.appendChild(banner);
    }
    banner.hidden = false;
  }

  function start() {
    const choice = remembered();
    if (choice === "yes") loadTagManager();
    else if (choice !== "no") showBanner();
    document.addEventListener("click", (event) => {
      if (event.target.closest("[data-cookie-choice]")) {
        event.preventDefault();
        showBanner();
        banner.querySelector("button").focus();
      }
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
