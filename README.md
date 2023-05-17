# SmartHouse
[![Coverage Status](https://coveralls.io/repos/github/vivenchik/smarthouse/badge.svg?branch=master)](https://coveralls.io/github/vivenchik/smarthouse?branch=master)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

SmartHouse - библиотека для управления умным домом. На текущий момент реализована интеграция с экосистемой [Яндекса](https://yandex.ru/dev/dialogs/smart-home/doc/concepts/platform-protocol.html).

Какие задачи решает
-------------
* Каркас для написания сценариев
* Использование устройств как объектов или напрямую через клиента
* Доведение устройств до конечного состояния (проверяет с сервера)
* Введение устройств в карантин, если они не отвечают или как-то еще сломаны, таким образом, чтобы сценарии продолжали работать корректно
* При быстром выводе из карантина (происходит опрос устройства) после последней команды доведет устройство до состояния с последней команды
* Система lock'ов устройств
* Обнаружение человеческого вмешательства и установка lock'ов, от сценариев на ближайшее время
* Легкое хранилище данных в файле
* Интеграция с web для управления
* Интеграция с tg ботом для сообщений об ошибках и управлением
