<?php
/*
 * Template Name: Galería de Trabajos
 */
get_header();
$img = get_template_directory_uri() . '/img/';

/* Image data arrays */
$trabajos_cejas = [
  ['microblading-cejas-zaragoza2.jpg', 'Microblading cejas Zaragoza'],
  ['microblading-cejas-zaragoza3.jpg', 'Cejas microblading — resultado natural'],
  ['cejas1.jpg', 'Micropigmentación cejas Zaragoza'],
  ['cejas2.jpg', 'Cejas permanentes diseño personalizado'],
  ['cejas3.jpg', 'Micropigmentación cejas antes y después'],
  ['cejas4.jpg', 'Diseño cejas Zaragoza'],
  ['microblading-cejas-zaragoza4.jpg', 'Cejas microblading pelo a pelo'],
  ['microblading-cejas-zaragoza5.jpg', 'Microblading natural Zaragoza'],
  ['tecnica-ceja-pixelada.jpg', 'Técnica cejas pixeladas Zaragoza'],
  ['micropigmentacion-ceja-antes-y-despues.jpg', 'Antes y después cejas micropigmentación'],
  ['cejas6.jpg', 'Cejas naturales micropigmentadas'],
  ['cejas7.jpg', 'Micropigmentación cejas — resultado final'],
  ['microblading-cejas-zaragoza8.jpg', 'Microblading Zaragoza — cejas 2023'],
  ['microblading-cejas-zaragoza9.jpg', 'Cejas perfectas microblading'],
  ['cejas-noviembre-2021-1.jpg', 'Cejas micropigmentación noviembre 2021'],
  ['cejas-noviembre-2021-2.jpg', 'Resultado cejas micropigmentación'],
];

$trabajos_ojos = [
  ['micropigmentacion-ojos-antes-y-despues.jpg', 'Eyeliner permanente antes y después Zaragoza'],
  ['1.jpg', 'Eyeliner permanente resultado'],
  ['2.jpg', 'Delineado permanente Zaragoza'],
  ['3.jpg', 'Micropigmentación ojos resultado natural'],
];

$trabajos_labios = [
  ['labios1.jpg', 'Micropigmentación labios Zaragoza'],
  ['labios2.jpg', 'Labios definidos — resultado natural'],
  ['labios3.jpg', 'Micropigmentación labios antes y después'],
  ['micropigmentacion-labios-zaragoza1.jpg', 'Labios micropigmentados resultado'],
  ['micropigmentacion-labios-zaragoza2.jpg', 'Contorno labios permanente Zaragoza'],
  ['labios-noviembre-2021-1.jpg', 'Labios micropigmentación resultado 2021'],
];
?>

<!-- PAGE HERO -->
<section class="page-hero" aria-label="Galería de trabajos">
  <div class="page-hero-bg" style="background-image:url('<?php echo $img; ?>trabajos/cejas/microblading-cejas-zaragoza2.jpg')"></div>
  <div class="container">
    <div class="page-hero-content">
      <span class="label">Trabajos reales</span>
      <h1>Galería de<br>resultados</h1>
      <p>Cada caso es único. Cada resultado, también.</p>
    </div>
  </div>
</section>

<!-- INTRO + FILTROS -->
<section class="section">
  <div class="container">
    <div class="text-center reveal" style="max-width:620px;margin:0 auto 48px">
      <span class="label">Los trabajos</span>
      <h2>Estos son algunos de<br>mis trabajos favoritos.</h2>
      <p>
        Lo que ves aquí no son fotos de catálogo. Son resultados reales, de personas reales
        que se sentaron en mi silla con una ilusión y se fueron con el resultado que querían.
      </p>
    </div>

    <!-- Filtros -->
    <div class="gallery-filters reveal">
      <button class="filter-btn active" data-filter="all">Todos</button>
      <button class="filter-btn" data-filter="cejas">Cejas</button>
      <button class="filter-btn" data-filter="ojos">Ojos</button>
      <button class="filter-btn" data-filter="labios">Labios</button>
    </div>

    <!-- Masonry -->
    <div class="masonry-grid">
      <?php foreach ($trabajos_cejas as $item) : ?>
        <div class="masonry-item reveal" data-cat="cejas">
          <img src="<?php echo $img; ?>trabajos/cejas/<?php echo esc_attr($item[0]); ?>"
               alt="<?php echo esc_attr($item[1]); ?>"
               loading="lazy">
          <div class="masonry-overlay"><span>Cejas</span></div>
        </div>
      <?php endforeach; ?>

      <?php foreach ($trabajos_ojos as $item) : ?>
        <div class="masonry-item reveal" data-cat="ojos">
          <img src="<?php echo $img; ?>trabajos/ojos/<?php echo esc_attr($item[0]); ?>"
               alt="<?php echo esc_attr($item[1]); ?>"
               loading="lazy">
          <div class="masonry-overlay"><span>Ojos · Eyeliner</span></div>
        </div>
      <?php endforeach; ?>

      <?php foreach ($trabajos_labios as $item) : ?>
        <div class="masonry-item reveal" data-cat="labios">
          <img src="<?php echo $img; ?>trabajos/labios/<?php echo esc_attr($item[0]); ?>"
               alt="<?php echo esc_attr($item[1]); ?>"
               loading="lazy">
          <div class="masonry-overlay"><span>Labios</span></div>
        </div>
      <?php endforeach; ?>
    </div>
  </div>
</section>

<!-- CTA -->
<section class="cta-block">
  <div class="container">
    <div class="reveal">
      <span class="label" style="color:var(--nude)">El siguiente puede ser el tuyo</span>
      <h2>¿Añadimos el tuyo a esta galería?</h2>
      <p>Escríbeme y hablamos. Primera consulta siempre gratuita.</p>
      <div class="cta-actions">
        <a href="https://wa.me/34620834002" class="btn btn--whatsapp" target="_blank" rel="noopener">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.122 1.524 5.863L.057 23.57a.75.75 0 00.918.918l5.702-1.467A11.94 11.94 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75A9.74 9.74 0 016.31 19.94l-.387-.23-3.384.87.886-3.295-.25-.404A9.71 9.71 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
          Pide tu cita
        </a>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--white">Contacto</a>
      </div>
    </div>
  </div>
</section>

<?php get_footer(); ?>
