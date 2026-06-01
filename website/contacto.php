<?php
$pageTitle    = 'Contacto — Virginia Aguilera Micropigmentación Zaragoza | 620 834 002';
$pageDesc     = 'Escríbeme sin compromiso. Primera consulta gratuita. Virginia Aguilera, especialista en micropigmentación en Zaragoza. WhatsApp: 620 834 002.';
$pageKeywords = 'contacto micropigmentación Zaragoza, cita micropigmentación Zaragoza, teléfono micropigmentación Zaragoza, Virginia Aguilera contacto';
$canonicalUrl = 'https://micropigmentacionzgz.es/contacto.php';

/* Handle form submission */
$success = false;
$error   = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
  $nombre  = filter_input(INPUT_POST, 'nombre',   FILTER_SANITIZE_SPECIAL_CHARS);
  $email   = filter_input(INPUT_POST, 'email',    FILTER_SANITIZE_EMAIL);
  $telefono = filter_input(INPUT_POST, 'telefono', FILTER_SANITIZE_SPECIAL_CHARS);
  $servicio = filter_input(INPUT_POST, 'servicio', FILTER_SANITIZE_SPECIAL_CHARS);
  $mensaje  = filter_input(INPUT_POST, 'mensaje',  FILTER_SANITIZE_SPECIAL_CHARS);
  $privacy  = isset($_POST['privacy']) ? true : false;

  if (!$nombre || !$email || !$mensaje || !$privacy) {
    $error = 'Por favor, rellena todos los campos obligatorios.';
  } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    $error = 'El email no parece válido.';
  } else {
    $to      = 'virginiamicropigmentacion@gmail.com';
    $subject = 'Nueva consulta web — ' . htmlspecialchars($nombre);
    $body    = "Nombre: $nombre\nEmail: $email\nTeléfono: $telefono\nServicio: $servicio\n\n$mensaje";
    $headers = "From: noreply@micropigmentacionzgz.es\r\nReply-To: $email\r\nContent-Type: text/plain; charset=UTF-8";
    if (mail($to, $subject, $body, $headers)) {
      $success = true;
    } else {
      $error = 'Hubo un problema enviando el mensaje. Escríbeme directamente por WhatsApp.';
    }
  }
}

include 'includes/header.php';
?>

<!-- PAGE HERO -->
<section style="padding:140px 0 60px;background:var(--white)">
  <div class="container">
    <div class="text-center reveal">
      <span class="label">Hablemos</span>
      <h1>Escríbeme sin compromiso.</h1>
      <p style="font-size:1.1rem;margin:16px auto 0;max-width:540px">
        Te respondo lo antes posible. La primera consulta siempre es gratuita.
        Sin presiones, sin formularios eternos.
      </p>
    </div>
  </div>
</section>

<!-- CONTACTO GRID -->
<section class="section" style="padding-top:40px">
  <div class="container">
    <div class="contact-grid">

      <!-- INFO -->
      <div class="reveal">
        <h3>Cómo contactarme</h3>

        <!-- WhatsApp destacado -->
        <div style="margin:28px 0">
          <a href="https://wa.me/34620834002?text=Hola%20Virginia%2C%20me%20gustar%C3%ADa%20pedir%20informaci%C3%B3n."
             class="btn btn--whatsapp"
             target="_blank" rel="noopener"
             style="width:100%;justify-content:center;font-size:1.05rem">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.122 1.524 5.863L.057 23.57a.75.75 0 00.918.918l5.702-1.467A11.94 11.94 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75A9.74 9.74 0 016.31 19.94l-.387-.23-3.384.87.886-3.295-.25-.404A9.71 9.71 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
            WhatsApp: 620 834 002
          </a>
        </div>

        <div class="contact-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 014.5 11.5a19.79 19.79 0 01-3.07-8.67A2 2 0 013.41 1h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 8.91A16 16 0 0015.1 15.9l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/></svg>
          <div>
            <h4>Teléfono / WhatsApp</h4>
            <p><a href="tel:+34620834002" style="color:var(--gold);font-weight:600">620 834 002</a></p>
          </div>
        </div>

        <div class="contact-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
          <div>
            <h4>CC El Caracol (centro)</h4>
            <p>Pº Independencia 24-26, Planta -1, Local 72<br>Zaragoza</p>
            <a href="https://maps.google.com/?q=Paseo+Independencia+24+Zaragoza"
               target="_blank" rel="noopener"
               style="font-size:0.82rem;color:var(--gold);font-weight:600">
              Ver en Google Maps →
            </a>
          </div>
        </div>

        <div class="contact-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
          <div>
            <h4>Hospital Viamed Montecanal</h4>
            <p>C/ Franz Schubert, 2<br>50012 Zaragoza</p>
            <a href="https://maps.google.com/?q=Calle+Franz+Schubert+2+Zaragoza"
               target="_blank" rel="noopener"
               style="font-size:0.82rem;color:var(--gold);font-weight:600">
              Ver en Google Maps →
            </a>
          </div>
        </div>

        <div class="contact-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>
          <div>
            <h4>Consulta previa</h4>
            <p>La primera consulta es <strong>gratuita y sin compromiso</strong>.<br>Escríbeme y quedamos.</p>
          </div>
        </div>
      </div>

      <!-- FORM -->
      <div class="contact-form-wrap reveal reveal-delay-1">
        <h3 style="margin-bottom:28px">Formulario de contacto</h3>

        <?php if ($success): ?>
          <div style="background:#d4edda;border:1px solid #c3e6cb;border-radius:var(--radius);padding:24px;color:#155724;margin-bottom:24px">
            <strong>¡Mensaje enviado!</strong> Te respondo lo antes posible. Si tienes prisa, escríbeme por WhatsApp.
          </div>
        <?php endif; ?>

        <?php if ($error): ?>
          <div style="background:#f8d7da;border:1px solid #f5c6cb;border-radius:var(--radius);padding:16px;color:#721c24;margin-bottom:24px">
            <?= htmlspecialchars($error) ?>
          </div>
        <?php endif; ?>

        <form id="contact-form" method="POST" action="/contacto.php">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
            <div class="form-group">
              <label for="nombre">Nombre *</label>
              <input type="text" id="nombre" name="nombre"
                     value="<?= htmlspecialchars($_POST['nombre'] ?? '') ?>"
                     placeholder="Tu nombre" required>
            </div>
            <div class="form-group">
              <label for="telefono">Teléfono</label>
              <input type="tel" id="telefono" name="telefono"
                     value="<?= htmlspecialchars($_POST['telefono'] ?? '') ?>"
                     placeholder="Tu teléfono">
            </div>
          </div>

          <div class="form-group">
            <label for="email">Email *</label>
            <input type="email" id="email" name="email"
                   value="<?= htmlspecialchars($_POST['email'] ?? '') ?>"
                   placeholder="tu@email.com" required>
          </div>

          <div class="form-group">
            <label for="servicio">¿En qué puedo ayudarte?</label>
            <select id="servicio" name="servicio">
              <option value="">Selecciona un servicio</option>
              <option value="cejas" <?= (($_POST['servicio'] ?? '') === 'cejas') ? 'selected' : '' ?>>Micropigmentación de cejas</option>
              <option value="ojos" <?= (($_POST['servicio'] ?? '') === 'ojos') ? 'selected' : '' ?>>Micropigmentación de ojos</option>
              <option value="labios" <?= (($_POST['servicio'] ?? '') === 'labios') ? 'selected' : '' ?>>Micropigmentación de labios</option>
              <option value="microblading" <?= (($_POST['servicio'] ?? '') === 'microblading') ? 'selected' : '' ?>>Microblading</option>
              <option value="otro" <?= (($_POST['servicio'] ?? '') === 'otro') ? 'selected' : '' ?>>Otra consulta</option>
            </select>
          </div>

          <div class="form-group">
            <label for="mensaje">Cuéntame *</label>
            <textarea id="mensaje" name="mensaje" placeholder="Escríbeme lo que quieras. Sin compromisos." required><?= htmlspecialchars($_POST['mensaje'] ?? '') ?></textarea>
          </div>

          <div class="form-group">
            <div class="form-checkbox">
              <input type="checkbox" id="privacy" name="privacy" required
                     <?= isset($_POST['privacy']) ? 'checked' : '' ?>>
              <label for="privacy">
                He leído y acepto la <a href="/politica-privacidad.php">política de privacidad</a>.
                Los datos que me facilitas solo se usarán para responderte.
              </label>
            </div>
          </div>

          <div class="form-submit">
            <button type="submit" class="btn btn--primary">Enviar mensaje</button>
          </div>
        </form>
      </div>

    </div>
  </div>
</section>

<?php include 'includes/footer.php'; ?>
