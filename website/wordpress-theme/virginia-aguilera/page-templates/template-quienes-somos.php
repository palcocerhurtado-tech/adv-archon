<?php
/*
 * Template Name: Quiénes Somos
 */
get_header();
$img = get_template_directory_uri() . '/img/';
?>

<!-- ABOUT HERO -->
<section class="section section--lg" style="background:var(--white);padding-top:120px">
  <div class="container">
    <div class="about-hero">

      <div class="about-photo reveal">
        <img src="<?php echo $img; ?>virginia-aguilera-micropigmentacion.jpg"
             alt="Virginia Aguilera — Especialista en micropigmentación Zaragoza"
             loading="eager">
        <div class="about-photo-badge">
          <strong>+20</strong>
          <span>años de experiencia</span>
        </div>
      </div>

      <div class="about-text reveal reveal-delay-1">
        <span class="label">Quién soy</span>
        <h1>Hola, soy Virginia.<br><em style="font-style:italic;color:var(--gold)">Encantada de conocerte.</em></h1>

        <p>
          Llevo más de veinte años dedicándome en exclusiva a la micropigmentación facial.
          No fue casualidad: fue una elección deliberada. Quería hacer algo con las manos,
          con precisión, con un resultado que la persona pudiera ver y sentir.
          Y cuando me formé por primera vez en micropigmentación, supe que era eso.
        </p>
        <p>
          He formado a otras profesionales. Distribuyo pigmentos de alta calidad.
          He competido a nivel nacional. Pero lo que me sigue haciendo levantarme con ganas
          cada mañana es lo mismo de siempre: ver la expresión de una persona cuando
          se mira al espejo por primera vez después de una sesión.
        </p>
        <p>
          No trabajo en cadena. Cada cliente es un caso único. Antes de empezar, hablo.
          Escucho. Diseño. Y solo procedo cuando estoy segura de que el resultado va a ser
          exactamente lo que esa persona esperaba, o mejor.
        </p>

        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--primary" style="margin-top:8px">Ven a conocerme</a>
      </div>

    </div>
  </div>
</section>

<!-- CREDENCIALES -->
<section class="section" style="background:var(--cream)">
  <div class="container">
    <div class="content-grid">
      <div class="content-text reveal">
        <span class="label">Mi trayectoria</span>
        <h2>Años de trabajo, de estudio<br>y de resultados.</h2>
        <p>
          No me gusta hablar de mí misma como si fuera un currículum. Pero hay cosas
          que son relevantes para ti y que merece la pena que sepas.
        </p>

        <div class="credentials-list">
          <div class="credential-item">
            <span>Titular del sello <strong>"Perfecta Micro"</strong> de la AMME
              (Asociación de Micropigmentación y Maquillaje Estético de España). No es
              un sello que te den solo por pedir.</span>
          </div>
          <div class="credential-item">
            <span><strong>Instructora de micropigmentación.</strong> He formado a otras profesionales
              porque creo que compartir el conocimiento eleva el nivel del sector.</span>
          </div>
          <div class="credential-item">
            <span><strong>Semifinalista del Campeonato de España Wulop.</strong> Competir me ayuda
              a conocer mis límites y superarlos.</span>
          </div>
          <div class="credential-item">
            <span><strong>Distribuidora de pigmentos de alta calidad</strong> con registro sanitario
              europeo. Uso lo mismo que distribuyo porque confío en ello.</span>
          </div>
          <div class="credential-item">
            <span>Formación continua en España y en el extranjero. Este sector avanza y
              yo avanzo con él.</span>
          </div>
        </div>
      </div>

      <div class="reveal reveal-delay-1" style="display:flex;flex-direction:column;gap:20px">
        <div style="border-radius:var(--radius-lg);overflow:hidden;box-shadow:var(--shadow)">
          <img src="<?php echo $img; ?>diploma-micropigmentacion.jpg"
               alt="Diploma formación micropigmentación Virginia Aguilera"
               loading="lazy">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
          <div style="border-radius:var(--radius-lg);overflow:hidden;box-shadow:var(--shadow)">
            <img src="<?php echo $img; ?>sello-de-calidad-negro.png"
                 alt="Sello Perfecta Micro AMME"
                 loading="lazy"
                 style="padding:24px;background:var(--white)">
          </div>
          <div style="border-radius:var(--radius-lg);overflow:hidden;box-shadow:var(--shadow)">
            <img src="<?php echo $img; ?>certificado.jpg"
                 alt="Certificado micropigmentación Virginia Aguilera"
                 loading="lazy">
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- DÓNDE ENCONTRARME -->
<section class="section" style="background:var(--white)">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Dónde trabajo</span>
      <h2>Dos ubicaciones en Zaragoza.</h2>
      <p style="margin:14px auto 0">
        Tengo consulta en el centro de la ciudad y también en el Hospital Viamed Montecanal.
        Me dices cuál te viene mejor.
      </p>
    </div>

    <div class="locations-grid">
      <div class="location-card reveal reveal-delay-1">
        <iframe
          class="map-embed"
          src="https://maps.google.com/maps?q=Paseo+Independencia+24+Zaragoza&output=embed"
          loading="lazy"
          title="CC El Caracol — Paseo Independencia Zaragoza"
          allowfullscreen></iframe>
        <div class="location-card-body">
          <h4>CC El Caracol</h4>
          <p>Pº de la Independencia 24-26<br>Planta -1, Local 72<br>Zaragoza (centro)</p>
          <a href="https://maps.google.com/?q=Paseo+Independencia+24+Zaragoza" target="_blank" rel="noopener">
            Ver en Google Maps &rarr;
          </a>
        </div>
      </div>

      <div class="location-card reveal reveal-delay-2">
        <iframe
          class="map-embed"
          src="https://maps.google.com/maps?q=Franz+Schubert+2+Zaragoza&output=embed"
          loading="lazy"
          title="Hospital Viamed Montecanal — Zaragoza"
          allowfullscreen></iframe>
        <div class="location-card-body">
          <h4>Hospital Viamed Montecanal</h4>
          <p>C/ Franz Schubert, 2<br>50012 Zaragoza</p>
          <a href="https://maps.google.com/?q=Calle+Franz+Schubert+2+Zaragoza" target="_blank" rel="noopener">
            Ver en Google Maps &rarr;
          </a>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- FILOSOFÍA / FORMA DE TRABAJAR -->
<section class="quote-section">
  <div class="container">
    <div class="quote-inner reveal">
      <span class="quote-mark" aria-hidden="true">"</span>
      <p class="quote-text">
        No me importa tanto el resultado técnico como cómo se siente la persona
        cuando sale por esa puerta. Si lleva lo que quería, si se ve a sí misma,
        ese día ha sido un buen día de trabajo.
      </p>
      <span class="quote-author">Virginia Aguilera</span>
    </div>
  </div>
</section>

<!-- CTA -->
<section class="cta-block">
  <div class="container">
    <div class="reveal">
      <span class="label" style="color:var(--nude)">Nos conocemos</span>
      <h2>Ven a conocerme.</h2>
      <p>Sin presiones. Solo hablamos.</p>
      <div class="cta-actions">
        <a href="https://wa.me/34620834002?text=Hola%20Virginia%2C%20me%20gustar%C3%ADa%20conocerte%20y%20pedir%20informaci%C3%B3n."
           class="btn btn--whatsapp" target="_blank" rel="noopener">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.122 1.524 5.863L.057 23.57a.75.75 0 00.918.918l5.702-1.467A11.94 11.94 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75A9.74 9.74 0 016.31 19.94l-.387-.23-3.384.87.886-3.295-.25-.404A9.71 9.71 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
          Escríbeme por WhatsApp
        </a>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--white">Formulario de contacto</a>
      </div>
    </div>
  </div>
</section>

<?php get_footer(); ?>
