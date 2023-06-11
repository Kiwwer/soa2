# soa2
SOA HW2,3,4


## Содержание

Реализованы:
1. gRPC-сервер, обеспечивающий работу "движка"
2. Клиент, обеспечивающий взаимодействие с сервером и базовый функционал ботов
3. Сервис текстового чата, привязанный к игровой сессии
4. Простой flask-сервер, сконнекченный с базой данных, позволяющий делать REST-запросы


### 1. gRPC-сервер (HW2, p1,2;HW3, p1,2)
Язык: Python
Файл: Maf1/service/server/service.py (нестабильная докер-версия: Maf1/service/server/serviced.py)
(gRPC- и proto-файлы доступны в папке)

Требования: запущенный сервер RabbitMQ
Лучший способ запуска:
1. Запустить локалхост RabbitMQ
2. (Linux) python3 service.py из папки Maf1/service/server
Возможен запуск с использованием docker-compose, но могут быть классические проблемы с подключением и синхронизацией.

- Сервер поддерживает последовательные или одновременные сессии.
- Для подключения клиенту требуется регистрация - за неё он получает uniqueclientID (ucid) и передаёт свой никнейм серверу
- Постановка в очередь ожидания происходит автоматически при регистрации, из-за чего можно каждую игру менять свой ник (это не повлияет на ucid)
- Игра начинается когда набирается MAX_PLAYERS игроков в очереди ожидания, роли назначаются автоматически в зависимости от констант
- Сервер предоставляет весь требуемый базовый функционал: любое корректное действие клиента приведёт к корректному и ожидаемому ответу
- Каждая игровая сессия предполагает создание двух независимых комнат текстового чата - глобальный и для мафии
- Закрытый чат мафии доступен в любую фазу, глобальный - только днём
- Передача сообщения в чат производится с помощью отдельного RPC: сервер передаёт RabbitMQ сообщение
- Рассылка сообщений чатов происходит по схеме Pub/Sub, на старте игровой сессии каждый клиент получает данные о точке обмена

Переменные окружения, отвечающие за настройку параметров функционала:
RABBITMQHOST: адрес сервиса RabbitMQ
SERVER_PORT: рабочий порт сервера

Переменные окружения, отвечающие за настройку параметров игры:
MAX_PHASE_TIME: отвечает за время автоматической смены фазы в игре без необходимости ожидания всех игроков
MAX_PLAYERS: отвечает за количество игроков в одной сессии
CRIM_CNT: отвечает за количество мафий среди игроков
COMI_CNT: отвечает за количество комиссаров среди игроков

### 2. Клиент (HW2, p1,2;HW3, p1,2)
Язык: Python
Файл: Maf1/service/server/client.py

Требования: запущенный сервер RabbitMQ, запущенный gRPC-сервер
Способ запуска:
1. Запустить RabbitMQ, gRPC-сервер
2. (Linux) python3 client.py из папки Maf1/service/server

Взаимодействие с клиентом:
- При запуске клиенту предоставляется возможность самостоятельно выбрать сервер или зарегистрироваться на игру на уже выбранном.
- Регистрация на игру возможна в двух вариантах: REG Ник = Регистрация для человека, REGBOT Ник = Регистрация автоигрока, совершающего случайные действия (бота)
- При регистрации клиент получает свой ucid и доступ к автообновлению данных: сервер передаёт информацию о пользователях в очереди (только никнеймы)
- Клиент автоматически раз в некоторое время получает данные у сервера
- После некоторого количества получений данных клиенту предлагается выбор: покинуть очередь командой UNREG или продолжить ожидать (вводится число обновлений до следующего решения)
- Игра начинается при достаточном количестве игроков автоматически, все игроки получают информацию о первом дне и свою роль
- Во время активной для игрока фазы (мафия и комиссары - день и ночь, мирные - только день) игрок получает возможность выполнять действия, если он жив
- Действие SAY {Сообщение} - чат, доступен только днём всем живым игрокам
- Действие VOTE {Номер игрока} - голосование (днём - общее, за убийство одного из игроков, ночью - отдельно за убийство у мафии и за расследование у комиссаров)
- (Свой голос можно поменять до завершения фазы)
- Действие END - закончить фазу для себя (игрок теряет возможность делать что-либо в этой фазе, невозможно отменить)
- Действие PASS - обновить информацию об игре, доступно днём (игрок узнаёт опубликованную комиссаром информацию, если она была опубликована в этой фазе)
- Действие WHISPER {Сообщение} - чат мафии, доступен в любой фазе живым членам мафии
- Действие PUBLISH - доступно днём каждому комиссару, если проверка игрока этой ночью нашла мафию
- После смерти игрок наблюдает за ходом игры, но не имеет возможности действовать и писать в чат (просмотр доступных своей роли чатов всё ещё доступен)
- Игра заканчивается при достижении требуемых условий
- После завершения игры или при непредвиденной ошибке игрок снова получает возможность регистрации или смены сервера

Переменные окружения, отвечающие за настройку параметров функционала:
RABBITMQHOST: адрес сервиса RabbitMQ
SERVER_ADDRESS: стандартный адрес gRPC-сервера

### 3. REST-API (HW4 p.1)
Язык: Python
Файлы: Maf1/service/server/app.py, Maf1/service/server/helper.py, Maf1/service/server/users.db

Поля базы данных:
- ucid: INTEGER, id пользователя
- nickname: TEXT, никнейм пользователя
- avatar_filepath: TEXT, предполагаемый путь к аватару пользователя
- gender: TEXT, пол пользователя
- email: TEXT, электронная почта пользователя

Запуск: (Linux) python3 -m flask run из папки Maf1/service/server
Взаимодействие (пример):
curl --location --request POST 'http://127.0.0.1:5000/restapp/api/v1.0/users' --header 'Content-Type: application/json' --data-raw '{"nickname": "TEST123", "avatar_filepath": "TEST321", "gender": "F", "email": "TEST1@TEST2.TEST3"}'
