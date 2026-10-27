(() => {
  const archivo = document.querySelector('#evidencia');
  const panelArchivo = document.querySelector('#panel-archivo');
  const panelCamara = document.querySelector('#panel-camara');
  const video = document.querySelector('#video-camara');
  const lienzo = document.querySelector('#lienzo-camara');
  const iniciar = document.querySelector('#iniciar-camara');
  const abrirCamara = document.querySelector('#abrir-camara');
  const limpiar = document.querySelector('#limpiar-evidencia');
  const capturar = document.querySelector('#capturar-camara');
  const formulario = document.querySelector('#form-evidencia');
  const estadoAnalisis = document.querySelector('#estado-analisis');
  const botonAnalizar = formulario?.querySelector('.boton-analizar');
  let flujo;
  const iniciarAnalisis = () => {
    if (estadoAnalisis) estadoAnalisis.hidden = false;
    if (botonAnalizar) botonAnalizar.disabled = true;
    if (capturar) capturar.disabled = true;
  };
  document.querySelectorAll('[data-modo]').forEach((boton) => boton.addEventListener('click', () => {
    const camara = boton.dataset.modo === 'camara';
    panelCamara.hidden = !camara; panelArchivo.hidden = camara;
    document.querySelectorAll('[data-modo]').forEach((item) => item.classList.toggle('activo', item === boton));
  }));
  abrirCamara?.addEventListener('click', () => {
    document.querySelector('[data-modo="camara"]')?.click();
    iniciar?.click();
  });
  limpiar?.addEventListener('click', () => {
    if (flujo) flujo.getTracks().forEach((pista) => pista.stop());
    flujo = undefined;
    formulario?.reset();
    panelCamara.hidden = true;
    panelArchivo.hidden = false;
    document.querySelectorAll('[data-modo]').forEach((item) => item.classList.toggle('activo', item.dataset.modo === 'archivo'));
    if (botonAnalizar) botonAnalizar.textContent = 'Analizar imagen';
    if (estadoAnalisis) estadoAnalisis.hidden = true;
  });
  iniciar?.addEventListener('click', async () => {
    try { flujo = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false }); video.srcObject = flujo; capturar.disabled = false; document.querySelector('#estado-camara').textContent = 'Cámara activa. Encuadra los productos y captura.'; }
    catch { document.querySelector('#estado-camara').textContent = 'No se pudo usar la cámara. Usa “Subir imagen”.'; }
  });
  capturar?.addEventListener('click', () => {
    if (!video.videoWidth || !video.videoHeight) { document.querySelector('#estado-camara').textContent = 'La cámara aún no está lista. Espera un momento e inténtalo otra vez.'; return; }
    lienzo.width = video.videoWidth; lienzo.height = video.videoHeight; lienzo.getContext('2d').drawImage(video, 0, 0);
    lienzo.toBlob((blob) => { if (!blob) { document.querySelector('#estado-camara').textContent = 'No se pudo crear la captura. Inténtalo nuevamente.'; return; } const datos = new DataTransfer(); datos.items.add(new File([blob], 'captura-sivia.jpg', { type: 'image/jpeg' })); archivo.files = datos.files; if (flujo) flujo.getTracks().forEach((pista) => pista.stop()); formulario.requestSubmit(); }, 'image/jpeg', .92);
  });
  archivo?.addEventListener('change', () => { if (archivo.files.length) formulario.querySelector('.boton-analizar').textContent = 'Analizar imagen seleccionada'; });
  formulario?.addEventListener('submit', iniciarAnalisis);
})();
