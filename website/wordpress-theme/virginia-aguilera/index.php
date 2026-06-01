<?php
/**
 * Fallback template — shown when no other template matches.
 */
get_header();
?>

<section style="padding:140px 0 80px">
  <div class="container">
    <?php if (have_posts()) : while (have_posts()) : the_post(); ?>
      <h1 style="margin-bottom:24px"><?php the_title(); ?></h1>
      <div class="post-content"><?php the_content(); ?></div>
    <?php endwhile; else : ?>
      <h1>Página no encontrada</h1>
      <p>El contenido que buscas no está disponible. <a href="<?php echo home_url('/'); ?>" style="color:var(--gold)">Volver al inicio</a>.</p>
    <?php endif; ?>
  </div>
</section>

<?php get_footer(); ?>
