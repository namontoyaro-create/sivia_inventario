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
  const estadoCamara = document.querySelector('#estado-camara');
  let flujo;

  const detenerCamara = () => {
    if (flujo) flujo.getTracks().forEach((pista) => pista.stop());
    flujo = undefined;
  };
  const iniciarAnalisis = () => {
    if (estadoAnalisis) estadoAnalisis.hidden = false;
    if (botonAnalizar) botonAnalizar.disabled = true;
    if (capturar) capturar.disabled = true;
  };
  const activarModo = (modo) => {
    const camara = modo === 'camara';
    panelCamara.hidden = !camara;
    panelArchivo.hidden = camara;
    document.querySelectorAll('[data-modo]').forEach((boton) => {
      boton.classList.toggle('activo', boton.dataset.modo === modo);
    });
  };

  document.querySelectorAll('[data-modo]').forEach((boton) => boton.addEventListener('click', () => {
    activarModo(boton.dataset.modo);
  }));
  abrirCamara?.addEventListener('click', () => {
    activarModo('camara');
    iniciar?.click();
  });
  limpiar?.addEventListener('click', () => {
    detenerCamara();
    formulario?.reset();
    activarModo('archivo');
    if (botonAnalizar) {
      botonAnalizar.disabled = false;
      botonAnalizar.textContent = '\ud83d\udd0e Analizar imagen';
    }
    if (capturar) capturar.disabled = true;
    if (estadoAnalisis) estadoAnalisis.hidden = true;
    if (estadoCamara) estadoCamara.textContent = 'Activa la c\u00e1mara para capturar la evidencia.';
  });
  iniciar?.addEventListener('click', async () => {
    try {
      detenerCamara();
      flujo = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      video.srcObject = flujo;
      capturar.disabled = false;
      if (estadoCamara) estadoCamara.textContent = 'C\u00e1mara activa. Encuadra los productos y captura.';
    } catch {
      if (estadoCamara) estadoCamara.textContent = 'No se pudo usar la c\u00e1mara. Usa Subir fotograf\u00eda.';
    }
  });
  capturar?.addEventListener('click', () => {
    if (!video.videoWidth || !video.videoHeight) {
      if (estadoCamara) estadoCamara.textContent = 'La c\u00e1mara a\u00fan no est\u00e1 lista. Espera un momento e int\u00e9ntalo otra vez.';
      return;
    }
    lienzo.width = video.videoWidth;
    lienzo.height = video.videoHeight;
    lienzo.getContext('2d').drawImage(video, 0, 0);
    lienzo.toBlob((blob) => {
      if (!blob) {
        if (estadoCamara) estadoCamara.textContent = 'No se pudo crear la captura. Int\u00e9ntalo nuevamente.';
        return;
      }
      const datos = new DataTransfer();
      datos.items.add(new File([blob], 'captura-sivia.jpg', { type: 'image/jpeg' }));
      archivo.files = datos.files;
      detenerCamara();
      iniciarAnalisis();
      formulario.requestSubmit();
    }, 'image/jpeg', 0.92);
  });
  archivo?.addEventListener('change', () => {
    if (archivo.files.length && botonAnalizar) botonAnalizar.textContent = '\ud83d\udd0e Analizar imagen seleccionada';
  });
  formulario?.addEventListener('submit', iniciarAnalisis);
})();
