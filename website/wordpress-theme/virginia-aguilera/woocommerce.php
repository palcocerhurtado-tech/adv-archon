<?php
/**
 * WooCommerce base template — overrides default WC layout with our design
 */
get_header();
?>

<!-- PAGE HERO -->
<section style="padding:140px 0 60px;background:var(--white)">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Tienda online</span>
      <?php if (is_shop()): ?>
        <h1>Pigmentos y materiales<br>de alta calidad.</h1>
        <p style="font-size:1.05rem;margin:16px auto 0;max-width:520px">
          Los mismos materiales que uso en consulta. Con registro sanitario europeo,
          para profesionales y entusiastas que no quieren comprometer la calidad.
        </p>
      <?php elseif (is_product_category()): ?>
        <h1><?php single_cat_title(); ?></h1>
      <?php elseif (is_product()): ?>
        <h1 style="font-size:clamp(1.4rem,3vw,2.2rem)"><?php the_title(); ?></h1>
      <?php else: ?>
        <h1><?php woocommerce_page_title(); ?></h1>
      <?php endif; ?>
    </div>
  </div>
</section>

<!-- WOOCOMMERCE CONTENT -->
<section class="section" style="padding-top:40px;background:var(--cream)">
  <div class="container">
    <?php woocommerce_content(); ?>
  </div>
</section>

<?php get_footer(); ?>
