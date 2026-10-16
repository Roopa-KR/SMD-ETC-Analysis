# Bundled chart renderer

`plotly.min.js` is the Plotly.js bundle distributed with the locally installed
Python `plotly` package (version 6.5.2); vendored for an offline-capable chart
renderer and reproducible report screenshots. Plotly is MIT-licensed.

Bootstrap 5.3.3 CSS/JS, Bootstrap Icons and optional Inter font remain CDN
resources, as in the preexisting Flask application. The supplied application's
own CSS provides substantial fallback layout when fonts or icons cannot load,
but full iconography and Bootstrap widgets require those external stylesheets.
The project does not redistribute any third-party font files.
