<?php
/*
 * Template Name: Micropigmentación de Cejas
 */
get_header();
$img = get_template_directory_uri() . '/img/';
?>

<!-- PAGE HERO -->
<section class="page-hero" aria-label="Micropigmentación de cejas">
  <div class="page-hero-bg" style="background-image:url('<?php echo $img; ?>banner-cejas-lateral.jpg')"></div>
  <div class="container">
    <div class="page-hero-content">
      <span class="label">Servicio</span>
      <h1>Micropigmentación<br>de cejas</h1>
      <p>Ceja por ceja. Trazo por trazo. Diseñadas para tu cara, no para ninguna otra.</p>
    </div>
  </div>
</section>

<!-- INTRO -->
<section class="section" style="background:var(--white)">
  <div class="container">
    <div class="content-grid">
      <div class="content-text reveal">
        <span class="label">Por qué las cejas importan</span>
        <h2>La ceja lo cambia todo.</h2>
        <p>
          No hay ninguna parte del rostro que tenga tanto impacto como las cejas.
          Enmarcan los ojos, definen la expresión, equilibran las facciones.
          Y sin embargo, muchas personas conviven durante años con unas cejas que no les gustan,
          que no les representan, o que simplemente han desaparecido.
        </p>
        <p>
          La micropigmentación de cejas es una solución duradera y de aspecto completamente natural.
          No un tatuaje, no una máscara: un resultado que parece que siempre has tenido esas cejas.
        </p>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--primary">Pide tu valoración gratuita</a>
      </div>
      <div class="content-img reveal reveal-delay-1">
        <img src="<?php echo $img; ?>micropigmentacion-cejas.jpg"
             alt="Micropigmentación de cejas resultado natural Zaragoza"
             loading="lazy"
             style="aspect-ratio:4/5;object-fit:cover">
      </div>
    </div>
  </div>
</section>

<!-- TÉCNICAS -->
<section class="section">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Las técnicas</span>
      <h2>¿Cuál es la tuya?</h2>
      <p style="margin:14px auto 0">
        No hay una técnica mejor que otra. Hay la que mejor se adapta a tu tipo de piel,
        a tus cejas actuales y al resultado que buscas. Te lo explico y lo decidimos juntas.
      </p>
    </div>

    <div class="tecnicas-grid">
      <div class="tecnica-card reveal reveal-delay-1">
        <h4>Pelo a pelo</h4>
        <p>
          Trazos finos que imitan cada pelo natural de la ceja. El resultado es hiperrealista
          y de aspecto completamente natural. Ideal si tienes buena base de ceja o si
          quieres un resultado sutil pero definido.
        </p>
      </div>
      <div class="tecnica-card reveal reveal-delay-2">
        <h4>Técnica combinada</h4>
        <p>
          Combina el pelo a pelo con sombreado suave (pixelado o difuminado).
          Aporta más densidad visual y duración. Perfecta si tienes poca ceja
          o si quieres un acabado más "maquillado" pero sin excesos.
        </p>
      </div>
      <div class="tecnica-card reveal reveal-delay-3">
        <h4>Microblading</h4>
        <p>
          Técnica manual, pelo a pelo, con un resultado ultra-natural. A diferencia de la
          máquina, el trazo es más suave y orgánico. Duración variable según el tipo de piel
          (entre 1 y 3 años). Te cuento si es la más adecuada para ti en la primera visita.
        </p>
      </div>
    </div>
  </div>
</section>

<!-- PARA QUIÉN ES IDEAL -->
<section class="section" style="background:var(--white)">
  <div class="container">
    <div class="content-grid reverse">
      <div class="content-img reveal">
        <img src="<?php echo $img; ?>trabajos/cejas/microblading-cejas-zaragoza3.jpg"
             alt="Antes y después micropigmentación cejas Zaragoza"
             loading="lazy"
             style="aspect-ratio:1;object-fit:cover">
      </div>
      <div class="content-text reveal reveal-delay-1">
        <span class="label">¿Es para ti?</span>
        <h2>Hay muchas razones para hacerlo.</h2>
        <p>
          La micropigmentación de cejas es una buena opción si:
        </p>
        <ul style="margin:16px 0 24px;padding-left:0;list-style:none;display:flex;flex-direction:column;gap:10px">
          <li style="display:flex;gap:12px;align-items:flex-start">
            <span style="color:var(--gold);font-weight:700;flex-shrink:0">—</span>
            Tienes las cejas despobladas, con huecos o asimétricas
          </li>
          <li style="display:flex;gap:12px;align-items:flex-start">
            <span style="color:var(--gold);font-weight:700;flex-shrink:0">—</span>
            Has depilado demasiado con el tiempo y ya no te crecen igual
          </li>
          <li style="display:flex;gap:12px;align-items:flex-start">
            <span style="color:var(--gold);font-weight:700;flex-shrink:0">—</span>
            Tienes alopecia parcial o total en la zona de las cejas
          </li>
          <li style="display:flex;gap:12px;align-items:flex-start">
            <span style="color:var(--gold);font-weight:700;flex-shrink:0">—</span>
            Tardas mucho maquillándote las cejas y quieres simplificar tu rutina
          </li>
          <li style="display:flex;gap:12px;align-items:flex-start">
            <span style="color:var(--gold);font-weight:700;flex-shrink:0">—</span>
            Simplemente quieres mejorar la forma o el aspecto de tus cejas actuales
          </li>
        </ul>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--primary">Cuéntame tu caso</a>
      </div>
    </div>
  </div>
</section>

<!-- PROCESO -->
<section class="section">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">El proceso</span>
      <h2>Paso a paso, sin sorpresas.</h2>
      <p style="margin:14px auto 0">
        Sé que el proceso puede generar dudas. Por eso te explico exactamente qué pasa
        desde que me escribes hasta que ves el resultado final.
      </p>
    </div>

    <div class="proceso-steps" style="max-width:680px;margin:0 auto">
      <div class="proceso-step reveal">
        <div class="step-number">1</div>
        <div class="step-body">
          <h4>Valoración gratuita</h4>
          <p>
            Hablamos de lo que quieres, veo tus cejas, tu tipo de piel, tu tono.
            Sin compromiso de ningún tipo. Si no encaja, te lo digo con honestidad.
          </p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">2</div>
        <div class="step-body">
          <h4>Diseño personalizado</h4>
          <p>
            Diseñamos la forma de tu ceja ideal sobre tu rostro, con lápiz, antes de empezar.
            Tú la ves, la apruebas, la ajustamos si es necesario. Solo empiezo cuando estás
            segura de que es exactamente lo que quieres.
          </p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">3</div>
        <div class="step-body">
          <h4>Aplicación</h4>
          <p>
            Aplicamos anestesia tópica para que el proceso sea lo más cómodo posible.
            La sesión dura entre 90 y 120 minutos aproximadamente.
          </p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">4</div>
        <div class="step-body">
          <h4>Cuidados post-tratamiento</h4>
          <p>
            Te doy todas las instrucciones por escrito. Los primeros días el color se ve
            más intenso — es completamente normal. La piel tarda entre 4 y 6 semanas
            en mostrar el resultado definitivo.
          </p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">5</div>
        <div class="step-body">
          <h4>Revisión a las 6-8 semanas</h4>
          <p>
            Vemos el resultado final y hacemos los ajustes que necesite. Esta sesión de
            repaso está incluida en el tratamiento.
          </p>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- FAQ -->
<section class="section" style="background:var(--white)">
  <div class="container" style="max-width:740px">
    <div class="text-center reveal">
      <span class="label">Dudas frecuentes</span>
      <h2>Lo que más me preguntan.</h2>
    </div>

    <div class="faq-list">
      <div class="faq-item">
        <button class="faq-question">
          ¿Duele la micropigmentación de cejas?
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <div class="faq-answer">
          <p>
            Aplicamos anestesia tópica antes de empezar, así que la mayoría de las personas
            describen la sensación como un rasguño suave, muy tolerable. No es un proceso
            doloroso. Eso sí, te lo digo siempre: cada persona tiene un umbral distinto.
          </p>
        </div>
      </div>
      <div class="faq-item">
        <button class="faq-question">
          ¿Cuánto dura la micropigmentación de cejas?
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <div class="faq-answer">
          <p>
            Depende de la técnica y, sobre todo, de tu tipo de piel. De media, entre 1 y 3 años.
            Las pieles más grasas tienden a difuminar antes el pigmento. Con una sesión de
            retoque anual puedes mantener el resultado indefinidamente.
          </p>
        </div>
      </div>
      <div class="faq-item">
        <button class="faq-question">
          ¿Cuándo veo el resultado final?
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <div class="faq-answer">
          <p>
            La piel necesita entre 4 y 6 semanas para cicatrizar completamente. Los primeros
            días el color se ve más oscuro e intenso — es normal y va aclarando solo.
            El resultado definitivo lo ves en la revisión a las 6-8 semanas.
          </p>
        </div>
      </div>
      <div class="faq-item">
        <button class="faq-question">
          ¿Qué cuidados necesito después?
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <div class="faq-answer">
          <p>
            Los primeros días evitar agua directa, sol intenso, sudoración excesiva y no tocar
            la zona. Te lo explico todo detallado por escrito el mismo día de la sesión y
            también tienes el PDF de cuidados disponible para descargarte.
          </p>
        </div>
      </div>
      <div class="faq-item">
        <button class="faq-question">
          ¿Puedo hacerme la micropigmentación si tengo alopecia?
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <div class="faq-answer">
          <p>
            Sí, es uno de los casos en los que más impacto tiene el tratamiento. He trabajado
            con muchas personas con alopecia areata y los resultados son muy bonitos.
            Lo valoramos en consulta.
          </p>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- CTA -->
<section class="cta-block">
  <div class="container">
    <div class="reveal">
      <span class="label" style="color:var(--nude)">Sin compromiso</span>
      <h2>¿Hablamos de tus cejas?</h2>
      <p>La primera consulta es gratuita. Sin presiones, sin venderte nada.</p>
      <div class="cta-actions">
        <a href="https://wa.me/34620834002?text=Hola%20Virginia%2C%20me%20gustar%C3%ADa%20pedir%20informaci%C3%B3n%20sobre%20micropigmentaci%C3%B3n%20de%20cejas."
           class="btn btn--whatsapp" target="_blank" rel="noopener">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.122 1.524 5.863L.057 23.57a.75.75 0 00.918.918l5.702-1.467A11.94 11.94 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75A9.74 9.74 0 016.31 19.94l-.387-.23-3.384.87.886-3.295-.25-.404A9.71 9.71 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
          Pide tu valoración gratuita
        </a>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--white">Formulario</a>
      </div>
    </div>
  </div>
</section>

<?php get_footer(); ?>
