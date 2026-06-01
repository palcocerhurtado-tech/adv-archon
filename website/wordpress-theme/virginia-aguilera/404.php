<?php
/**
 * 404 Not Found template
 */
get_header();
?>

<section style="padding:160px 0 100px;text-align:center;background:var(--white)">
  <div class="container" style="max-width:600px">
    <span class="label">Error 404</span>
    <h1 style="margin:12px 0 24px;font-size:clamp(2rem,5vw,3.5rem)">Página no encontrada</h1>
    <p style="font-size:1.1rem;margin-bottom:40px">
      Lo sentimos, la página que buscas no existe o ha sido movida.
      Puede que hayas seguido un enlace antiguo o cometido un error al escribir la dirección.
    </p>
    <div style="display:flex;gap:14px;justify-content:center;flex-wrap:wrap">
      <a href="<?php echo home_url('/'); ?>" class="btn btn--primary">Volver al inicio</a>
      <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--outline">Contactar</a>
    </div>
  </div>
</section>

<?php get_footer(); ?>
