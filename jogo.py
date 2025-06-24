import json
import random
import pygame
import requests
import os
import ssl
import time

# --- Bloco de correção SSL ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError: pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- CONSTANTES ---
BRANCO, PRETO, CINZA_CLARO, CINZA_ESCURO = (255, 255, 255), (0, 0, 0), (200, 200, 200), (50, 50, 50)
VERMELHO, AZUL, VERDE, AMARELO = (255, 60, 60), (60, 60, 255), (60, 255, 60), (255, 255, 60)
LARGURA_TELA, ALTURA_TELA = 1000, 700
LARGURA_CARTA, ALTURA_CARTA = 280, 450
POS_CARTA_JOGADOR = (100, 150)
POS_CARTA_IA = (LARGURA_TELA - LARGURA_CARTA - 100, 150)

class Carta:
    def __init__(self, data):
        self.nome = data['nome']
        self.bandeira_url = data['bandeira_url']
        self.atributos = data['atributos']
        self.super_trunfo = data.get('super_trunfo', False)
        self.anti_trunfo = data.get('anti_trunfo', False)
        self.caminho_imagem = f"assets/flags/{self.nome.lower().replace(' ', '_')}.png"
        self._baixar_imagem()
        if os.path.exists(self.caminho_imagem):
            self.imagem_bandeira = pygame.image.load(self.caminho_imagem).convert_alpha()
            self.imagem_bandeira = pygame.transform.scale(self.imagem_bandeira, (240, 140))
        else:
            self.imagem_bandeira = pygame.Surface((240, 140)); self.imagem_bandeira.fill(CINZA_CLARO)

    def _baixar_imagem(self):
        if not os.path.exists(self.caminho_imagem):
            try:
                resposta = requests.get(self.bandeira_url, stream=True, verify=False, timeout=5)
                if resposta.status_code == 200:
                    with open(self.caminho_imagem, 'wb') as f: f.write(resposta.content)
            except requests.exceptions.RequestException: pass

    def __repr__(self): return f"Carta({self.nome})"
    def obter_valor_atributo(self, nome_attr): return self.atributos.get(nome_attr, 0)

class Baralho:
    def __init__(self, arquivo_json):
        self.todas_as_cartas_data = []
        os.makedirs("assets/flags", exist_ok=True)
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            self.todas_as_cartas_data = json.load(f)
        self.cartas = self._criar_cartas()
    
    def _criar_cartas(self):
        cartas_obj = []
        for dados_carta in self.todas_as_cartas_data:
            try: cartas_obj.append(Carta(dados_carta))
            except Exception: print(f"ATENÇÃO: Falha ao criar a carta '{dados_carta.get('nome', 'N/A')}'. Pulando.")
        return cartas_obj

    def embaralhar(self): random.shuffle(self.cartas)

    def distribuir(self, num_jogadores):
        self.embaralhar()
        maos = [[] for _ in range(num_jogadores)]
        for i, carta in enumerate(self.cartas): maos[i % num_jogadores].append(carta)
        return maos

# --- FUNÇÕES DE DESENHO E LÓGICA ---

def desenhar_texto(surface, texto, pos, fonte, cor=BRANCO, center=False):
    texto_surface = fonte.render(texto, True, cor)
    if center:
        texto_rect = texto_surface.get_rect(center=pos)
        surface.blit(texto_surface, texto_rect)
    else:
        surface.blit(texto_surface, pos)
    return texto_surface.get_rect(topleft=pos)

def desenhar_carta(surface, carta, x, y, escondida=False, atributo_selecionado=None, turno_oponente=False):
    retangulo_carta = pygame.Rect(x, y, LARGURA_CARTA, ALTURA_CARTA)
    cor_borda = AMARELO if turno_oponente else PRETO
    
    if escondida:
        pygame.draw.rect(surface, AZUL, retangulo_carta, border_radius=15)
        pygame.draw.rect(surface, BRANCO, retangulo_carta, 4, border_radius=15)
        desenhar_texto(surface, "Super Trunfo", (x + LARGURA_CARTA/2, y + ALTURA_CARTA/2), fonte_titulo, BRANCO, center=True)
        return {}
    
    pygame.draw.rect(surface, BRANCO, retangulo_carta, border_radius=15)
    pygame.draw.rect(surface, cor_borda, retangulo_carta, 4, border_radius=15)
    
    desenhar_texto(surface, carta.nome, (x + 20, y + 15), fonte_titulo, PRETO)
    surface.blit(carta.imagem_bandeira, (x + 20, y + 60))
    
    pos_y_atributo, areas_clicaveis = y + 220, {}
    for nome_attr, valor_attr in carta.atributos.items():
        cor_texto = PRETO
        if nome_attr == atributo_selecionado: cor_texto = VERDE
        
        texto_renderizado = f"{nome_attr.replace('_', ' ').title()}: {valor_attr}"
        rect_atributo = desenhar_texto(surface, texto_renderizado, (x + 20, pos_y_atributo), fonte_atributo, cor_texto)
        areas_clicaveis[nome_attr] = rect_atributo
        pos_y_atributo += 28

    if carta.super_trunfo: desenhar_texto(surface, "SUPER TRUNFO", (x + LARGURA_CARTA/2, y + ALTURA_CARTA - 40), fonte_atributo_destaque, VERMELHO, center=True)
    elif carta.anti_trunfo: desenhar_texto(surface, "ANTI-TRUNFO", (x + LARGURA_CARTA/2, y + ALTURA_CARTA - 40), fonte_atributo_destaque, AZUL, center=True)
    return areas_clicaveis

def desenhar_hud(surface, mao_jogador, mao_ia, pilha_empate):
    desenhar_texto(surface, f"Suas Cartas: {len(mao_jogador)}", (POS_CARTA_JOGADOR[0], POS_CARTA_JOGADOR[1] - 40), fonte_atributo_destaque)
    desenhar_texto(surface, f"Cartas da IA: {len(mao_ia)}", (POS_CARTA_IA[0], POS_CARTA_IA[1] - 40), fonte_atributo_destaque)
    if pilha_empate:
        desenhar_texto(surface, f"Pilha de Empate: {len(pilha_empate)}", (LARGURA_TELA/2, 40), fonte_atributo_destaque, AMARELO, center=True)

def resolver_rodada(carta_jogador, carta_ia, atributo):
    if carta_jogador.super_trunfo and not carta_ia.anti_trunfo: return 'JOGADOR'
    if carta_ia.super_trunfo and not carta_jogador.anti_trunfo: return 'IA'
    if carta_jogador.super_trunfo and carta_ia.anti_trunfo: return 'IA'
    if carta_ia.super_trunfo and carta_jogador.anti_trunfo: return 'JOGADOR'
    
    valor_jogador = carta_jogador.obter_valor_atributo(atributo)
    valor_ia = carta_ia.obter_valor_atributo(atributo)
    
    if valor_jogador > valor_ia: return 'JOGADOR'
    if valor_ia > valor_jogador: return 'IA'
    return 'EMPATE'

def ia_escolhe_atributo(carta_ia):
    # Estratégia simples: escolher o maior valor absoluto. Pode ser melhorada.
    melhor_atributo = max(carta_ia.atributos, key=carta_ia.atributos.get)
    return melhor_atributo

# --- INICIALIZAÇÃO ---
pygame.init()
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
tela = pygame.display.set_mode((LARGURA_TELA, ALTURA_TELA))
pygame.display.set_caption("Super Trunfo - Países")
clock = pygame.time.Clock()
fonte_titulo = pygame.font.Font(None, 36)
fonte_atributo = pygame.font.Font(None, 26)
fonte_atributo_destaque = pygame.font.Font(None, 28)
fonte_resultado = pygame.font.Font(None, 90)
fonte_menu = pygame.font.Font(None, 70)

# --- Variáveis de estado do Jogo ---
baralho_paises = Baralho('baralho.json')
mao_jogador, mao_ia, pilha_empate = [], [], []
areas_clicaveis_jogador = {}
game_state = 'TELA_INICIAL' # TELA_INICIAL, ESCOLHENDO, PENSANDO_IA, RESULTADO, ANIMANDO, FIM_DE_JOGO
turno_do_jogador = True
vencedor_rodada = None
atributo_escolhido = None
tempo_estado = 0
anim_start_time, anim_duration = 0, 0.5

def resetar_jogo():
    """Reseta o jogo para um novo começo."""
    global mao_jogador, mao_ia, pilha_empate, game_state, turno_do_jogador
    maos = baralho_paises.distribuir(2)
    mao_jogador, mao_ia = maos[0], maos[1]
    pilha_empate = []
    game_state = 'ESCOLHENDO'
    turno_do_jogador = True

# --- LOOP PRINCIPAL ---
if __name__ == "__main__":
    rodando = True
    while rodando:
        mouse_pos = pygame.mouse.get_pos()
        # --- EVENTOS ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT: rodando = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if game_state == 'TELA_INICIAL' or game_state == 'FIM_DE_JOGO':
                    resetar_jogo() # Clicar em qualquer lugar nessas telas inicia o jogo
                elif game_state == 'ESCOLHENDO' and turno_do_jogador:
                    for attr, rect in areas_clicaveis_jogador.items():
                        if rect.collidepoint(mouse_pos):
                            atributo_escolhido = attr
                            vencedor_rodada = resolver_rodada(mao_jogador[0], mao_ia[0], atributo_escolhido)
                            game_state = 'RESULTADO'
                            tempo_estado = time.time()
        
        # --- LÓGICA DE JOGO POR ESTADO ---
        if game_state == 'PENSANDO_IA':
            if time.time() - tempo_estado > 1: # IA "pensa" por 1 segundo
                atributo_escolhido = ia_escolhe_atributo(mao_ia[0])
                vencedor_rodada = resolver_rodada(mao_jogador[0], mao_ia[0], atributo_escolhido)
                game_state = 'RESULTADO'
                tempo_estado = time.time()

        if game_state == 'RESULTADO':
            if time.time() - tempo_estado > 2: # Mostra resultado por 2 segundos
                game_state = 'ANIMANDO'
                anim_start_time = time.time()

        if game_state == 'ANIMANDO':
            if time.time() - anim_start_time > anim_duration:
                carta_j, carta_i = mao_jogador.pop(0), mao_ia.pop(0)
                if vencedor_rodada == 'JOGADOR':
                    mao_jogador.extend([carta_j, carta_i] + pilha_empate)
                    turno_do_jogador = True
                elif vencedor_rodada == 'IA':
                    mao_ia.extend([carta_j, carta_i] + pilha_empate)
                    turno_do_jogador = False
                else: # EMPATE
                    pilha_empate.extend([carta_j, carta_i])
                
                pilha_empate.clear() if vencedor_rodada != 'EMPATE' else None

                if not mao_ia or not mao_jogador: game_state = 'FIM_DE_JOGO'
                else: game_state = 'PENSANDO_IA' if not turno_do_jogador else 'ESCOLHENDO'
                
                if game_state == 'PENSANDO_IA': tempo_estado = time.time()


        # --- RENDERIZAÇÃO ---
        tela.fill(CINZA_ESCURO)
        
        if game_state == 'TELA_INICIAL':
            desenhar_texto(tela, "Super Trunfo: Países", (LARGURA_TELA/2, ALTURA_TELA/2 - 50), fonte_menu, AMARELO, center=True)
            desenhar_texto(tela, "Clique para Jogar", (LARGURA_TELA/2, ALTURA_TELA/2 + 30), fonte_titulo, BRANCO, center=True)

        elif game_state == 'FIM_DE_JOGO':
            vencedor_final = "VOCÊ GANHOU O JOGO!" if mao_jogador else "A IA GANHOU O JOGO!"
            cor_final = VERDE if mao_jogador else VERMELHO
            desenhar_texto(tela, vencedor_final, (LARGURA_TELA/2, ALTURA_TELA/2 - 50), fonte_resultado, cor_final, center=True)
            desenhar_texto(tela, "Clique para Jogar Novamente", (LARGURA_TELA/2, ALTURA_TELA/2 + 50), fonte_titulo, BRANCO, center=True)
        else:
            desenhar_hud(tela, mao_jogador, mao_ia, pilha_empate)
            carta_j, carta_i = mao_jogador[0], mao_ia[0]

            # Animação
            if game_state == 'ANIMANDO':
                progresso = (time.time() - anim_start_time) / anim_duration
                progresso = min(progresso, 1.0) # Garante que não passe de 1

                if vencedor_rodada == 'JOGADOR':
                    start_pos_j, start_pos_i = POS_CARTA_JOGADOR, POS_CARTA_IA
                    end_pos = (POS_CARTA_JOGADOR[0], ALTURA_TELA)
                elif vencedor_rodada == 'IA':
                    start_pos_j, start_pos_i = POS_CARTA_JOGADOR, POS_CARTA_IA
                    end_pos = (POS_CARTA_IA[0], ALTURA_TELA)
                else: # EMPATE
                    start_pos_j, start_pos_i = POS_CARTA_JOGADOR, POS_CARTA_IA
                    end_pos = (LARGURA_TELA/2 - LARGURA_CARTA/2, -ALTURA_CARTA)

                current_pos_j = (start_pos_j[0] + (end_pos[0] - start_pos_j[0]) * progresso, start_pos_j[1] + (end_pos[1] - start_pos_j[1]) * progresso)
                current_pos_i = (start_pos_i[0] + (end_pos[0] - start_pos_i[0]) * progresso, start_pos_i[1] + (end_pos[1] - start_pos_i[1]) * progresso)
                
                desenhar_carta(tela, carta_j, current_pos_j[0], current_pos_j[1], atributo_selecionado=atributo_escolhido)
                desenhar_carta(tela, carta_i, current_pos_i[0], current_pos_i[1], atributo_selecionado=atributo_escolhido)
            else:
                areas_clicaveis_jogador = desenhar_carta(tela, carta_j, POS_CARTA_JOGADOR[0], POS_CARTA_JOGADOR[1], turno_oponente=(not turno_do_jogador))
                
                escondida = game_state == 'ESCOLHENDO' and turno_do_jogador
                desenhar_carta(tela, carta_i, POS_CARTA_IA[0], POS_CARTA_IA[1], escondida=escondida, atributo_selecionado=atributo_escolhido, turno_oponente=turno_do_jogador)
                
                if game_state == 'PENSANDO_IA':
                    desenhar_texto(tela, "IA está escolhendo...", (LARGURA_TELA/2, 60), fonte_titulo, AMARELO, center=True)
                
                if game_state == 'RESULTADO':
                    if vencedor_rodada == 'JOGADOR': texto, cor = "VOCÊ VENCEU!", VERDE
                    elif vencedor_rodada == 'IA': texto, cor = "VOCÊ PERDEU!", VERMELHO
                    else: texto, cor = "EMPATE!", AMARELO
                    desenhar_texto(tela, texto, (LARGURA_TELA/2, ALTURA_TELA/2), fonte_resultado, cor, center=True)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    print("Jogo finalizado.")