
$js = @'

(function() {
  const body = document.getElementById('modalBody');
  const head = document.getElementById('modalTitle');
  const mask = document.querySelector('.modal-mask');
  const headText = head ? head.innerText : '';
  const bodyText = body ? (body.innerText || '').replace(/\s+/g,' ').trim() : '';
  const bodyHtml = body ? body.innerHTML : '';
  return JSON.stringify({headText, bodyText: bodyText.substring(0, 3000), bodyHtmlLen: bodyHtml.length}, null, 2);
})()

'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser --session bills eval -b $b64
