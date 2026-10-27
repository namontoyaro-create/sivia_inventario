(() => {
  const buscar = document.querySelector('#buscar-productos');
  const categoria = document.querySelector('#filtro-categoria');
  const presentacion = document.querySelector('#filtro-presentacion');
  const orden = document.querySelector('#orden-productos');
  const estado = document.querySelector('#filtro-estado');
  const limpiar = document.querySelector('#limpiar-filtros');
  const cuerpo = document.querySelector('#filas-productos');
  if (!buscar || !cuerpo) return;
  const contador = document.querySelector('#contador-productos');
  const vacio = document.querySelector('#sin-resultados');
  const filas = [...cuerpo.querySelectorAll('tr')];
  const normalizar = (texto) => (texto || '').toLocaleLowerCase('es');
  function actualizar() {
    const texto = normalizar(buscar.value).trim();
    const familia = normalizar(categoria.value);
    const tipo = normalizar(presentacion.value);
    const estadoSeleccionado = normalizar(estado?.value);
    const visibles = filas.filter((fila) => {
      const coincideTexto = !texto || ['codigo', 'producto', 'categoria', 'clase'].some((dato) => fila.dataset[dato].includes(texto));
      return coincideTexto && (!familia || fila.dataset.categoria === familia) && (!tipo || fila.dataset.presentacion === tipo) && (!estadoSeleccionado || fila.dataset.estado === estadoSeleccionado);
    });
    const comparadores = {
      codigo: (a, b) => a.dataset.codigo.localeCompare(b.dataset.codigo),
      'nombre-asc': (a, b) => a.dataset.producto.localeCompare(b.dataset.producto, 'es'),
      'nombre-desc': (a, b) => b.dataset.producto.localeCompare(a.dataset.producto, 'es'),
      'stock-asc': (a, b) => Number(a.dataset.stock) - Number(b.dataset.stock),
      'stock-desc': (a, b) => Number(b.dataset.stock) - Number(a.dataset.stock),
    };
    filas.sort(comparadores[orden.value] || comparadores.codigo).forEach((fila) => cuerpo.append(fila));
    filas.forEach((fila) => { fila.hidden = !visibles.includes(fila); });
    contador.textContent = visibles.length;
    vacio.hidden = visibles.length !== 0;
  }
  [buscar, categoria, presentacion, orden, estado].filter(Boolean).forEach((control) => control.addEventListener('input', actualizar));
  [categoria, presentacion, orden, estado].filter(Boolean).forEach((control) => control.addEventListener('change', actualizar));
  limpiar?.addEventListener('click', () => { buscar.value = ''; categoria.value = ''; presentacion.value = ''; orden.value = 'codigo'; if (estado) estado.value = ''; actualizar(); });
  actualizar();
})();
