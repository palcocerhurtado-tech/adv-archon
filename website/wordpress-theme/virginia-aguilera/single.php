<?php
/**
 * Single blog post template
 */
get_header();
?>

<?php while (have_posts()) : the_post(); ?>

<section style="padding:140px 0 40px;background:var(--white)">
  <div class="container" style="max-width:740px">
    <a href="<?php echo home_url('/blog/'); ?>" style="font-size:0.85rem;color:var(--gold);font-weight:600;display:inline-flex;align-items:center;gap:6px;margin-bottom:32px">
      &#8592; Volver al blog
    </a>
    <?php
    $categories = get_the_category();
    $cat_name = 'Blog';
    if (!empty($categories)) {
        $raw = $categories[0]->name;
        $tr = ['Uncategorized'=>'Blog','Uncategorised'=>'Blog','Sin categoría'=>'Blog','News'=>'Noticias','Tips'=>'Consejos','Results'=>'Resultados','Techniques'=>'Técnicas','Trends'=>'Tendencias'];
        $cat_name = isset($tr[$raw]) ? $tr[$raw] : esc_html($raw);
    }
    ?>
    <span class="label"><?php echo $cat_name; ?> · <?php echo virginia_fecha_es(); ?></span>
    <h1 style="margin:12px 0 32px"><?php the_title(); ?></h1>
    <?php if (has_post_thumbnail()) : ?>
      <img src="<?php the_post_thumbnail_url('large'); ?>"
           alt="<?php the_title_attribute(); ?>"
           style="width:100%;border-radius:var(--radius-lg);margin-bottom:40px"
           loading="eager">
    <?php endif; ?>
  </div>
</section>

<section class="post-content container">
  <?php the_content(); ?>

  <div style="margin-top:40px;padding-top:32px;border-top:1px solid var(--border)">
    <p style="margin-bottom:20px;font-size:0.9rem;color:var(--text-light)">¿Tienes dudas? Escríbeme.</p>
    <div style="display:flex;gap:14px;flex-wrap:wrap">
      <a href="<?php echo home_url('/trabajos/'); ?>" class="btn btn--outline">Ver trabajos</a>
      <a href="https://wa.me/34620834002?text=Hola%20Virginia%2C%20me%20gustar%C3%ADa%20pedir%20informaci%C3%B3n."
         class="btn btn--whatsapp" target="_blank" rel="noopener">
        <svg viewBox="0 0 24 24" fill="currentColor" style="width:20px;height:20px"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.122 1.524 5.863L.057 23.57a.75.75 0 00.918.918l5.702-1.467A11.94 11.94 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75A9.74 9.74 0 016.31 19.94l-.387-.23-3.384.87.886-3.295-.25-.404A9.71 9.71 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
        Pide tu consulta
      </a>
    </div>
  </div>
</section>

<div style="height:80px"></div>

<?php endwhile; ?>

<?php get_footer(); ?>
