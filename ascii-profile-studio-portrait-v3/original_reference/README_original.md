# ASCII Profile Studio

Gerador de **cartões SVG estilo terminal/neofetch para GitHub**, com **retrato ASCII a partir de sua própria foto** e todos os campos livremente editáveis. Inclui editor local no navegador, modo claro/escuro, importação opcional de dados públicos do GitHub e geração via linha de comando. Feito em Python, sem serviços de IA nem upload de imagem a terceiros.

Inspirado no estilo visual do perfil de [Andrew6rant](https://github.com/Andrew6rant/Andrew6rant). Implementação independente.

![Exemplo gerado com campos fictícios](output/preview.png)

## Visualizar e editar (Fedora, Linux, Windows ou macOS)

### 1. Preparar o Python

Fedora (atalho que prepara o ambiente e inicia):

```bash
./iniciar-fedora.sh
```

Ou configure manualmente:

```bash
sudo dnf install python3 python3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Abrir o editor

```bash
python app.py
```

Acesse **http://127.0.0.1:8765** no navegador. O editor oferece:

- Envio de foto PNG, JPG ou WebP, independente do avatar do GitHub.
- Inclusão/exclusão/reordenação de **seções e campos**. Por exemplo, troque `Uptime` por `Projetos` ou remova o campo inteiramente.
- Configuração de densidade, contraste, brilho, conjunto de caracteres ASCII e cores.
- Prévia do SVG antes de salvar; clique **Salvar alterações e gerar SVG** para escrever `config.yaml`, `output/dark_mode.svg` e `output/light_mode.svg`.
- Botão **Buscar estatísticas públicas** para obter total de repositórios públicos e seguidores (sem autenticação). Demais métricas devem ser preenchidas manualmente.

O aplicativo funciona **somente no seu computador**, no endereço local `127.0.0.1`. A foto não é enviada para serviços externos. A consulta opcional das estatísticas acessa a API pública do GitHub.

### 3. Opção: editar só o YAML e regenerar

```bash
python generator.py
```

Tudo está em `config.yaml` e usa listas de seções e campos:

```yaml
sections:
  - title: ""
    rows:
      - label: "OS"
        value: "Fedora Linux"
      - label: "Projetos"
        value: "IA, web e automação"
  - title: "Contato"
    rows:
      - label: "GitHub"
        value: "github.com/seu-usuario"
```

Para mudar a foto, copie um PNG/JPG para `assets/` e altere `profile.photo` no YAML, ou use o seletor do editor.

### 4. Publicar no README do GitHub

1. Crie um repositório **público** com o mesmo nome do seu usuário GitHub (ex.: `meunome/meunome`).
2. Envie os arquivos deste projeto para lá ou apenas os arquivos `output/*.svg` e um README.
3. Se publicar todo o projeto, copie o conteúdo de [README_PROFILE_TEMPLATE.md](README_PROFILE_TEMPLATE.md) para seu `README.md` do repositório de perfil. **Atenção:** substituir o README do próprio projeto pelo perfil faz sentido apenas se você usar o mesmo repositório para ambas as coisas. É mais organizado manter dois repositórios: um do gerador e outro do perfil. Nesse segundo caso, copie os arquivos para um diretório `output` no repositório de perfil.
4. Configure as informações e seus links; faça commit.

O projeto também traz uma [GitHub Action](.github/workflows/generate.yml) que gera os SVGs após alterações em `config.yaml`, `generator.py` ou `assets/`, e os salva no repositório. **Esse workflow não atualiza os números do GitHub periodicamente**; edite os valores ou acrescente uma rotina se quiser acompanhamento contínuo.

## Estrutura

```text
ascii-profile-studio/
├── app.py                         # servidor web local
├── generator.py                   # foto → ASCII → SVG
├── config.yaml                    # todas as informações editáveis
├── assets/
│   ├── retrato.png                # foto principal (pode trocar)
│   └── foto-original.jpg          # foto original
├── static/index.html              # editor em navegador
├── output/dark_mode.svg           # resultado escuro
├── output/light_mode.svg          # resultado claro
├── .github/workflows/generate.yml # opcional: atualizar SVG no push
└── README_PROFILE_TEMPLATE.md     # trecho para o README do perfil
```

## Testes

```bash
python -m unittest discover -s tests
```

## Considerações

- O retrato ASCII é calculado com pixels, transparência, brilho e um conjunto de caracteres. A precisão varia conforme foto, iluminação e resolução. Experimente `34–44` colunas e contraste `1.1–1.5`.
- SVG preserva linhas e caracteres editáveis. Não é uma captura de tela gerada por IA.
- Para um formato de retrato vertical, considere uma foto sem fundo: a imagem fornecida vem com as duas opções.
- O SVG usa fontes monoespaçadas comuns, sem incluir arquivos de fontes no repositório.
- Fotos e informações pessoais incluídas em um repositório **público** ficam públicas. Se não quiser publicar a foto original, publique apenas os dois SVGs no repositório do perfil e mantenha o gerador e as fotos localmente ou em repositório privado.
- A licença MIT cobre o **código do gerador**, não concede direitos sobre a fotografia pessoal do usuário.
- Se quiser que o perfil seja sempre sincronizado entre dois repositórios, é necessário copiar os SVGs exportados para o repositório do perfil ou configurar uma action dedicada.

## Licença

MIT — veja [LICENSE](LICENSE).
