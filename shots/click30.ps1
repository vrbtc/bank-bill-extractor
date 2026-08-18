
$js = @'

(function() {
  const cells = document.querySelectorAll('.cal-cell');
  const idx = Array.from(cells).findIndex(c => (c.innerText||'').replace(/\s+/g,' ').trim() === '30 兴 5.43万');
  if (idx < 0) return JSON.stringify({err:'not found 30 cell'});
  const cell = cells[idx];
  ['mousedown','mouseup','click'].forEach(ev => cell.dispatchEvent(new MouseEvent(ev, {bubbles:true,cancelable:true,view:window})));
  return JSON.stringify({clicked:'30', idx, html: cell.outerHTML.substring(0, 300)});
})()

'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser --session bills eval -b $b64
