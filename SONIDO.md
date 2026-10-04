# LAIN · Sonido

Hasta ahora el juego no tenía ni un sonido. Todos los de esta versión los
sintetiza `tools/make_sounds.py` en Python puro: no hay grabaciones de nadie ni
licencias que cumplir. Para regenerarlos:

```bash
python tools/make_sounds.py
```

## Qué suena

| Sitio | Ambiente |
|---|---|
| Barrio | Lluvia sobre la calle |
| Casa | Lluvia tras el cristal y el tono de la habitación |
| Estación | Retumbo grave y zumbido de fluorescentes |
| Escuela y aula de informática | Zumbido de fluorescentes |
| Videoclub, tienda, librería | Fluorescentes y tono de sala |
| Izakaya y kissa | Tono cálido de sala, lluvia lejana |
| Recreativos | Pitidos de máquinas en escala pentatónica |
| Sótano Azul | Bombo y bajo a 120 pulsaciones |

Al cambiar de sitio, un ambiente se funde con el siguiente y suena una puerta.

**Interfaz:**
- teclas y «enter» en el Terminal;
- un zumbido cuando una orden no vale;
- un aviso cuando llega correo o se abre una capa nueva;
- un campanilleo cuando Nora da una pista;
- un arpegio y la estática de la Sesión Cero al completar una capa.

**F7** cambia el volumen: entero, a la mitad o apagado. La elección se guarda.

## Cómo está hecho

- `client/scripts/art/AudioDirector.gd` (autoload) elige los ambientes por
  sitio, los funde, reparte los efectos en seis canales por turnos y reacciona
  al correo y a las respuestas del Terminal.
- `client/audio/*.wav`: 22 050 Hz mono. Godot los comprime con QOA al importar,
  y los ambientes están marcados como bucle.
- En las ejecuciones sin pantalla (pruebas, CI) todo se prepara pero no se
  reproduce, para que ningún sonido siga vivo al cerrar.

## Validación

`client/tools/test_audio.gd` recorre los doce sitios y comprueba:
- que cada uno tiene sus capas de ambiente en bucle y que el estado del juego
  no cambia;
- que existen todos los efectos;
- que errores, capas completadas, pistas y correo suenan;
- que el primer estado no suena;
- que F7 recorre los tres volúmenes y silencia.
