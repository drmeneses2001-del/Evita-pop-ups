# Evita Pop-ups y Anuncios

Extensión de navegador que bloquea ventanas emergentes (pop-ups), pop-unders,
solicitudes de notificaciones no solicitadas y anuncios de redes conocidas
mientras navegas. Funciona en **Google Chrome** de forma nativa y puede
convertirse en una extensión de **Safari** con Xcode.

## Qué hace

- **Bloquea `window.open`**: impide que los scripts abran ventanas o pestañas
  emergentes no deseadas.
- **Bloquea el spam de permisos de notificaciones**: evita que los sitios
  pidan permiso de notificaciones apenas cargan la página, sin que el
  usuario haya interactuado.
- **Bloquea anuncios a nivel de red**: usa reglas `declarativeNetRequest`
  para impedir que se carguen recursos de dominios publicitarios conocidos
  (Google Ads, Taboola, Outbrain, PopAds, Adsterra, etc.), ver
  [`rules/ad_rules.json`](rules/ad_rules.json).
- **Oculta contenedores de anuncios**: inyecta CSS para ocultar los
  elementos típicos de anuncios embebidos (`ins.adsbygoogle`, iframes de
  Google Ads, banners de Taboola/Outbrain, etc.).
- **Lista blanca por sitio**: permite excluir sitios de confianza donde
  quieras permitir ventanas emergentes (por ejemplo, para inicios de sesión
  con ventana emergente tipo OAuth).
- Icono de la barra de herramientas con contador de bloqueos por sitio y
  total, interruptor de activar/desactivar y acceso rápido a la lista
  blanca.

## Instalación en Google Chrome

1. Abre `chrome://extensions`.
2. Activa el **Modo de desarrollador** (arriba a la derecha).
3. Haz clic en **Cargar descomprimida** y selecciona la carpeta de este
   proyecto (`Evita-pop-ups`).
4. La extensión quedará instalada y activa. Haz clic en su icono en la
   barra de herramientas para ver el contador de bloqueos, activarla o
   desactivarla, y permitir sitios concretos.

Este mismo procedimiento funciona en navegadores basados en Chromium
(Microsoft Edge, Brave, Opera, Vivaldi) usando su página equivalente de
extensiones.

## Conversión e instalación en Safari

Safari (macOS 14+) admite extensiones basadas en el mismo estándar
**Web Extensions** que usa esta carpeta, pero deben empaquetarse como una
app nativa con Xcode. Pasos (requiere un Mac con Xcode instalado):

1. Instala [Xcode](https://developer.apple.com/xcode/) desde la Mac App Store.
2. Abre una terminal y ejecuta la herramienta de conversión de Apple
   apuntando a esta carpeta:

   ```bash
   xcrun safari-web-extension-converter /ruta/a/Evita-pop-ups
   ```

3. La herramienta generará y abrirá un proyecto de Xcode. Pulsa **Run**
   (▶) para compilar e instalar la app contenedora con la extensión.
4. En Safari, ve a **Ajustes → Extensiones** y activa "Evita Pop-ups y
   Anuncios".
5. Si Safari no te deja activarla, ve a **Ajustes → Avanzado** y activa
   "Mostrar el menú Desarrollo", luego en el menú **Desarrollo** activa
   "Permitir extensiones no firmadas" (solo necesario para desarrollo/uso
   personal sin publicar en la App Store).

> Nota: para distribuir la extensión a otras personas a través de la Mac
> App Store, Apple exige firmarla y enviarla a revisión con una cuenta de
> desarrollador. Para uso personal, el paso anterior es suficiente.

## Estructura del proyecto

```
manifest.json         Manifest V3 (Chrome/Edge/Brave y base para Safari)
background.js         Service worker: gestiona reglas de red, contador y badge
content.js            Bloqueo de window.open, notificaciones y CSS cosmético
rules/ad_rules.json   Reglas declarativeNetRequest con dominios publicitarios
popup/                Interfaz del icono de la barra de herramientas
options/              Página de opciones (lista blanca)
icons/                Iconos de la extensión
```

## Limitaciones conocidas

- Algunos sitios legítimos usan `window.open` para funciones reales (por
  ejemplo, ventanas de inicio de sesión de terceros). Si una función deja
  de funcionar en un sitio de confianza, añádelo a la lista blanca desde
  el icono de la extensión.
- El bloqueo por dominio depende de la lista incluida en
  `rules/ad_rules.json`; puedes ampliarla añadiendo más entradas con el
  mismo formato.
