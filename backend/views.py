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
import json
from pathlib import Path

W = 1000
H = 500
BASE_DIR = Path(__file__).resolve().parent.parent
PATH = str(BASE_DIR)
RADIO_VISION = 105

COLORES_LABERINTO = [
    (100, 220, 100), (240, 150, 60), (80, 100, 240),
    (200, 90, 180), (40, 200, 250), (200, 200, 50)
]

ESTADO_JUEGO = {
    "nivel": 1,
    "monedas": 0,
    "enemigos_derrotados_nivel": 0,
    "ultimo_premio_nivel": 0,
    "ultimo_premio_enemigos": 0,
    "en_tienda": False,
    "vidas": 3,
    "max_vidas": 3,
    "escudo": 0,
    "max_escudo": 0,
    "ultimo_dano": 0.0,
    "mejoras": {
        "multidisparo": 0,   # Dispara 1 + 2*lv proyectiles en abanico
        "dano": 0,           # +1 de daño por bala por nivel (1, 2, 3, 4...)
        "rafaga": 0,         # Ráfagas rápidas continuas
        "perforante": 0,     # Atraviesa paredes y enemigos
        "hielo": 0,          # Balas criogénicas que congelan/ralentizan 60%
        "rebote": 0,         # Balas rebotan en muros
        "iman": 0,           # +25% de oro por baja y cofre
        "velocidad": 0,      # Aumenta velocidad de movimiento
        "vision": 0,         # Aumenta el campo de visión / linterna
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
    ESTADO_JUEGO["mejoras"] = {
        "multidisparo": 0,
        "dano": 0,
        "rafaga": 0,
        "perforante": 0,
        "hielo": 0,
        "rebote": 0,
        "iman": 0,
        "velocidad": 0,
        "vision": 0,
    }
    ESTADO_JUEGO["balas"].clear()
    ESTADO_JUEGO["balas_enemigas"].clear()

def obtener_costo_mejora(item):
    if item == "triple":
        item = "multidisparo"
    m = ESTADO_JUEGO["mejoras"]
    if item == "multidisparo":
        return 80 + m.get("multidisparo", 0) * 40
    elif item == "dano":
        return 110 + m.get("dano", 0) * 55
    elif item == "rafaga":
        return 90 + m.get("rafaga", 0) * 45
    elif item == "perforante":
        return 100 + m.get("perforante", 0) * 50
    elif item == "hielo":
        return 85 + m.get("hielo", 0) * 40
    elif item == "rebote":
        return 95 + m.get("rebote", 0) * 45
    elif item == "iman":
        return 70 + m.get("iman", 0) * 35
    elif item == "velocidad":
        return 60 + m.get("velocidad", 0) * 30
    elif item == "vision":
        return 50 + m.get("vision", 0) * 25
    elif item == "vida":
        return 60 + max(0, ESTADO_JUEGO["max_vidas"] - 3) * 30
    elif item == "escudo":
        return 75 + ESTADO_JUEGO["max_escudo"] * 35
    return 100

def obtener_resumen_tienda():
    return {
        "multidisparo": {"nivel": ESTADO_JUEGO["mejoras"].get("multidisparo", 0), "costo": obtener_costo_mejora("multidisparo")},
        "dano": {"nivel": ESTADO_JUEGO["mejoras"].get("dano", 0), "costo": obtener_costo_mejora("dano")},
        "rafaga": {"nivel": ESTADO_JUEGO["mejoras"].get("rafaga", 0), "costo": obtener_costo_mejora("rafaga")},
        "perforante": {"nivel": ESTADO_JUEGO["mejoras"].get("perforante", 0), "costo": obtener_costo_mejora("perforante")},
        "hielo": {"nivel": ESTADO_JUEGO["mejoras"].get("hielo", 0), "costo": obtener_costo_mejora("hielo")},
        "rebote": {"nivel": ESTADO_JUEGO["mejoras"].get("rebote", 0), "costo": obtener_costo_mejora("rebote")},
        "iman": {"nivel": ESTADO_JUEGO["mejoras"].get("iman", 0), "costo": obtener_costo_mejora("iman")},
        "velocidad": {"nivel": ESTADO_JUEGO["mejoras"].get("velocidad", 0), "costo": obtener_costo_mejora("velocidad")},
        "vision": {"nivel": ESTADO_JUEGO["mejoras"].get("vision", 0), "costo": obtener_costo_mejora("vision")},
        "vida": {"nivel": ESTADO_JUEGO["max_vidas"], "costo": obtener_costo_mejora("vida")},
        "escudo": {"nivel": ESTADO_JUEGO["max_escudo"], "costo": obtener_costo_mejora("escudo")},
    }

def obtener_radio_vision():
    lv_vis = ESTADO_JUEGO["mejoras"].get("vision", 0)
    return 105 + lv_vis * 25

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
    cantidad = min(3 + nivel, 15)
    enemigos = []
    
    # Cada 5 niveles hay un Jefe Dorado desafiante
    tiene_jefe = (nivel % 5 == 0)

    for i in range(cantidad):
        c = random.randint(cols // 3, cols - 1)
        r = random.randint(0, filas - 1)
        ex = c * ancho_celda + (ancho_celda - tam_p) // 2
        ey = r * alto_celda + (alto_celda - tam_p) // 2

        if tiene_jefe and i == 0:
            # Jefe Dorado (20+ HP, alto botín)
            vida = 18 + nivel * 2
            enemigo = {
                "x": float(ex), "y": float(ey), "cd": random.randint(15, 30),
                "vida": vida, "vida_max": vida, "tipo": "jefe",
                "color": (0, 215, 255), "borde": (50, 245, 255),
                "oro": 120 + nivel * 10, "vel": 2.2, "congelado_hasta": 0.0
            }
        else:
            rnd = random.random()
            if nivel >= 4 and rnd < 0.28:
                # Tanque Verde: 10 HP (¡aguanta 10 disparos!)
                vida = 10
                enemigo = {
                    "x": float(ex), "y": float(ey), "cd": random.randint(25, 45),
                    "vida": vida, "vida_max": vida, "tipo": "verde",
                    "color": (40, 215, 50), "borde": (100, 255, 120),
                    "oro": 60 + nivel * 5, "vel": 1.5, "congelado_hasta": 0.0
                }
            elif nivel >= 3 and rnd < 0.55:
                # Blindado Morado: 6 HP
                vida = 6
                enemigo = {
                    "x": float(ex), "y": float(ey), "cd": random.randint(20, 42),
                    "vida": vida, "vida_max": vida, "tipo": "morado",
                    "color": (210, 40, 160), "borde": (255, 120, 220),
                    "oro": 35 + nivel * 4, "vel": 1.8, "congelado_hasta": 0.0
                }
            elif nivel >= 2 and rnd < 0.80:
                # Ágil Naranja: 3 HP
                vida = 3
                enemigo = {
                    "x": float(ex), "y": float(ey), "cd": random.randint(15, 36),
                    "vida": vida, "vida_max": vida, "tipo": "naranja",
                    "color": (30, 140, 255), "borde": (80, 210, 255),
                    "oro": 22 + nivel * 3, "vel": 2.5, "congelado_hasta": 0.0
                }
            else:
                # Básico Rojo: 1 HP (muere de 1 impacto)
                vida = 1
                enemigo = {
                    "x": float(ex), "y": float(ey), "cd": random.randint(22, 50),
                    "vida": vida, "vida_max": vida, "tipo": "rojo",
                    "color": (45, 45, 235), "borde": (100, 100, 255),
                    "oro": 12 + nivel * 2, "vel": 2.0, "congelado_hasta": 0.0
                }
        enemigos.append(enemigo)
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
    if item == "triple":
        item = "multidisparo"
    costo = obtener_costo_mejora(item)
    if ESTADO_JUEGO["monedas"] < costo:
        mostrar_aviso(f"Necesitas {costo}G de oro")
        return

    if item in ["multidisparo", "dano", "rafaga", "perforante", "hielo", "rebote", "iman", "velocidad", "vision"]:
        ESTADO_JUEGO["monedas"] -= costo
        ESTADO_JUEGO["mejoras"][item] += 1
        nuevo_lv = ESTADO_JUEGO["mejoras"][item]
        nombres = {
            "multidisparo": f"¡Multidisparo Nivel {nuevo_lv}!",
            "dano": f"¡Daño Potenciado Nivel {nuevo_lv} (+{nuevo_lv+1} Daño)! ",
            "rafaga": f"¡Ráfaga Nivel {nuevo_lv}!",
            "perforante": f"¡Bala Perforante Nivel {nuevo_lv}!",
            "hielo": f"¡Balas Criogénicas Nivel {nuevo_lv} (Congela 60%)!",
            "rebote": f"¡Rebote Balístico Nivel {nuevo_lv}!",
            "iman": f"¡Imán de Oro Nivel {nuevo_lv} (+{nuevo_lv*25}%)!",
            "velocidad": f"¡Botas Nivel {nuevo_lv} (+20% Vel)!",
            "vision": f"¡Linterna Nivel {nuevo_lv} (+25px)!",
        }
        mostrar_aviso(nombres.get(item, f"¡{item.upper()} Nivel {nuevo_lv}!"))
    elif item == "vida":
        ESTADO_JUEGO["monedas"] -= costo
        ESTADO_JUEGO["max_vidas"] += 1
        ESTADO_JUEGO["vidas"] = min(ESTADO_JUEGO["max_vidas"], ESTADO_JUEGO["vidas"] + 1)
        mostrar_aviso(f"¡+1 Vida Máxima! ({ESTADO_JUEGO['vidas']}/{ESTADO_JUEGO['max_vidas']})")
    elif item == "escudo":
        ESTADO_JUEGO["monedas"] -= costo
        ESTADO_JUEGO["max_escudo"] += 1
        ESTADO_JUEGO["escudo"] = ESTADO_JUEGO["max_escudo"]
        mostrar_aviso(f"¡Escudo de Plasma Nivel {ESTADO_JUEGO['max_escudo']}!")

def disparar_armas_jugador(cx, cy, target_x, target_y):
    dx, dy = target_x - cx, target_y - cy
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    angulo_base = math.atan2(dy, dx)
    vel_base = 14.0 + ESTADO_JUEGO["mejoras"].get("rafaga", 0) * 1.5

    lv_multi = ESTADO_JUEGO["mejoras"].get("multidisparo", 0)
    if lv_multi <= 0:
        angulos = [angulo_base]
    else:
        num_balas = 1 + lv_multi * 2
        apertura_total = min(1.3, 0.22 * num_balas)
        paso = apertura_total / (num_balas - 1)
        angulos = [angulo_base - apertura_total / 2.0 + paso * i for i in range(num_balas)]

    lv_rafaga = ESTADO_JUEGO["mejoras"].get("rafaga", 0)
    if lv_rafaga <= 0:
        multiplicadores_rafaga = [1.0]
    else:
        cant_rafaga = min(7, 1 + lv_rafaga * 2)
        multiplicadores_rafaga = [1.0 - i * 0.12 for i in range(cant_rafaga)]

    lv_perf = ESTADO_JUEGO["mejoras"].get("perforante", 0)
    perforaciones = 1 + lv_perf * 3
    rebotes = ESTADO_JUEGO["mejoras"].get("rebote", 0)

    for mult in multiplicadores_rafaga:
        vel = vel_base * mult
        for ang in angulos:
            vx = math.cos(ang) * vel
            vy = math.sin(ang) * vel
            ESTADO_JUEGO["balas"].append([cx, cy, vx, vy, perforaciones, rebotes])

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
        cd_recarga = max(1.8, 5.0 - ESTADO_JUEGO["max_escudo"] * 0.4)
        if ahora - ESTADO_JUEGO["ultimo_dano"] >= cd_recarga:
            ESTADO_JUEGO["escudo"] += 1
            ESTADO_JUEGO["ultimo_dano"] = ahora
            mostrar_aviso("¡Escudo recargado!")

    radio_bala = 4
    nuevas_balas = []
    dano_jugador = 1 + ESTADO_JUEGO["mejoras"].get("dano", 0)
    lv_hielo = ESTADO_JUEGO["mejoras"].get("hielo", 0)
    tiempo_congelar = (2.2 + lv_hielo * 0.6) if lv_hielo > 0 else 0.0
    mult_oro = 1.0 + ESTADO_JUEGO["mejoras"].get("iman", 0) * 0.25

    # 1. Mover balas del jugador
    for bala in ESTADO_JUEGO["balas"]:
        bx, by, vx, vy, perf, rebs = bala[0], bala[1], bala[2], bala[3], bala[4], bala[5]
        nbx, nby = bx + vx, by + vy
        cercanas_b = obtener_paredes_en_rango(nbx, nby, radio_bala*2, radio_bala*2, paredes, radio=40, min_k=4)
        
        if toca_pared(nbx - radio_bala, nby - radio_bala, radio_bala*2, radio_bala*2, cercanas_b):
            if rebs > 0:
                rebs -= 1
                vx = -vx
                vy = -vy
                nbx = bx + vx
                nby = by + vy
            else:
                perf -= 1
                if perf <= 0:
                    continue

        impacto = False
        for i in range(len(ESTADO_JUEGO["enemigos"]) - 1, -1, -1):
            en = ESTADO_JUEGO["enemigos"][i]
            ex, ey = en["x"], en["y"]
            if rect_colision(nbx - radio_bala, nby - radio_bala, radio_bala*2, radio_bala*2, ex, ey, tam_p, tam_p):
                en["vida"] -= dano_jugador

                if tiempo_congelar > 0:
                    en["congelado_hasta"] = ahora + tiempo_congelar

                if en["vida"] <= 0:
                    oro_ganado = int(en.get("oro", 15) * mult_oro)
                    ESTADO_JUEGO["monedas"] += oro_ganado
                    ESTADO_JUEGO["enemigos_derrotados_nivel"] += 1
                    tipo_str = en.get("tipo", "enemigo").capitalize()
                    mostrar_aviso(f"+{oro_ganado}G (¡{tipo_str} derrotado!)")
                    ESTADO_JUEGO["enemigos"].pop(i)
                else:
                    mostrar_aviso(f"¡Impacto! {en['vida']}/{en['vida_max']} HP")

                perf -= 1
                impacto = True
                if perf <= 0:
                    break

        if perf > 0 and 0 <= nbx <= W and 0 <= nby <= H:
            nuevas_balas.append([nbx, nby, vx, vy, perf, rebs])

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
    rad_v = obtener_radio_vision()
    for en in ESTADO_JUEGO["enemigos"]:
        ex, ey = en["x"], en["y"]
        dx, dy = px - ex, py - ey
        dist = math.hypot(dx, dy)
        vel_en = en.get("vel", 2.0)

        if ahora < en.get("congelado_hasta", 0.0):
            vel_en *= 0.45
        
        if 0 < dist < rad_v * 1.5:
            vx = (dx / dist) * vel_en
            vy = (dy / dist) * vel_en
            cercanas_e = obtener_paredes_en_rango(ex, ey, tam_p, tam_p, paredes, radio=50, min_k=4)
            if not toca_pared(ex + vx, ey, tam_p, tam_p, cercanas_e):
                en["x"] += vx
            if not toca_pared(en["x"], ey + vy, tam_p, tam_p, cercanas_e):
                en["y"] += vy

            en["cd"] -= 1
            if en["cd"] <= 0:
                vel_be = 7.5
                ecx, ecy = en["x"] + tam_p / 2.0, en["y"] + tam_p / 2.0
                ESTADO_JUEGO["balas_enemigas"].append([ecx, ecy, (dx / dist) * vel_be, (dy / dist) * vel_be])
                cadencia = 22 if en["tipo"] == "jefe" else (30 if en["tipo"] == "naranja" else 42)
                en["cd"] = random.randint(cadencia, cadencia + 25)

        if rect_colision(px, py, tam_p, tam_p, en["x"], en["y"], tam_p, tam_p):
            en["x"] -= (dx / max(1.0, dist)) * 18
            en["y"] -= (dy / max(1.0, dist)) * 18
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
            lv_vel = ESTADO_JUEGO["mejoras"].get("velocidad", 0)
            max_speed = 8 + lv_vel * 2
            dx = max(-max_speed, min(max_speed, int(x_dest) - x_origen))
            dy = max(-max_speed, min(max_speed, int(y_dest) - y_origen))
            pasos = max(abs(dx), abs(dy))
            rad_v = obtener_radio_vision()
            for i in range(1, pasos + 1):
                sig_x = int(round(x_origen + (dx / pasos) * i))
                sig_y = int(round(y_origen + (dy / pasos) * i))
                paredes_cercanas = obtener_paredes_en_rango(sig_x, sig_y, tam_p, tam_p, paredes, radio=rad_v, min_k=4)
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

        # Si toca el tesoro -> premio según el nivel y abre la tienda sobre el tablero
        gano = rect_colision(x_origen, y_origen, tam_p, tam_p, tx, ty, tam_t, tam_t)
        if gano:
            mult_oro = 1.0 + ESTADO_JUEGO["mejoras"].get("iman", 0) * 0.25
            premio_nivel = int((100 + ESTADO_JUEGO["nivel"] * 25) * mult_oro)
            premio_enemigos = int(ESTADO_JUEGO["enemigos_derrotados_nivel"] * (12 + ESTADO_JUEGO["nivel"] * 3) * mult_oro)
            ESTADO_JUEGO["monedas"] += premio_nivel
            ESTADO_JUEGO["ultimo_premio_nivel"] = premio_nivel
            ESTADO_JUEGO["ultimo_premio_enemigos"] = premio_enemigos
            ESTADO_JUEGO["nivel"] += 1
            ESTADO_JUEGO["en_tienda"] = True
            x_origen, y_origen = 8, 8
            ESTADO_JUEGO["balas"].clear()
            ESTADO_JUEGO["balas_enemigas"].clear()

        p.x, p.y = x_origen, y_origen
        p.save()

    # --- RENDERIZADO EN CUARTO OSCURO ---
    ahora_render = time.time()
    sprite_p, sprite_t = cargar_sprites(p.imagen.url, tam_p, tam_t)
    img = np.full((H, W, 3), 12, dtype=np.uint8)
    
    cx_p = int(x_origen + tam_p // 2)
    cy_p = int(y_origen + tam_p // 2)
    rad_v = obtener_radio_vision()

    cv2.circle(img, (cx_p, cy_p), rad_v, (28, 28, 34), -1)
    cv2.circle(img, (cx_p, cy_p), int(rad_v * 0.65), (42, 42, 50), -1)
    cv2.circle(img, (cx_p, cy_p), int(rad_v * 0.35), (56, 56, 66), -1)

    paredes_visibles = obtener_paredes_en_rango(x_origen, y_origen, tam_p, tam_p, paredes, radio=rad_v, min_k=4)
    for x1, y1, x2, y2 in paredes_visibles:
        cv2.line(img, (x1, y1), (x2, y2), color_pared, 3)

    if math.hypot((tx + tam_t/2) - cx_p, (ty + tam_t/2) - cy_p) <= rad_v:
        pegar_sprite_seguro(img, sprite_t, tx, ty)

    pegar_sprite_seguro(img, sprite_p, x_origen, y_origen)

    if ESTADO_JUEGO["escudo"] > 0:
        cv2.circle(img, (cx_p, cy_p), int(tam_p * 0.85), (255, 220, 0), 2)
        cv2.circle(img, (cx_p, cy_p), int(tam_p * 0.95), (255, 170, 0), 1)

    # Renderizado de enemigos con tiers de color y barra de vida flotante
    for en in ESTADO_JUEGO["enemigos"]:
        ex, ey = en["x"], en["y"]
        if math.hypot((ex + tam_p/2) - cx_p, (ey + tam_p/2) - cy_p) <= rad_v:
            ix, iy = int(ex), int(ey)
            es_congelado = ahora_render < en.get("congelado_hasta", 0.0)
            color_cuerpo = (255, 225, 120) if es_congelado else en.get("color", (45, 45, 235))
            color_borde = (255, 255, 200) if es_congelado else en.get("borde", (100, 100, 255))
            
            cv2.rectangle(img, (ix, iy), (ix + tam_p, iy + tam_p), color_cuerpo, -1)
            cv2.rectangle(img, (ix, iy), (ix + tam_p, iy + tam_p), color_borde, 2)

            # Efecto corona si es Jefe Dorado
            if en.get("tipo") == "jefe":
                cv2.circle(img, (ix + tam_p // 2, iy + tam_p // 2), int(tam_p * 0.85), (0, 240, 255), 1)

            # Barra de vida flotante si vida_max > 1
            vida_max = en.get("vida_max", 1)
            if vida_max > 1:
                vida_act = max(0, en.get("vida", 1))
                bar_w = tam_p + 4
                bar_h = 3
                bar_x = ix - 2
                bar_y = max(1, iy - 6)
                # Fondo oscuro de barra
                cv2.rectangle(img, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (25, 25, 25), -1)
                pct = max(0.0, min(1.0, vida_act / float(vida_max)))
                fill_w = int(bar_w * pct)
                if fill_w > 0:
                    col_hp = (40, 220, 60) if pct > 0.5 else ((30, 200, 245) if pct > 0.25 else (40, 40, 245))
                    cv2.rectangle(img, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), col_hp, -1)

    # Renderizado de balas del jugador
    lv_perf = ESTADO_JUEGO["mejoras"].get("perforante", 0)
    lv_dano = ESTADO_JUEGO["mejoras"].get("dano", 0)
    lv_hielo = ESTADO_JUEGO["mejoras"].get("hielo", 0)
    lv_rebote = ESTADO_JUEGO["mejoras"].get("rebote", 0)

    if lv_hielo > 0:
        color_bala_j = (255, 235, 120)  # Glacial cyan
    elif lv_dano > 0:
        color_bala_j = (40, 160, 255)  # Fuego / plasma naranja
    elif lv_perf > 0:
        color_bala_j = (255, 230, 50)  # Amarillo dorado
    else:
        color_bala_j = (0, 210, 255)   # Azul clásico

    tam_bala = 4 + min(4, lv_perf + (1 if lv_dano > 1 else 0))

    for b in ESTADO_JUEGO["balas"]:
        bx, by = b[0], b[1]
        ibx, iby = int(bx), int(by)
        cv2.circle(img, (ibx, iby), tam_bala, color_bala_j, -1)
        if lv_rebote > 0:
            cv2.circle(img, (ibx, iby), tam_bala + 2, (120, 255, 180), 1)
        elif lv_perf > 0:
            cv2.circle(img, (ibx, iby), tam_bala + 2, (100, 255, 255), 1)

    # Renderizado de balas enemigas
    for ebx, eby, _, _ in ESTADO_JUEGO["balas_enemigas"]:
        if math.hypot(ebx - cx_p, eby - cy_p) <= rad_v * 1.2:
            cv2.circle(img, (int(ebx), int(eby)), 4, (60, 60, 255), -1)

    ok, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    response = HttpResponse(buffer.tobytes(), content_type="image/jpg")
    
    msg_hud = ESTADO_JUEGO["mensaje_hud"] if time.time() < ESTADO_JUEGO["tiempo_mensaje"] else ""
    response["X-Mensaje-HUD"] = msg_hud
    
    response["X-En-Tienda"] = "1" if ESTADO_JUEGO["en_tienda"] else "0"
    response["X-Monedas"] = str(ESTADO_JUEGO["monedas"])
    response["X-Nivel"] = str(ESTADO_JUEGO["nivel"])
    response["X-Vidas"] = str(ESTADO_JUEGO["vidas"])
    response["X-Max-Vidas"] = str(ESTADO_JUEGO["max_vidas"])
    response["X-Escudo"] = str(ESTADO_JUEGO["escudo"])
    response["X-Max-Escudo"] = str(ESTADO_JUEGO["max_escudo"])
    response["X-Premio-Nivel"] = str(ESTADO_JUEGO["ultimo_premio_nivel"])
    response["X-Premio-Enemigos"] = str(ESTADO_JUEGO["ultimo_premio_enemigos"])
    response["X-Kills"] = str(ESTADO_JUEGO["enemigos_derrotados_nivel"])
    response["X-Info-Tienda"] = json.dumps(obtener_resumen_tienda())
    response["Cache-Control"] = "no-store"
    return response

def tablero(request):
    return render(request, "tablero.html")