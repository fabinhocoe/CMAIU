// CMAIU – app.js

// ── Máscara: Inscrição Imobiliária XX.XX.XXX.XXXX ─────────────────────────────
function mascaraInscricao(input) {
  var d = input.value.replace(/\D/g, '').slice(0, 11);
  if (d.length > 7)      d = d.slice(0,2)+'.'+d.slice(2,4)+'.'+d.slice(4,7)+'.'+d.slice(7);
  else if (d.length > 4) d = d.slice(0,2)+'.'+d.slice(2,4)+'.'+d.slice(4);
  else if (d.length > 2) d = d.slice(0,2)+'.'+d.slice(2);
  input.value = d;
}
document.addEventListener('DOMContentLoaded', function () {
  // Sidebar toggle for mobile
  const btn = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  if (btn && sidebar) {
    btn.addEventListener('click', function () {
      sidebar.classList.toggle('show');
    });
  }

  // Auto-dismiss alerts after 5s
  document.querySelectorAll('.alert.alert-success').forEach(function (el) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      if (bsAlert) bsAlert.close();
    }, 5000);
  });
});
