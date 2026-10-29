(() => {
  const input = document.querySelector('#audio');
  const iniciar = document.querySelector('#grabar-audio');
  const detener = document.querySelector('#detener-audio');
  const enviar = document.querySelector('#transcribir-audio');
  const estado = document.querySelector('#estado-audio');
  const vista = document.querySelector('#vista-audio');
  const resultado = document.querySelector('#resultado-transcripcion');
  const texto = document.querySelector('#texto-transcripcion');
  if (!input || !iniciar || !detener || !enviar || !estado) return;

  let grabador = null, flujo = null, partes = [], procesando = false, urlTemporal = null;
  const cambiarControles = (ocupado) => {
    iniciar.disabled = ocupado;
    detener.disabled = ocupado || !grabador || grabador.state !== 'recording';
    enviar.disabled = ocupado;
    input.disabled = ocupado;
  };
  const mostrarError = (mensaje) => { estado.textContent = `Error: ${mensaje}`; procesando = false; cambiarControles(false); };
  const prepararVista = (archivo) => {
    if (!archivo || archivo.size === 0) { mostrarError('la grabación no contiene audio. Intenta nuevamente.'); return false; }
    if (archivo.size > 25 * 1024 * 1024) { mostrarError('el audio supera 25 MB.'); return false; }
    if (urlTemporal) URL.revokeObjectURL(urlTemporal);
    urlTemporal = URL.createObjectURL(archivo); vista.src = urlTemporal; vista.hidden = false;
    return true;
  };
  const transcribir = async (archivo) => {
    if (procesando || !prepararVista(archivo)) return;
    procesando = true; cambiarControles(true); estado.textContent = 'Transcribiendo audio…';
    try {
      const datos = new FormData(); datos.append('audio', archivo, archivo.name);
      const respuesta = await fetch('/asistente-voz/transcribir', { method: 'POST', body: datos });
      const cuerpo = await respuesta.json().catch(() => ({ ok: false, error: 'El servidor devolvió una respuesta no válida.' }));
      if (!respuesta.ok || !cuerpo.ok) throw new Error(cuerpo.error || 'No se pudo transcribir el audio.');
      texto.value = cuerpo.transcripcion; resultado.hidden = false; estado.textContent = 'Transcripción completada.';
    } catch (error) { mostrarError(error.message || 'No se pudo transcribir el audio.'); return; }
    procesando = false; cambiarControles(false);
  };
  const iniciarTranscripcion = (archivo) => {
    void transcribir(archivo).catch((error) => mostrarError(error?.message || 'No se pudo transcribir el audio.'));
  };
  input.addEventListener('change', () => { const archivo = input.files?.[0]; if (archivo) iniciarTranscripcion(archivo); });
  enviar.addEventListener('click', () => { const archivo = input.files?.[0]; if (archivo) iniciarTranscripcion(archivo); else mostrarError('selecciona o graba un audio antes de transcribir.'); });
  iniciar.addEventListener('click', async () => {
    try {
      flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : (MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '');
      grabador = mime ? new MediaRecorder(flujo, { mimeType: mime }) : new MediaRecorder(flujo); partes = [];
      grabador.ondataavailable = (evento) => { if (evento.data && evento.data.size > 0) partes.push(evento.data); };
      grabador.onerror = () => { flujo?.getTracks().forEach((pista) => pista.stop()); mostrarError('la grabación falló. Intenta nuevamente.'); };
      grabador.onstop = () => {
        flujo?.getTracks().forEach((pista) => pista.stop());
        const tipo = grabador.mimeType || 'audio/webm';
        const blob = new Blob(partes, { type: tipo }); grabador = null;
        if (blob.size === 0) { mostrarError('no se generó audio válido. Revisa el permiso del micrófono.'); return; }
        iniciarTranscripcion(new File([blob], `grabacion-${Date.now()}.webm`, { type: tipo }));
      };
      grabador.start(); estado.textContent = 'Grabando…'; iniciar.disabled = true; detener.disabled = false;
    } catch (_) { mostrarError('no se pudo acceder al micrófono. Autoriza el permiso o sube un audio.'); }
  });
  detener.addEventListener('click', () => {
    if (grabador?.state === 'recording') { detener.disabled = true; estado.textContent = 'Preparando audio…'; grabador.stop(); }
  });
  document.querySelectorAll('[data-hablar]').forEach((boton) => boton.addEventListener('click', () => {
    if (!('speechSynthesis' in window)) { estado.textContent = 'La síntesis de voz no está disponible en este navegador.'; return; }
    window.speechSynthesis.cancel();
    const mensaje = new SpeechSynthesisUtterance(boton.dataset.hablar || '');
    const voces = window.speechSynthesis.getVoices();
    mensaje.voice = voces.find((voz) => voz.lang.toLowerCase() === 'es-pe') || voces.find((voz) => voz.lang.toLowerCase().startsWith('es')) || null;
    mensaje.lang = mensaje.voice?.lang || 'es-PE';
    window.speechSynthesis.speak(mensaje);
  }));
})();
