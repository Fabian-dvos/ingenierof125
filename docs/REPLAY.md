# Recorder + Replay

## Grabar (con juego abierto)
python -m ingenierof125 --no-supervisor --record --record-dir recordings

## Reproducir (sin abrir el juego)
python -m ingenierof125 --no-supervisor --replay recordings\\TU_ARCHIVO.ingrec --replay-speed 1.0

Opciones:
- --replay-speed 2.0  (2x)
- --replay-no-sleep   (lo más rápido posible)
