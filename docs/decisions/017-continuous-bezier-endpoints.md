# ADR 017 — Continuous Bezier: preservar os handles gravados

Data: 08/10/2026. Status: parcial, implementado na 0.15.1.

## Evidência

py-aep fixado em edcae7abf08dc31b75c878d84b2a4e952105d842,
docs/file_format.md, seção ldat: flag 0x0008 é temporalContinuous, 0x0010
é temporalAutoBezier. Registros não espaciais guardam valor, in speed,
in influence, out speed, out influence por componente. A restrição de
continuidade de edição não autoriza zerar ou equalizar derivadas por suposição.

Auditoria estruturada dos 144 FFX privados encontrou dois streams normais
48 bytes com o flag 0x0008: Dissolve Percent de S_DissolveShake e Amplitude
de S_Shake. Ambos têm duas chaves Bezier. As velocidades gravadas dos lados
externos diferem das internas nos endpoints; não há chave interior nesses
dois streams. Os valores privados permanecem apenas nos artifacts ignorados.
Não foi encontrado stream normal com temporalAutoBezier nesse corpus.

EffectCraft no commit e38a92e792c07f1c57c5dcfcab37d91932b9e2b8 avalia Bezier
manual usando as eases explícitas. O flag continuous é uma restrição de edição;
keys.interpolation/keys.setEase com continuous=true podem alterar handles.
Portanto o Bridge envia curvas Bezier manuais com as derivadas exatas,
e informa a perda desse vínculo de edição. Não usa continuous=true como atalho.

## Perfil aceito

- Stream normal ou intercalado já verificado por tamanho, dimensões e tempo.
- Flags 0x7C0 de labels, além de 0x0008; sem Auto, Roving ou bits desconhecidos.
- Chaves com continuous exigem in/out Bezier explícitos.
- Endpoints conservam todos os valores, inclusive o lado externo não usado.
- Chave interior continuous exige in_speed == out_speed por componente;
  divergência recusa a propriedade inteira, sem usar média ou copiar um lado.
- Influências finitas 0..1, valores e velocidades finitos, tempos em ordem,
  orçamento compartilhado e regras existentes continuam obrigatórios.

IR guarda source_temporal_continuous por componente no metadata. Não houve
mudança de versão do schema: metadata já é campo aberto existente. Exportação
bem-sucedida desse controle acrescenta KEYFRAME_CONTINUITY com loss=true;
strict recusa publicar o resultado. O aviso não bloqueia a leitura dos handles.
Nenhum novo ID de efeito/parâmetro ou unidade foi criado.

Auto Bezier, espacial, Roving, continuidade interior conflitante e curva XML
Premiere continuam sem tradução certificada. S_DissolveShake passa a ter suas
duas chaves decodificadas, mas ainda não possui mapa/renderer por depender de
duas imagens e limites de camada. Não se declara suporte a esse efeito.

## Verificação

13 testes originais sintéticos cobrem endpoints assimétricos, influência,
interior consistente/conflitante, bits recusados, lados Linear/Hold, dimensões,
exportação com loss e ausência de saída strict. Teste real opt-in compara
campos diretamente com os registros ldat do arquivo original, sem distribuí-lo.

S_Shake selecionado real agora exporta 11 propriedades/12 chaves, incluindo
Amplitude com duas chaves antes recusadas. Session nativa própria em 47.952 fps:
11 propriedades/12 chaves, quatro lados Bezier conferidos, três samples internos
por inversão cúbica independente, salvamento/reabertura. UID, índice, enabled,
propriedade não selecionada e composição inicialmente ativa preservados.
Sem comparação visual Adobe; renderer Shake continua aproximação original.

Harness encerrado após a verificação. Evidências ignoradas:
artifacts/auto-bezier-source-audit.json e artifacts/continuous-v0.15.1/native/.
