
$js = @'

(function() {
  const cells = document.querySelectorAll('.cal-cell');
  const list = [];
  for (const c of cells) {
    const d = c.getAttribute('data-date') || '';
    const t = (c.innerText || '').replace(/\s+/g,' ').trim();
    list.push({date: d, text: t.substring(0, 80)});
  }
  // 查看是否有全局 openDayDetail / showModal 之类
  const globalFns = Object.keys(window || {}).filter(k => /open|day|detail|modal|show/i.test(k) && typeof window[k] === 'function').slice(0, 20);
  return JSON.stringify({cells: list.slice(0, 45), globalFns}, null, 2);
})()

'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser --session bills eval -b $b64
