<?php
/*
 * Template Name: Micropigmentación de Ojos
 */
get_header();
$img = get_template_directory_uri() . '/img/';
?>

<!-- PAGE HERO -->
<section class="page-hero" aria-label="Micropigmentación de ojos">
  <div class="page-hero-bg" style="background-image:url('<?php echo $img; ?>banner-ojos-lateral.jpg')"></div>
  <div class="container">
    <div class="page-hero-content">
      <span class="label">Servicio</span>
      <h1>Micropigmentación<br>de ojos</h1>
      <p>Una mirada que habla, sin necesidad de maquillarte cada mañana.</p>
    </div>
  </div>
</section>

<!-- INTRO -->
<section class="section" style="background:var(--white)">
  <div class="container">
    <div class="content-grid">
      <div class="content-text reveal">
        <span class="label">El eyeliner permanente</span>
        <h2>El delineado que no se borra. Ni con agua, ni con el tiempo.</h2>
        <p>
          ¿Cuánto tiempo llevas aplicándote el mismo trazo cada mañana? ¿Cuántas veces
          se ha corrido, se ha borrado o simplemente no ha quedado como querías?
        </p>
        <p>
          La micropigmentación de ojos — o eyeliner permanente — define la línea del párpado
          de forma duradera y de aspecto completamente natural. Se despierta con la mirada puesta.
        </p>
        <p>
          Y sí, se aplica anestesia tópica. Más cómodo de lo que imaginas.
        </p>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--primary">¿Te lo cuento todo? Escríbeme</a>
      </div>
      <div class="content-img reveal reveal-delay-1">
        <img src="<?php echo $img; ?>micropigmentacion-ojos.jpg"
             alt="Eyeliner permanente resultado Zaragoza"
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
      <span class="label">Tipos de eyeliner</span>
      <h2>Hay tantos estilos como miradas.</h2>
      <p style="margin:14px auto 0">
        Desde el más discreto hasta el más definido. Te explico cada opción y decidimos
        cuál se adapta mejor a tu forma de ojo, tu estilo de vida y lo que buscas.
      </p>
    </div>

    <div class="tecnicas-grid" style="grid-template-columns:repeat(2,1fr)">
      <div class="tecnica-card reveal reveal-delay-1">
        <h4>Tribal (delineado clásico)</h4>
        <p>
          Una línea limpia y definida sobre el párpado superior. El resultado más natural
          y versátil. Perfecto si quieres un toque sutil que defina sin exagerar.
        </p>
      </div>
      <div class="tecnica-card reveal reveal-delay-2">
        <h4>Sombreado</h4>
        <p>
          Un delineado con efecto difuminado, más suave y gradual. Da profundidad a la
          mirada sin el trazo tan marcado. Muy natural y favorecedor en casi todos los ojos.
        </p>
      </div>
      <div class="tecnica-card reveal reveal-delay-3">
        <h4>Fuzzy (borroso)</h4>
        <p>
          Similar al sombreado pero con un aspecto más "desenfocado", como un delineado
          aplicado con la yema del dedo. Muy de moda, queda muy bonito en ojos grandes.
        </p>
      </div>
      <div class="tecnica-card reveal reveal-delay-4">
        <h4>Eyecolor (párpado)</h4>
        <p>
          Pigmentación en la zona del párpado para dar color y profundidad. Un efecto
          de sombra permanente muy sofisticado. Requiere más precisión y mantenimiento,
          pero el resultado es espectacular.
        </p>
      </div>
    </div>
  </div>
</section>

<!-- AVISO IMPORTANTE -->
<section class="section" style="background:var(--white)">
  <div class="container" style="max-width:740px">
    <div class="reveal" style="background:var(--champagne);border-radius:var(--radius-lg);padding:40px 48px;border-left:4px solid var(--gold)">
      <span class="label">Algo importante antes de reservar</span>
      <h3 style="margin-bottom:16px">Hay dos momentos en los que es mejor esperar.</h3>
      <p style="margin-bottom:14px">
        <strong>El verano no es la mejor época</strong> para hacerse la micropigmentación de ojos.
        El calor, el sudor y la exposición solar durante la cicatrización pueden afectar al resultado.
        Mejor en otoño, invierno o primavera.
      </p>
      <p>
        <strong>Tampoco lo hagas justo antes de un evento importante</strong> —una boda, una
        presentación, unas vacaciones—. La zona necesita entre 2 y 4 semanas para cicatrizar
        bien y el color puede verse más intenso los primeros días. Planifícalo con margen.
      </p>
    </div>
  </div>
</section>

<!-- PROCESO -->
<section class="section">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Cómo funciona</span>
      <h2>Sin sorpresas, sin letra pequeña.</h2>
    </div>

    <div class="proceso-steps" style="max-width:680px;margin:0 auto">
      <div class="proceso-step reveal">
        <div class="step-number">1</div>
        <div class="step-body">
          <h4>Consulta previa</h4>
          <p>Hablamos de tu forma de ojo, el estilo que buscas y qué técnica encaja mejor. Gratuita y sin compromiso.</p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">2</div>
        <div class="step-body">
          <h4>Anestesia tópica</h4>
          <p>Aplicamos crema anestésica antes de empezar. La zona del párpado es sensible, pero con anestesia el proceso es muy tolerable.</p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">3</div>
        <div class="step-body">
          <h4>Aplicación del pigmento</h4>
          <p>Trabajo con mucha precisión y calma. La sesión dura aproximadamente 90 minutos.</p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">4</div>
        <div class="step-body">
          <h4>Cicatrización (2-4 semanas)</h4>
          <p>Los primeros días la zona estará algo rosada y el color muy intenso. Es completamente normal. No toques, no pongas maquillaje en la zona y sigue las instrucciones.</p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">5</div>
        <div class="step-body">
          <h4>Revisión y ajuste</h4>
          <p>A las 6-8 semanas revisamos el resultado y hacemos cualquier corrección que sea necesaria.</p>
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
      <h2>¿Te lo cuento todo sin compromiso?</h2>
      <p>Escríbeme y hablamos de tu mirada. La primera consulta es gratuita.</p>
      <div class="cta-actions">
        <a href="https://wa.me/34620834002?text=Hola%20Virginia%2C%20me%20gustar%C3%ADa%20informaci%C3%B3n%20sobre%20micropigmentaci%C3%B3n%20de%20ojos."
           class="btn btn--whatsapp" target="_blank" rel="noopener">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.122 1.524 5.863L.057 23.57a.75.75 0 00.918.918l5.702-1.467A11.94 11.94 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75A9.74 9.74 0 016.31 19.94l-.387-.23-3.384.87.886-3.295-.25-.404A9.71 9.71 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
          Escríbeme
        </a>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--white">Formulario</a>
      </div>
    </div>
  </div>
</section>

<?php get_footer(); ?>
