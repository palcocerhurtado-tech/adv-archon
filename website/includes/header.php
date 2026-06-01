<?php
/* Reusable header — set $pageTitle, $pageDesc, $pageImage, $pageKeywords before including */
$pageTitle    = $pageTitle    ?? 'Virginia Aguilera — Micropigmentación Zaragoza';
$pageDesc     = $pageDesc     ?? 'Especialista en micropigmentación de cejas, ojos y labios en Zaragoza. Primera consulta gratuita. Llama o escríbeme: 620 834 002.';
$pageImage    = $pageImage    ?? 'https://micropigmentacionzgz.es/img/virginia-aguilera-micropigmentacion.jpg';
$pageKeywords = $pageKeywords ?? 'micropigmentación Zaragoza, microblading Zaragoza, cejas permanentes Zaragoza, eyeliner permanente, micropigmentación labios Zaragoza';
$canonicalUrl = $canonicalUrl ?? 'https://micropigmentacionzgz.es/' . basename($_SERVER['PHP_SELF']);
?>
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title><?= htmlspecialchars($pageTitle) ?></title>
  <meta name="description" content="<?= htmlspecialchars($pageDesc) ?>">
  <meta name="keywords"    content="<?= htmlspecialchars($pageKeywords) ?>">
  <link rel="canonical"    href="<?= htmlspecialchars($canonicalUrl) ?>">

  <!-- Open Graph -->
  <meta property="og:type"        content="website">
  <meta property="og:title"       content="<?= htmlspecialchars($pageTitle) ?>">
  <meta property="og:description" content="<?= htmlspecialchars($pageDesc) ?>">
  <meta property="og:image"       content="<?= htmlspecialchars($pageImage) ?>">
  <meta property="og:url"         content="<?= htmlspecialchars($canonicalUrl) ?>">
  <meta property="og:locale"      content="es_ES">
  <meta property="og:site_name"   content="Virginia Aguilera Micropigmentación">

  <!-- Twitter Card -->
  <meta name="twitter:card"        content="summary_large_image">
  <meta name="twitter:title"       content="<?= htmlspecialchars($pageTitle) ?>">
  <meta name="twitter:description" content="<?= htmlspecialchars($pageDesc) ?>">
  <meta name="twitter:image"       content="<?= htmlspecialchars($pageImage) ?>">

  <!-- Favicon -->
  <link rel="icon" href="/img/favicon.ico" sizes="any">

  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">

  <!-- CSS -->
  <link rel="stylesheet" href="/css/style.css">
</head>
<body>

<!-- WhatsApp flotante -->
<a href="https://wa.me/34620834002" class="whatsapp-float" target="_blank" rel="noopener" aria-label="Escríbenos por WhatsApp">
  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.122 1.524 5.863L.057 23.57a.75.75 0 00.918.918l5.702-1.467A11.94 11.94 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75A9.74 9.74 0 016.31 19.94l-.387-.23-3.384.87.886-3.295-.25-.404A9.71 9.71 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
</a>

<!-- Header -->
<header class="site-header" id="site-header">
  <div class="container">
    <div class="header-inner">

      <a href="/index.php" class="site-logo">
        <img src="/img/logotipo-micropigmentacion-virginia.png"
             alt="Virginia Aguilera Micropigmentación Zaragoza"
             onerror="this.style.display='none';this.nextElementSibling.style.display='inline'">
        <span style="display:none">Virginia Aguilera</span>
      </a>

      <nav class="site-nav" aria-label="Navegación principal">
        <ul>
          <li class="nav-dropdown">
            <a href="/micropigmentacion-cejas.php">Servicios</a>
            <div class="nav-dropdown-menu">
              <a href="/micropigmentacion-cejas.php">Cejas</a>
              <a href="/micropigmentacion-ojos.php">Ojos</a>
              <a href="/micropigmentacion-labios.php">Labios</a>
              <a href="/microblading-zaragoza.php">Microblading</a>
            </div>
          </li>
          <li><a href="/trabajos-cejas.php">Trabajos</a></li>
          <li><a href="/quienes-somos.php">Virginia</a></li>
          <li><a href="/blog.php">Blog</a></li>
          <li><a href="/contacto.php">Contacto</a></li>
        </ul>
      </nav>

      <div class="nav-cta">
        <a href="/contacto.php" class="btn btn--primary">Pide tu cita</a>
      </div>

      <button class="hamburger" aria-label="Abrir menú" aria-expanded="false">
        <span></span><span></span><span></span>
      </button>

    </div>
  </div>
</header>

<!-- Mobile nav -->
<nav class="mobile-nav" aria-label="Menú móvil">
  <a href="/index.php">Inicio</a>
  <a href="/micropigmentacion-cejas.php">Cejas</a>
  <a href="/micropigmentacion-ojos.php">Ojos</a>
  <a href="/micropigmentacion-labios.php">Labios</a>
  <a href="/microblading-zaragoza.php">Microblading</a>
  <a href="/trabajos-cejas.php">Trabajos</a>
  <a href="/quienes-somos.php">Virginia</a>
  <a href="/blog.php">Blog</a>
  <a href="/contacto.php">Contacto</a>
  <div class="mobile-nav-cta">
    <a href="/contacto.php" class="btn btn--primary">Pide tu cita</a>
  </div>
</nav>

<main>
