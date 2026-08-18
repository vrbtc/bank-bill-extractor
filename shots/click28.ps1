
$js = @'

(function() {
  // 找 8/28 格子：通用策略 - 搜索显示 "28" 且包含 "2.8k" 或 "车贷" 或 日期 data-date=2026-08-28 的格子
  function findDayCell(month, day, substr) {
    const all = document.querySelectorAll('[data-date], .cal-day, .day-cell, [role="gridcell"], td, div[class*="day"], div[class*="cell"]');
    for (const el of all) {
      const d = el.getAttribute && el.getAttribute('data-date');
      if (d) {
        const m = d.match(/(\d{4})-(\d{2})-(\d{2})/);
        if (m && Number(m[2]) === month && Number(m[3]) === day) return el;
      }
      const txt = el.innerText || '';
      if (substr && txt.includes(substr)) {
        // 同时要求包含 day 数字且在当前月份容器内
        const parent = el.closest && (el.closest('.calendar') || el.closest('[id*=cal]') || document.body);
        if (txt.includes(String(day))) return el;
      }
    }
    return null;
  }
  // 找 8/28：点击 显示 "28" 且附近 "2.8k" 的格子
  let cell = null;
  const candidates = document.querySelectorAll('*');
  for (const c of candidates) {
    if (c.children && c.children.length > 0) continue;
    const t = (c.textContent || '').trim();
    if (t === '282.8k' || t === '28 2.8k' || t === '28¥2,833.33' || /28[^0-9]*(2\.8k|2833|车)/.test(t)) {
      cell = c.closest('[role=gridcell], td, [class*=day], [class*=cell]') || c;
      break;
    }
  }
  if (!cell) {
    // 找 calTitle 所在容器，然后遍历其中文本包含 28 且样式为日历格子的元素
    const calRoot = document.querySelector('.calendar, #calendar, [class*=cal-view]') || document.body;
    const gridcells = calRoot.querySelectorAll('[role=gridcell], td');
    for (const gc of gridcells) {
      const txt = gc.innerText || '';
      if (/^\s*28[\s\S]*(2\.8k|2833)/m.test(txt) || txt.includes('2.8k')) {
        cell = gc; break;
      }
    }
  }
  if (!cell) return JSON.stringify({err: 'no 8/28 cell found'});
  cell.click();
  return JSON.stringify({clicked: '8/28', text: (cell.innerText||'').replace(/\s+/g,' ').trim()});
})()

'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser --session bills eval -b $b64
