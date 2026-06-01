<?php
$pageTitle    = 'Blog Micropigmentación Zaragoza — Virginia Aguilera | Consejos y Tendencias';
$pageDesc     = 'Todo sobre micropigmentación: consejos, tendencias, preguntas frecuentes y más. Blog de Virginia Aguilera, especialista en micropigmentación en Zaragoza.';
$pageKeywords = 'blog micropigmentación Zaragoza, consejos micropigmentación, microblading blog, tendencias maquillaje permanente';
$canonicalUrl = 'https://micropigmentacionzgz.es/blog.php';
include 'includes/header.php';

$posts = [
  [
    'slug'    => 'micropigmentacion-o-tatuaje',
    'titulo'  => '¿La micropigmentación es un tatuaje? Te cuento la verdad.',
    'extracto'=> 'Te lo preguntan constantemente, así que lo aclaro de una vez: hay diferencias importantes entre un tatuaje y la micropigmentación. Te explico cuáles y por qué importan.',
    'fecha'   => '15 mayo 2024',
    'cat'     => 'Información',
    'img'     => 'micropigmentacion-cejas.jpg',
  ],
  [
    'slug'    => 'micropigmentacion-famosas',
    'titulo'  => 'Micropigmentación: de Megan Fox a Drew Barrymore, el secreto que nadie confiesa.',
    'extracto'=> '¿Cómo es que siempre tienen las cejas perfectas, llueva o truene? No es genética ni suerte. Te cuento qué hay detrás de esa mirada impecable que no se borra.',
    'fecha'   => '8 abril 2024',
    'cat'     => 'Tendencias',
    'img'     => 'megan-fox-micropigmentacion.jpg',
  ],
  [
    'slug'    => 'cuando-hacerse-micropigmentacion-cejas',
    'titulo'  => '¿Cuándo es el momento de hacerse la micropigmentación de cejas?',
    'extracto'=> 'No hay una respuesta única, pero sí hay señales que te dicen que quizás ha llegado el momento. Y otras que te dicen que mejor espera un poco más.',
    'fecha'   => '20 marzo 2024',
    'cat'     => 'Consejos',
    'img'     => 'micropigmentacion-cejas.jpg',
  ],
  [
    'slug'    => 'mejora-aspecto-rostro-micropigmentacion',
    'titulo'  => 'Cómo la micropigmentación puede cambiar tu cara (y tu mañana).',
    'extracto'=> 'No es exageración: unos pequeños cambios en la ceja, en el contorno del labio o en el delineado del ojo pueden transformar completamente la percepción de tu rostro.',
    'fecha'   => '5 febrero 2024',
    'cat'     => 'Resultados',
    'img'     => 'micropigmentacion-virginia.jpg',
  ],
];
?>

<!-- PAGE HERO -->
<section style="padding:140px 0 60px;background:var(--white)">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Blog</span>
      <h1>Ideas, consejos<br>y algo de realidad.</h1>
      <p style="font-size:1.05rem;margin:16px auto 0;max-width:520px">
        Escribo cuando tengo algo útil que contar. Sin relleno, sin SEO forzado.
        Cosas que te sirven de verdad si estás pensando en micropigmentarte.
      </p>
    </div>
  </div>
</section>

<!-- POSTS GRID -->
<section class="section" style="padding-top:0">
  <div class="container">
    <div class="blog-grid">
      <?php foreach ($posts as $post): ?>
        <article class="blog-card reveal">
          <div class="blog-card-img">
            <img src="/img/<?= htmlspecialchars($post['img']) ?>"
                 alt="<?= htmlspecialchars($post['titulo']) ?>"
                 loading="lazy">
          </div>
          <div class="blog-card-body">
            <div class="blog-card-meta"><?= htmlspecialchars($post['cat']) ?> · <?= htmlspecialchars($post['fecha']) ?></div>
            <h3><?= htmlspecialchars($post['titulo']) ?></h3>
            <p><?= htmlspecialchars($post['extracto']) ?></p>
            <a href="/blog/<?= htmlspecialchars($post['slug']) ?>.php">
              Leer artículo
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </a>
          </div>
        </article>
      <?php endforeach; ?>
    </div>
  </div>
</section>

<!-- CTA -->
<section class="cta-block">
  <div class="container">
    <div class="reveal">
      <span class="label" style="color:var(--nude)">¿Tienes alguna duda?</span>
      <h2>Pregúntame directamente.</h2>
      <p>A veces la respuesta que buscas no está en ningún artículo. Escríbeme y te contesto yo.</p>
      <div class="cta-actions">
        <a href="https://wa.me/34620834002" class="btn btn--whatsapp" target="_blank" rel="noopener">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.122 1.524 5.863L.057 23.57a.75.75 0 00.918.918l5.702-1.467A11.94 11.94 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75A9.74 9.74 0 016.31 19.94l-.387-.23-3.384.87.886-3.295-.25-.404A9.71 9.71 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
          Pregúntame por WhatsApp
        </a>
      </div>
    </div>
  </div>
</section>

<?php include 'includes/footer.php'; ?>
