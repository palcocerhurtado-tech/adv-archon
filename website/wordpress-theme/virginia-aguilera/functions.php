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

// ─── Crear posts del blog en español ───────────────────────────
function virginia_create_blog_posts() {
    if (!is_admin() || get_transient('virginia_posts_created')) return;

    // Borrar posts de ejemplo en inglés (Hello World, sample posts)
    $sample_posts = get_posts([
        'post_status'    => ['publish','draft','auto-draft'],
        'posts_per_page' => -1,
        'post_type'      => 'post',
    ]);
    foreach ($sample_posts as $sp) {
        $title = strtolower($sp->post_title);
        if (
            str_contains($title, 'hello world') ||
            str_contains($title, 'intriguing post title') ||
            str_contains($title, 'your first post') ||
            str_contains($title, 'sample post') ||
            str_contains($title, 'welcome') && str_contains($title, 'wordpress')
        ) {
            wp_delete_post($sp->ID, true);
        }
    }

    // Obtener o crear categorías en español
    $cats = [];
    foreach (['Técnicas','Consejos','Resultados','Tendencias','Información'] as $cat_name) {
        $existing = get_term_by('name', $cat_name, 'category');
        if ($existing) {
            $cats[$cat_name] = $existing->term_id;
        } else {
            $new = wp_insert_term($cat_name, 'category');
            $cats[$cat_name] = is_wp_error($new) ? 1 : $new['term_id'];
        }
    }

    $img_base = get_template_directory_uri() . '/img/';

    $posts = [
        [
            'title'   => 'Qué esperar de tu primera sesión de micropigmentación.',
            'slug'    => 'primera-sesion-micropigmentacion',
            'cat'     => 'Técnicas',
            'date'    => '2025-06-01 10:00:00',
            'excerpt' => 'Dudas, nervios, expectativas. Te cuento exactamente qué pasa desde que entras por la puerta hasta que ves el resultado final.',
            'content' => '<p>Es normal llegar con nervios a la primera sesión. Lo veo cada día. Por eso quiero contarte, con total honestidad, qué va a pasar exactamente.</p>

<h2>Antes de empezar: la consulta</h2>
<p>Antes de tocar nada, hablamos. Me cuentas lo que quieres, yo miro tu tipo de piel, la forma de tu rostro, el tono que mejor te va. No hay prisas. Es la parte más importante de todo el proceso porque un buen resultado empieza por un buen diseño.</p>

<h2>El diseño: tú lo apruebas antes de empezar</h2>
<p>Dibujamos la forma sobre tu piel con lápiz. La ves en el espejo, la ajustamos si hace falta. Solo empiezo cuando estás completamente segura de que es exactamente lo que quieres. Nunca avanzo sin tu aprobación.</p>

<h2>La aplicación: más cómoda de lo que imaginas</h2>
<p>Aplicamos anestesia tópica antes de empezar. La mayoría de las clientas me dicen que la sensación es mucho más suave de lo que esperaban. La sesión dura entre 90 y 120 minutos.</p>

<h2>Los primeros días: el color se ve más intenso</h2>
<p>Es completamente normal. La piel está cicatrizando y el pigmento está asentándose. En 4-6 semanas el color baja a su tono definitivo y el resultado es exactamente lo que diseñamos juntas.</p>

<h2>La revisión: incluida siempre</h2>
<p>A las 6-8 semanas revisamos el resultado y hacemos los ajustes necesarios. Esta sesión de repaso está incluida en el precio. Porque para mí, el trabajo no termina hasta que el resultado es perfecto.</p>',
        ],
        [
            'title'   => '¿La micropigmentación es un tatuaje? Te cuento la verdad.',
            'slug'    => 'micropigmentacion-o-tatuaje',
            'cat'     => 'Información',
            'date'    => '2024-05-15 10:00:00',
            'excerpt' => 'Te lo preguntan constantemente, así que lo aclaro de una vez: hay diferencias importantes entre un tatuaje y la micropigmentación. Te explico cuáles y por qué importan.',
            'content' => '<p>Es la pregunta que me hacen casi a diario. Y tiene sentido hacerla: al final, en los dos casos estamos depositando pigmento en la piel con una aguja. Pero ahí acaban las similitudes.</p>

<h2>La diferencia clave: la profundidad</h2>
<p>Un tatuaje convencional deposita tinta en la dermis profunda — una zona estable donde el pigmento queda prácticamente para siempre. La micropigmentación trabaja en la dermis superficial, una capa que se renueva con el tiempo. Por eso la micropigmentación es semipermanente: dura entre 2 y 4 años y luego se va desvaneciendo de forma natural.</p>

<h2>Los pigmentos son completamente diferentes</h2>
<p>Los tatuajes usan tintas con componentes diseñados para durar décadas. La micropigmentación usa pigmentos específicos formulados para la piel del rostro, con registro sanitario europeo, que no viran con el tiempo ni generan las reacciones que pueden aparecer con tintes de tatuaje convencionales.</p>

<h2>¿Y el resultado estético?</h2>
<p>Un tatuaje en la cara se hace para siempre. La micropigmentación te da un resultado natural que puedes ajustar con el tiempo — si tu cara cambia, tu ceja también puede cambiar. Esa flexibilidad es algo que el tatuaje no te da nunca.</p>',
        ],
        [
            'title'   => '¿Cuándo es el momento de hacerse la micropigmentación de cejas?',
            'slug'    => 'cuando-hacerse-micropigmentacion-cejas',
            'cat'     => 'Consejos',
            'date'    => '2024-03-20 10:00:00',
            'excerpt' => 'No hay una respuesta única, pero sí hay señales que te dicen que quizás ha llegado el momento. Y otras que te dicen que mejor espera un poco más.',
            'content' => '<p>Me lo preguntan mucho: "¿cómo sé si ha llegado el momento?" No hay una respuesta perfecta, pero hay señales que te ayudan a decidir.</p>

<h2>Señales de que quizás ha llegado tu momento</h2>
<ul>
<li>Te maquillas las cejas todos los días y llevas años haciéndolo.</li>
<li>Hay días que no sales de casa sin hacerlo porque no te ves bien.</li>
<li>Tus cejas han perdido densidad por el tiempo, la depilación o una enfermedad.</li>
<li>Tus cejas son asimétricas y corregirlas con maquillaje requiere mucho tiempo.</li>
<li>Se te borra el maquillaje con facilidad: con el sudor, la lluvia, al frotarte.</li>
<li>Llevas años pensando en hacértelo pero siempre lo pospones.</li>
</ul>

<h2>¿Cuándo es mejor esperar?</h2>
<ul>
<li>Si estás embarazada o en período de lactancia.</li>
<li>Si tienes una condición dermatológica activa en la zona.</li>
<li>Si estás en tratamiento con isotretinoína (hay que esperar al menos 6 meses).</li>
<li>Si tienes un evento importante en menos de 4 semanas.</li>
<li>Si no tienes claro lo que quieres — en ese caso, primero hablamos en consulta.</li>
</ul>

<h2>Mi recomendación</h2>
<p>Si llevas tiempo dándole vueltas, lo más probable es que ya estés lista. Escríbeme, hablamos de lo que buscas, y vemos si tiene sentido hacerlo ahora.</p>',
        ],
        [
            'title'   => 'Cómo la micropigmentación puede cambiar tu cara (y tu mañana).',
            'slug'    => 'micropigmentacion-mejora-aspecto-rostro',
            'cat'     => 'Resultados',
            'date'    => '2024-02-05 10:00:00',
            'excerpt' => 'No es exageración: unos pequeños cambios en la ceja, en el contorno del labio o en el delineado del ojo pueden transformar completamente la percepción de tu rostro.',
            'content' => '<p>No me gustan las exageraciones. Pero en este caso, no exagero: la micropigmentación puede transformar la percepción visual de tu cara. Y lo hace de forma muy discreta, sin que nadie sepa exactamente qué ha cambiado.</p>

<h2>Las cejas estructuran el rostro</h2>
<p>Hay estudios de imagen y percepción que lo confirman: la ceja es el elemento del rostro que más influye en cómo percibimos las emociones y la edad de una persona. Una ceja bien definida, en la posición correcta para tu cara, eleva la mirada, rejuvenece el gesto y da simetría.</p>

<h2>Los labios y la percepción de la edad</h2>
<p>Con los años, el contorno del labio se va difuminando. Es uno de los primeros signos de envejecimiento del tercio inferior de la cara. La micropigmentación de labios — incluso solo el contorno — puede recuperar esa definición perdida y dar la impresión de unos labios más jóvenes y carnosos, sin necesidad de rellenos ni procedimientos invasivos.</p>

<h2>Y luego está lo que no se ve en el espejo</h2>
<p>Muchas de mis clientas me dicen, semanas después, que lo que más han notado no es el cambio estético. Es que ya no piensan en ello. Que se duchan, salen, y no tienen que detenerse delante del espejo a reconstruir su cara. Eso, para muchas personas, vale más que cualquier resultado concreto.</p>',
        ],
        [
            'title'   => 'Micropigmentación: de Megan Fox a Drew Barrymore, el secreto que nadie confiesa.',
            'slug'    => 'micropigmentacion-famosas',
            'cat'     => 'Tendencias',
            'date'    => '2024-04-08 10:00:00',
            'excerpt' => '¿Cómo es que siempre tienen las cejas perfectas, llueva o truene? No es genética ni suerte. Te cuento qué hay detrás de esa mirada impecable que no se borra.',
            'content' => '<p>Cada vez que ves una alfombra roja y piensas "qué cejas tan perfectas", lo más probable es que estés viendo el resultado de una micropigmentación. Es el secreto mejor guardado de Hollywood — y de muchas mujeres normales que simplemente no quieren estar pendientes del maquillaje cada mañana.</p>

<h2>¿Por qué no lo dicen?</h2>
<p>Porque hay un estigma absurdo alrededor de los procedimientos estéticos. Todo el mundo quiere parecer perfecta "de forma natural". Pero la naturalidad tiene mucho trabajo detrás, y la micropigmentación es parte de él para muchísimas personas públicas.</p>

<h2>Megan Fox y esas cejas que no se mueven</h2>
<p>Las cejas de Megan Fox son un caso de estudio: perfectamente arqueadas, densas, siempre en su sitio. En playas, en rodajes bajo el agua, en fotos sin maquillaje. Ese tipo de consistencia no se consigue solo con lápiz.</p>

<h2>Drew Barrymore y el contorno de labios</h2>
<p>Drew Barrymore ha hablado en varias entrevistas de su relación con el maquillaje permanente. Su contorno de labios perfectamente definido, incluso en sus apariciones más naturales, es el ejemplo perfecto de lo que la micropigmentación de labios puede hacer.</p>

<h2>¿Y qué tiene que ver contigo?</h2>
<p>Que lo que funciona para ellas funciona igual para ti. La técnica no discrimina. Lo que importa es que el profesional la ejecute bien y use los materiales adecuados. Eso es exactamente lo que hago.</p>',
        ],
    ];

    foreach ($posts as $p) {
        // No crear si ya existe con ese slug
        if (get_page_by_path($p['slug'], OBJECT, 'post')) continue;

        $post_id = wp_insert_post([
            'post_title'    => $p['title'],
            'post_name'     => $p['slug'],
            'post_content'  => $p['content'],
            'post_excerpt'  => $p['excerpt'],
            'post_status'   => 'publish',
            'post_type'     => 'post',
            'post_date'     => $p['date'],
            'post_category' => isset($cats[$p['cat']]) ? [$cats[$p['cat']]] : [1],
        ]);

        // Asignar imagen destacada si existe en el tema
        $img_map = [
            'primera-sesion-micropigmentacion'     => 'micropigmentacion-cejas.jpg',
            'micropigmentacion-o-tatuaje'          => 'micropigmentacion-cejas.jpg',
            'cuando-hacerse-micropigmentacion-cejas' => 'consejos-antes-micropigmentacion.jpg',
            'micropigmentacion-mejora-aspecto-rostro' => 'micropigmentacion-virginia.jpg',
            'micropigmentacion-famosas'            => 'megan-fox-micropigmentacion.jpg',
        ];
        // (La imagen destacada requiere subir al Media Library — se hace desde el admin)
    }

    set_transient('virginia_posts_created', 1, YEAR_IN_SECONDS);
}
add_action('admin_init', 'virginia_create_blog_posts');

// ─── Auto-crear páginas requeridas ─────────────────────────────
// Crea o corrige las páginas del tema en cada admin_init (solo toca algo si hay cambios)
function virginia_create_required_pages() {
    if (!is_admin()) return;
    $pages = [
        ['title' => 'Contacto',                    'slug' => 'contacto',                  'template' => 'page-templates/template-contacto.php'],
        ['title' => 'Micropigmentación de Cejas',  'slug' => 'micropigmentacion-cejas',   'template' => 'page-templates/template-cejas.php'],
        ['title' => 'Micropigmentación de Ojos',   'slug' => 'micropigmentacion-ojos',    'template' => 'page-templates/template-ojos.php'],
        ['title' => 'Micropigmentación de Labios', 'slug' => 'micropigmentacion-labios',  'template' => 'page-templates/template-labios.php'],
        ['title' => 'Galería de Trabajos',         'slug' => 'trabajos',                  'template' => 'page-templates/template-trabajos.php'],
        ['title' => 'Virginia Aguilera',           'slug' => 'virginia',                  'template' => 'page-templates/template-quienes-somos.php'],
    ];
    $changed = false;
    foreach ($pages as $p) {
        $existing = get_page_by_path($p['slug']);
        if (!$existing) {
            $id = wp_insert_post([
                'post_title'   => $p['title'],
                'post_name'    => $p['slug'],
                'post_status'  => 'publish',
                'post_type'    => 'page',
                'post_content' => '',
            ]);
            if ($id && !is_wp_error($id)) {
                update_post_meta($id, '_wp_page_template', $p['template']);
                $changed = true;
            }
        } else {
            // Asegurar que la plantilla correcta está asignada aunque la página ya exista
            $current = get_post_meta($existing->ID, '_wp_page_template', true);
            if ($current !== $p['template']) {
                update_post_meta($existing->ID, '_wp_page_template', $p['template']);
                $changed = true;
            }
        }
    }
    if ($changed) {
        flush_rewrite_rules(false);
    }
}
add_action('admin_init', 'virginia_create_required_pages');

// ─── Forzar plantilla correcta por slug ────────────────────────
// Garantiza que la plantilla se carga aunque WordPress no tenga
// el _wp_page_template meta asignado en la base de datos.
add_filter('template_include', function($template) {
    if (!is_page()) return $template;
    $slug_map = [
        'micropigmentacion-cejas'   => 'template-cejas.php',
        'micropigmentacion-ojos'    => 'template-ojos.php',
        'micropigmentacion-labios'  => 'template-labios.php',
        'trabajos'                  => 'template-trabajos.php',
        'contacto'                  => 'template-contacto.php',
        'virginia'                  => 'template-quienes-somos.php',
    ];
    $slug = get_post_field('post_name', get_the_ID());
    if (isset($slug_map[$slug])) {
        $tpl = get_template_directory() . '/page-templates/' . $slug_map[$slug];
        if (file_exists($tpl)) return $tpl;
    }
    return $template;
}, 99);

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
