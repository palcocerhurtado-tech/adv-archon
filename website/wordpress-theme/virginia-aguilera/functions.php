<?php
// Theme setup
function virginia_theme_setup() {
    add_theme_support('title-tag');
    add_theme_support('post-thumbnails');
    add_theme_support('html5', ['search-form','comment-form','comment-list','gallery','caption','script','style']);
    add_theme_support('custom-logo');
    add_theme_support('automatic-feed-links');

    // Cargar dominio de texto en español
    load_theme_textdomain('virginia-aguilera', get_template_directory() . '/languages');

    register_nav_menus([
        'primary' => 'Menú principal',
        'footer'  => 'Menú pie de página',
    ]);
}
add_action('after_setup_theme', 'virginia_theme_setup');

// Forzar idioma español en WordPress
function virginia_set_spanish() {
    if (get_option('WPLANG') !== 'es_ES') {
        update_option('WPLANG', 'es_ES');
    }
    // Renombrar "Uncategorized" a "Blog" en español
    $cat = get_term_by('name', 'Uncategorized', 'category');
    if ($cat) {
        wp_update_term($cat->term_id, 'category', ['name' => 'Blog', 'slug' => 'blog-general']);
    }
    // Renombrar "Sin categoría" si ya está en español pero con ese nombre
    $cat2 = get_term_by('name', 'Sin categoría', 'category');
    if ($cat2) {
        wp_update_term($cat2->term_id, 'category', ['name' => 'Blog', 'slug' => 'blog-general']);
    }
}
add_action('admin_init', 'virginia_set_spanish');

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

// Spanish date helper — returns "3 de junio de 2025"
function virginia_fecha_es($timestamp = null) {
    $ts = $timestamp ?: get_the_time('U');
    $meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
    return date('j', $ts) . ' de ' . $meses[(int)date('n', $ts) - 1] . ' de ' . date('Y', $ts);
}

// ─── Auto-crear páginas requeridas ─────────────────────────────
// Crea las páginas del tema si aún no existen (se ejecuta en admin_init)
function virginia_create_required_pages() {
    if (!is_admin() || get_transient('virginia_pages_created')) return;
    $pages = [
        ['title' => 'Contacto',                    'slug' => 'contacto',                  'template' => 'page-templates/template-contacto.php'],
        ['title' => 'Micropigmentación de Cejas',  'slug' => 'micropigmentacion-cejas',   'template' => 'page-templates/template-cejas.php'],
        ['title' => 'Micropigmentación de Ojos',   'slug' => 'micropigmentacion-ojos',    'template' => 'page-templates/template-ojos.php'],
        ['title' => 'Micropigmentación de Labios', 'slug' => 'micropigmentacion-labios',  'template' => 'page-templates/template-labios.php'],
        ['title' => 'Galería de Trabajos',         'slug' => 'trabajos',                  'template' => 'page-templates/template-trabajos.php'],
        ['title' => 'Virginia Aguilera',           'slug' => 'virginia',                  'template' => 'page-templates/template-quienes-somos.php'],
    ];
    foreach ($pages as $p) {
        if (!get_page_by_path($p['slug'])) {
            $id = wp_insert_post([
                'post_title'   => $p['title'],
                'post_name'    => $p['slug'],
                'post_status'  => 'publish',
                'post_type'    => 'page',
                'post_content' => '',
            ]);
            if ($id && !is_wp_error($id)) {
                update_post_meta($id, '_wp_page_template', $p['template']);
            }
        }
    }
    set_transient('virginia_pages_created', 1, DAY_IN_SECONDS);
}
add_action('admin_init', 'virginia_create_required_pages');

// Admin notice si falta la página de contacto
function virginia_missing_pages_notice() {
    if (get_page_by_path('contacto')) return;
    echo '<div class="notice notice-warning"><p><strong>Virginia Aguilera:</strong> Haz clic en <a href="' . admin_url() . '">cualquier enlace del panel</a> para crear las páginas del tema automáticamente, o créalas manualmente con los slugs: <code>contacto</code>, <code>micropigmentacion-cejas</code>, <code>micropigmentacion-ojos</code>, <code>micropigmentacion-labios</code>, <code>trabajos</code>, <code>virginia</code>.</p></div>';
}
add_action('admin_notices', 'virginia_missing_pages_notice');

// ─── WooCommerce ───────────────────────────────────────────────
function virginia_woocommerce_setup() {
    add_theme_support('woocommerce', [
        'thumbnail_image_width' => 600,
        'single_image_width'    => 900,
        'product_grid'          => ['default_rows' => 3, 'default_columns' => 3],
    ]);
    add_theme_support('wc-product-gallery-zoom');
    add_theme_support('wc-product-gallery-lightbox');
    add_theme_support('wc-product-gallery-slider');
}
add_action('after_setup_theme', 'virginia_woocommerce_setup');

// Cart count in header via JS data attribute (used by header.php)
function virginia_cart_count() {
    if (!function_exists('WC')) return 0;
    return WC()->cart ? WC()->cart->get_cart_contents_count() : 0;
}

// Refresh cart fragments
add_filter('woocommerce_add_to_cart_fragments', function($fragments) {
    $fragments['.cart-count'] = '<span class="cart-count">' . virginia_cart_count() . '</span>';
    return $fragments;
});
