
$js = @'

(function() {
  const cells = document.querySelectorAll('.cal-cell');
  const idx28 = Array.from(cells).findIndex(c => (c.innerText||'').replace(/\s+/g,' ').trim() === '28 2.8k');
  if (idx28 < 0) return JSON.stringify({err:'not found 28 2.8k'});
  const cell = cells[idx28];
  // 触发一系列鼠标事件
  ['mousedown','mouseup','click'].forEach(ev => {
    cell.dispatchEvent(new MouseEvent(ev, {bubbles: true, cancelable: true, view: window}));
  });
  return JSON.stringify({clicked: '28 2.8k', idx: idx28, class: cell.className, html: cell.outerHTML.substring(0, 300)});
})()

'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser --session bills eval -b $b64
