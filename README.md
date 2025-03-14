# teste-tecnico-backend-2025-trimestre-1
Teste técnico para a posição de Backend Dev. Edição do primeiro trimestre de 2025.

## A proposta: Upload e Streaming de Vídeos + Cache + Docker

A ideia é bem simples:

- [x] uma rota `POST /upload/video` que recebe um **único vídeo** com limite de 10MB e
    - [x] retornando o código de status 400 em caso de arquivo com tipo diferente de vídeo
    - [x] retornando o código de status 400 em caso de arquivo com tamanho maior que 10MB
    - [x] retornando o código de status 204 em caso de sucesso
- [x] uma rota `GET /static/video/:filename` que pode receber um Range por cabeçalho para indicar o offset de streaming
    - [x] retornando o código de status 404 em caso de não existência de um arquivo
    - [x] retornando o conteúdo completo caso nenhum range seja especificado com código de status 200 em caso o arquivo exista no servidor
    - [x] retornando a fatia desejada do conteúdo caso o range seja especificado com código de status 206
    caso o arquivo exista no servidor

Para infra, vamos usar o seguinte conjunto:

- [x] um arquivo `Dockerfile` para fazer o build da imagem a partir da imagem `node:22-alpine`;
- [x] um arquivo `docker-compose.yml` para compor um ambiente com algum serviço de cache de sua escolha.

```plain
A ideia inicial é que os arquivos sejam armazenados dentro do volume do container da aplicação.
Teremos um cache de 60s de TTL para cada arquivo.
O arquivo deve estar disponível antes mesmo de ser persistido no sistema de arquivos.
O arquivo só deve ser lido a partir do sistema de arquivos se não houver cache válido para o mesmo.
```

## Restrições

A única limitação é o uso requerido da runtime `node.js`.

Você tem total liberdade para usar as demais bibliotecas que mais lhe fornecerem produtividade.

Acaso você esteja utilizando este projeto como um meio de estudo, nós o aconselhamos a usar a biblioteca padrão para lidar com requisições web do Node.js, `http`.

## Tempo proposto de conclusão e o que estamos avaliando

Este teste busca avaliar as seguintes competências:

- Capacidade de interação com APIs de sistema;
- Capacidade de desenvolver soluções que usam o conceito de concorrência para extrair maior desempenho do hardware;
- Domínio sobre a linguagem JavaScript;
- Domínio sobre a runtime `node.js`;
- Capacidade de organização de código (Adendo: organize da forma que for mais familiarizado, não estamos olhando para a estrutura de pastas, mas sim para a coesão e o desacoplamento) e
- Capacidade de lidar com contêineres Docker.

O tempo proposto para a conclusão deste desafio técnico é de 1 (um) dia.

# Gerenciamento da Aplicação com `manage.sh`

O script `manage.sh` facilita a execução dos principais comandos relacionados ao Docker Compose e à execução de testes da aplicação.

## Como utilizar o script

Certifique-se de que o arquivo `manage.sh` tenha permissões de execução. Execute no terminal:

```bash
chmod +x manage.sh
```

## Comandos Disponíveis

| Comando       | Descrição                                       |
|---------------|-------------------------------------------------|
| `./manage.sh start`   | 🚀 Inicia a aplicação usando Docker Compose. |
| `./manage.sh stop`    | 🛑 Para todos os containers Docker.          |
| `./manage.sh restart` | 🔄 Reinicia os containers da aplicação.     |
| `./manage.sh build`   | 📦 Constrói as imagens Docker novamente.    |
| `./manage.sh test`    | ✅ Executa testes unitários da aplicação.  |

## Exemplos de Uso

### Iniciar a aplicação
```bash
./manage.sh start
```

### Parar a aplicação
```bash
./manage.sh stop
```

### Reiniciar a aplicação
```bash
./manage.sh restart
```

### Construir novamente as imagens Docker
```bash
./manage.sh build
```

### Executar testes unitários
```bash
./manage.sh test
```

