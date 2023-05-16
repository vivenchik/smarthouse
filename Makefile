linters:
	black .
	isort .
	mypy smarthouse example server.py lambda/lambda.py
	flake8 smarthouse example server.py lambda/lambda.py

up:
	docker compose up --build -d

build:
	python setup.py pytest ; python setup.py sdist bdist_wheel

upload:
	twine upload dist/*
