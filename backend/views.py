from django.shortcuts import render, get_object_or_404
from backend.models import Personaje, PersonajeSeleccionado
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from backend.generar_imagen.Jugador import Jugador
import random
import os
import math
import time
import numpy as np
import cv2 
from pathlib import Path

W = 1000
H = 500
BASE_DIR = Path(__file__).resolve().parent.parent
PATH = str(BASE_DIR)

RADIO_VISION = 100

COLORES_LABERINTO = [
    (100, 220, 100), (240, 150, 60), (80, 100, 240),
    (200, 90, 180), (40, 200, 250), (200, 200, 50)
]

PRECIOS_TIENDA = {
    "triple": 100,
    "rafaga": 120,
    "perforante": 150,
    "vida": 60,
    "escudo": 90
}

ESTADO_JUEGO = {
    "nivel": 1,
    "monedas": 0,
    "enemigos_derrotados_nivel": 0,
    "ultimo_premio_nivel": 0,
    "ultimo_premio_enemigos": 0,
    "en_tienda": False,       # Pausa el juego entre niveles y abre las tarjetas
    "vidas": 3,
    "max_vidas": 3,
    "escudo": 0,
    "max_escudo": 0,
    "ultimo_dano": 0.0,
    "mejoras": {
        "triple": False,
        "rafaga": False,
        "perforante": False,
    },
    "balas": [],
    "balas_enemigas": [],
    "enemigos": [],
    "mensaje_hud": "",
    "tiempo_mensaje": 0.0,
    "inicializado": False
}

CACHE_IMAGENES = {}

def resetear_progreso_total():
    ESTADO_JUEGO["nivel"] = 1
    ESTADO_JUEGO["monedas"] = 0
    ESTADO_JUEGO["enemigos_derrotados_nivel"] = 0
    ESTADO_JUEGO["ultimo_premio_nivel"] = 0
    ESTADO_JUEGO["ultimo_premio_enemigos"] = 0
    ESTADO_JUEGO["en_tienda"] = False
    ESTADO_JUEGO["vidas"] = 3
    ESTADO_JUEGO["max_vidas"] = 3
    ESTADO_JUEGO["escudo"] = 0
    ESTADO_JUEGO["max_escudo"] = 0
    ESTADO_JUEGO["mejoras"] = {"triple": False, "rafaga": False, "perforante": False}
    ESTADO_JUEGO["balas"].clear()
    ESTADO_JUEGO["balas_enemigas"].clear()

def mostrar_aviso(texto):
    ESTADO_JUEGO["mensaje_hud"] = texto
    ESTADO_JUEGO["tiempo_mensaje"] = time.time() + 2.5

def cargar_sprites(ruta_personaje, tam_p, tam_t):
    clave_p = (ruta_personaje, tam_p)
    if clave_p not in CACHE_IMAGENES:
        ruta_completa = os.path.join(PATH, ruta_personaje.lstrip("/\\"))
        img_p = cv2.imread(ruta_completa)
        if img_p is None:
            img_p = cv2.imread(PATH + ruta_personaje)
        if img_p is None:
            # Fallback seguro si no encuentra la imagen
            img_p = np.full((tam_p, tam_p, 3), (230, 120, 40), dtype=np.uint8)
        CACHE_IMAGENES[clave_p] = cv2.resize(img_p, (tam_p, tam_p))
        
    clave_t = ("tesoro", tam_t)
    if clave_t not in CACHE_IMAGENES:
        img_t = cv2.imread(os.path.join(PATH, "tesoro.jpg"))
        if img_t is None:
            img_t = np.full((tam_t, tam_t, 3), (0, 215, 255), dtype=np.uint8)
        CACHE_IMAGENES[clave_t] = cv2.resize(img_t, (tam_t, tam_t))
        
    return CACHE_IMAGENES[clave_p], CACHE_IMAGENES[clave_t]

def pegar_sprite_seguro(img, sprite, x, y):
    """Evita que OpenCV/NumPy falle si el personaje o tesoro toca el borde del canvas."""
    h, w = sprite.shape[:2]
    x, y = int(x), int(y)
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(W, x + w), min(H, y + h)
    if x1 < x2 and y1 < y2:
        sx1, sy1 = x1 - x, y1 - y
        sx2, sy2 = sx1 + (x2 - x1), sy1 + (y2 - y1)
        img[y1:y2, x1:x2] = sprite[sy1:sy2, sx1:sx2]

def seleccion_personaje(request):
    personajes_db = Personaje.objects.all()
    personajes = [{"id": p.id, "nombre": p.nombre, "imagen_url": p.imagen.url} for p in personajes_db]
    ps = PersonajeSeleccionado.objects.first()
    return render(request, "seleccion_personaje.html", {
        "personajes": personajes, 
        "personaje_seleccionado": {"nombre": ps.seleccionado.nombre, "imagen_url": ps.seleccionado.imagen.url} if ps else None
    })

@require_POST
def seleccionar_personaje(request, id):
    personaje = get_object_or_404(Personaje, id=id)
    ps = PersonajeSeleccionado.objects.first()
    if ps:
        ps.seleccionado = personaje
        ps.save()
    else:
        PersonajeSeleccionado.objects.create(seleccionado=personaje)
    return JsonResponse({"id": personaje.id, "nombre": personaje.nombre})

def obtener_config_nivel(nivel):
    etapa_10 = nivel // 10
    cols = min(16 + etapa_10 * 4, 40)
    filas = min(6 + etapa_10 * 2, 20)
    ancho_celda = W // cols
    alto_celda = H // filas
    color = COLORES_LABERINTO[etapa_10 % len(COLORES_LABERINTO)]
    lado_min = min(ancho_celda, alto_celda)
    tam_personaje = max(12, min(28, int(lado_min * 0.55)))
    tam_tesoro = max(14, min(35, int(lado_min * 0.65)))
    return cols, filas, ancho_celda, alto_celda, color, tam_personaje, tam_tesoro

def obtener_laberinto(nivel):
    random.seed(nivel * 1337)
    cols, filas, ancho_celda, alto_celda, color, tam_p, tam_t = obtener_config_nivel(nivel)
    max_w, max_h = cols * ancho_celda, filas * alto_celda

    paredes = [(0, 0, max_w, 0), (max_w, 0, max_w, max_h), (max_w, max_h, 0, max_h), (0, max_h, 0, 0)]
    visitadas = [[False for _ in range(cols)] for _ in range(filas)]
    caminos_abiertos = set()

    def dfs(r, c):
        visitadas[r][c] = True
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        random.shuffle(dirs)
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < filas and 0 <= nc < cols and not visitadas[nr][nc]:
                caminos_abiertos.add(((r, c), (nr, nc)))
                caminos_abiertos.add(((nr, nc), (r, c)))
                dfs(nr, nc)

    dfs(0, 0)

    for r in range(filas):
        for c in range(cols):
            x1, y1 = c * ancho_celda, r * alto_celda
            x2, y2 = x1 + ancho_celda, y1 + alto_celda
            if c + 1 < cols and ((r, c), (r, c + 1)) not in caminos_abiertos:
                paredes.append((x2, y1, x2, y2))
            if r + 1 < filas and ((r, c), (r + 1, c)) not in caminos_abiertos:
                paredes.append((x1, y2, x2, y2))
                
    tx = (cols - 1) * ancho_celda + (ancho_celda - tam_t) // 2
    ty = (filas - 1) * alto_celda + (alto_celda - tam_t) // 2
    return paredes, color, tam_p, tam_t, tx, ty, cols, filas, ancho_celda, alto_celda

def spawnear_enemigos(nivel, cols, filas, ancho_celda, alto_celda, tam_p):
    random.seed(nivel * 999)
    cantidad = min(2 + (nivel // 2), 9)
    enemigos = []
    for _ in range(cantidad):
        c = random.randint(cols // 3, cols - 1)
        r = random.randint(0, filas - 1)
        ex = c * ancho_celda + (ancho_celda - tam_p) // 2
        ey = r * alto_celda + (alto_celda - tam_p) // 2
        enemigos.append([float(ex), float(ey), random.randint(15, 45)])
    return enemigos

def distancia_punto_a_segmento(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return (px - x1)**2 + (py - y1)**2
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / float(dx*dx + dy*dy)))
    return (px - (x1 + t * dx))**2 + (py - (y1 + t * dy))**2

def obtener_paredes_en_rango(px, py, ancho, alto, paredes, radio=RADIO_VISION, min_k=4):
    cx, cy = px + ancho / 2.0, py + alto / 2.0
    radio_cuad = radio ** 2
    paredes_con_dist = [
        (distancia_punto_a_segmento(cx, cy, x1, y1, x2, y2), (x1, y1, x2, y2))
        for x1, y1, x2, y2 in paredes
    ]
    paredes_con_dist.sort(key=lambda item: item[0])
    en_radio = [pared for dist_cuad, pared in paredes_con_dist if dist_cuad <= radio_cuad]
    if len(en_radio) < min_k:
        return [pared for _, pared in paredes_con_dist[:min_k]]
    return en_radio

def rect_colision(x1, y1, w1, h1, x2, y2, w2, h2):
    return (x1 + w1 > x2) and (x1 < x2 + w2) and (y1 + h1 > y2) and (y1 < y2 + h2)

def toca_pared(px, py, ancho, alto, paredes_candidatas):
    mitad_g = 3
    for x1, y1, x2, y2 in paredes_candidatas:
        min_x, max_x = min(x1, x2) - mitad_g, max(x1, x2) + mitad_g
        min_y, max_y = min(y1, y2) - mitad_g, max(y1, y2) + mitad_g
        if (px + ancho > min_x) and (px < max_x) and (py + alto > min_y) and (py < max_y):
            return True
    return False

def procesar_compra(item):
    if item not in PRECIOS_TIENDA:
        return
    costo = PRECIOS_TIENDA[item]
    if ESTADO_JUEGO["monedas"] < costo:
        mostrar_aviso(f"No tienes suficiente oro ({costo}G)")
        return

    if item in ["triple", "rafaga", "perforante"]:
        if ESTADO_JUEGO["mejoras"][item]:
            mostrar_aviso("Ya compraste esta mejora")
            return
        ESTADO_JUEGO["monedas"] -= costo
        ESTADO_JUEGO["mejoras"][item] = True
        mostrar_aviso(f"¡{item.upper()} desbloqueado!")
    elif item == "vida":
        ESTADO_JUEGO["monedas"] -= costo
        ESTADO_JUEGO["max_vidas"] += 1
        ESTADO_JUEGO["vidas"] += 1
        mostrar_aviso("¡+1 Vida Maxima!")
    elif item == "escudo":
        ESTADO_JUEGO["monedas"] -= costo
        ESTADO_JUEGO["max_escudo"] += 1
        ESTADO_JUEGO["escudo"] = ESTADO_JUEGO["max_escudo"]
        mostrar_aviso("¡Escudo Recargable mejorado!")

def disparar_armas_jugador(cx, cy, target_x, target_y):
    dx, dy = target_x - cx, target_y - cy
    angulo_base = math.atan2(dy, dx)
    vel_base = 14.0

    angulos = [angulo_base - 0.26, angulo_base, angulo_base + 0.26] if ESTADO_JUEGO["mejoras"]["triple"] else [angulo_base]
    multiplicadores_rafaga = [1.0, 0.78, 0.56] if ESTADO_JUEGO["mejoras"]["rafaga"] else [1.0]
    perforaciones = 3 if ESTADO_JUEGO["mejoras"]["perforante"] else 1

    for mult in multiplicadores_rafaga:
        vel = vel_base * mult
        for ang in angulos:
            vx = math.cos(ang) * vel
            vy = math.sin(ang) * vel
            ESTADO_JUEGO["balas"].append([cx, cy, vx, vy, perforaciones])

def aplicar_dano_jugador():
    ESTADO_JUEGO["ultimo_dano"] = time.time()
    if ESTADO_JUEGO["escudo"] > 0:
        ESTADO_JUEGO["escudo"] -= 1
        mostrar_aviso("¡Escudo absorbió el golpe!")
        return False
    else:
        ESTADO_JUEGO["vidas"] -= 1
        mostrar_aviso(f"¡Daño recibido! Vidas: {ESTADO_JUEGO['vidas']}")
        return True

def actualizar_entidades(px, py, tam_p, paredes):
    ahora = time.time()
    if ESTADO_JUEGO["max_escudo"] > 0 and ESTADO_JUEGO["escudo"] < ESTADO_JUEGO["max_escudo"]:
        if ahora - ESTADO_JUEGO["ultimo_dano"] >= 5.0:
            ESTADO_JUEGO["escudo"] += 1
            ESTADO_JUEGO["ultimo_dano"] = ahora
            mostrar_aviso("¡Escudo recargado!")

    radio_bala = 4
    nuevas_balas = []

    # 1. Mover balas del jugador (+10 monedas por enemigo derrotado)
    for bx, by, vx, vy, perf in ESTADO_JUEGO["balas"]:
        nbx, nby = bx + vx, by + vy
        cercanas_b = obtener_paredes_en_rango(nbx, nby, radio_bala*2, radio_bala*2, paredes, radio=40, min_k=4)
        
        if toca_pared(nbx - radio_bala, nby - radio_bala, radio_bala*2, radio_bala*2, cercanas_b):
            perf -= 1
            if perf <= 0:
                continue

        for i in range(len(ESTADO_JUEGO["enemigos"]) - 1, -1, -1):
            ex, ey, _ = ESTADO_JUEGO["enemigos"][i]
            if rect_colision(nbx - radio_bala, nby - radio_bala, radio_bala*2, radio_bala*2, ex, ey, tam_p, tam_p):
                ESTADO_JUEGO["enemigos"].pop(i)
                ESTADO_JUEGO["monedas"] += 10
                ESTADO_JUEGO["enemigos_derrotados_nivel"] += 1
                mostrar_aviso("+10G (Enemigo derrotado)")
                perf -= 1
                if perf <= 0:
                    break

        if perf > 0 and 0 <= nbx <= W and 0 <= nby <= H:
            nuevas_balas.append([nbx, nby, vx, vy, perf])

    ESTADO_JUEGO["balas"] = nuevas_balas

    # 2. Mover balas enemigas
    nuevas_balas_enemigas = []
    devolver_inicio = False

    for ebx, eby, evx, evy in ESTADO_JUEGO["balas_enemigas"]:
        nebx, neby = ebx + evx, eby + evy
        cercanas_eb = obtener_paredes_en_rango(nebx, neby, 6, 6, paredes, radio=40, min_k=4)
        if toca_pared(nebx - 3, neby - 3, 6, 6, cercanas_eb):
            continue

        if rect_colision(nebx - 3, neby - 3, 6, 6, px, py, tam_p, tam_p):
            if aplicar_dano_jugador():
                devolver_inicio = True
            continue

        if 0 <= nebx <= W and 0 <= neby <= H:
            nuevas_balas_enemigas.append([nebx, neby, evx, evy])

    ESTADO_JUEGO["balas_enemigas"] = nuevas_balas_enemigas

    # 3. Mover enemigos y disparar
    vel_enemigo = 2.0
    for enemigo in ESTADO_JUEGO["enemigos"]:
        ex, ey, cd = enemigo
        dx, dy = px - ex, py - ey
        dist = math.hypot(dx, dy)
        
        if 0 < dist < RADIO_VISION * 1.7:
            vx = (dx / dist) * vel_enemigo
            vy = (dy / dist) * vel_enemigo
            cercanas_e = obtener_paredes_en_rango(ex, ey, tam_p, tam_p, paredes, radio=50, min_k=4)
            if not toca_pared(ex + vx, ey, tam_p, tam_p, cercanas_e):
                enemigo[0] += vx
            if not toca_pared(enemigo[0], ey + vy, tam_p, tam_p, cercanas_e):
                enemigo[1] += vy

            enemigo[2] -= 1
            if enemigo[2] <= 0:
                vel_be = 7.5
                ecx, ecy = enemigo[0] + tam_p / 2.0, enemigo[1] + tam_p / 2.0
                ESTADO_JUEGO["balas_enemigas"].append([ecx, ecy, (dx / dist) * vel_be, (dy / dist) * vel_be])
                enemigo[2] = random.randint(28, 50)

        if rect_colision(px, py, tam_p, tam_p, enemigo[0], enemigo[1], tam_p, tam_p):
            enemigo[0] -= (dx / max(1.0, dist)) * 18
            enemigo[1] -= (dy / max(1.0, dist)) * 18
            if aplicar_dano_jugador():
                devolver_inicio = True

    return devolver_inicio

def generar_imagen(request):
    ps = PersonajeSeleccionado.objects.first()
    p = ps.seleccionado if ps else Personaje.objects.first()
    if p is None:
        class DummyPersonaje:
            x, y = 8, 8
            class imagen:
                url = ""
            def save(self): pass
        p = DummyPersonaje()
    key = request.GET.get("tecla", "")
    mx = request.GET.get("mx")
    my = request.GET.get("my")
    comprar = request.GET.get("comprar", "")
    continuar = request.GET.get("continuar", "")

    if not ESTADO_JUEGO["inicializado"] or key.lower() == "r":
        resetear_progreso_total()
        paredes, color_pared, tam_p, tam_t, tx, ty, cols, filas, ancho_c, alto_c = obtener_laberinto(1)
        p.x, p.y = 8, 8
        p.save()
        ESTADO_JUEGO["enemigos"] = spawnear_enemigos(1, cols, filas, ancho_c, alto_c, tam_p)
        ESTADO_JUEGO["inicializado"] = True

    if comprar:
        procesar_compra(comprar)

    # Cuando el jugador hace clic en "Empezar Nivel X" dentro del modal de tienda
    if continuar == "1" and ESTADO_JUEGO["en_tienda"]:
        ESTADO_JUEGO["en_tienda"] = False
        ESTADO_JUEGO["enemigos_derrotados_nivel"] = 0
        nivel = ESTADO_JUEGO["nivel"]
        paredes, color_pared, tam_p, tam_t, tx, ty, cols, filas, ancho_c, alto_c = obtener_laberinto(nivel)
        p.x, p.y = 8, 8
        p.save()
        ESTADO_JUEGO["balas"].clear()
        ESTADO_JUEGO["balas_enemigas"].clear()
        ESTADO_JUEGO["enemigos"] = spawnear_enemigos(nivel, cols, filas, ancho_c, alto_c, tam_p)

    nivel = ESTADO_JUEGO["nivel"]
    paredes, color_pared, tam_p, tam_t, tx, ty, cols, filas, ancho_c, alto_c = obtener_laberinto(nivel)
    x_origen, y_origen = int(p.x), int(p.y)

    # Solo actualizar físicas y disparos si NO está en la tienda entre niveles
    if not ESTADO_JUEGO["en_tienda"]:
        if mx is not None and my is not None:
            try:
                target_x, target_y = float(mx), float(my)
                cx, cy = x_origen + tam_p / 2.0, y_origen + tam_p / 2.0
                disparar_armas_jugador(cx, cy, target_x, target_y)
            except ValueError:
                pass

        if key and key.lower() != "r":
            jugador = Jugador(p)
            x_dest, y_dest = jugador.movimiento_personaje(key)
            MAX_SPEED = 8
            dx = max(-MAX_SPEED, min(MAX_SPEED, int(x_dest) - x_origen))
            dy = max(-MAX_SPEED, min(MAX_SPEED, int(y_dest) - y_origen))
            pasos = max(abs(dx), abs(dy))
            for i in range(1, pasos + 1):
                sig_x = int(round(x_origen + (dx / pasos) * i))
                sig_y = int(round(y_origen + (dy / pasos) * i))
                paredes_cercanas = obtener_paredes_en_rango(sig_x, sig_y, tam_p, tam_p, paredes, radio=RADIO_VISION, min_k=4)
                if toca_pared(sig_x, sig_y, tam_p, tam_p, paredes_cercanas):
                    break
                x_origen, y_origen = sig_x, sig_y

        devolver_inicio = actualizar_entidades(x_origen, y_origen, tam_p, paredes)

        if ESTADO_JUEGO["vidas"] <= 0:
            resetear_progreso_total()
            nivel = 1
            paredes, color_pared, tam_p, tam_t, tx, ty, cols, filas, ancho_c, alto_c = obtener_laberinto(1)
            ESTADO_JUEGO["enemigos"] = spawnear_enemigos(1, cols, filas, ancho_c, alto_c, tam_p)
            x_origen, y_origen = 8, 8
            mostrar_aviso("¡SIN VIDAS! Regresas al Nivel 1")
        elif devolver_inicio:
            x_origen, y_origen = 8, 8
            ESTADO_JUEGO["balas"].clear()
            ESTADO_JUEGO["balas_enemigas"].clear()

        # Si toca el tesoro -> +100 monedas por el nivel y abre la tienda sobre el tablero
        gano = rect_colision(x_origen, y_origen, tam_p, tam_p, tx, ty, tam_t, tam_t)
        if gano:
            ESTADO_JUEGO["monedas"] += 100
            ESTADO_JUEGO["ultimo_premio_nivel"] = 100
            ESTADO_JUEGO["ultimo_premio_enemigos"] = ESTADO_JUEGO["enemigos_derrotados_nivel"] * 10
            ESTADO_JUEGO["nivel"] += 1
            ESTADO_JUEGO["en_tienda"] = True
            x_origen, y_origen = 8, 8
            ESTADO_JUEGO["balas"].clear()
            ESTADO_JUEGO["balas_enemigas"].clear()

        p.x, p.y = x_origen, y_origen
        p.save()

    # --- RENDERIZADO EN CUARTO OSCURO ---
    sprite_p, sprite_t = cargar_sprites(p.imagen.url, tam_p, tam_t)
    img = np.full((H, W, 3), 12, dtype=np.uint8)
    
    cx_p = int(x_origen + tam_p // 2)
    cy_p = int(y_origen + tam_p // 2)

    cv2.circle(img, (cx_p, cy_p), RADIO_VISION, (28, 28, 32), -1)
    cv2.circle(img, (cx_p, cy_p), int(RADIO_VISION * 0.65), (40, 40, 46), -1)

    paredes_visibles = obtener_paredes_en_rango(x_origen, y_origen, tam_p, tam_p, paredes, radio=RADIO_VISION, min_k=4)
    for x1, y1, x2, y2 in paredes_visibles:
        cv2.line(img, (x1, y1), (x2, y2), color_pared, 3)

    if math.hypot((tx + tam_t/2) - cx_p, (ty + tam_t/2) - cy_p) <= RADIO_VISION:
        pegar_sprite_seguro(img, sprite_t, tx, ty)

    pegar_sprite_seguro(img, sprite_p, x_origen, y_origen)

    if ESTADO_JUEGO["escudo"] > 0:
        cv2.circle(img, (cx_p, cy_p), int(tam_p * 0.8), (255, 220, 0), 2)

    for ex, ey, _ in ESTADO_JUEGO["enemigos"]:
        if math.hypot((ex + tam_p/2) - cx_p, (ey + tam_p/2) - cy_p) <= RADIO_VISION:
            ix, iy = int(ex), int(ey)
            cv2.rectangle(img, (ix, iy), (ix + tam_p, iy + tam_p), (40, 40, 230), -1)
            cv2.rectangle(img, (ix, iy), (ix + tam_p, iy + tam_p), (120, 120, 255), 2)

    color_bala_j = (255, 230, 50) if ESTADO_JUEGO["mejoras"]["perforante"] else (0, 180, 255)
    for bx, by, _, _, _ in ESTADO_JUEGO["balas"]:
        cv2.circle(img, (int(bx), int(by)), 5, color_bala_j, -1)

    for ebx, eby, _, _ in ESTADO_JUEGO["balas_enemigas"]:
        if math.hypot(ebx - cx_p, eby - cy_p) <= RADIO_VISION * 1.2:
            cv2.circle(img, (int(ebx), int(eby)), 4, (60, 60, 255), -1)

    # HUD Superior
    cv2.rectangle(img, (0, 0), (W, 38), (20, 20, 24), -1)
    bonos_activos = [k.capitalize() for k, v in ESTADO_JUEGO["mejoras"].items() if v]
    txt_bonos = ", ".join(bonos_activos) if bonos_activos else "Ninguno"
    hud_texto = (
        f"Niv: {ESTADO_JUEGO['nivel']} | Vidas: {ESTADO_JUEGO['vidas']}/{ESTADO_JUEGO['max_vidas']} | "
        f"Escudo: {ESTADO_JUEGO['escudo']}/{ESTADO_JUEGO['max_escudo']} | "
        f"Oro: {ESTADO_JUEGO['monedas']}G | Bonos: {txt_bonos}"
    )
    cv2.putText(img, hud_texto, (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 2)

    if time.time() < ESTADO_JUEGO["tiempo_mensaje"]:
        cv2.putText(img, ESTADO_JUEGO["mensaje_hud"], (320, 480), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 230, 255), 2)

    ok, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    response = HttpResponse(buffer.tobytes(), content_type="image/jpg")
    
    # Cabeceras para que el HTML sepa cuándo abrir las tarjetas de la tienda y cuánto dinero mostrar
    response["X-En-Tienda"] = "1" if ESTADO_JUEGO["en_tienda"] else "0"
    response["X-Monedas"] = str(ESTADO_JUEGO["monedas"])
    response["X-Nivel"] = str(ESTADO_JUEGO["nivel"])
    response["X-Premio-Nivel"] = str(ESTADO_JUEGO["ultimo_premio_nivel"])
    response["X-Premio-Enemigos"] = str(ESTADO_JUEGO["ultimo_premio_enemigos"])
    response["X-Kills"] = str(ESTADO_JUEGO["enemigos_derrotados_nivel"])
    response["Cache-Control"] = "no-store"
    return response

def tablero(request):
    return render(request, "tablero.html")