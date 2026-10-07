# Personajes 3D con VRoid Studio

Los personajes del juego en 3D se hacen con **VRoid Studio**: un editor gratuito de
personajes anime en el que se elige pelo, cara, ojos y ropa sin saber modelar. Se
exporta un archivo `.vrm` y el juego hace el resto: lo importa, le pone el
sombreado anime, lo anima al andar y le añade los detalles que VRoid no trae.

Empezamos por **Ryoko**. La referencia son los bocetos (fila D):
https://claude.ai/artifact/T3yKuYuCGHeZBRNdMByyny

## 1. Instalarlo

VRoid Studio es gratis para Windows y Mac: https://vroid.com/en/studio (también está
en Steam). Al abrirlo, **Crear nuevo** y elige el modelo base femenino.

## 2. Ryoko

| Parte | Cómo |
|---|---|
| Altura | Algo por debajo de la media (es estudiante, ~1,58 m). |
| Pelo | Media melena recta, a la altura de la mandíbula, color azul noche `#1C1A30`. Flequillo en mechones de punta que tapan las cejas. |
| Mechón rosa | En el editor de pelo, crea un grupo nuevo con un solo mechón del flequillo, algo a la derecha del centro, en rosa `#E0397A`. |
| Ojos | Iris magenta `#C0407A`, con brillo. Párpados un poco caídos: mira con desconfianza. |
| Cejas y boca | Cejas rectas, algo bajas hacia el centro. Boca pequeña, sin sonrisa. |
| Piel | Clara, con un poco de rosa. |
| Chaqueta | Bomber o cazadora corta, verde oliva `#5D6B3A`, puños y bajo más oscuros `#3F4A28`. |
| Debajo | Camiseta negra. |
| Piernas | Pantalón corto negro y medias oscuras `#3A3046`. |
| Calzado | Botas negras con suela gruesa. |
| Parche | En el editor de texturas de la chaqueta, pinta un círculo rosa `#E0397A` en el pecho izquierdo con un **23** blanco (es el puerto de Indara). |

Los **auriculares** al cuello (rosas) no hace falta hacerlos: VRoid no trae, los
pongo yo en el juego.

## 3. Exportar

1. Arriba a la derecha, el botón de **exportar** → **Exportar como VRM**.
2. Versión **VRM 1.0** (si diera problemas, VRM 0.0).
3. En las opciones de exportación:
   - **Reducir polígonos**: sí, alrededor de 30.000.
   - **Atlas de texturas**: 2048.
   - No reduzcas los huesos.
4. En los datos del modelo: título «Ryoko», tu nombre como autor y una licencia que
   permita usarla en tu propio juego.
5. Guárdalo como `ryoko.vrm`.

## 4. Dármelo

Copia `ryoko.vrm` a `client/art/characters/vrm/` (o dime dónde está). Yo:

- lo importo y le pongo el sombreado anime del juego;
- le doy movimiento al andar, respirar y girar la cabeza;
- le añado los auriculares;
- y cambio a Ryoko en la discoteca por ella.

Si algo no convence al verla en el juego, se retoca en VRoid y se vuelve a exportar:
el juego toma el archivo nuevo.

## Cómo entra en el juego

- El `.vrm` se copia como `client/art/characters/vrm/<nombre>.glb` (un VRM es un glTF):
  Godot lo importa sin complementos. Las texturas salen a la misma carpeta.
- `client/scripts/art/VrmAvatar.gd` le da el sombreado anime (VRoid exporta materiales
  planos), le baja los brazos de la postura en T y lo mantiene vivo: respira, se mece un
  poco, parpadea (con su forma `Fcl_EYE_Close`), gira la cabeza hacia el jugador cercano
  y anda cuando se mueve. Los auriculares de Ryoko los pone este script, sobre el pelo.
- `client/scripts/world/PrologueLocation.gd` (`VRM_MODELS`) dice qué personaje usa qué
  modelo; sin modelo, sigue la figura de antes.
- Prueba: `client/tools/test_vrm_avatar.gd`.

Ryoko ya está (versión 0.37). Su pelo azul y la sudadera son como los hizo su autor en
VRoid.

**Licencia:** al exportar, VRoid guarda quién puede usar el modelo. El de Ryoko dice
«solo el autor» y «uso personal sin ánimo de lucro»: vale para el juego mientras el
autor sea quien lo publica; si algún día se vende, se vuelve a exportar permitiendo el
uso comercial.

## Después

El profesor, Haruto y K, con la misma idea (sus colores están en los bocetos). Los
vecinos pueden compartir unos pocos modelos con colores distintos.
