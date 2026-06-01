<?php
/*
 * Template Name: Microblading Zaragoza
 */
get_header();
$img = get_template_directory_uri() . '/img/';
?>

<!-- PAGE HERO -->
<section class="page-hero" aria-label="Microblading Zaragoza">
  <div class="page-hero-bg" style="background-image:url('<?php echo $img; ?>microblading-zaragoza-ent.gif');background-size:cover"></div>
  <div class="container">
    <div class="page-hero-content">
      <span class="label">Técnica exclusiva</span>
      <h1>Microblading<br>en Zaragoza</h1>
      <p>Cejas hiperrealistas, pelo a pelo. Como si siempre hubieras tenido esas cejas.</p>
    </div>
  </div>
</section>

<!-- INTRO — diferencia microblading vs micropigmentación -->
<section class="section" style="background:var(--white)">
  <div class="container">
    <div class="content-grid">
      <div class="content-text reveal">
        <span class="label">¿Qué es exactamente?</span>
        <h2>Microblading vs micropigmentación clásica.</h2>
        <p>
          Mucha gente los confunde porque el resultado final puede ser muy parecido.
          La diferencia está en la técnica y en el tipo de trazo que se consigue.
        </p>
        <p>
          La <strong>micropigmentación clásica</strong> se realiza con máquina. Permite
          mayor control de la presión y la velocidad, y los resultados duran más en general.
        </p>
        <p>
          El <strong>microblading</strong> es una técnica manual: se trabaja con una cuchilla
          muy fina que deposita el pigmento con trazos ultra-delgados, imitando cada pelo
          de forma hiperrealista. El resultado es extraordinariamente natural, casi imposible
          de distinguir de las cejas reales.
        </p>
        <p>
          ¿Cuál es mejor? Depende de tu piel y de lo que busques. En la consulta gratuita
          te digo cuál te conviene más.
        </p>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--primary">¿Es el microblading para ti? Cuéntame</a>
      </div>
      <div class="content-img reveal reveal-delay-1">
        <img src="<?php echo $img; ?>microblading-proceso.jpg"
             alt="Proceso microblading cejas Zaragoza"
             loading="lazy"
             style="aspect-ratio:4/5;object-fit:cover">
      </div>
    </div>
  </div>
</section>

<!-- COMPARATIVA VISUAL -->
<section class="section">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Las diferencias</span>
      <h2>Microblading vs Micropigmentación</h2>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:32px;margin-top:48px">
      <div class="reveal" style="background:var(--white);border-radius:var(--radius-lg);padding:36px;border:1.5px solid var(--border)">
        <div class="label" style="margin-bottom:16px">Microblading</div>
        <ul style="display:flex;flex-direction:column;gap:14px">
          <li style="display:flex;gap:12px"><span style="color:var(--gold);font-weight:700;flex-shrink:0">&#10003;</span> Técnica 100% manual</li>
          <li style="display:flex;gap:12px"><span style="color:var(--gold);font-weight:700;flex-shrink:0">&#10003;</span> Trazos ultra-finos, hiperrealistas</li>
          <li style="display:flex;gap:12px"><span style="color:var(--gold);font-weight:700;flex-shrink:0">&#10003;</span> Resultado más suave y orgánico</li>
          <li style="display:flex;gap:12px"><span style="color:var(--gold);font-weight:700;flex-shrink:0">&#10003;</span> Ideal para pieles normales o secas</li>
          <li style="display:flex;gap:12px"><span style="color:var(--text-light);flex-shrink:0">&middot;</span> Duración: 1-3 años según piel</li>
          <li style="display:flex;gap:12px"><span style="color:var(--text-light);flex-shrink:0">&middot;</span> Puede difuminar antes en pieles grasas</li>
        </ul>
      </div>
      <div class="reveal reveal-delay-1" style="background:var(--champagne);border-radius:var(--radius-lg);padding:36px;border:1.5px solid var(--nude)">
        <div class="label" style="margin-bottom:16px">Micropigmentación con máquina</div>
        <ul style="display:flex;flex-direction:column;gap:14px">
          <li style="display:flex;gap:12px"><span style="color:var(--gold);font-weight:700;flex-shrink:0">&#10003;</span> Técnica con máquina profesional</li>
          <li style="display:flex;gap:12px"><span style="color:var(--gold);font-weight:700;flex-shrink:0">&#10003;</span> Mayor control y precisión de trazo</li>
          <li style="display:flex;gap:12px"><span style="color:var(--gold);font-weight:700;flex-shrink:0">&#10003;</span> Funciona bien en todo tipo de piel</li>
          <li style="display:flex;gap:12px"><span style="color:var(--gold);font-weight:700;flex-shrink:0">&#10003;</span> Resultados más duraderos</li>
          <li style="display:flex;gap:12px"><span style="color:var(--text-light);flex-shrink:0">&middot;</span> Duración: 1-3 años con retoques</li>
          <li style="display:flex;gap:12px"><span style="color:var(--text-light);flex-shrink:0">&middot;</span> Permite técnicas combinadas (sombreado)</li>
        </ul>
      </div>
    </div>
  </div>
</section>

<!-- GALERÍA MICROBLADING -->
<section class="section" style="background:var(--white)">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Resultados</span>
      <h2>Trabajos de microblading.</h2>
      <p style="margin:14px auto 0">Pelo a pelo. Naturales. Sin que nadie sepa que llevas algo.</p>
    </div>
    <div class="gallery-grid" style="margin-top:40px">
      <?php
      $microblading_imgs = [
        ['microblading-cejas-zaragoza2.jpg', 'Microblading cejas resultado Zaragoza'],
        ['microblading-cejas-zaragoza3.jpg', 'Cejas microblading antes y después'],
        ['microblading-cejas-zaragoza4.jpg', 'Microblading pelo a pelo natural'],
        ['microblading-cejas-zaragoza5.jpg', 'Técnica microblading Zaragoza'],
      ];
      foreach ($microblading_imgs as $mi) : ?>
        <div class="gallery-item reveal">
          <img src="<?php echo $img; ?>trabajos/cejas/<?php echo esc_attr($mi[0]); ?>"
               alt="<?php echo esc_attr($mi[1]); ?>"
               loading="lazy">
          <div class="gallery-item-overlay"><span>Microblading</span></div>
        </div>
      <?php endforeach; ?>
    </div>
  </div>
</section>

<!-- FAQ -->
<section class="section">
  <div class="container" style="max-width:740px">
    <div class="text-center reveal">
      <span class="label">Preguntas frecuentes</span>
      <h2>Lo que más me preguntan sobre microblading.</h2>
    </div>
    <div class="faq-list">
      <div class="faq-item">
        <button class="faq-question">
          ¿Es el microblading para todo el mundo?
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <div class="faq-answer">
          <p>
            No exactamente. La técnica manual del microblading funciona especialmente bien
            en pieles normales o secas. En pieles muy grasas, los trazos tienden a difuminarse
            antes. En esos casos suelo recomendar la técnica combinada o la micropigmentación
            con máquina. Te lo digo en la primera consulta.
          </p>
        </div>
      </div>
      <div class="faq-item">
        <button class="faq-question">
          ¿Cuánto dura el microblading?
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <div class="faq-answer">
          <p>
            En general, entre 1 y 3 años. La duración depende mucho del tipo de piel,
            los hábitos de cuidado y la exposición solar. Con un retoque anual puedes
            mantener el resultado indefinidamente.
          </p>
        </div>
      </div>
      <div class="faq-item">
        <button class="faq-question">
          ¿Se puede hacer sobre micropigmentación anterior?
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <div class="faq-answer">
          <p>
            Depende del estado en que esté la micropigmentación anterior. En algunos casos
            sí se puede trabajar encima, en otros hay que esperar a que se desvanezca más.
            Te lo digo sin rodeos en la consulta tras ver el estado de tus cejas actuales.
          </p>
        </div>
      </div>
      <div class="faq-item">
        <button class="faq-question">
          ¿Es doloroso?
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <div class="faq-answer">
          <p>
            Aplicamos anestesia tópica antes de empezar. La mayoría de las personas lo
            describe como una sensación de presión suave, muy tolerable. Cada persona
            tiene un umbral diferente, pero en general es un proceso muy llevadero.
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
      <span class="label" style="color:var(--nude)">Hablemos de tus cejas</span>
      <h2>¿Es el microblading para ti?</h2>
      <p>Cuéntame tu caso. La primera consulta es gratuita y sin ningún compromiso.</p>
      <div class="cta-actions">
        <a href="https://wa.me/34620834002?text=Hola%20Virginia%2C%20me%20gustar%C3%ADa%20informaci%C3%B3n%20sobre%20microblading%20en%20Zaragoza."
           class="btn btn--whatsapp" target="_blank" rel="noopener">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.122 1.524 5.863L.057 23.57a.75.75 0 00.918.918l5.702-1.467A11.94 11.94 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75A9.74 9.74 0 016.31 19.94l-.387-.23-3.384.87.886-3.295-.25-.404A9.71 9.71 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
          Cuéntame tu caso
        </a>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--white">Formulario</a>
      </div>
    </div>
  </div>
</section>

<?php get_footer(); ?>
