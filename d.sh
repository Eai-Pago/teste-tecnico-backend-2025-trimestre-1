#!/bin/bash

# Script: manage.sh
# Para facilitar o uso do docker-compose e testes no projeto.

case "$1" in
    start)
        echo "🚀 Iniciando a aplicação..."
        docker-compose up -d
        ;;

    stop)
        echo "🛑 Parando a aplicação..."
        docker-compose down
        ;;

    restart)
        echo "🔄 Reiniciando a aplicação..."
        docker-compose down && docker-compose up -d
        ;;

    build)
        echo "📦 Construindo as imagens Docker..."
        docker-compose build
        ;;

    logs)
        echo "📃 Exibindo logs..."
        docker-compose logs -f
        ;;

    status)
        echo "📌 Status dos containers:"
        docker-compose ps
        ;;

    test)
        echo "🧪 Executando testes unitários..."
        docker-compose run --rm app npm test
        ;;

    *)
        echo "Uso: $0 {start|stop|restart|build|test}"
        exit 1
        ;;
esac
