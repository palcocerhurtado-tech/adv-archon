<?php
/**
 * Homepage template (front-page.php)
 */
get_header();
$img = get_template_directory_uri() . '/img/';
?>

<!-- ========== HERO ========== -->
<section class="hero" aria-label="Portada">
  <div class="hero-bg" role="img" aria-label="Resultado de micropigmentación de cejas en Zaragoza"></div>
  <div class="hero-overlay"></div>
  <div class="container">
    <div class="hero-content">
      <span class="label">Micropigmentación · Zaragoza</span>
      <h1>Tu mirada,<br><em>perfecta. Cada día.</em></h1>
      <p class="hero-subtitle">
        Cejas, ojos y labios con la técnica más precisa y el trato más cercano.
        Sin clínicas frías: solo Virginia y tú hablando de lo que quieres.
      </p>
      <div class="hero-actions">
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--primary">Pide tu cita</a>
        <a href="<?php echo home_url('/trabajos/'); ?>" class="btn btn--outline" style="border-color:rgba(255,255,255,0.6);color:#fff">Ver trabajos</a>
      </div>
    </div>
  </div>
  <div class="hero-scroll" aria-hidden="true">Desplázate</div>
</section>

<!-- ========== SERVICIOS ========== -->
<section class="section" id="servicios">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Lo que hago</span>
      <h2>Especialización total.<br>Resultados que se notan.</h2>
    </div>

    <div class="services-grid">
      <div class="service-card reveal reveal-delay-1">
        <img class="service-card-img"
             src="<?php echo $img; ?>micropigmentacion-cejas.jpg"
             alt="Micropigmentación de cejas Zaragoza"
             loading="lazy">
        <div class="service-card-overlay"></div>
        <div class="service-card-body">
          <h3>Cejas</h3>
          <p>Pelo a pelo, sombreado o técnica combinada. Diseñamos la ceja perfecta para tu rostro.</p>
          <a href="<?php echo home_url('/micropigmentacion-cejas/'); ?>" class="btn btn--outline" style="border-color:rgba(255,255,255,0.5);color:#fff">Saber más</a>
        </div>
      </div>

      <div class="service-card reveal reveal-delay-2">
        <img class="service-card-img"
             src="<?php echo $img; ?>micropigmentacion-ojos.jpg"
             alt="Micropigmentación de ojos — eyeliner permanente Zaragoza"
             loading="lazy">
        <div class="service-card-overlay"></div>
        <div class="service-card-body">
          <h3>Ojos</h3>
          <p>Eyeliner permanente que define tu mirada sin necesidad de maquillarte cada mañana.</p>
          <a href="<?php echo home_url('/micropigmentacion-ojos/'); ?>" class="btn btn--outline" style="border-color:rgba(255,255,255,0.5);color:#fff">Saber más</a>
        </div>
      </div>

      <div class="service-card reveal reveal-delay-3">
        <img class="service-card-img"
             src="<?php echo $img; ?>micropigmentacion-labios.jpg"
             alt="Micropigmentación de labios Zaragoza"
             loading="lazy">
        <div class="service-card-overlay"></div>
        <div class="service-card-body">
          <h3>Labios</h3>
          <p>Contorno perfecto y color natural. Labios más jóvenes, más definidos, sin esfuerzo.</p>
          <a href="<?php echo home_url('/micropigmentacion-labios/'); ?>" class="btn btn--outline" style="border-color:rgba(255,255,255,0.5);color:#fff">Saber más</a>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ========== BADGES / SELLOS ========== -->
<section class="section" style="padding-top:0;padding-bottom:0">
  <div class="container">
    <div class="badges-row reveal">
      <div class="badge-item">
        <img src="<?php echo $img; ?>sello-de-calidad-negro.png" alt='Sello "Perfecta Micro" AMME' loading="lazy">
        <span>Sello Perfecta Micro · AMME</span>
      </div>
      <div class="badge-item" style="text-align:center">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" style="margin:0 auto 8px">
          <circle cx="20" cy="20" r="19" stroke="#c9a96e" stroke-width="1.5"/>
          <path d="M12 20l5 5 11-11" stroke="#c9a96e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>Registro sanitario europeo</span>
      </div>
      <div class="badge-item" style="text-align:center">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" style="margin:0 auto 8px">
          <circle cx="20" cy="20" r="19" stroke="#c9a96e" stroke-width="1.5"/>
          <path d="M20 10v10l6 4" stroke="#c9a96e" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span>+20 años de experiencia</span>
      </div>
      <div class="badge-item" style="text-align:center">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" style="margin:0 auto 8px">
          <circle cx="20" cy="20" r="19" stroke="#c9a96e" stroke-width="1.5"/>
          <path d="M20 13a4 4 0 100 8 4 4 0 000-8zm-8 14c0-4 3.6-7 8-7s8 3 8 7" stroke="#c9a96e" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
        <span>Atención personalizada</span>

      </div>
    </div>
  </div>
</section>

<!-- ========== POR QUÉ VIRGINIA ========== -->
<section class="section why-section" id="por-que-virginia">
  <div class="container">
    <div class="text-center reveal" style="max-width:680px;margin:0 auto">
      <span class="label">Por qué elegirme</span>
      <h2>No hago un poco de todo.<br>Hago esto, y lo hago muy bien.</h2>
    </div>

    <div class="why-grid">
      <div class="why-item reveal reveal-delay-1">
        <div class="why-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
          </svg>
        </div>
        <div>
          <h4>Especialización exclusiva</h4>
          <p>
            Solo micropigmentación facial. No disperso mi atención en otros tratamientos.
            Eso significa que cada sesión, cada técnica, la tengo absolutamente dominada.
          </p>
        </div>
      </div>

      <div class="why-item reveal reveal-delay-2">
        <div class="why-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <div>
          <h4>Sello de calidad AMME</h4>
          <p>
            Soy titular del sello "Perfecta Micro" de la Asociación de Micropigmentación y
            Maquillaje Estético. Una certificación de calidad que no te va a dar cualquiera.
          </p>
        </div>
      </div>

      <div class="why-item reveal reveal-delay-3">
        <div class="why-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 8v4l3 3"/>
          </svg>
        </div>
        <div>
          <h4>Materiales con registro sanitario europeo</h4>
          <p>
            Uso únicamente pigmentos y materiales con registro sanitario europeo.
            Tu seguridad no es opcional; es el punto de partida.
          </p>
        </div>
      </div>

      <div class="why-item reveal reveal-delay-4">
        <div class="why-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/>
          </svg>
        </div>
        <div>
          <h4>Trato completamente personalizado</h4>
          <p>
            Antes de hacer nada, hablamos. Escucho lo que quieres, estudio tu rostro,
            y diseñamos juntas el resultado. Sin prisa, sin tallas únicas.
          </p>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ========== GALERÍA PREVIEW ========== -->
<section class="section gallery-preview" id="galeria">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Resultados reales</span>
      <h2>Algunos de mis trabajos favoritos</h2>
      <p style="margin:16px auto 0">
        Cada resultado es único, como cada persona. Aquí van algunos que me hacen
        especialmente feliz. Los mejores están aún por llegar — el tuyo, quizás.
      </p>
    </div>

    <div class="gallery-grid">
      <div class="gallery-item reveal reveal-delay-1">
        <img src="<?php echo $img; ?>trabajos/cejas/micropigmentacion-cejas-zaragoza25.jpg"
             alt="Micropigmentación cejas Zaragoza" loading="lazy">
        <div class="gallery-item-overlay"><span>Cejas · Pelo a pelo</span></div>
      </div>
      <div class="gallery-item reveal reveal-delay-2">
        <img src="<?php echo $img; ?>trabajos/labios/labios1.jpg"
             alt="Micropigmentación labios Zaragoza" loading="lazy">
        <div class="gallery-item-overlay"><span>Labios</span></div>
      </div>
      <div class="gallery-item reveal reveal-delay-3">
        <img src="<?php echo $img; ?>trabajos/cejas/cejas1.jpg"
             alt="Micropigmentación cejas Zaragoza" loading="lazy">
        <div class="gallery-item-overlay"><span>Cejas · Pelo a pelo</span></div>
      </div>
      <div class="gallery-item reveal reveal-delay-4">
        <img src="<?php echo $img; ?>trabajos/ojos/micropigmentacion-ojos-antes-y-despues.jpg"
             alt="Eyeliner permanente Zaragoza" loading="lazy">
        <div class="gallery-item-overlay"><span>Ojos · Eyeliner</span></div>
      </div>
    </div>

    <div class="gallery-cta reveal">
      <a href="<?php echo home_url('/trabajos/'); ?>" class="btn btn--outline">Ver todos los trabajos</a>
    </div>
  </div>
</section>

<!-- ========== CITA / FILOSOFÍA ========== -->
<section class="quote-section">
  <div class="container">
    <div class="quote-inner reveal">
      <span class="quote-mark" aria-hidden="true">"</span>
      <p class="quote-text">
        Para mí lo más importante no es el técnico, es la persona.
        Quiero que cuando te vayas de aquí sientas que eres más tú,
        no que llevas encima algo que no te representa.
      </p>
      <span class="quote-author">Virginia Aguilera · Micropigmentación Zaragoza</span>
      <div class="quote-stat">
        <strong>+350</strong>
        clientas satisfechas · 98% repetiría · 20+ años de experiencia
      </div>
    </div>
  </div>
</section>

<!-- ========== VIRGINIA — MINI BIO ========== -->
<section class="section" style="background:var(--white)">
  <div class="container">
    <div class="content-grid">
      <div class="content-img reveal">
        <img src="<?php echo $img; ?>virginia-aguilera-micropigmentacion.jpg"
             alt="Virginia Aguilera, especialista en micropigmentación Zaragoza"
             loading="lazy"
             style="aspect-ratio:3/4;object-fit:cover">
      </div>
      <div class="content-text reveal reveal-delay-1">
        <span class="label">Quién soy</span>
        <h2>Hola, soy Virginia.</h2>
        <p>
          Llevo más de veinte años dedicándome en exclusiva a la micropigmentación facial.
          No porque no pudiera hacer otra cosa, sino porque me enamoré de este oficio y
          decidí hacerlo bien, muy bien.
        </p>
        <p>
          Formo a otras profesionales, distribuyo pigmentos de alta calidad, y he competido
          a nivel nacional. Pero lo que más me importa sigue siendo lo mismo de siempre:
          que la persona que se sienta frente a mí se vaya con exactamente lo que quería.
        </p>
        <p>
          Sin presiones. Solo tú contándome lo que buscas
          y yo diciéndote con honestidad si puedo dártelo y cómo.
        </p>
        <a href="<?php echo home_url('/virginia/'); ?>" class="btn btn--primary" style="margin-top:8px">Conoce mi historia</a>
      </div>
    </div>
  </div>
</section>

<!-- ========== TESTIMONIOS ========== -->
<section class="section" style="background:var(--cream)">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Lo que dicen ellas</span>
      <h2>Resultados que hablan por sí solos.</h2>
    </div>
    <div class="services-grid" style="margin-top:48px">
      <div class="reveal reveal-delay-1" style="background:var(--white);border-radius:var(--radius-lg);padding:36px;box-shadow:var(--shadow)">
        <svg viewBox="0 0 24 24" fill="var(--gold)" width="32" height="32" style="margin-bottom:16px"><path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z"/></svg>
        <p style="font-size:1.05rem;line-height:1.7;color:var(--text-dark);font-style:italic">
          "Llevaba años pensando en hacerme las cejas y lo fui posponiendo. Por fin me decidí y me alegro muchísimo. Virginia te escucha, te explica todo, y el resultado es exactamente lo que quería. Natural, discreto y precioso."
        </p>
        <div style="margin-top:24px;display:flex;align-items:center;gap:12px">
          <div style="width:44px;height:44px;border-radius:50%;background:var(--champagne);display:flex;align-items:center;justify-content:center;font-family:var(--font-serif);font-size:1.1rem;color:var(--gold-dark)">JM</div>
          <div>
            <strong style="display:block;font-size:0.95rem">José Martínez</strong>
            <span style="font-size:0.82rem;color:var(--text-light)">Micropigmentación de cejas · Zaragoza</span>
          </div>
        </div>
      </div>

      <div class="reveal reveal-delay-2" style="background:var(--white);border-radius:var(--radius-lg);padding:36px;box-shadow:var(--shadow)">
        <svg viewBox="0 0 24 24" fill="var(--gold)" width="32" height="32" style="margin-bottom:16px"><path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z"/></svg>
        <p style="font-size:1.05rem;line-height:1.7;color:var(--text-dark);font-style:italic">
          "Me hice los labios con Virginia y el cambio ha sido increíble. El color es súper natural y ya no tengo que preocuparme por el maquillaje. Su trato es cálido y profesional, te hace sentir cómoda desde el primer momento."
        </p>
        <div style="margin-top:24px;display:flex;align-items:center;gap:12px">
          <div style="width:44px;height:44px;border-radius:50%;background:var(--champagne);display:flex;align-items:center;justify-content:center;font-family:var(--font-serif);font-size:1.1rem;color:var(--gold-dark)">AG</div>
          <div>
            <strong style="display:block;font-size:0.95rem">Ana Gómez</strong>
            <span style="font-size:0.82rem;color:var(--text-light)">Micropigmentación de labios · Zaragoza</span>
          </div>
        </div>
      </div>

      <div class="reveal reveal-delay-3" style="background:var(--white);border-radius:var(--radius-lg);padding:36px;box-shadow:var(--shadow)">
        <svg viewBox="0 0 24 24" fill="var(--gold)" width="32" height="32" style="margin-bottom:16px"><path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z"/></svg>
        <p style="font-size:1.05rem;line-height:1.7;color:var(--text-dark);font-style:italic">
          "Primera vez que me hago algo así y fue una experiencia genial. Virginia no te presiona, te aconseja con honestidad y el resultado supera cualquier expectativa. Ya tengo cita para el retoque."
        </p>
        <div style="margin-top:24px;display:flex;align-items:center;gap:12px">
          <div style="width:44px;height:44px;border-radius:50%;background:var(--champagne);display:flex;align-items:center;justify-content:center;font-family:var(--font-serif);font-size:1.1rem;color:var(--gold-dark)">CR</div>
          <div>
            <strong style="display:block;font-size:0.95rem">Carmen R.</strong>
            <span style="font-size:0.82rem;color:var(--text-light)">Eyeliner permanente · Zaragoza</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ========== CTA FINAL ========== -->
<section class="cta-block">
  <div class="container">
    <div class="reveal">
      <span class="label" style="color:var(--nude)">Damos el primer paso</span>
      <h2>¿Hablamos?</h2>
      <p>
        Escríbeme por WhatsApp o rellena el formulario y te respondo lo antes posible.
      </p>
      <div class="cta-actions">
        <a href="https://wa.me/34620834002?text=Hola%20Virginia%2C%20me%20gustar%C3%ADa%20pedir%20informaci%C3%B3n%20sobre%20micropigmentaci%C3%B3n."
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
