#!/bin/bash

set -x

docker build . -t "cr.yandex/$REG_ID/home:latest"

printf '%s' $KEY_JSON | docker login \
  --username json_key \
  --password-stdin \
  cr.yandex

docker push "cr.yandex/$REG_ID/home:latest"
