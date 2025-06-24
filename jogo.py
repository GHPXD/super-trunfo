import json
import random
import pygame
import requests
import os
import ssl
import time
from enum import Enum

# --- Bloco de correção SSL (mantido do original) ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- CONSTANTES ---
BRANCO, PRETO, CINZA_CLARO, CINZA_ESCURO = (255, 255, 255), (0, 0, 0), (200, 200, 200), (50, 50, 50)
VERMELHO, AZUL, VERDE, AMARELO = (255, 60, 60), (60, 60, 255), (60, 255, 60), (255, 255, 60)
LARGURA_TELA, ALTURA_TELA = 1000, 700
LARGURA_CARTA, ALTURA_CARTA = 280, 450
POS_CARTA_JOGADOR = (100, 150)
POS_CARTA_IA = (LARGURA_TELA - LARGURA_CARTA - 100, 150)

# --- ENUMS PARA ESTADOS (Melhoria) ---
class GameState(Enum):
    TELA_INICIAL = 1
    ESCOLHENDO = 2
    REVELANDO_CARTA_IA = 3
    RESULTADO = 4
    ANIMANDO_FIM_RODADA = 5
    FIM_DE_JOGO = 6

class Difficulty(Enum):
    FACIL = 1
    NORMAL = 2
    DIFICIL = 3

# --- CLASSES DO JOGO ---

class Carta:
    """ Mantida similar à original, mas agora carrega a imagem do verso. """
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
            self.imagem_bandeira = pygame.Surface((240, 140))
            self.imagem_bandeira.fill(CINZA_CLARO)

    def _baixar_imagem(self):
        if not os.path.exists(self.caminho_imagem):
            try:
                resposta = requests.get(self.bandeira_url, stream=True, verify=False, timeout=5)
                if resposta.status_code == 200:
                    with open(self.caminho_imagem, 'wb') as f:
                        f.write(resposta.content)
            except requests.exceptions.RequestException:
                print(f"AVISO: Falha ao baixar a bandeira de {self.nome}")

    def obter_valor_atributo(self, nome_attr):
        return self.atributos.get(nome_attr, 0)

class Baralho:
    """ Mantida similar à original. """
    def __init__(self, arquivo_json):
        self.todas_as_cartas_data = []
        os.makedirs("assets/flags", exist_ok=True)
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            self.todas_as_cartas_data = json.load(f)
        self.cartas = self._criar_cartas()
    
    def _criar_cartas(self):
        return [Carta(dados) for dados in self.todas_as_cartas_data]

    def embaralhar_e_distribuir(self):
        cartas_embaralhadas = self.cartas[:]
        random.shuffle(cartas_embaralhadas)
        metade = len(cartas_embaralhadas) // 2
        return cartas_embaralhadas[:metade], cartas_embaralhadas[metade:]

class Botao:
    """ (Nova Funcionalidade) Classe para criar botões interativos. """
    def __init__(self, x, y, largura, altura, texto, cor_fundo, cor_hover, fonte, cor_texto=BRANCO):
        self.rect = pygame.Rect(x, y, largura, altura)
        self.texto = texto
        self.cor_fundo = cor_fundo
        self.cor_hover = cor_hover
        self.fonte = fonte
        self.cor_texto = cor_texto
        self.is_hovering = False

    def desenhar(self, surface):
        cor_atual = self.cor_hover if self.is_hovering else self.cor_fundo
        pygame.draw.rect(surface, cor_atual, self.rect, border_radius=10)
        
        texto_surf = self.fonte.render(self.texto, True, self.cor_texto)
        texto_rect = texto_surf.get_rect(center=self.rect.center)
        surface.blit(texto_surf, texto_rect)

    def checar_hover(self, pos_mouse):
        self.is_hovering = self.rect.collidepoint(pos_mouse)

    def foi_clicado(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and self.is_hovering

class Jogo:
    """ (Refatoração) Classe principal que encapsula toda a lógica e estado do jogo. """
    def __init__(self):
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512) # Prepara o mixer
        self.tela = pygame.display.set_mode((LARGURA_TELA, ALTURA_TELA))
        pygame.display.set_caption("Super Trunfo - Países (Versão Melhorada)")
        self.clock = pygame.time.Clock()
        self.rodando = True
        
        self.carregar_assets()
        self.baralho = Baralho('baralho.json')
        self.criar_menus()

        self.game_state = GameState.TELA_INICIAL
        self.dificuldade = Difficulty.NORMAL
        
        # Variáveis de estado do jogo
        self.mao_jogador, self.mao_ia, self.pilha_empate = [], [], []
        self.turno_do_jogador = True
        self.atributo_escolhido = None
        self.vencedor_rodada = None
        
        # Variáveis de animação
        self.tempo_estado = 0
        self.anim_progresso = 0
        self.anim_duracao = 0.5 # Duração padrão

    def carregar_assets(self):
        """ (Melhoria) Centraliza o carregamento de assets. """
        self.fontes = {
            'titulo': pygame.font.Font(None, 36),
            'atributo': pygame.font.Font(None, 26),
            'atributo_destaque': pygame.font.Font(None, 28),
            'resultado': pygame.font.Font(None, 90),
            'menu': pygame.font.Font(None, 70),
            'botao': pygame.font.Font(None, 40)
        }
        # Placeholder para sons - substitua 'som.wav' pelos seus arquivos
        self.sons = {
            'vitoria': None, # pygame.mixer.Sound('assets/sounds/vitoria.wav'),
            'derrota': None, # pygame.mixer.Sound('assets/sounds/derrota.wav'),
            'empate': None, # pygame.mixer.Sound('assets/sounds/empate.wav'),
            'click': None, # pygame.mixer.Sound('assets/sounds/click.wav')
        }
        self.imagem_verso_carta = self.criar_imagem_verso()

    def tocar_som(self, nome_som):
        if self.sons.get(nome_som):
            self.sons[nome_som].play()

    def criar_imagem_verso(self):
        surf = pygame.Surface((LARGURA_CARTA, ALTURA_CARTA))
        pygame.draw.rect(surf, AZUL, surf.get_rect(), border_radius=15)
        pygame.draw.rect(surf, BRANCO, surf.get_rect(), 4, border_radius=15)
        self.desenhar_texto(surf, "Super Trunfo", (LARGURA_CARTA/2, ALTURA_CARTA/2), self.fontes['titulo'], BRANCO, center=True)
        return surf

    def criar_menus(self):
        self.botoes_menu = [
            Botao(LARGURA_TELA/2 - 150, 350, 300, 60, "Fácil", CINZA_ESCURO, VERDE, self.fontes['botao']),
            Botao(LARGURA_TELA/2 - 150, 420, 300, 60, "Normal", CINZA_ESCURO, AMARELO, self.fontes['botao']),
            Botao(LARGURA_TELA/2 - 150, 490, 300, 60, "Difícil", CINZA_ESCURO, VERMELHO, self.fontes['botao'])
        ]
        self.botao_jogar_novamente = Botao(LARGURA_TELA/2 - 150, ALTURA_TELA/2 + 100, 300, 60, "Jogar Novamente", AZUL, VERDE, self.fontes['botao'])

    def resetar_jogo(self, dificuldade):
        self.dificuldade = dificuldade
        self.mao_jogador, self.mao_ia = self.baralho.embaralhar_e_distribuir()
        self.pilha_empate = []
        self.turno_do_jogador = random.choice([True, False])
        self.atributo_escolhido = None
        self.vencedor_rodada = None
        self.mudar_estado(GameState.ESCOLHENDO if self.turno_do_jogador else GameState.REVELANDO_CARTA_IA)

    def mudar_estado(self, novo_estado):
        self.game_state = novo_estado
        self.tempo_estado = time.time()
        self.anim_progresso = 0 # Reseta progresso da animação
        
        # Lógica de transição de estado
        if self.game_state == GameState.REVELANDO_CARTA_IA and not self.turno_do_jogador:
            self.anim_duracao = 1.0 # Duração para a IA "pensar"
        elif self.game_state == GameState.RESULTADO:
            self.anim_duracao = 2.0 # Duração para mostrar o resultado
            self.resolver_rodada()
        elif self.game_state == GameState.ANIMANDO_FIM_RODADA:
            self.anim_duracao = 0.7 # Duração da animação das cartas
            
    def run(self):
        while self.rodando:
            self.processar_eventos()
            self.atualizar_logica()
            self.renderizar_tela()
            self.clock.tick(60)
        pygame.quit()

    def processar_eventos(self):
        mouse_pos = pygame.mouse.get_pos()
        
        if self.game_state == GameState.TELA_INICIAL:
            for i, botao in enumerate(self.botoes_menu):
                botao.checar_hover(mouse_pos)
                if botao.foi_clicado(pygame.event.Event(pygame.MOUSEBUTTONDOWN)):
                    self.tocar_som('click')
                    dificuldades = [Difficulty.FACIL, Difficulty.NORMAL, Difficulty.DIFICIL]
                    self.resetar_jogo(dificuldades[i])
        
        elif self.game_state == GameState.FIM_DE_JOGO:
            self.botao_jogar_novamente.checar_hover(mouse_pos)
            if self.botao_jogar_novamente.foi_clicado(pygame.event.Event(pygame.MOUSEBUTTONDOWN)):
                self.tocar_som('click')
                self.mudar_estado(GameState.TELA_INICIAL)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.rodando = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.game_state == GameState.ESCOLHENDO and self.turno_do_jogador:
                    for attr, rect in self.areas_clicaveis_jogador.items():
                        if rect.collidepoint(mouse_pos):
                            self.tocar_som('click')
                            self.atributo_escolhido = attr
                            self.mudar_estado(GameState.REVELANDO_CARTA_IA)
                            self.anim_duracao = 1.0 # Duração da virada da carta

    def atualizar_logica(self):
        """ (Refatoração) Máquina de estados principal para a lógica. """
        delta_tempo = time.time() - self.tempo_estado
        
        # Animação de virar a carta da IA
        if self.game_state == GameState.REVELANDO_CARTA_IA:
            self.anim_progresso = min(delta_tempo / self.anim_duracao, 1.0)
            if self.anim_progresso >= 1.0:
                # Se era turno da IA, ela escolhe o atributo agora
                if not self.turno_do_jogador:
                    self.atributo_escolhido = self.ia_escolhe_atributo()
                self.mudar_estado(GameState.RESULTADO)

        elif self.game_state == GameState.RESULTADO:
            if delta_tempo > self.anim_duracao:
                self.mudar_estado(GameState.ANIMANDO_FIM_RODADA)

        elif self.game_state == GameState.ANIMANDO_FIM_RODADA:
            self.anim_progresso = min(delta_tempo / self.anim_duracao, 1.0)
            if self.anim_progresso >= 1.0:
                self.finalizar_rodada()

    def renderizar_tela(self):
        """ (Refatoração) Máquina de estados principal para a renderização. """
        self.tela.fill(CINZA_ESCURO)

        if self.game_state == GameState.TELA_INICIAL:
            self.renderizar_menu_inicial()
        elif self.game_state == GameState.FIM_DE_JOGO:
            self.renderizar_fim_de_jogo()
        else: # Estados de jogo ativo
            self.renderizar_hud()
            self.renderizar_cartas()
            self.renderizar_feedback_estados()

        pygame.display.flip()

    # --- Funções de Renderização Específicas ---
    
    def renderizar_menu_inicial(self):
        self.desenhar_texto(self.tela, "Super Trunfo: Países", (LARGURA_TELA/2, 150), self.fontes['menu'], AMARELO, center=True)
        self.desenhar_texto(self.tela, "Escolha a Dificuldade:", (LARGURA_TELA/2, 280), self.fontes['titulo'], BRANCO, center=True)
        for botao in self.botoes_menu:
            botao.desenhar(self.tela)

    def renderizar_fim_de_jogo(self):
        vencedor_final = "VOCÊ GANHOU O JOGO!" if self.mao_jogador else "A IA GANHOU O JOGO!"
        cor_final = VERDE if self.mao_jogador else VERMELHO
        self.desenhar_texto(self.tela, vencedor_final, (LARGURA_TELA/2, ALTURA_TELA/2 - 50), self.fontes['resultado'], cor_final, center=True)
        self.botao_jogar_novamente.desenhar(self.tela)

    def renderizar_hud(self):
        self.desenhar_texto(self.tela, f"Suas Cartas: {len(self.mao_jogador)}", (POS_CARTA_JOGADOR[0], POS_CARTA_JOGADOR[1] - 40), self.fontes['atributo_destaque'])
        self.desenhar_texto(self.tela, f"Cartas da IA: {len(self.mao_ia)}", (POS_CARTA_IA[0], POS_CARTA_IA[1] - 40), self.fontes['atributo_destaque'])
        if self.pilha_empate:
            self.desenhar_texto(self.tela, f"Pilha de Empate: {len(self.pilha_empate)}", (LARGURA_TELA/2, 40), self.fontes['atributo_destaque'], AMARELO, center=True)

    def renderizar_cartas(self):
        carta_j = self.mao_jogador[0]
        carta_i = self.mao_ia[0]
        
        if self.game_state == GameState.ANIMANDO_FIM_RODADA:
            self.animar_cartas_fim_rodada(carta_j, carta_i)
        else:
            # Carta do Jogador
            self.areas_clicaveis_jogador = self.desenhar_carta(self.tela, carta_j, POS_CARTA_JOGADOR, turno_oponente=(not self.turno_do_jogador))
            
            # Carta da IA
            if self.game_state == GameState.ESCOLHENDO and self.turno_do_jogador:
                self.tela.blit(self.imagem_verso_carta, POS_CARTA_IA)
            elif self.game_state == GameState.REVELANDO_CARTA_IA:
                self.animar_virada_carta(carta_i)
            else:
                 self.desenhar_carta(self.tela, carta_i, POS_CARTA_IA, atributo_selecionado=self.atributo_escolhido, turno_oponente=self.turno_do_jogador)

    def renderizar_feedback_estados(self):
        if self.game_state == GameState.REVELANDO_CARTA_IA and not self.turno_do_jogador:
             self.desenhar_texto(self.tela, "IA está escolhendo...", (LARGURA_TELA/2, 60), self.fontes['titulo'], AMARELO, center=True)
        
        if self.game_state == GameState.RESULTADO:
            if self.vencedor_rodada == 'JOGADOR': texto, cor = "VOCÊ VENCEU!", VERDE
            elif self.vencedor_rodada == 'IA': texto, cor = "VOCÊ PERDEU!", VERMELHO
            else: texto, cor = "EMPATE!", AMARELO
            self.desenhar_texto(self.tela, texto, (LARGURA_TELA/2, ALTURA_TELA/2 - 80), self.fontes['resultado'], cor, center=True)
            self.renderizar_comparacao_atributo()

    def renderizar_comparacao_atributo(self):
        """ (Nova Funcionalidade) Mostra a comparação de valores. """
        if not self.atributo_escolhido: return

        carta_j = self.mao_jogador[0]
        carta_i = self.mao_ia[0]
        valor_j = carta_j.obter_valor_atributo(self.atributo_escolhido)
        valor_i = carta_i.obter_valor_atributo(self.atributo_escolhido)

        texto_comp = f"{self.atributo_escolhido.replace('_', ' ').title()}: {valor_j} vs {valor_i}"
        
        if self.vencedor_rodada == 'JOGADOR': cor = VERDE
        elif self.vencedor_rodada == 'IA': cor = VERMELHO
        else: cor = AMARELO
        
        self.desenhar_texto(self.tela, texto_comp, (LARGURA_TELA/2, ALTURA_TELA/2), self.fontes['titulo'], cor, center=True)


    # --- Funções de Animação (Melhoria) ---

    def ease_in_out_quad(self, t):
        """ (Nova Funcionalidade) Função de suavização para animações. """
        t *= 2
        if t < 1: return 0.5 * t * t
        t -= 1
        return -0.5 * (t * (t - 2) - 1)

    def animar_virada_carta(self, carta_ia):
        """ (Nova Animação) Anima a carta da IA virando. """
        progresso = self.anim_progresso * 2 - 1  # Mapeia 0->1 para -1->1
        
        escala_x = abs(progresso)
        largura_animada = int(LARGURA_CARTA * escala_x)
        
        if largura_animada == 0: return # Evita erro de escala 0

        if progresso < 0: # Mostra o verso
            imagem_para_desenhar = self.imagem_verso_carta
        else: # Mostra a frente
            # Recria a superfície da carta para desenhar
            surf_frente = pygame.Surface((LARGURA_CARTA, ALTURA_CARTA), pygame.SRCALPHA)
            self.desenhar_carta(surf_frente, carta_ia, (0,0), atributo_selecionado=self.atributo_escolhido)
            imagem_para_desenhar = surf_frente
        
        imagem_redimensionada = pygame.transform.scale(imagem_para_desenhar, (largura_animada, ALTURA_CARTA))
        pos_x_centralizado = POS_CARTA_IA[0] + (LARGURA_CARTA - largura_animada) / 2
        
        self.tela.blit(imagem_redimensionada, (pos_x_centralizado, POS_CARTA_IA[1]))
    
    def animar_cartas_fim_rodada(self, carta_j, carta_i):
        progresso = self.ease_in_out_quad(self.anim_progresso)
        
        start_j, start_i = POS_CARTA_JOGADOR, POS_CARTA_IA
        
        if self.vencedor_rodada == 'JOGADOR':
            end_j = (POS_CARTA_JOGADOR[0], ALTURA_TELA + 50)
            end_i = end_j
        elif self.vencedor_rodada == 'IA':
            end_j = (POS_CARTA_IA[0], ALTURA_TELA + 50)
            end_i = end_j
        else: # EMPATE
            end_j = (LARGURA_TELA/2 - LARGURA_CARTA, -ALTURA_CARTA - 50)
            end_i = (LARGURA_TELA/2, -ALTURA_CARTA - 50)

        pos_j_x = start_j[0] + (end_j[0] - start_j[0]) * progresso
        pos_j_y = start_j[1] + (end_j[1] - start_j[1]) * progresso
        
        pos_i_x = start_i[0] + (end_i[0] - start_i[0]) * progresso
        pos_i_y = start_i[1] + (end_i[1] - start_i[1]) * progresso

        self.desenhar_carta(self.tela, carta_j, (pos_j_x, pos_j_y), atributo_selecionado=self.atributo_escolhido)
        self.desenhar_carta(self.tela, carta_i, (pos_i_x, pos_i_y), atributo_selecionado=self.atributo_escolhido)

    # --- Funções de Lógica ---
    
    def ia_escolhe_atributo(self):
        """ (Melhoria) IA com níveis de dificuldade. """
        carta_ia = self.mao_ia[0]
        if self.dificuldade == Difficulty.FACIL:
            return random.choice(list(carta_ia.atributos.keys()))
        
        # Dificuldade Normal e Difícil (pode ser expandida)
        # Para Difícil, uma estratégia seria analisar os valores médios, etc.
        # Por simplicidade, Normal e Difícil usarão a melhor escolha.
        return max(carta_ia.atributos, key=carta_ia.atributos.get)

    def resolver_rodada(self):
        carta_j = self.mao_jogador[0]
        carta_i = self.mao_ia[0]

        if carta_j.super_trunfo and not carta_i.anti_trunfo: self.vencedor_rodada = 'JOGADOR'
        elif carta_i.super_trunfo and not carta_j.anti_trunfo: self.vencedor_rodada = 'IA'
        elif carta_j.super_trunfo and carta_i.anti_trunfo: self.vencedor_rodada = 'IA' # Anti-trunfo vence
        elif carta_i.super_trunfo and carta_j.anti_trunfo: self.vencedor_rodada = 'JOGADOR' # Anti-trunfo vence
        else:
            valor_j = carta_j.obter_valor_atributo(self.atributo_escolhido)
            valor_i = carta_i.obter_valor_atributo(self.atributo_escolhido)
            if valor_j > valor_i: self.vencedor_rodada = 'JOGADOR'
            elif valor_i > valor_j: self.vencedor_rodada = 'IA'
            else: self.vencedor_rodada = 'EMPATE'
        
        # Tocar som com base no resultado
        if self.vencedor_rodada == 'JOGADOR': self.tocar_som('vitoria')
        elif self.vencedor_rodada == 'IA': self.tocar_som('derrota')
        else: self.tocar_som('empate')

    def finalizar_rodada(self):
        """ Atualiza as mãos após a animação de fim de rodada. """
        carta_j = self.mao_jogador.pop(0)
        carta_i = self.mao_ia.pop(0)
        
        cartas_da_rodada = [carta_j, carta_i] + self.pilha_empate
        self.pilha_empate.clear()

        if self.vencedor_rodada == 'JOGADOR':
            self.mao_jogador.extend(cartas_da_rodada)
            self.turno_do_jogador = True
        elif self.vencedor_rodada == 'IA':
            self.mao_ia.extend(cartas_da_rodada)
            self.turno_do_jogador = False
        else: # EMPATE
            self.pilha_empate.extend(cartas_da_rodada)
            # O turno não muda em caso de empate
        
        self.atributo_escolhido = None

        if not self.mao_jogador or not self.mao_ia:
            self.mudar_estado(GameState.FIM_DE_JOGO)
        else:
            novo_estado = GameState.ESCOLHENDO if self.turno_do_jogador else GameState.REVELANDO_CARTA_IA
            self.mudar_estado(novo_estado)

    # --- Funções de Desenho ---
    def desenhar_texto(self, surface, texto, pos, fonte, cor=BRANCO, center=False):
        texto_surface = fonte.render(texto, True, cor)
        if center:
            texto_rect = texto_surface.get_rect(center=pos)
            surface.blit(texto_surface, texto_rect)
        else:
            surface.blit(texto_surface, pos)
        return texto_surface.get_rect(topleft=pos)

    def desenhar_carta(self, surface, carta, pos, escondida=False, atributo_selecionado=None, turno_oponente=False):
        x, y = pos
        if escondida:
            surface.blit(self.imagem_verso_carta, pos)
            return {}

        retangulo_carta = pygame.Rect(x, y, LARGURA_CARTA, ALTURA_CARTA)
        cor_borda = AMARELO if turno_oponente else PRETO
        
        pygame.draw.rect(surface, BRANCO, retangulo_carta, border_radius=15)
        pygame.draw.rect(surface, cor_borda, retangulo_carta, 4, border_radius=15)
        
        self.desenhar_texto(surface, carta.nome, (x + 20, y + 15), self.fontes['titulo'], PRETO)
        surface.blit(carta.imagem_bandeira, (x + 20, y + 60))
        
        pos_y_atributo, areas_clicaveis = y + 220, {}
        mouse_pos = pygame.mouse.get_pos()
        
        for nome_attr, valor_attr in carta.atributos.items():
            cor_texto = PRETO
            is_hovering = False

            # Lógica de highlight
            if self.turno_do_jogador and self.game_state == GameState.ESCOLHENDO:
                temp_rect = pygame.Rect(x + 20, pos_y_atributo, LARGURA_CARTA - 40, 28)
                if temp_rect.collidepoint(mouse_pos):
                    cor_texto = AZUL
                    is_hovering = True

            if nome_attr == atributo_selecionado:
                cor_texto = VERDE if not is_hovering else (60, 255, 60)

            texto_renderizado = f"{nome_attr.replace('_', ' ').title()}: {valor_attr}"
            rect_atributo = self.desenhar_texto(surface, texto_renderizado, (x + 20, pos_y_atributo), self.fontes['atributo'], cor_texto)
            areas_clicaveis[nome_attr] = rect_atributo
            pos_y_atributo += 28

        if carta.super_trunfo:
            self.desenhar_texto(surface, "SUPER TRUNFO", (x + LARGURA_CARTA/2, y + ALTURA_CARTA - 40), self.fontes['atributo_destaque'], VERMELHO, center=True)
        elif carta.anti_trunfo:
            self.desenhar_texto(surface, "ANTI-TRUNFO", (x + LARGURA_CARTA/2, y + ALTURA_CARTA - 40), self.fontes['atributo_destaque'], AZUL, center=True)
        
        return areas_clicaveis

# --- PONTO DE ENTRADA ---
if __name__ == "__main__":
    jogo = Jogo()
    jogo.run()