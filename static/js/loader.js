(function () {
  var cache = {};

  function loadScript(src) {
    if (cache[src]) return cache[src];
    cache[src] = new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = src;
      s.onload = function () { resolve(); };
      s.onerror = function () {
        delete cache[src];
        reject(new Error('加载失败: ' + src));
      };
      document.head.appendChild(s);
    });
    return cache[src];
  }

  function loadModule(src) {
    return import(src);
  }

  function loadPdfJs() {
    var legacy = window.MRDetect && window.MRDetect.isLegacy;
    var base = '/static/vendor/pdfjs/';
    var lib = legacy ? base + 'pdf.legacy.min.mjs' : base + 'pdf.min.mjs';
    var worker = legacy ? base + 'pdf.worker.legacy.min.mjs' : base + 'pdf.worker.min.mjs';
    return loadModule(lib).then(function (pdfjs) {
      pdfjs.GlobalWorkerOptions.workerSrc = worker;
      return pdfjs;
    });
  }

  function loadPptxLib() {
    return loadScript('/static/vendor/pptx/jszip.min.js')
      .then(function () { return loadScript('/static/vendor/pptx/chart.umd.min.js'); })
      .catch(function () {})
      .then(function () { return loadScript('/static/vendor/pptx/PptxViewJS.min.js'); })
      .then(function () { return window.PptxViewJS; });
  }

  function loadFoliate() {
    return loadModule('/static/vendor/foliate-js/view.js');
  }

  window.MRLoad = {
    script: loadScript,
    module: loadModule,
    pdfjs: loadPdfJs,
    pptx: loadPptxLib,
    foliate: loadFoliate
  };
})();
