<?php
/*
 * Template Name: Micropigmentación de Labios
 */
get_header();
$img = get_template_directory_uri() . '/img/';
?>

<!-- PAGE HERO -->
<section class="page-hero" aria-label="Micropigmentación de labios">
  <div class="page-hero-bg" style="background-image:url('<?php echo $img; ?>banner-labios-lateral.jpg')"></div>
  <div class="container">
    <div class="page-hero-content">
      <span class="label">Servicio</span>
      <h1>Micropigmentación<br>de labios</h1>
      <p>Contorno perfecto, color natural, aspecto rejuvenecido. Todo el día, todos los días.</p>
    </div>
  </div>
</section>

<!-- INTRO -->
<section class="section" style="background:var(--white)">
  <div class="container">
    <div class="content-grid">
      <div class="content-text reveal">
        <span class="label">Por qué los labios</span>
        <h2>Unos labios definidos cambian el rostro entero.</h2>
        <p>
          Con los años, el contorno de los labios tiende a difuminarse y perder definición.
          O simplemente tienes unos labios más finos de lo que te gustaría, o asimétricos,
          o con un perfil que no te favorece del todo.
        </p>
        <p>
          La micropigmentación de labios no es hacerse "los labios de otra". Es realzar
          los tuyos: definir el contorno, añadir un toque de color natural y rejuvenecer
          el gesto de forma muy sutil.
        </p>
        <p>
          El resultado es tan natural que la gente no va a saber qué has hecho.
          Solo van a notar que estás más radiante.
        </p>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--primary">Reserva tu cita</a>
      </div>
      <div class="content-img reveal reveal-delay-1">
        <img src="<?php echo $img; ?>micropigmentacion-labios.jpg"
             alt="Micropigmentación de labios resultado natural Zaragoza"
             loading="lazy"
             style="aspect-ratio:4/5;object-fit:cover">
      </div>
    </div>
  </div>
</section>

<!-- TÉCNICAS / RESULTADOS -->
<section class="section">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Lo que conseguimos</span>
      <h2>Resultados reales, con matices.</h2>
    </div>

    <div class="tecnicas-grid" style="grid-template-columns:repeat(2,1fr)">
      <div class="tecnica-card reveal reveal-delay-1">
        <h4>Contorno definido</h4>
        <p>
          Marcamos la línea del labio con precisión. Corregimos asimetrías, recuperamos
          el arco de Cupido, definimos el perfil. El resultado es inmediato y permanente.
        </p>
      </div>
      <div class="tecnica-card reveal reveal-delay-2">
        <h4>Color y relleno (aquarelle)</h4>
        <p>
          Además del contorno, añadimos pigmento en el interior del labio. Un color suave,
          natural, que imita el tono natural de tu labio pero más uniforme y luminoso.
        </p>
      </div>
      <div class="tecnica-card reveal reveal-delay-3">
        <h4>Efecto volumen</h4>
        <p>
          Con una técnica de sombreado y degradado podemos dar sensación de más volumen
          sin necesidad de rellenos. El truco está en cómo difuminamos el pigmento.
        </p>
      </div>
      <div class="tecnica-card reveal reveal-delay-4">
        <h4>Corrección de cicatrices</h4>
        <p>
          Si tienes cicatrices en la zona de los labios (labio leporino corregido, por ejemplo),
          la micropigmentación puede ayudar a disimular la diferencia de color.
        </p>
      </div>
    </div>
  </div>
</section>

<!-- PROCESO + TRANQUILIDAD -->
<section class="section" style="background:var(--white)">
  <div class="container">
    <div class="content-grid reverse">
      <div class="content-img reveal">
        <img src="<?php echo $img; ?>trabajos/labios/labios1.jpg"
             alt="Antes y después micropigmentación labios Zaragoza"
             loading="lazy"
             style="aspect-ratio:1;object-fit:cover">
      </div>
      <div class="content-text reveal reveal-delay-1">
        <span class="label">Sin miedos</span>
        <h2>Más cómodo de lo que crees.</h2>
        <p>
          Lo primero que aplico es anestesia tópica. Los labios son una zona sensible,
          pero con anestesia la mayoría de las personas describen la sesión como muy llevadera.
        </p>
        <p>
          Después del tratamiento, los labios pueden estar algo hinchados y el color se verá
          más intenso los primeros días. Es completamente normal y va pasando solo.
        </p>
        <p>
          Entre los días 4 y 7 puede aparecer una pequeña costrita — es la piel cicatrizando
          y el pigmento asentándose. <strong>No la toques, no la arranques.</strong>
          Cae sola y con ella el exceso de color. El resultado final lo ves a las 4-6 semanas.
        </p>
        <p>
          Te doy todas las instrucciones por escrito el mismo día de la sesión.
          Nada de sorpresas.
        </p>
      </div>
    </div>
  </div>
</section>

<!-- PROCESO PASOS -->
<section class="section">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">El proceso</span>
      <h2>Paso a paso.</h2>
    </div>
    <div class="proceso-steps" style="max-width:680px;margin:0 auto">
      <div class="proceso-step reveal">
        <div class="step-number">1</div>
        <div class="step-body">
          <h4>Primera cita</h4>
          <p>Hablamos de tu labio, el tono que buscas, las correcciones que quieres.</p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">2</div>
        <div class="step-body">
          <h4>Diseño del contorno</h4>
          <p>Diseñamos el perfil sobre tus labios antes de empezar. Tú lo apruebas. Solo procedemos cuando estás segura.</p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">3</div>
        <div class="step-body">
          <h4>Anestesia + aplicación</h4>
          <p>Anestesia tópica primero, aplicación del pigmento después. La sesión dura entre 90 y 120 minutos.</p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">4</div>
        <div class="step-body">
          <h4>Cicatrización (4-6 semanas)</h4>
          <p>Sigue las instrucciones, evita el sol y los labiales. La costrita es normal y cae sola entre los días 5 y 10.</p>
        </div>
      </div>
      <div class="proceso-step reveal">
        <div class="step-number">5</div>
        <div class="step-body">
          <h4>Revisión incluida</h4>
          <p>A las 6-8 semanas revisamos juntas el resultado y ajustamos lo que sea necesario.</p>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- GALERÍA LABIOS -->
<section class="section" style="background:var(--white)">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Resultados</span>
      <h2>Algunos trabajos de labios.</h2>
    </div>
    <div class="gallery-grid" style="margin-top:40px">
      <?php
      $labios_imgs = [
        ['labios2.jpg', 'Micropigmentación labios — contorno y color'],
        ['labios3.jpg', 'Labios definidos antes y después Zaragoza'],
        ['micropigmentacion-labios-zaragoza1.jpg', 'Resultado micropigmentación labios'],
        ['micropigmentacion-labios-zaragoza2.jpg', 'Labios naturales con micropigmentación'],
      ];
      foreach ($labios_imgs as $li) : ?>
        <div class="gallery-item reveal">
          <img src="<?php echo $img; ?>trabajos/labios/<?php echo esc_attr($li[0]); ?>"
               alt="<?php echo esc_attr($li[1]); ?>"
               loading="lazy">
          <div class="gallery-item-overlay"><span>Labios</span></div>
        </div>
      <?php endforeach; ?>
    </div>
    <div class="gallery-cta reveal">
      <a href="<?php echo home_url('/trabajos/'); ?>" class="btn btn--outline">Ver todos los trabajos de labios</a>
    </div>
  </div>
</section>

<!-- CTA -->
<section class="cta-block">
  <div class="container">
    <div class="reveal">
      <span class="label" style="color:var(--nude)">Da el paso</span>
      <h2>Reserva tu cita.</h2>
      <p>Escríbeme y lo hablamos. Te respondo lo antes posible.</p>
      <div class="cta-actions">
        <a href="https://wa.me/34620834002?text=Hola%20Virginia%2C%20me%20gustar%C3%ADa%20informaci%C3%B3n%20sobre%20micropigmentaci%C3%B3n%20de%20labios."
           class="btn btn--whatsapp" target="_blank" rel="noopener">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.122 1.524 5.863L.057 23.57a.75.75 0 00.918.918l5.702-1.467A11.94 11.94 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75A9.74 9.74 0 016.31 19.94l-.387-.23-3.384.87.886-3.295-.25-.404A9.71 9.71 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
          Reserva tu cita
        </a>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--white">Formulario</a>
      </div>
    </div>
  </div>
</section>

<?php get_footer(); ?>
