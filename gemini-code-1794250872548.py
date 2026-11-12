import cv2
import numpy as np
import random
import math

W, H = 1000, 500
WIN_NAME = "Prototipo Laberinto - WASD: Mover | Click: Disparar | Q: Salir"

nivel = 1
px, py = 10.0, 10.0
balas = []     # [x, y, vx, vy]
enemigos = []  # [x, y]

def generar_nivel(niv):
    random.seed(niv * 1337)
    etapa = niv // 10
    cols, filas = min(16 + etapa * 4, 40), min(6 + etapa * 2, 20)
    cw, ch = W // cols, H // filas
    tam_p = max(12, min(26, int(min(cw, ch) * 0.55)))
    
    paredes = [(0, 0, cols*cw, 0), (cols*cw, 0, cols*cw, filas*ch), (cols*cw, filas*ch, 0, filas*ch), (0, filas*ch, 0, 0)]
    vis = [[False]*cols for _ in range(filas)]
    abiertos = set()

    def dfs(r, c):
        vis[r][c] = True
        dirs = [(-1,0), (1,0), (0,-1), (0,1)]
        random.shuffle(dirs)
        for dr, dc in dirs:
            nr, nc = r+dr, c+dc
            if 0 <= nr < filas and 0 <= nc < cols and not vis[nr][nc]:
                abiertos.add(((r,c),(nr,nc)))
                abiertos.add(((nr,nc),(r,c)))
                dfs(nr, nc)
    dfs(0, 0)

    for r in range(filas):
        for c in range(cols):
            x1, y1 = c*cw, r*ch
            if c+1 < cols and ((r,c),(r,c+1)) not in abiertos:
                paredes.append((x1+cw, y1, x1+cw, y1+ch))
            if r+1 < filas and ((r,c),(r+1,c)) not in abiertos:
                paredes.append((x1, y1+ch, x1+cw, y1+ch))

    tx, ty = (cols-1)*cw + (cw-tam_p)//2, (filas-1)*ch + (ch-tam_p)//2
    enems = [[float(random.randint(cols//3, cols-1)*cw + 8), float(random.randint(0, filas-1)*ch + 8)] for _ in range(min(3 + niv//2, 10))]
    return paredes, tam_p, tx, ty, enems

paredes, tam_p, tx, ty, enemigos = generar_nivel(nivel)

def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        cx, cy = px + tam_p/2, py + tam_p/2
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d > 0:
            balas.append([cx, cy, (dx/d)*12.0, (dy/d)*12.0])

cv2.namedWindow(WIN_NAME)
cv2.setMouseCallback(WIN_NAME, on_mouse)

while True:
    img = np.full((H, W, 3), 245, dtype=np.uint8)
    for x1, y1, x2, y2 in paredes:
        cv2.line(img, (x1, y1), (x2, y2), (100, 180, 100), 3)

    # Dibujar Tesoro, Jugador, Enemigos y Balas
    cv2.rectangle(img, (tx, ty), (tx+tam_p, ty+tam_p), (0, 215, 255), -1)
    cv2.rectangle(img, (int(px), int(py)), (int(px)+tam_p, int(py)+tam_p), (220, 100, 30), -1)

    for ex, ey in enemigos:
        cv2.rectangle(img, (int(ex), int(ey)), (int(ex)+tam_p, int(ey)+tam_p), (50, 50, 230), -1)

    for bx, by, _, _ in balas:
        cv2.circle(img, (int(bx), int(by)), 4, (20, 20, 20), -1)

    cv2.imshow(WIN_NAME, img)
    key = cv2.waitKey(16) & 0xFF
    if key == ord('q'):
        break

    # Mover Jugador
    vx = (-6 if key == ord('a') else (6 if key == ord('d') else 0))
    vy = (-6 if key == ord('w') else (6 if key == ord('s') else 0))
    if not toca_pared_local(px+vx, py, tam_p, paredes) if 'toca_pared_local' in globals() else True:
        # Colisión simplificada con las paredes
        choque = any((px+vx+tam_p > min(x1,x2)-2 and px+vx < max(x1,x2)+2 and py+tam_p > min(y1,y2)-2 and py < max(y1,y2)+2) for x1,y1,x2,y2 in paredes)
        if not choque: px += vx
        choque_y = any((px+tam_p > min(x1,x2)-2 and px < max(x1,x2)+2 and py+vy+tam_p > min(y1,y2)-2 and py+vy < max(y1,y2)+2) for x1,y1,x2,y2 in paredes)
        if not choque_y: py += vy

    # Actualizar Balas
    nuevas_b = []
    for bx, by, bvx, bvy in balas:
        nbx, nby = bx + bvx, by + bvy
        if any((nbx+3 > min(x1,x2)-2 and nbx-3 < max(x1,x2)+2 and nby+3 > min(y1,y2)-2 and nby-3 < max(y1,y2)+2) for x1,y1,x2,y2 in paredes):
            continue
        pegado = False
        for i, (ex, ey) in enumerate(enemigos):
            if nbx > ex and nbx < ex+tam_p and nby > ey and nby < ey+tam_p:
                enemigos.pop(i)
                pegado = True
                break
        if not pegado:
            nuevas_b.append([nbx, nby, bvx, bvy])
    balas = nuevas_b

    # Mover Enemigos hacia el Jugador
    for e in enemigos:
        dx, dy = px - e[0], py - e[1]
        d = math.hypot(dx, dy)
        if d > 0:
            evx, evy = (dx/d)*1.8, (dy/d)*1.8
            if not any((e[0]+evx+tam_p > min(x1,x2)-2 and e[0]+evx < max(x1,x2)+2 and e[1]+tam_p > min(y1,y2)-2 and e[1] < max(y1,y2)+2) for x1,y1,x2,y2 in paredes):
                e[0] += evx
            if not any((e[0]+tam_p > min(x1,x2)-2 and e[0] < max(x1,x2)+2 and e[1]+evy+tam_p > min(y1,y2)-2 and e[1]+evy < max(y1,y2)+2) for x1,y1,x2,y2 in paredes):
                e[1] += evy
        # Si atrapa al jugador -> vuelve al inicio (10, 10)
        if px+tam_p > e[0] and px < e[0]+tam_p and py+tam_p > e[1] and py < e[1]+tam_p:
            px, py = 10.0, 10.0
            balas.clear()

    # Si toca el tesoro -> sube de nivel
    if px+tam_p > tx and px < tx+tam_p and py+tam_p > ty and py < ty+tam_p:
        nivel += 1
        px, py = 10.0, 10.0
        balas.clear()
        paredes, tam_p, tx, ty, enemigos = generar_nivel(nivel)

cv2.destroyAllWindows()