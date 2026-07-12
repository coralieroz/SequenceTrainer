/**
 * charts.js — pure, dependency-free SVG charts for the Number-Sequence trainer.
 *
 * No fetch calls, no knowledge of the API, no external libraries or CDNs.
 * Exposes a single global: window.Charts = { contribution, line, donut }.
 *
 * Drop into any page via: <script src="charts.js"></script>
 */
(function () {
  'use strict';

  var SVG_NS = 'http://www.w3.org/2000/svg';
  var FONT = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
  var MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  // ---- generic helpers -----------------------------------------------

  function clear(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function svgEl(tag, attrs) {
    var node = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      for (var key in attrs) {
        if (Object.prototype.hasOwnProperty.call(attrs, key)) {
          node.setAttribute(key, attrs[key]);
        }
      }
    }
    return node;
  }

  function makeTitle(text) {
    var t = document.createElementNS(SVG_NS, 'title');
    t.textContent = text;
    return t;
  }

  function createSvg(width, height, viewBox) {
    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', viewBox || ('0 0 ' + width + ' ' + height));
    svg.setAttribute('width', '100%');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.setAttribute('style', 'width:100%; height:auto; display:block;');
    return svg;
  }

  function startOfDay(d) {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  function addDays(d, n) {
    var copy = new Date(d);
    copy.setDate(copy.getDate() + n);
    return copy;
  }

  function fmtDate(d) {
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  function formatMinutes(m) {
    return Number.isInteger(m) ? String(m) : m.toFixed(1);
  }

  function colorForMinutes(m) {
    if (!m || m <= 0) return '#ebedf0';
    if (m < 10) return '#c6e48b';
    if (m < 20) return '#7bc96f';
    if (m < 40) return '#239a3b';
    return '#196127';
  }

  // ---- Charts.contribution ---------------------------------------------

  function contribution(el, data) {
    if (!el) return;
    clear(el);

    var cellSize = 12, gap = 3, pitch = cellSize + gap;
    var cols = 26, rows = 7;
    var leftLabelW = 28, topLabelH = 14;
    var gridW = cols * pitch - gap;
    var gridH = rows * pitch - gap;
    var width = leftLabelW + gridW;
    var height = topLabelH + gridH;

    var map = new Map();
    (data || []).forEach(function (d) {
      if (d && d.date) map.set(d.date, d.minutes || 0);
    });

    var today = startOfDay(new Date());
    var dow = today.getDay(); // 0=Sun..6=Sat
    var mondayOffset = (dow + 6) % 7; // days since most-recent Monday
    var currentMonday = addDays(today, -mondayOffset);
    var startMonday = addDays(currentMonday, -25 * 7); // 26 weeks total incl. current

    var days = [];
    for (var i = 0; i < cols * rows; i++) {
      days.push(addDays(startMonday, i));
    }

    var svg = createSvg(width, height);

    // Row labels: Mon / Wed / Fri (rows 0, 2, 4 — Monday-top)
    var rowLabels = { 0: 'Mon', 2: 'Wed', 4: 'Fri' };
    Object.keys(rowLabels).forEach(function (rowStr) {
      var row = Number(rowStr);
      var text = svgEl('text', {
        x: leftLabelW - 4,
        y: topLabelH + row * pitch + cellSize - 2,
        'font-size': 9,
        fill: '#57606a',
        'text-anchor': 'end',
        'font-family': FONT
      });
      text.textContent = rowLabels[row];
      svg.appendChild(text);
    });

    // Month labels above the first column that starts a new month
    var lastMonth = -1;
    for (var col = 0; col < cols; col++) {
      var monday = days[col * rows];
      var month = monday.getMonth();
      if (month !== lastMonth) {
        lastMonth = month;
        var label = svgEl('text', {
          x: leftLabelW + col * pitch,
          y: topLabelH - 4,
          'font-size': 9,
          fill: '#57606a',
          'text-anchor': 'start',
          'font-family': FONT
        });
        label.textContent = MONTH_ABBR[month];
        svg.appendChild(label);
      }
    }

    // Day cells
    for (var idx = 0; idx < days.length; idx++) {
      var day = days[idx];
      var c = Math.floor(idx / rows);
      var r = idx % rows;
      var dateStr = fmtDate(day);
      var minutes = map.has(dateStr) ? map.get(dateStr) : 0;

      var rect = svgEl('rect', {
        x: leftLabelW + c * pitch,
        y: topLabelH + r * pitch,
        width: cellSize,
        height: cellSize,
        rx: 2,
        ry: 2,
        fill: colorForMinutes(minutes)
      });
      var titleText = minutes > 0
        ? (dateStr + ': ' + formatMinutes(minutes) + ' min')
        : (dateStr + ': no practice');
      rect.appendChild(makeTitle(titleText));
      svg.appendChild(rect);
    }

    el.appendChild(svg);
  }

  // ---- Charts.line -------------------------------------------------------

  function line(el, points) {
    if (!el) return;
    clear(el);

    var VB_W = 480, VB_H = 220;
    var padTop = 34, padRight = 12, padBottom = 24, padLeft = 40;
    var plotW = VB_W - padLeft - padRight;
    var plotH = VB_H - padTop - padBottom;

    var svg = createSvg(VB_W, VB_H, '0 0 ' + VB_W + ' ' + VB_H);

    points = points || [];

    if (points.length === 0) {
      var empty = svgEl('text', {
        x: VB_W / 2,
        y: VB_H / 2,
        'text-anchor': 'middle',
        'font-size': 14,
        fill: '#8c959f',
        'font-family': FONT
      });
      empty.textContent = 'No sessions yet';
      svg.appendChild(empty);
      el.appendChild(svg);
      return;
    }

    var scores = points.map(function (p) { return p.score; });
    var low = Math.min.apply(null, [0].concat(scores));
    var high = Math.max.apply(null, [1].concat(scores));
    var rawRange = high - low;
    var pad = rawRange * 0.1;
    low -= pad;
    high += pad;
    var range = high - low;

    function yScale(v) {
      return padTop + plotH - ((v - low) / range) * plotH;
    }
    function xScale(i) {
      if (points.length === 1) return padLeft + plotW / 2;
      return padLeft + (plotW * i) / (points.length - 1);
    }

    // 4 gridlines evenly spaced across the y-domain (incl. both ends)
    for (var g = 0; g < 4; g++) {
      var value = low + (range * g) / 3;
      var y = yScale(value);
      var gline = svgEl('line', {
        x1: padLeft, y1: y, x2: VB_W - padRight, y2: y,
        stroke: '#eaeef2', 'stroke-width': 1
      });
      svg.appendChild(gline);

      var glabel = svgEl('text', {
        x: padLeft - 6, y: y + 3,
        'text-anchor': 'end', 'font-size': 9, fill: '#57606a', 'font-family': FONT
      });
      glabel.textContent = value.toFixed(1);
      svg.appendChild(glabel);
    }

    if (points.length >= 2) {
      var pointsAttr = points.map(function (p, i) {
        return xScale(i) + ',' + yScale(p.score);
      }).join(' ');
      var poly = svgEl('polyline', {
        points: pointsAttr,
        fill: 'none',
        stroke: '#2da44e',
        'stroke-width': 2,
        'stroke-linejoin': 'round',
        'stroke-linecap': 'round'
      });
      svg.appendChild(poly);
    }

    points.forEach(function (p, i) {
      var cx = xScale(i), cy = yScale(p.score);
      var circle = svgEl('circle', { cx: cx, cy: cy, r: 3, fill: '#2da44e' });
      circle.appendChild(makeTitle(p.date + ': ' + p.score + '/min'));
      svg.appendChild(circle);
    });

    el.appendChild(svg);
  }

  // ---- Charts.donut --------------------------------------------------

  function donut(el, opts) {
    if (!el) return;
    clear(el);

    opts = opts || {};
    var VB = 120;
    var cx = 60, cy = 60, r = 48, sw = 12;
    var circumference = 2 * Math.PI * r;

    var svg = createSvg(VB, VB, '0 0 ' + VB + ' ' + VB);

    var track = svgEl('circle', {
      cx: cx, cy: cy, r: r, stroke: '#ebedf0', 'stroke-width': sw, fill: 'none'
    });
    svg.appendChild(track);

    var pct = opts.pct;
    var hasPct = pct !== null && pct !== undefined && !isNaN(pct);
    var centerText, centerColor;

    if (!hasPct) {
      centerColor = '#8c959f';
      centerText = '—'; // em dash
    } else {
      var clamped = Math.max(0, Math.min(1, pct));
      var arcColor;
      if (clamped > 0.85) arcColor = '#2da44e';
      else if (clamped >= 0.60) arcColor = '#d4a72c';
      else arcColor = '#cf222e';

      var arc = svgEl('circle', {
        cx: cx, cy: cy, r: r,
        stroke: arcColor,
        'stroke-width': sw,
        fill: 'none',
        'stroke-dasharray': (clamped * circumference) + ' ' + circumference,
        'stroke-linecap': 'round',
        transform: 'rotate(-90 ' + cx + ' ' + cy + ')'
      });
      svg.appendChild(arc);

      centerColor = '#1f2328';
      centerText = Math.round(clamped * 100) + '%';
    }

    var text = svgEl('text', {
      x: cx, y: cy + 6,
      'text-anchor': 'middle',
      'font-size': 20,
      'font-weight': 'bold',
      fill: centerColor,
      'font-family': FONT
    });
    text.textContent = centerText;
    svg.appendChild(text);

    el.appendChild(svg);
  }

  window.Charts = {
    contribution: contribution,
    line: line,
    donut: donut
  };
})();
