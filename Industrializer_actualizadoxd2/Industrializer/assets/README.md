# Recursos visuales de Industrializer

La aplicación busca estos dos archivos en esta carpeta:

- `santos_corp_seal.png` — primera imagen enviada por el autor. Se utiliza como sello/marca de agua en cada hoja de la previsualización PDF y en el PDF exportado.
- `industrializer.png` — segunda imagen enviada por el autor. Se utiliza como icono de la aplicación de escritorio.

**Importante:** estos dos archivos son imágenes binarias. Deben colocarse aquí conservando exactamente esos nombres. La lógica de la aplicación ya está preparada para usarlos y funciona también sin ellos, pero sin el sello/icono no se mostrará la identidad gráfica.

Después de colocarlos, `make_icon.py` genera automáticamente `industrializer.ico` para la compilación de Windows.
