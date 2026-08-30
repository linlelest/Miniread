(function () {
  function supports() {
    if (!Array.prototype.at) return false;
    if (!Object.hasOwn) return false;
    if (typeof window.structuredClone !== 'function') return false;
    if (!(window.CSS && window.CSS.supports && window.CSS.supports('selector(:has(*))'))) return false;
    if (!window.Element || !Element.prototype.replaceChildren) return false;
    return true;
  }

  var isLegacy = !supports();

  try {
    if (isLegacy) {
      sessionStorage.setItem('mr-legacy', '1');
      if (window.location.pathname.indexOf('/old') !== 0) {
        window.location.replace('/old' + window.location.pathname + window.location.search);
      }
    } else {
      sessionStorage.setItem('mr-modern', '1');
    }
  } catch (e) {}

  window.MRDetect = { isLegacy: isLegacy };
})();
