
$js = @'
(function() { const c = document.getElementById('modalClose'); if (c) c.click(); else { const m = document.querySelector('.modal-mask'); if (m) m.style.display='none'; } return 'closed'; })()
'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser --session bills eval -b $b64
