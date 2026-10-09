/* Grace & Bloom — procedural botanical artwork.
   Every flower, card, print and journal cover on the site is painted here, so there are no
   stock images to license. Output is a canvas (used for product tiles and as 3D textures). */
(function () {
  var GB = (window.GB = window.GB || {});

  var PALETTES = {
    blush:  { bg: ['#f7f1ee', '#ece1dd'], petals: ['#f7dedb', '#e8b5b3', '#cf8c91'], center: '#8f6a58', leaf: ['#b9c4b1', '#8a9a85'], ink: '#4a3f3d', accent: '#cf8c91' },
    lilac:  { bg: ['#f3f0f6', '#e4dded'], petals: ['#ece4f5', '#cdbde3', '#a88fcb'], center: '#7c6a98', leaf: ['#bcc6b4', '#8b9b87'], ink: '#46405a', accent: '#a88fcb' },
    peach:  { bg: ['#faf1ea', '#f1e0d4'], petals: ['#fde8dc', '#f4c2a8', '#e39b7c'], center: '#b98a52', leaf: ['#bfc9b0', '#8e9d80'], ink: '#5a4438', accent: '#e39b7c' },
    sage:   { bg: ['#f1f3ee', '#e0e6da'], petals: ['#fbfaf6', '#eceadf', '#d6d2bf'], center: '#c7a652', leaf: ['#a8b89e', '#7a8d73'], ink: '#3f4a3d', accent: '#7a8d73' },
    blue:   { bg: ['#eff2f5', '#dde5ec'], petals: ['#e8eef4', '#b9cadb', '#8aa4bf'], center: '#2f3b4a', leaf: ['#b4c1b2', '#84977f'], ink: '#33404f', accent: '#8aa4bf' },
    plum:   { bg: ['#efe9ec', '#dccfd5'], petals: ['#e9c9d3', '#b96f8c', '#7a3d5c'], center: '#4a2438', leaf: ['#9fae9a', '#6f8268'], ink: '#4a2c3c', accent: '#b96f8c' },
    butter: { bg: ['#faf6e9', '#efe8cd'], petals: ['#fff7d6', '#f5de93', '#e6bf5a'], center: '#a9772f', leaf: ['#bcc7a6', '#8c9c75'], ink: '#5a4a25', accent: '#e6bf5a' },
    frost:  { bg: ['#f1f3f4', '#dde2e4'], petals: ['#ffffff', '#eef1f2', '#cfd7da'], center: '#6f7d6a', leaf: ['#9fb09c', '#6b7f69'], ink: '#3a4647', accent: '#a64b55' },
    ink:    { bg: ['#4a4745', '#2f2d2c'], petals: ['#f4ddd9', '#dfaeaa', '#c4807f'], center: '#d9b97a', leaf: ['#93a38f', '#6c7d68'], ink: '#f3eeeb', accent: '#dfaeaa', dark: true },
    slate:  { bg: ['#d9dbdc', '#b9bdbf'], petals: ['#f7efe9', '#e2bfae', '#c58f7c'], center: '#4b4a49', leaf: ['#8d9c88', '#65745f'], ink: '#2f3233', accent: '#c58f7c' },
    gold:   { bg: ['#f3ebdc', '#e3d3b4'], petals: ['#fbeee8', '#eec3b8', '#d98f88'], center: '#8d6a2a', leaf: ['#a9b494', '#7b8a69'], ink: '#4a3a1f', accent: '#b98f3e' }
  };
  GB.palettes = PALETTES;

  /* ---------- helpers ---------- */
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function hex2rgb(h) { h = h.replace('#', ''); return [parseInt(h.substr(0, 2), 16), parseInt(h.substr(2, 2), 16), parseInt(h.substr(4, 2), 16)]; }
  function rgba(h, a) { var c = hex2rgb(h); return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a + ')'; }
  function mix(a, b, t) {
    var x = hex2rgb(a), y = hex2rgb(b);
    return 'rgb(' + Math.round(x[0] + (y[0] - x[0]) * t) + ',' + Math.round(x[1] + (y[1] - x[1]) * t) + ',' + Math.round(x[2] + (y[2] - x[2]) * t) + ')';
  }
  function rgbToHex(str) { var m = str.match(/\d+/g); return '#' + m.slice(0, 3).map(function (n) { return ('0' + (+n).toString(16)).slice(-2); }).join(''); }
  function mixHex(a, b, t) { return rgbToHex(mix(a, b, t)); }
  var R = function (rng, a, b) { return a + (b - a) * rng(); };

  /* ---------- petals, leaves, blooms ---------- */
  function petalPath(ctx, len, wid, tip, round) {
    tip = tip == null ? 0.95 : tip; round = round == null ? 1 : round;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.bezierCurveTo(-wid * 1.1, -len * 0.25, -wid * round, -len * tip, 0, -len);
    ctx.bezierCurveTo(wid * round, -len * tip, wid * 1.1, -len * 0.25, 0, 0);
    ctx.closePath();
  }
  function drawPetal(ctx, len, wid, c1, c2, o) {
    o = o || {};
    petalPath(ctx, len, wid, o.tip, o.round);
    var g = ctx.createLinearGradient(0, 0, 0, -len);
    g.addColorStop(0, c1); g.addColorStop(1, c2);
    ctx.fillStyle = g; ctx.fill();
    ctx.lineWidth = Math.max(0.6, len * 0.012);
    ctx.strokeStyle = rgba(mixHex(c1, '#000000', 0.25), 0.28); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, -len * 0.1); ctx.quadraticCurveTo(wid * 0.12, -len * 0.5, 0, -len * 0.84);
    ctx.strokeStyle = 'rgba(255,255,255,0.26)'; ctx.lineWidth = Math.max(0.6, len * 0.025); ctx.stroke();
  }
  function drawLeaf(ctx, x, y, len, ang, pal) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(ang);
    petalPath(ctx, len, len * 0.3, 0.8, 0.9);
    var g = ctx.createLinearGradient(0, 0, 0, -len);
    g.addColorStop(0, pal.leaf[1]); g.addColorStop(1, pal.leaf[0]);
    ctx.fillStyle = g; ctx.fill();
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.quadraticCurveTo(len * 0.04, -len * 0.5, 0, -len * 0.92);
    ctx.strokeStyle = rgba(pal.leaf[1], 0.8); ctx.lineWidth = Math.max(0.6, len * 0.018); ctx.stroke();
    ctx.restore();
  }

  function bloom(ctx, x, y, r, pal, rng, kind) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(R(rng, 0, Math.PI * 2));
    ctx.shadowColor = 'rgba(60,40,40,0.16)'; ctx.shadowBlur = r * 0.18; ctx.shadowOffsetY = r * 0.05;
    var P = pal.petals, i, n, t, l;

    if (kind === 'peony') {
      var L = 5;
      for (l = 0; l < L; l++) {
        t = l / (L - 1); n = 10 - l; var len = r * (1 - t * 0.64), off = R(rng, 0, 6.28);
        for (i = 0; i < n; i++) {
          ctx.save(); ctx.rotate(off + (i * Math.PI * 2) / n + R(rng, -0.08, 0.08));
          drawPetal(ctx, len * R(rng, 0.92, 1.05), len * 0.5, mixHex(P[1], P[2], t * 0.9), mixHex(P[0], P[1], t * 0.55), { tip: 0.9, round: 1.25 });
          ctx.restore();
        }
        ctx.shadowColor = 'transparent';
        var rg = ctx.createRadialGradient(0, 0, 0, 0, 0, len * 0.55);
        rg.addColorStop(0, rgba(P[2], 0.35)); rg.addColorStop(1, rgba(P[2], 0));
        ctx.fillStyle = rg; ctx.beginPath(); ctx.arc(0, 0, len * 0.55, 0, 6.28); ctx.fill();
      }
      ctx.fillStyle = rgba(pal.center, 0.5); ctx.beginPath(); ctx.arc(0, 0, r * 0.05, 0, 6.28); ctx.fill();
    } else if (kind === 'daisy') {
      n = 18;
      for (i = 0; i < n; i++) { ctx.save(); ctx.rotate((i * 6.2832) / n + R(rng, -0.05, 0.05)); drawPetal(ctx, r * R(rng, 0.92, 1.02), r * 0.13, P[1], P[0], { tip: 0.95, round: 0.9 }); ctx.restore(); }
      ctx.shadowColor = 'transparent';
      var dg = ctx.createRadialGradient(-r * 0.04, -r * 0.04, 0, 0, 0, r * 0.24);
      dg.addColorStop(0, mixHex(pal.center, '#ffffff', 0.35)); dg.addColorStop(1, pal.center);
      ctx.fillStyle = dg; ctx.beginPath(); ctx.arc(0, 0, r * 0.23, 0, 6.28); ctx.fill();
      for (i = 0; i < 40; i++) { var a = R(rng, 0, 6.28), d = R(rng, 0, r * 0.2); ctx.fillStyle = rgba(mixHex(pal.center, '#000', 0.35), 0.45); ctx.fillRect(Math.cos(a) * d, Math.sin(a) * d, r * 0.012, r * 0.012); }
    } else if (kind === 'anemone') {
      n = 7;
      for (i = 0; i < n; i++) { ctx.save(); ctx.rotate((i * 6.2832) / n + R(rng, -0.1, 0.1)); drawPetal(ctx, r * R(rng, 0.92, 1.0), r * 0.52, P[1], P[0], { tip: 0.85, round: 1.25 }); ctx.restore(); }
      ctx.shadowColor = 'transparent';
      for (i = 0; i < 70; i++) { var aa = R(rng, 0, 6.28), ll = r * R(rng, 0.14, 0.34); ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(Math.cos(aa) * ll, Math.sin(aa) * ll); ctx.strokeStyle = rgba(pal.center, 0.7); ctx.lineWidth = r * 0.012; ctx.stroke(); ctx.fillStyle = pal.center; ctx.beginPath(); ctx.arc(Math.cos(aa) * ll, Math.sin(aa) * ll, r * 0.017, 0, 6.28); ctx.fill(); }
      ctx.fillStyle = mixHex(pal.center, '#000', 0.2); ctx.beginPath(); ctx.arc(0, 0, r * 0.14, 0, 6.28); ctx.fill();
    } else if (kind === 'dahlia') {
      var rings = 8;
      for (l = 0; l < rings; l++) {
        t = l / (rings - 1); n = 16 - Math.floor(l * 1.1); var ln = r * (1 - t * 0.78), o2 = R(rng, 0, 6.28);
        for (i = 0; i < n; i++) { ctx.save(); ctx.rotate(o2 + (i * 6.2832) / n); drawPetal(ctx, ln, ln * 0.2, mixHex(P[2], P[1], t * 0.6), mixHex(P[1], P[0], t), { tip: 0.78, round: 0.7 }); ctx.restore(); }
        ctx.shadowColor = 'transparent';
      }
      ctx.fillStyle = rgba(pal.center, 0.6); ctx.beginPath(); ctx.arc(0, 0, r * 0.05, 0, 6.28); ctx.fill();
    } else { /* sweetpea */
      for (i = 0; i < 5; i++) { ctx.save(); ctx.rotate((i * 6.2832) / 5 + R(rng, -0.1, 0.1)); drawPetal(ctx, r * R(rng, 0.85, 1), r * 0.62, P[1], P[0], { tip: 1.0, round: 1.7 }); ctx.restore(); }
      ctx.shadowColor = 'transparent';
      for (i = 0; i < 3; i++) { ctx.save(); ctx.rotate((i * 6.2832) / 3 + 0.4); drawPetal(ctx, r * 0.55, r * 0.34, P[2], P[1], { tip: 1.0, round: 1.6 }); ctx.restore(); }
      ctx.fillStyle = rgba(pal.center, 0.55); ctx.beginPath(); ctx.arc(0, 0, r * 0.06, 0, 6.28); ctx.fill();
    }
    ctx.restore();
  }

  function stem(ctx, x0, y0, x1, y1, pal, w) {
    var cx = (x0 + x1) / 2 + (x1 - x0) * 0.25 + (y0 - y1) * 0.08, cy = (y0 + y1) / 2;
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.quadraticCurveTo(cx, cy, x1, y1);
    ctx.strokeStyle = pal.leaf[1]; ctx.lineWidth = w; ctx.lineCap = 'round'; ctx.stroke();
    return { x0: x0, y0: y0, cx: cx, cy: cy, x1: x1, y1: y1 };
  }
  function pointOn(s, t) {
    var u = 1 - t;
    return { x: u * u * s.x0 + 2 * u * t * s.cx + t * t * s.x1, y: u * u * s.y0 + 2 * u * t * s.cy + t * t * s.y1 };
  }

  /* A fanned bouquet rising from (bx,by). */
  function bouquet(ctx, w, h, pal, rng, o) {
    var bx = o.bx, by = o.by, kind = o.kind, S = o.scale;
    var spots = o.spots || [
      { x: 0.26, y: 0.64, r: 0.15 }, { x: 0.76, y: 0.67, r: 0.14 },
      { x: 0.5, y: 0.56, r: 0.25 },
      { x: 0.4, y: 0.8, r: 0.1 }, { x: 0.64, y: 0.82, r: 0.095 }
    ];
    var stems = spots.map(function (s) { return stem(ctx, bx, by, s.x * w, s.y * h, pal, w * 0.007 * S); });
    stems.forEach(function (s) {
      for (var i = 0; i < 3; i++) {
        var p = pointOn(s, R(rng, 0.45, 0.85));
        drawLeaf(ctx, p.x, p.y, w * R(rng, 0.1, 0.17) * S, R(rng, -1.4, 1.4) + (rng() > 0.5 ? 0.3 : -0.3), pal);
      }
    });
    for (var j = 0; j < 7; j++) {
      var a = R(rng, -0.9, 0.9);
      drawLeaf(ctx, bx + R(rng, -w * 0.05, w * 0.05), by, w * R(rng, 0.22, 0.34) * S, a, pal);
    }
    var order = spots.map(function (s, i) { return i; }).sort(function (a, b) { return spots[a].r - spots[b].r; });
    order.forEach(function (i, k) {
      var s = spots[i], kk = (k === order.length - 1) ? kind : (rng() > 0.55 ? 'daisy' : kind);
      bloom(ctx, s.x * w, s.y * h, s.r * w * S, pal, rng, kk);
    });
    if (o.berries) {
      for (var b = 0; b < 26; b++) {
        var sp = stems[Math.floor(rng() * stems.length)], pp = pointOn(sp, R(rng, 0.4, 0.95));
        var bx2 = pp.x + R(rng, -w * 0.07, w * 0.07), by2 = pp.y + R(rng, -w * 0.05, w * 0.07), br = w * R(rng, 0.011, 0.017);
        var bg = ctx.createRadialGradient(bx2 - br * 0.3, by2 - br * 0.3, 0, bx2, by2, br);
        bg.addColorStop(0, '#d9707a'); bg.addColorStop(1, '#8f2f3b');
        ctx.fillStyle = bg; ctx.beginPath(); ctx.arc(bx2, by2, br, 0, 6.28); ctx.fill();
      }
    }
  }

  /* ---------- paper, text ---------- */
  function paper(ctx, w, h, colors, rng) {
    var g = ctx.createLinearGradient(0, 0, w * 0.4, h);
    g.addColorStop(0, colors[0]); g.addColorStop(1, colors[1]);
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  }
  function grain(ctx, w, h, rng, dark) {
    for (var i = 0; i < 5200; i++) {
      ctx.fillStyle = rng() > 0.5 ? 'rgba(0,0,0,0.028)' : 'rgba(255,255,255,' + (dark ? 0.03 : 0.07) + ')';
      ctx.fillRect(rng() * w, rng() * h, 1.4, 1.4);
    }
    var v = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.45, w / 2, h / 2, Math.max(w, h) * 0.8);
    v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(60,45,40,' + (dark ? 0.35 : 0.1) + ')');
    ctx.fillStyle = v; ctx.fillRect(0, 0, w, h);
  }
  var SERIF = '"Cormorant Garamond", "Cormorant", Georgia, "Times New Roman", serif';
  var SANS = '"Jost", "Helvetica Neue", Arial, sans-serif';
  function text(ctx, str, x, y, size, color, o) {
    o = o || {};
    ctx.save();
    ctx.font = (o.style || 'italic 500') + ' ' + size + 'px ' + (o.sans ? SANS : SERIF);
    ctx.fillStyle = color; ctx.textAlign = o.align || 'center'; ctx.textBaseline = 'alphabetic';
    if ('letterSpacing' in ctx && o.spacing) ctx.letterSpacing = o.spacing + 'px';
    ctx.fillText(str, x, y);
    ctx.restore();
  }

  /* ---------- layouts ---------- */
  var LAYOUTS = {
    bouquet: function (ctx, w, h, pal, rng, a) {
      paper(ctx, w, h, pal.bg, rng);
      var lines = a.text || [];
      lines.forEach(function (t, i) { text(ctx, t, w / 2, h * 0.14 + i * w * 0.115, w * (i === 0 ? 0.13 : 0.145), pal.ink, { style: i === 0 ? 'italic 500' : 'italic 600' }); });
      bouquet(ctx, w, h, pal, rng, { bx: w * 0.5, by: h * 1.03, kind: a.bloom, scale: 1, berries: a.berries });
      ctx.strokeStyle = rgba(pal.ink, 0.18); ctx.lineWidth = 2; ctx.strokeRect(w * 0.04, w * 0.04, w * 0.92, h - w * 0.08);
    },
    single: function (ctx, w, h, pal, rng, a) {
      ctx.fillStyle = '#fbfaf8'; ctx.fillRect(0, 0, w, h);
      var m = w * 0.09, x = m, y = m, iw = w - 2 * m, ih = h - 2 * m - h * 0.09;
      ctx.save(); ctx.beginPath(); ctx.rect(x, y, iw, ih); ctx.clip();
      paper(ctx, iw + x, ih + y, pal.bg, rng);
      ctx.translate(0, 0);
      bouquet(ctx, w, h * 0.9, pal, rng, {
        bx: w * 0.5, by: y + ih + 40, kind: a.bloom, scale: 1.1,
        spots: [{ x: 0.5, y: 0.4, r: 0.27 }, { x: 0.27, y: 0.6, r: 0.11 }, { x: 0.74, y: 0.62, r: 0.1 }]
      });
      ctx.restore();
      ctx.strokeStyle = 'rgba(0,0,0,0.12)'; ctx.lineWidth = 2; ctx.strokeRect(x, y, iw, ih);
      var cap = (a.text || []).join(' ');
      text(ctx, cap.toUpperCase(), w / 2, h - m * 1.15, w * 0.036, '#6c6560', { sans: true, style: '500', spacing: w * 0.012 });
    },
    cover: function (ctx, w, h, pal, rng, a) {
      paper(ctx, w, h, pal.bg, rng);
      ctx.save();
      bouquet(ctx, w, h, pal, rng, {
        bx: w * 1.02, by: h * 0.5, kind: a.bloom, scale: 1.0,
        spots: [{ x: 0.78, y: 0.2, r: 0.21 }, { x: 0.52, y: 0.32, r: 0.12 }, { x: 0.92, y: 0.42, r: 0.12 }, { x: 0.62, y: 0.12, r: 0.08 }]
      });
      ctx.restore();
      var l = a.text || [], x0 = w * 0.1;
      ctx.strokeStyle = rgba(pal.ink, 0.35); ctx.lineWidth = 2; ctx.strokeRect(w * 0.05, w * 0.05, w * 0.9, h - w * 0.1);
      l.forEach(function (t, i) { text(ctx, t, x0, h * 0.7 + i * w * 0.14, w * 0.145, pal.ink, { align: 'left', style: 'italic 500' }); });
      ctx.fillStyle = pal.accent; ctx.fillRect(x0, h * 0.7 + l.length * w * 0.14 - w * 0.04, w * 0.1, 3);
      if (a.sub) text(ctx, a.sub.toUpperCase(), x0, h * 0.7 + l.length * w * 0.14 + w * 0.045, w * 0.028, rgba(pal.ink, 0.85), { align: 'left', sans: true, style: '500', spacing: w * 0.007 });
      text(ctx, 'GRACE & BLOOM', w / 2, h - w * 0.085, w * 0.022, rgba(pal.ink, 0.6), { sans: true, style: '500', spacing: w * 0.008 });
    },
    pad: function (ctx, w, h, pal, rng, a) {
      paper(ctx, w, h, ['#fbfaf8', '#f0eeeb'], rng);
      ctx.fillStyle = pal.bg[1]; ctx.fillRect(0, 0, w, h * 0.055);
      ctx.strokeStyle = 'rgba(0,0,0,0.09)'; ctx.lineWidth = 1.5;
      for (var y = h * 0.4; y < h * 0.93; y += h * 0.045) { ctx.beginPath(); ctx.moveTo(w * 0.1, y); ctx.lineTo(w * 0.9, y); ctx.stroke(); }
      bouquet(ctx, w, h, pal, rng, {
        bx: w * 0.05, by: h * 0.32, kind: a.bloom, scale: 0.9,
        spots: [{ x: 0.82, y: 0.15, r: 0.15 }, { x: 0.62, y: 0.2, r: 0.09 }, { x: 0.93, y: 0.27, r: 0.08 }]
      });
      (a.text || []).forEach(function (t, i) { text(ctx, t, w * 0.1, h * 0.17 + i * w * 0.13, w * 0.13, pal.ink, { align: 'left' }); });
    },
    calendar: function (ctx, w, h, pal, rng, a) {
      ctx.fillStyle = '#fbfaf8'; ctx.fillRect(0, 0, w, h);
      var ph = h * 0.56;
      ctx.save(); ctx.beginPath(); ctx.rect(0, 0, w, ph); ctx.clip();
      paper(ctx, w, ph, pal.bg, rng);
      bouquet(ctx, w, ph, pal, rng, {
        bx: w * 0.5, by: ph * 1.06, kind: a.bloom, scale: 0.95,
        spots: [{ x: 0.5, y: 0.5, r: 0.24 }, { x: 0.22, y: 0.62, r: 0.12 }, { x: 0.8, y: 0.6, r: 0.13 }, { x: 0.35, y: 0.3, r: 0.07 }]
      });
      ctx.restore();
      var month = a.month || 0, year = a.year || 2027;
      var names = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'];
      text(ctx, names[month] + ' ' + year, w / 2, ph + h * 0.065, w * 0.05, '#4a4543', { sans: true, style: '500', spacing: w * 0.012 });
      var days = ['M', 'T', 'W', 'T', 'F', 'S', 'S'], gx = w * 0.08, gw = w * 0.84, cw = gw / 7;
      days.forEach(function (d, i) { text(ctx, d, gx + cw * (i + 0.5), ph + h * 0.115, w * 0.026, '#8a837e', { sans: true, style: '500' }); });
      var first = (new Date(year, month, 1).getDay() + 6) % 7, dim = new Date(year, month + 1, 0).getDate(), top = ph + h * 0.135, rh = (h - top - h * 0.04) / 6;
      ctx.strokeStyle = 'rgba(0,0,0,0.1)'; ctx.lineWidth = 1;
      for (var r = 0; r <= 6; r++) { ctx.beginPath(); ctx.moveTo(gx, top + r * rh); ctx.lineTo(gx + gw, top + r * rh); ctx.stroke(); }
      for (var d = 1; d <= dim; d++) { var idx = first + d - 1; text(ctx, String(d), gx + cw * (idx % 7) + cw * 0.12, top + Math.floor(idx / 7) * rh + rh * 0.38, w * 0.027, '#5d5754', { align: 'left', sans: true, style: '400' }); }
    },
    bookmark: function (ctx, w, h, pal, rng, a) {
      paper(ctx, w, h, pal.bg, rng);
      bouquet(ctx, w, h, pal, rng, {
        bx: w * 0.5, by: h * 1.02, kind: a.bloom, scale: 0.6,
        spots: [{ x: 0.5, y: 0.42, r: 0.3 }, { x: 0.32, y: 0.64, r: 0.16 }, { x: 0.7, y: 0.74, r: 0.15 }, { x: 0.5, y: 0.88, r: 0.12 }]
      });
      ctx.strokeStyle = rgba(pal.ink, 0.25); ctx.lineWidth = 2; ctx.strokeRect(w * 0.08, w * 0.08, w * 0.84, h - w * 0.16);
      ctx.fillStyle = 'rgba(0,0,0,0.12)'; ctx.beginPath(); ctx.arc(w / 2, h * 0.035, w * 0.045, 0, 6.28); ctx.fill();
    }
  };

  /* ---------- public API ---------- */
  var cache = {};
  GB.art = {
    SERIF: SERIF, SANS: SANS,
    make: function (p, scale) {
      scale = scale || 1;
      var key = p.id + '@' + scale;
      if (cache[key]) return cache[key];
      var a = p.art, pal = PALETTES[a.palette] || PALETTES.blush;
      var bw = p.kind === 'bookmark' ? 320 : 640, bh = p.kind === 'bookmark' ? 860 : 800;
      var cv = document.createElement('canvas');
      cv.width = Math.round(bw * scale); cv.height = Math.round(bh * scale);
      var ctx = cv.getContext('2d');
      ctx.scale(scale, scale);
      var rng = mulberry32(hash(p.id));
      LAYOUTS[a.layout](ctx, bw, bh, pal, rng, a);
      grain(ctx, bw, bh, rng, !!pal.dark);
      cache[key] = cv;
      return cv;
    },
    /* Blank inside-of-card paper with a handwritten note, for the 3D hero. */
    inside: function (note, small) {
      var cv = document.createElement('canvas'); cv.width = 640; cv.height = 800;
      var ctx = cv.getContext('2d'), rng = mulberry32(7);
      paper(ctx, 640, 800, ['#fdfcfa', '#f3f0ec'], rng);
      if (note) {
        note.forEach(function (t, i) { text(ctx, t, 320, 320 + i * 100, i === 0 ? 92 : 70, '#5a4f4b', { style: 'italic 500' }); });
        text(ctx, 'with love, always', 320, 560, 44, '#8a7d78', { style: 'italic 400' });
      }
      if (small) bouquet(ctx, 640, 800, PALETTES.blush, rng, { bx: 320, by: 830, kind: 'daisy', scale: 0.55, spots: [{ x: 0.5, y: 0.82, r: 0.09 }, { x: 0.3, y: 0.9, r: 0.06 }, { x: 0.7, y: 0.9, r: 0.06 }] });
      grain(ctx, 640, 800, rng, false);
      return cv;
    },
    pal: PALETTES
  };
})();
