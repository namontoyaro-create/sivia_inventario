(() => {
  const campos = ['codigo', 'producto', 'categoria', 'categoria_ia', 'presentacion', 'stock_registrado'];
  const destino = { codigo: 'vista-codigo', producto: 'vista-producto', categoria: 'vista-categoria', categoria_ia: 'vista-clase', presentacion: 'vista-presentacion' };
  const stock = document.querySelector('#stock_registrado');
  function actualizar() {
    campos.forEach((campo) => { const origen = document.querySelector(`#${campo}`); const vista = document.querySelector(`#${destino[campo]}`); if (origen && vista) vista.textContent = origen.value || (campo === 'categoria_ia' ? 'Sin seleccionar' : '—'); });
    const cantidad = Number(stock?.value || 0); const estado = document.querySelector('#vista-estado');
    document.querySelector('#vista-stock').textContent = `${cantidad} unidades`;
    estado.textContent = cantidad < 10 ? 'Stock bajo' : 'Stock normal';
    estado.className = `badge ${cantidad < 10 ? 'bajo' : 'normal'}`;
  }
  campos.forEach((campo) => document.querySelector(`#${campo}`)?.addEventListener('input', actualizar));
  document.querySelector('#categoria_ia')?.addEventListener('change', actualizar);
  document.querySelector('#fotografia')?.addEventListener('change', (event) => {
    const archivo = event.target.files?.[0]; if (!archivo) return;
    const url = URL.createObjectURL(archivo);
    ['previsualizacion-foto', 'previsualizacion-tarjeta'].forEach((id) => { const imagen = document.querySelector(`#${id}`); imagen.src = url; imagen.hidden = false; });
    ['placeholder-foto', 'placeholder-tarjeta'].forEach((id) => { document.querySelector(`#${id}`).hidden = true; });
  });
  actualizar();
})();
