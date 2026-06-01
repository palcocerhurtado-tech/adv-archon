<?php
$logo_url = get_template_directory_uri() . '/img/logotipo-micropigmentacion-virginia.png';
?>
<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
<meta charset="<?php bloginfo('charset'); ?>">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="<?php echo get_template_directory_uri(); ?>/img/favicon.ico" sizes="any">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<?php wp_head(); ?>
</head>
<body <?php body_class(); ?>>
<?php wp_body_open(); ?>

<!-- WhatsApp flotante -->
<a href="https://wa.me/34620834002" class="whatsapp-float" target="_blank" rel="noopener" aria-label="Escríbenos por WhatsApp">
  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.122 1.524 5.863L.057 23.57a.75.75 0 00.918.918l5.702-1.467A11.94 11.94 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75A9.74 9.74 0 016.31 19.94l-.387-.23-3.384.87.886-3.295-.25-.404A9.71 9.71 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
</a>

<!-- Header -->
<header class="site-header" id="site-header">
  <div class="container">
    <div class="header-inner">

      <a href="<?php echo home_url('/'); ?>" class="site-logo">
        <img src="<?php echo esc_url($logo_url); ?>"
             alt="<?php bloginfo('name'); ?> Zaragoza"
             onerror="this.style.display='none';this.nextElementSibling.style.display='inline'">
        <span style="display:none"><?php bloginfo('name'); ?></span>
      </a>

      <nav class="site-nav" aria-label="Navegación principal">
        <ul>
          <li class="nav-dropdown">
            <a href="<?php echo home_url('/micropigmentacion-cejas/'); ?>">Servicios</a>
            <div class="nav-dropdown-menu">
              <a href="<?php echo home_url('/micropigmentacion-cejas/'); ?>">Cejas</a>
              <a href="<?php echo home_url('/micropigmentacion-ojos/'); ?>">Ojos</a>
              <a href="<?php echo home_url('/micropigmentacion-labios/'); ?>">Labios</a>
            </div>
          </li>
          <li><a href="<?php echo home_url('/trabajos/'); ?>">Trabajos</a></li>
          <li><a href="<?php echo home_url('/virginia/'); ?>">Virginia</a></li>
          <li><a href="<?php echo home_url('/blog/'); ?>">Blog</a></li>
          <li><a href="<?php echo home_url('/contacto/'); ?>">Contacto</a></li>
          <?php if (function_exists('WC')): ?>
          <li><a href="<?php echo wc_get_page_permalink('shop'); ?>">Tienda</a></li>
          <?php endif; ?>
        </ul>
      </nav>

      <div class="nav-cta" style="display:flex;align-items:center;gap:14px">
        <?php if (function_exists('WC')): ?>
        <a href="<?php echo wc_get_cart_url(); ?>" class="nav-cart" aria-label="Carrito de compra">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="22" height="22"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/></svg>
          <span class="cart-count"><?php echo virginia_cart_count(); ?></span>
        </a>
        <?php endif; ?>
        <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--primary">Pide tu cita</a>
      </div>

      <button class="hamburger" aria-label="Abrir menú" aria-expanded="false">
        <span></span><span></span><span></span>
      </button>

    </div>
  </div>
</header>

<!-- Mobile nav -->
<nav class="mobile-nav" aria-label="Menú móvil">
  <a href="<?php echo home_url('/'); ?>">Inicio</a>
  <a href="<?php echo home_url('/micropigmentacion-cejas/'); ?>">Cejas</a>
  <a href="<?php echo home_url('/micropigmentacion-ojos/'); ?>">Ojos</a>
  <a href="<?php echo home_url('/micropigmentacion-labios/'); ?>">Labios</a>
  <a href="<?php echo home_url('/trabajos/'); ?>">Trabajos</a>
  <a href="<?php echo home_url('/virginia/'); ?>">Virginia</a>
  <a href="<?php echo home_url('/blog/'); ?>">Blog</a>
  <a href="<?php echo home_url('/contacto/'); ?>">Contacto</a>
  <?php if (function_exists('WC')): ?>
  <a href="<?php echo wc_get_page_permalink('shop'); ?>">Tienda</a>
  <?php endif; ?>
  <div class="mobile-nav-cta">
    <a href="<?php echo home_url('/contacto/'); ?>" class="btn btn--primary">Pide tu cita</a>
  </div>
</nav>

<main>
