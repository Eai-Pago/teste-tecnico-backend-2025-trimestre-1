# teste-tecnico-backend-2025-trimestre-1
Teste técnico para a posição de Backend Dev. Edição do primeiro trimestre de 2025.

## A proposta: Upload e Streaming de Vídeos + Cache + Docker

A ideia é bem simples:

- [ ] uma rota `POST /upload/video` que recebe um **único vídeo** com limite de 10MB e
    - [ ] retornando o código de status 400 em caso de arquivo com tipo diferente de vídeo
    - [ ] retornando o código de status 400 em caso de arquivo com tamanho maior que 10MB
    - [ ] retornando o código de status 204 em caso de sucesso
- [ ] uma rota `GET /static/video/:filename` que pode receber um Range por cabeçalho para indicar o offset de streaming
    - [ ] retornando o código de status 404 em caso de não existência de um arquivo
    - [ ] retornando o conteúdo completo caso nenhum range seja especificado com código de status 200 em caso o arquivo exista no servidor
    - [ ] retornando a fatia desejada do conteúdo caso o range seja especificado com código de status 206
    caso o arquivo exista no servidor

Para infra, vamos usar o seguinte conjunto:

- [ ] um arquivo `Dockerfile` para fazer o build da imagem a partir da imagem `node:22-alpine`;
- [ ] um arquivo `docker-compose.yml` para compor um ambiente com algum serviço de cache de sua escolha.

```plain
A ideia inicial é que os arquivos sejam armazenados dentro do volume do container da aplicação.
Entretanto o sistema deve conseguir trocar facilmente o sistema de arquivos usado.
(Isso não significa, entretanto, uma implementação extra de outro sistema de arquivos, apenas a
capacidade de troca entre sistemas de arquivos)

Teremos um cache de 60s de TTL para cada arquivo.
O arquivo deve estar disponível antes mesmo de ser persistido no sistema de arquivos.
O arquivo só deve ser lido a partir do sistema de arquivos se não houver cache válido para o mesmo.
```

## Restrições

A única limitação é o uso requerido da runtime `node.js`.

Você tem total liberdade para usar as demais bibliotecas que mais lhe fornecerem produtividade.

Acaso você esteja utilizando este projeto como um meio de estudo, nós o aconselhamos a usar a biblioteca padrão para lidar com requisições web do Node.js, `http`.

## O que estamos avaliando

Este teste busca avaliar as seguintes competências:

1. Capacidade de uso correto de design patterns;
2. Capacidade de interação com APIs de sistema;
3. Capacidade de desenvolver soluções que usam o conceito de concorrência para extrair maior desempenho do hardware;
4. Domínio sobre a linguagem JavaScript;
5. Domínio sobre a runtime `node.js`;
6. Capacidade de organização de código (Adendo: organize da forma que for mais familiarizado, não estamos olhando para a estrutura de pastas, mas sim para a coesão e o desacoplamento) e
7. Capacidade de lidar com contêineres Docker.
