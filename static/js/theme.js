(function () {
  var KEY = 'mr-theme';
  var mql = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function systemTheme() {
    return mql && mql.matches ? 'dark' : 'light';
  }

  function apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
  }

  function stored() {
    try {
      return localStorage.getItem(KEY);
    } catch (e) {
      return null;
    }
  }

  function resolve() {
    var s = stored();
    return s === 'light' || s === 'dark' ? s : systemTheme();
  }

  function get() {
    var s = stored();
    return s === 'light' || s === 'dark' ? s : 'auto';
  }

  function set(theme) {
    try {
      localStorage.setItem(KEY, theme);
    } catch (e) {}
    apply(resolve());
  }

  function followSystem() {
    try {
      localStorage.removeItem(KEY);
    } catch (e) {}
    apply(systemTheme());
  }

  function toggle() {
    set(resolve() === 'dark' ? 'light' : 'dark');
  }

  function onSystemChange() {
    if (!stored()) apply(systemTheme());
  }

  if (mql) {
    if (mql.addEventListener) mql.addEventListener('change', onSystemChange);
    else if (mql.addListener) mql.addListener(onSystemChange);
  }

  apply(resolve());

  window.MRTheme = {
    get: get,
    set: set,
    toggle: toggle,
    followSystem: followSystem,
    resolve: resolve
  };
})();
