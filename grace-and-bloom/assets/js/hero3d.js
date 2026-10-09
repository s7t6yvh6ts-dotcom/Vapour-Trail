/* Grace & Bloom — 3D hero (Three.js).
   A greeting card that opens, a floating journal and print, drifting petals.
   Falls back gracefully to a static layout if WebGL is unavailable. */
(function () {
  var GB = window.GB, THREE = window.THREE;
  var canvas = document.getElementById('hero-canvas');
  var stage = document.getElementById('hero-stage');
  if (!canvas || !THREE || !GB || !GB.art) { if (stage) stage.classList.add('no-webgl'); return; }

  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  } catch (e) { stage.classList.add('no-webgl'); return; }

  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(30, 1, 0.1, 60);
  scene.add(new THREE.HemisphereLight(0xffffff, 0xcfc6c2, 0.5));
  var key = new THREE.DirectionalLight(0xfff3ec, 0.55); key.position.set(3, 5, 6); scene.add(key);
  var rim = new THREE.DirectionalLight(0xdfe6ee, 0.25); rim.position.set(-5, 2, -3); scene.add(rim);

  function tex(cv) {
    var t = new THREE.CanvasTexture(cv);
    t.encoding = THREE.sRGBEncoding;
    t.anisotropy = renderer.capabilities.getMaxAnisotropy();
    t.needsUpdate = true;
    return t;
  }
  function mat(color, opts) { return new THREE.MeshStandardMaterial(Object.assign({ color: color, roughness: 0.82, metalness: 0 }, opts || {})); }
  function texMat(cv) { return new THREE.MeshStandardMaterial({ map: tex(cv), roughness: 0.78, metalness: 0 }); }

  var world = new THREE.Group(); scene.add(world);

  /* ---------- greeting card ---------- */
  var CW = 1.7, CH = 2.3, CT = 0.03;
  var card = new THREE.Group(); world.add(card);
  var paper = mat(0xf7f4f0);
  var backMats = [paper, paper, paper, paper, texMat(GB.art.inside(['Happy', 'Birthday'], false)), mat(0xe9e5e0)];
  var back = new THREE.Mesh(new THREE.BoxGeometry(CW, CH, CT), backMats);
  card.add(back);

  var hinge = new THREE.Group(); hinge.position.set(-CW / 2, 0, CT);
  card.add(hinge);
  var coverGeo = new THREE.BoxGeometry(CW, CH, CT); coverGeo.translate(CW / 2, 0, 0);
  var cover = new THREE.Mesh(coverGeo, [paper, paper, paper, paper, texMat(GB.art.make(GB.byId('peony-birthday'), 1.3)), texMat(GB.art.inside(null, true))]);
  hinge.add(cover);

  /* ---------- journal ---------- */
  var JW = 1.25, JH = 1.7, JT = 0.26;
  var focus = GB.byId('focus-planner');
  var pages = mat(0xf2ede7);
  var journal = new THREE.Mesh(new THREE.BoxGeometry(JW, JH, JT), [pages, mat(0x3a3836), pages, pages, texMat(GB.art.make(focus, 1.3)), mat(0x3a3836)]);
  var jg = new THREE.Group(); jg.add(journal);
  var band = new THREE.Mesh(new THREE.BoxGeometry(0.035, JH + 0.004, JT + 0.01), mat(0xdfaeaa)); band.position.set(JW * 0.34, 0, 0); jg.add(band);
  jg.position.set(-2.9, -0.15, -1.6); jg.rotation.set(-0.06, 0.55, 0.02);
  world.add(jg);

  /* ---------- framed print ---------- */
  var PW = 1.15, PH = 1.5;
  var print = GB.byId('dusk-dahlia');
  var frameMat = mat(0xefece8);
  var pr = new THREE.Mesh(new THREE.BoxGeometry(PW, PH, 0.08), [frameMat, frameMat, frameMat, frameMat, texMat(GB.art.make(print, 1.3)), frameMat]);
  var pg = new THREE.Group(); pg.add(pr);
  pg.position.set(2.9, 0.2, -1.6); pg.rotation.set(0.03, -0.5, -0.02);
  world.add(pg);

  /* ---------- soft ground shadow ---------- */
  var sh = document.createElement('canvas'); sh.width = sh.height = 128;
  var sctx = sh.getContext('2d'), grd = sctx.createRadialGradient(64, 64, 4, 64, 64, 62);
  grd.addColorStop(0, 'rgba(60,50,48,0.42)'); grd.addColorStop(1, 'rgba(60,50,48,0)');
  sctx.fillStyle = grd; sctx.fillRect(0, 0, 128, 128);
  var shadow = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sh), transparent: true, depthWrite: false }));
  shadow.rotation.x = -Math.PI / 2; shadow.position.y = -1.75; shadow.scale.set(5.2, 2.2, 1);
  world.add(shadow);

  /* ---------- drifting petals ---------- */
  var petalShape = new THREE.Shape();
  petalShape.moveTo(0, 0);
  petalShape.bezierCurveTo(-0.55, 0.25, -0.45, 0.95, 0, 1.15);
  petalShape.bezierCurveTo(0.45, 0.95, 0.55, 0.25, 0, 0);
  var petalGeo = new THREE.ShapeGeometry(petalShape, 10);
  petalGeo.translate(0, -0.55, 0);
  // gentle curl
  var pos = petalGeo.attributes.position;
  for (var i = 0; i < pos.count; i++) pos.setZ(i, Math.abs(pos.getX(i)) * 0.35);
  petalGeo.computeVertexNormals();
  var petalColors = [0xf2c9c6, 0xe9b3b3, 0xf7dedb, 0xd9a1a6, 0xe8d7e8, 0xdfe5d9];
  var petals = [];
  var PN = reduce ? 14 : 34;
  for (i = 0; i < PN; i++) {
    var m = new THREE.Mesh(petalGeo, new THREE.MeshStandardMaterial({ color: petalColors[i % petalColors.length], side: THREE.DoubleSide, roughness: 0.7 }));
    var s = 0.14 + Math.random() * 0.16; m.scale.setScalar(s);
    var d = { m: m, x: (Math.random() - 0.5) * 8, y: -3 + Math.random() * 7, z: -2.2 + Math.random() * 5.2, vy: 0.12 + Math.random() * 0.25, sw: 0.3 + Math.random() * 0.8, ph: Math.random() * 6.28, r: [Math.random() * 6, Math.random() * 6, Math.random() * 6], sp: 0.4 + Math.random() * 1.2 };
    petals.push(d); world.add(m);
  }

  /* ---------- state ---------- */
  var open = 0, openTarget = reduce ? 1 : 0, mx = 0, my = 0, tx = 0, ty = 0, visible = true, clock = new THREE.Clock(), started = performance.now();
  function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }

  function layout() {
    var w = stage.clientWidth, h = stage.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    var a = camera.aspect;
    camera.position.set(0, 0.25, a < 0.75 ? 15 : a < 1.3 ? 13 : 10.5);
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
    var narrow = a < 0.9;
    jg.visible = pg.visible = true;
    jg.position.x = narrow ? -2.5 : -2.9; pg.position.x = narrow ? 2.5 : 2.9;
  }
  window.addEventListener('resize', layout); layout();

  stage.addEventListener('pointermove', function (e) {
    var r = stage.getBoundingClientRect();
    mx = ((e.clientX - r.left) / r.width - 0.5) * 2; my = ((e.clientY - r.top) / r.height - 0.5) * 2;
  });
  stage.addEventListener('pointerleave', function () { mx = my = 0; });
  var btn = document.getElementById('toggle-card');
  function toggle() { openTarget = openTarget ? 0 : 1; if (btn) { btn.setAttribute('aria-pressed', String(!!openTarget)); btn.querySelector('span').textContent = openTarget ? 'Close the card' : 'Open the card'; } }
  canvas.addEventListener('click', toggle);
  if (btn) btn.addEventListener('click', toggle);

  if ('IntersectionObserver' in window) new IntersectionObserver(function (en) { visible = en[0].isIntersecting; }, { threshold: 0.01 }).observe(stage);

  function frame() {
    requestAnimationFrame(frame);
    if (!visible || document.hidden) return;
    var dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;

    if (!reduce && !started.done && performance.now() - started > 1100) { started = { done: true }; toggle(); }
    open += (openTarget - open) * Math.min(1, dt * 3.2);
    var e = ease(Math.max(0, Math.min(1, open)));

    hinge.rotation.y = -e * 2.3;
    card.position.x = e * (CW / 2) * 0.8;
    card.rotation.x = -0.1 * e;

    tx += (mx - tx) * 0.06; ty += (my - ty) * 0.06;
    world.rotation.y = tx * 0.28 + Math.sin(t * 0.4) * 0.05;
    world.rotation.x = ty * 0.1;
    var bob = reduce ? 0 : Math.sin(t * 0.9);
    card.position.y = bob * 0.06;
    jg.position.y = -0.15 + Math.sin(t * 0.8 + 1) * 0.08; jg.rotation.y = 0.55 + Math.sin(t * 0.5) * 0.06;
    pg.position.y = 0.2 + Math.sin(t * 0.7 + 2) * 0.08; pg.rotation.y = -0.5 + Math.sin(t * 0.55 + 1) * 0.06;
    shadow.scale.set(5.2 - bob * 0.2, 2.2 - bob * 0.1, 1);
    shadow.material.opacity = 0.9 - bob * 0.08;

    if (!reduce) petals.forEach(function (p) {
      p.y -= p.vy * dt;
      if (p.y < -3.2) { p.y = 3.4; p.x = (Math.random() - 0.5) * 8; }
      p.m.position.set(p.x + Math.sin(t * p.sw + p.ph) * 0.5, p.y, p.z);
      p.m.rotation.set(p.r[0] + t * p.sp, p.r[1] + t * p.sp * 0.7, p.r[2] + t * p.sp * 0.4);
    });
    else petals.forEach(function (p) { p.m.position.set(p.x, p.y, p.z); p.m.rotation.set(p.r[0], p.r[1], p.r[2]); });

    renderer.render(scene, camera);
  }
  stage.classList.add('webgl-ready');
  frame();
})();
