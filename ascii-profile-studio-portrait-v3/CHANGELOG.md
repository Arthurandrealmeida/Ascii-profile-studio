# Registro de versões

## 3.0 — Retrato ASCII detalhado

- Fonte do novo retrato: selfie original com olhos visíveis, máscara de fundo preparada localmente e crop específico para a região do rosto. O rosto em si não foi gerado por IA.
- Novo modo `portrait` com grade de até 120 × 90 caracteres, contraste local e tonalidade por caractere.
- **SVG exclusivamente com texto** no retrato, sem elementos de imagem embutida.
- Controle de tamanho dos caracteres no editor e preset Terminal clássico atualizado.
- Exportação independente do rosto (`portrait_only.svg`) em arquivo salvo e botão da interface.
- Preservados os modos clássicos, campos, cores, estatísticas, recorte e edição livre.
- Testes ampliados para verificar SVG sem raster, grade de caracteres, zoom, compatibilidade e rota de exportação.
- Fontes e configurações da versão anterior preservadas em `original_reference/`.

---

# Histórico de alterações

## v2.0 — 11/10/2026

### Implementações solicitadas

1. **Retrato ASCII:** modo clássico, bordas e dithering; nitidez e contraste local; resolução ampliada.
2. **Recorte:** interface com zoom, centro horizontal/vertical e arraste sobre canvas; recorte não destrutivo.
3. **Layout:** margens, largura das colunas, distância entre colunas, fonte e espaçamentos personalizáveis.
4. **Cores:** temas claro e escuro editáveis; valores com segmentos coloridos `[[+...]]` / `[[-...]]`.
5. **Exportação e validação:** SVGs exportados diretamente das alterações atuais; valores XML limpos e escrita atômica.
6. **Segurança:** acesso local padrão, checagem de Host e Origin, limites de upload, validação de foto e restrições de caminhos.
7. **Testes:** 28 testes, incluindo API, segurança, SVG, upload, layout, estatísticas e compatibilidade.
8. **Presets:** Andrew (terminal clássico), compacto, neon e minimalista.
9. **Desfazer/refazer:** botões e atalhos de teclado; histórico em memória limitado.
10. **Arrastar e soltar:** campos dentro da mesma seção e seções entre si; botões ↑↓ permanecem disponíveis.
11. **Estatísticas GitHub:** quatro métricas públicas possíveis, cache opt-in e GitHub Actions diária.

### Limitações assumidas

- O GitHub não oferece histórico completo de linhas escritas por todos os usuários numa API pública simples. Esses valores permanecem editáveis ou indisponíveis, não inventados.
- A atualização automática é configurada no repositório GitHub onde o workflow foi publicado; não atualiza outros repositórios automaticamente.
- O enquadramento e a arte ASCII variam por foto; há controles para ajustes manuais.
- Os testes de API e geração foram executados; a automação do navegador não pôde navegar ao servidor local no ambiente de validação.
