<?php
// Theme setup
function virginia_theme_setup() {
    add_theme_support('title-tag');
    add_theme_support('post-thumbnails');
    add_theme_support('html5', ['search-form','comment-form','comment-list','gallery','caption','script','style']);
    add_theme_support('custom-logo');
    add_theme_support('automatic-feed-links');

    register_nav_menus([
        'primary' => 'Menú principal',
        'footer'  => 'Menú pie de página',
    ]);
}
add_action('after_setup_theme', 'virginia_theme_setup');

// Enqueue
function virginia_scripts() {
    // Google Fonts
    wp_enqueue_style('virginia-fonts', 'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=DM+Sans:wght@400;500;600&display=swap', [], null);
    // Theme CSS
    wp_enqueue_style('virginia-style', get_stylesheet_uri(), ['virginia-fonts'], '1.0.0');
    // JS
    wp_enqueue_script('virginia-main', get_template_directory_uri() . '/js/main.js', [], '1.0.0', true);
}
add_action('wp_enqueue_scripts', 'virginia_scripts');

// SEO meta tags (description, OG, Twitter Card)
function virginia_head_meta() {
    global $post;
    $desc  = get_bloginfo('description');
    $image = get_template_directory_uri() . '/img/virginia-aguilera-micropigmentacion.jpg';
    $url   = get_permalink() ?: home_url('/');

    if (is_singular() && $post) {
        if (has_excerpt($post)) $desc = wp_strip_all_tags(get_the_excerpt($post));
        if (has_post_thumbnail($post)) $image = get_the_post_thumbnail_url($post, 'large');
        $url = get_permalink($post);
    }
    ?>
    <meta name="description" content="<?php echo esc_attr($desc); ?>">
    <link rel="canonical" href="<?php echo esc_url($url); ?>">
    <meta property="og:type" content="website">
    <meta property="og:title" content="<?php echo esc_attr(wp_get_document_title()); ?>">
    <meta property="og:description" content="<?php echo esc_attr($desc); ?>">
    <meta property="og:image" content="<?php echo esc_url($image); ?>">
    <meta property="og:url" content="<?php echo esc_url($url); ?>">
    <meta property="og:locale" content="es_ES">
    <meta property="og:site_name" content="Virginia Aguilera Micropigmentación">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="<?php echo esc_attr(wp_get_document_title()); ?>">
    <meta name="twitter:description" content="<?php echo esc_attr($desc); ?>">
    <meta name="twitter:image" content="<?php echo esc_url($image); ?>">
    <?php
}
add_action('wp_head', 'virginia_head_meta', 1);

// Contact form handler — fires on admin-post.php for both logged-in and non-logged-in users
function virginia_handle_contact_form() {
    if (!isset($_POST['virginia_contact_nonce'])) {
        wp_die('Solicitud no válida.');
    }
    if (!wp_verify_nonce($_POST['virginia_contact_nonce'], 'virginia_contact')) {
        wp_die('Solicitud no válida.');
    }
    $nombre   = sanitize_text_field($_POST['nombre'] ?? '');
    $email    = sanitize_email($_POST['email'] ?? '');
    $telefono = sanitize_text_field($_POST['telefono'] ?? '');
    $servicio = sanitize_text_field($_POST['servicio'] ?? '');
    $mensaje  = sanitize_textarea_field($_POST['mensaje'] ?? '');
    $privacy  = isset($_POST['privacy']);

    $referer = wp_get_referer() ?: home_url('/contacto/');

    if (!$nombre || !$email || !$mensaje || !$privacy || !is_email($email)) {
        set_transient('virginia_form_error', 'Por favor, rellena todos los campos obligatorios.', 60);
        wp_redirect(add_query_arg('form', 'error', $referer));
        exit;
    }
    $to      = 'virginiamicropigmentacion@gmail.com';
    $subject = 'Nueva consulta web — ' . $nombre;
    $body    = "Nombre: $nombre\nEmail: $email\nTeléfono: $telefono\nServicio: $servicio\n\n$mensaje";
    $headers = ["Content-Type: text/plain; charset=UTF-8", "Reply-To: $email"];
    if (wp_mail($to, $subject, $body, $headers)) {
        wp_redirect(add_query_arg('form', 'success', $referer));
    } else {
        set_transient('virginia_form_error', 'Error al enviar. Escríbeme por WhatsApp.', 60);
        wp_redirect(add_query_arg('form', 'error', $referer));
    }
    exit;
}
add_action('admin_post_virginia_contact_form', 'virginia_handle_contact_form');
add_action('admin_post_nopriv_virginia_contact_form', 'virginia_handle_contact_form');

// Excerpt length
add_filter('excerpt_length', fn() => 25);

// Remove WP emoji (performance)
remove_action('wp_head', 'print_emoji_detection_script', 7);
remove_action('wp_print_styles', 'print_emoji_styles');
