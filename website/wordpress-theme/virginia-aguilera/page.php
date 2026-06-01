<?php
/**
 * Generic page template
 */
get_header();
?>

<section style="padding:140px 0 80px">
  <div class="container" style="max-width:740px">
    <?php while (have_posts()) : the_post(); ?>
      <h1 style="margin-bottom:40px"><?php the_title(); ?></h1>
      <div class="post-content"><?php the_content(); ?></div>
    <?php endwhile; ?>
  </div>
</section>

<?php get_footer(); ?>
