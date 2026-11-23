(() => {
  const input = document.querySelector('#audio');
  const iniciar = document.querySelector('#grabar-audio');
  const detener = document.querySelector('#detener-audio');
  const estado = document.querySelector('#estado-audio');
  const insignia = document.querySelector('#insignia-estado-voz');
  const vista = document.querySelector('#vista-audio');
  const resultado = document.querySelector('#resultado-transcripcion');
  const texto = document.querySelector('#texto-transcripcion');
  if (!input || !iniciar || !detener || !estado) return;

  let grabador = null;
  let flujo = null;
  let partes = [];
  let procesando = false;
  let urlTemporal = null;

  const actualizarEstado = (tipo, mensaje) => {
    estado.textContent = mensaje;
    estado.dataset.estado = tipo;
    if (!insignia) return;
    const etiquetas = { listo: 'Listo', grabando: 'Grabando', procesando: 'Procesando', resultado: 'Resultado', error: 'Error' };
    insignia.textContent = etiquetas[tipo] || 'Listo';
    insignia.className = `estado-voz estado-${tipo}`;
  };
  const detenerFlujo = () => {
    if (flujo) flujo.getTracks().forEach((pista) => pista.stop());
    flujo = null;
  };
  const cambiarControles = (ocupado) => {
    iniciar.disabled = ocupado;
    detener.disabled = ocupado || !grabador || grabador.state !== 'recording';
    input.disabled = ocupado;
  };
  const mostrarError = (mensaje) => {
    procesando = false;
    actualizarEstado('error', `Error: ${mensaje}`);
    cambiarControles(false);
  };
  const prepararVista = (archivo) => {
    if (!archivo || archivo.size === 0) {
      mostrarError('no se detect\u00f3 audio. Intenta nuevamente.');
      return false;
    }
    if (archivo.size > 25 * 1024 * 1024) {
      mostrarError('el audio supera el l\u00edmite de 25 MB.');
      return false;
    }
    if (urlTemporal) URL.revokeObjectURL(urlTemporal);
    urlTemporal = URL.createObjectURL(archivo);
    vista.src = urlTemporal;
    vista.hidden = false;
    return true;
  };
  const transcribir = async (archivo) => {
    if (procesando || !prepararVista(archivo)) return;
    procesando = true;
    cambiarControles(true);
    actualizarEstado('procesando', 'Procesando audio y transcribiendo localmente...');
    try {
      const datos = new FormData();
      datos.append('audio', archivo, archivo.name);
      const respuesta = await fetch('/asistente-voz/transcribir', { method: 'POST', body: datos });
      const cuerpo = await respuesta.json().catch(() => ({ ok: false, error: 'El servidor devolvi\u00f3 una respuesta no v\u00e1lida.' }));
      if (!respuesta.ok || !cuerpo.ok) throw new Error(cuerpo.error || 'No se pudo transcribir el audio.');
      texto.value = cuerpo.transcripcion;
      resultado.hidden = false;
      actualizarEstado('resultado', 'Transcripci\u00f3n completada. Revisa el texto antes de interpretarlo.');
    } catch (error) {
      mostrarError(error.message || 'No se pudo transcribir el audio.');
      return;
    }
    procesando = false;
    cambiarControles(false);
  };
  const iniciarTranscripcion = (archivo) => {
    void transcribir(archivo).catch((error) => mostrarError(error?.message || 'No se pudo transcribir el audio.'));
  };

  input.addEventListener('change', () => {
    const archivo = input.files?.[0];
    if (archivo) iniciarTranscripcion(archivo);
  });
  iniciar.addEventListener('click', async () => {
    try {
      detenerFlujo();
      flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : (MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '');
      grabador = mime ? new MediaRecorder(flujo, { mimeType: mime }) : new MediaRecorder(flujo);
      partes = [];
      grabador.ondataavailable = (evento) => { if (evento.data?.size > 0) partes.push(evento.data); };
      grabador.onerror = () => {
        detenerFlujo();
        mostrarError('la grabaci\u00f3n fall\u00f3. Intenta nuevamente.');
      };
      grabador.onstop = () => {
        detenerFlujo();
        const tipo = grabador?.mimeType || 'audio/webm';
        const blob = new Blob(partes, { type: tipo });
        grabador = null;
        if (blob.size === 0) {
          mostrarError('no se gener\u00f3 audio v\u00e1lido. Revisa el permiso del micr\u00f3fono.');
          return;
        }
        iniciarTranscripcion(new File([blob], `grabacion-${Date.now()}.webm`, { type: tipo }));
      };
      grabador.start();
      actualizarEstado('grabando', 'Grabando... Pulsa Detener cuando termines.');
      iniciar.disabled = true;
      detener.disabled = false;
    } catch {
      mostrarError('no se pudo acceder al micr\u00f3fono. Autoriza el permiso o sube un audio.');
    }
  });
  detener.addEventListener('click', () => {
    if (grabador?.state === 'recording') {
      detener.disabled = true;
      actualizarEstado('procesando', 'Preparando audio para transcribir...');
      grabador.stop();
    }
  });
  document.querySelectorAll('[data-hablar]').forEach((boton) => boton.addEventListener('click', () => {
    if (!('speechSynthesis' in window)) {
      actualizarEstado('error', 'La s\u00edntesis de voz no est\u00e1 disponible en este navegador.');
      return;
    }
    window.speechSynthesis.cancel();
    const mensaje = new SpeechSynthesisUtterance(boton.dataset.hablar || '');
    const voces = window.speechSynthesis.getVoices();
    mensaje.voice = voces.find((voz) => voz.lang.toLowerCase() === 'es-pe') || voces.find((voz) => voz.lang.toLowerCase().startsWith('es')) || null;
    mensaje.lang = mensaje.voice?.lang || 'es-PE';
    window.speechSynthesis.speak(mensaje);
  }));
})();
