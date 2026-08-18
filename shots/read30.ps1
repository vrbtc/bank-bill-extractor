
$js = @'

(function() {
  const body = document.getElementById('modalBody');
  const head = document.getElementById('modalTitle');
  return JSON.stringify({head: head ? head.innerText : '', body: body ? (body.innerText||'').replace(/\s+/g,' ').trim().substring(0,3000) : ''}, null, 2);
})()

'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser --session bills eval -b $b64
