(() => {
  const campo = document.getElementById('busqueda-global');
  if (!campo) return;

  document.addEventListener('keydown', (evento) => {
    if ((evento.ctrlKey || evento.metaKey) && evento.key.toLowerCase() === 'k') {
      evento.preventDefault();
      campo.focus();
      campo.select();
    }
  });
})();
